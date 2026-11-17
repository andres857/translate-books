from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import runtime_settings
from app.api import (
    routes_admin,
    routes_auth,
    routes_files,
    routes_jobs,
    routes_playground,
    routes_settings,
    routes_terms,
    routes_users,
)
from app.auth.deps import optional_principal, require_admin, require_user, verify_write
from app.auth.errors import ApiError, payload
from app.auth.users import ensure_bootstrap_admin
from app.config import get_settings
from app.db.session import SessionLocal, session_scope
from app.pipeline.azw3 import ebook_convert_available
from app.storage.config import get_storage_settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # valida la configuración del almacenamiento al arrancar (falla rápido si el .env es incorrecto)
    get_storage_settings()
    with session_scope() as db:
        ensure_bootstrap_admin(db)
    yield


app = FastAPI(title="Traductor de libros PDF", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().allowed_origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   allow_headers=["Content-Type", "X-CSRF-Token", "X-Requested-With"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    if request.url.path.startswith("/api/auth") or request.url.path.startswith("/api/users"):
        h["Cache-Control"] = "no-store"
    if get_settings().secure_cookies:
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


_CODES = {400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT",
          413: "PAYLOAD_TOO_LARGE", 429: "TOO_MANY_ATTEMPTS"}


@app.exception_handler(ApiError)
async def api_error(_request: Request, exc: ApiError):
    return JSONResponse(payload(exc.status, exc.code, exc.message), status_code=exc.status, headers=exc.headers)


@app.exception_handler(StarletteHTTPException)
async def http_error(_request: Request, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "No pudimos completar la acción."
    body = payload(exc.status_code, _CODES.get(exc.status_code, "ERROR"), message)
    if not isinstance(exc.detail, str):
        body["detail"] = exc.detail
    return JSONResponse(body, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    body = payload(422, "VALIDATION_ERROR", "Los datos enviados no son válidos.")
    # solo ubicación y tipo: nunca se repite el valor recibido (podría ser una contraseña)
    body["errors"] = [{"loc": list(e.get("loc", ())), "type": e.get("type")} for e in exc.errors()]
    return JSONResponse(body, status_code=422)


# Matriz de autorización: el router entero exige sesión y rol; toda escritura exige Origin + CSRF.
# Las rutas de jobs comprueban además la propiedad de cada trabajo.
USER = [Depends(require_user), Depends(verify_write)]
ADMIN = [Depends(require_admin), Depends(verify_write)]
app.include_router(routes_auth.router)
app.include_router(routes_users.router, dependencies=ADMIN)
app.include_router(routes_jobs.router, dependencies=USER)
app.include_router(routes_settings.router, dependencies=USER)
app.include_router(routes_terms.router, dependencies=ADMIN)
app.include_router(routes_admin.router, dependencies=ADMIN)
app.include_router(routes_playground.router, dependencies=ADMIN)
app.include_router(routes_files.router, dependencies=ADMIN)


@app.get("/api/health")
def health(request: Request):
    """Sin sesión solo dice que el servicio vive (healthcheck de Docker); con sesión, los detalles."""
    with SessionLocal() as db:
        p = optional_principal(request, db)
    if p is None or p.session.kind != "normal":
        return {"ok": True}
    st = get_settings()
    # nunca se expone la llave, solo si está configurada
    rs = runtime_settings.load()
    return {"ok": True, "translation_configured": rs.configured(), "provider": rs.provider,
            "max_upload_mb": st.max_upload_mb, "azw3_available": ebook_convert_available()}
