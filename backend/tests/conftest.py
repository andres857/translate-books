import os
import sys
from contextlib import contextmanager
from pathlib import Path

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "tests" / "output"
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(OUT / 'test.db').as_posix()}")

LOREM = ("The planets move through the signs of the zodiac, and each placement adds a layer of meaning to the "
         "birth chart. Astrologers read these patterns to understand personality, relationships and timing. ")


def build_sample_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    W, H = 420, 595

    # 1. portada: imagen de fondo + título
    p = doc.new_page(width=W, height=H)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 80), False)
    pix.set_rect(pix.irect, (40, 70, 120))
    p.insert_image(p.rect, pixmap=pix)
    p.insert_textbox(pymupdf.Rect(40, 120, 380, 200), "THE SECRETS OF ASTROLOGY", fontsize=24, fontname="hebo",
                     color=(1, 1, 1), align=1)
    p.insert_textbox(pymupdf.Rect(40, 210, 380, 260), "A complete guide to sun signs, planets, houses and more",
                     fontsize=12, fontname="helv", color=(1, 1, 1), align=1)
    p.insert_text((150, 540), "Carole Taylor", fontsize=12, fontname="helv", color=(1, 1, 1))

    # 2. página vacía
    doc.new_page(width=W, height=H)

    # 3. índice con líneas de puntos
    p = doc.new_page(width=W, height=H)
    p.insert_text((40, 60), "Contents", fontsize=18, fontname="hebo")
    for i, (t, n) in enumerate([("Introduction", 6), ("Sun signs", 12), ("The planets", 40), ("Houses", 88),
                                ("Glossary", 180), ("Index", 186)]):
        y = 100 + i * 20
        p.insert_text((40, y), t, fontsize=10, fontname="helv")
        p.insert_text((150, y), "." * 40, fontsize=10, fontname="helv")
        p.insert_text((360, y), str(n), fontsize=10, fontname="helv")

    # 4. dos columnas + caja de color con texto + diagrama vectorial + número de página
    p = doc.new_page(width=W, height=H)
    p.insert_text((40, 50), "STEADY DOES IT", fontsize=16, fontname="hebo")
    p.insert_textbox(pymupdf.Rect(40, 70, 200, 330), LOREM * 2, fontsize=9, fontname="tiro")
    p.insert_textbox(pymupdf.Rect(220, 70, 380, 330), LOREM * 2, fontsize=9, fontname="tiro")
    p.draw_rect(pymupdf.Rect(40, 350, 380, 430), color=None, fill=(0.66, 0.83, 0.73))
    p.insert_textbox(pymupdf.Rect(50, 360, 370, 420), "Taurus energy is slow and patient, but it always gets there.",
                     fontsize=11, fontname="helv")
    p.draw_circle((210, 500), 40, color=(0.2, 0.3, 0.3), width=1.5)
    p.draw_line((170, 500), (250, 500), color=(0.2, 0.3, 0.3))
    p.insert_text((200, 575), "41", fontsize=9, fontname="helv")

    # 5. créditos / copyright
    p = doc.new_page(width=W, height=H)
    lines = ["Project Editor Kim Farley", "Senior Art Editor Jane Ewart", "First published in Great Britain in 2023",
             "by Dorling Kindersley Limited", "Copyright © 2023 Dorling Kindersley Limited",
             "All rights reserved.", "ISBN 978-0-7440-2366-4", "www.dk.com"]
    for i, t in enumerate(lines):
        p.insert_text((40, 80 + i * 16), t, fontsize=8, fontname="helv")

    doc.save(path)
    return path


@pytest.fixture(scope="session")
def sample_pdf() -> Path:
    return build_sample_pdf(OUT / "sample.pdf")


# ---- login: usuarios y clientes autenticados para las pruebas de la API

TEST_PASSWORD = "contraseña-de-prueba-12"


def make_user(role: str = "user", *, email: str | None = None, password: str = TEST_PASSWORD,
              must_change: bool = False, active: bool = True):
    """Crea una cuenta directamente en BD (correo único por llamada: la BD de pruebas se conserva)."""
    import uuid

    from app.auth import passwords
    from app.db.models import User
    from app.db.session import session_scope

    with session_scope() as db:
        u = User(email=email or f"{role}-{uuid.uuid4().hex[:10]}@example.com", name=f"Prueba {role}", role=role,
                 password_hash=passwords.hash_password(password), must_change_password=must_change, active=active)
        db.add(u)
        db.flush()
        db.expunge(u)
    return u


def login_headers(client, token: str):
    from app.auth import sessions
    from app.config import get_settings

    client.cookies.set(sessions.cookie_name(), token)
    client.headers.update({"Origin": get_settings().allowed_origins[0], "X-Requested-With": "traductor",
                           "X-CSRF-Token": sessions.csrf_for(token)})
    return client


def session_for(user, kind: str = "normal", reauth: bool = False) -> str:
    """Abre una sesión para `user` sin pasar por el login (y opcionalmente con reautenticación reciente)."""
    from starlette.requests import Request

    from app.auth import sessions
    from app.db.models import User
    from app.db.session import session_scope

    req = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1)})
    with session_scope() as db:
        s, token = sessions.create(db, db.get(User, user.id), kind, req)
        if reauth:
            s.reauth_at = sessions.now()
    return token


def auth_client(app, role: str = "admin", *, user=None, reauth: bool = False):
    """TestClient con cookie de sesión, Origin, X-Requested-With y CSRF. `client.user` es la cuenta."""
    from fastapi.testclient import TestClient

    user = user or make_user(role)
    c = TestClient(app)
    login_headers(c, session_for(user, reauth=reauth))
    c.user = user
    return c


def admin_client(app):
    return auth_client(app, "admin")


# ---- número de queries: para fijar en un test que un endpoint no hace N+1

class QueryCounter:
    def __init__(self):
        self.statements: list[str] = []

    @property
    def count(self) -> int:
        return len(self.statements)


@contextmanager
def count_queries(engine=None):
    """Cuenta las sentencias SQL ejecutadas dentro del bloque (por defecto en el engine de la app).

    `with count_queries() as q: client.get(...)` y luego `q.count` / `q.statements`.
    """
    from sqlalchemy import event

    if engine is None:
        from app.db.session import engine
    q = QueryCounter()

    def _record(conn, cursor, statement, parameters, context, executemany):
        q.statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield q
    finally:
        event.remove(engine, "before_cursor_execute", _record)
