from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import runtime_settings
from app.api import routes_admin, routes_jobs, routes_playground, routes_settings, routes_terms
from app.pipeline.azw3 import ebook_convert_available
from app.config import get_settings

app = FastAPI(title="Traductor de libros PDF", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins.split(","), allow_methods=["*"],
                   allow_headers=["*"])
app.include_router(routes_jobs.router)
app.include_router(routes_terms.router)
app.include_router(routes_admin.router)
app.include_router(routes_settings.router)
app.include_router(routes_playground.router)


@app.get("/api/health")
def health():
    st = get_settings()
    # nunca se expone la llave, solo si está configurada
    rs = runtime_settings.load()
    return {"ok": True, "translation_configured": rs.configured(), "provider": rs.provider,
            "max_upload_mb": st.max_upload_mb, "azw3_available": ebook_convert_available()}
