"""Modelo de datos. Los PDF viven en disco; aquí solo rutas, hashes y metadatos."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import false as sa_false
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_name: Mapped[str] = mapped_column(String(512))
    path: Mapped[str] = mapped_column(String(1024))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str | None] = mapped_column(Text)
    title_es: Mapped[str | None] = mapped_column(Text)
    # especialidad detectada al descubrir el glosario (p. ej. "astrología occidental"); va al prompt
    domain: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    jobs: Mapped[list[Job]] = relationship(back_populates="document")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    # queued | running | paused | cancelled | done | failed
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    # upload | analyze | protect | ocr | translate | rebuild | validate | done
    stage: Mapped[str] = mapped_column(String(16), default="upload")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_page: Mapped[int | None] = mapped_column(Integer)
    source_lang: Mapped[str] = mapped_column(String(8), default="en")
    target_lang: Mapped[str] = mapped_column(String(8), default="es")
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    output_path: Mapped[str | None] = mapped_column(String(1024))
    report_path: Mapped[str | None] = mapped_column(String(1024))
    # quién subió el libro; NULL = trabajos anteriores al login (solo los ve el admin)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    document: Mapped[Document] = relationship(back_populates="jobs")
    pages: Mapped[list[Page]] = relationship(back_populates="job", cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("job_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)  # 1-based
    width: Mapped[float] = mapped_column(Float)
    height: Mapped[float] = mapped_column(Float)
    rotation: Mapped[int] = mapped_column(Integer, default=0)
    # blank | digital | scanned | mixed | image_only
    kind: Mapped[str] = mapped_column(String(16))
    image_count: Mapped[int] = mapped_column(Integer, default=0)
    drawing_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reasons: Mapped[list] = mapped_column(JSON, default=list)

    job: Mapped[Job] = relationship(back_populates="pages")
    segments: Mapped[list[Segment]] = relationship(back_populates="page", cascade="all, delete-orphan")


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"), index=True)
    seg_key: Mapped[str] = mapped_column(String(32))  # p041_s03
    bbox: Mapped[list] = mapped_column(JSON)
    block_type: Mapped[str] = mapped_column(String(16), default="text")
    # "field": campo de ficha (etiqueta + valor); "figure": texto dentro de una ilustración (infografía).
    # Las páginas con alguno se traducen con el texto de toda la página como contexto.
    role: Mapped[str | None] = mapped_column(String(16))
    style: Mapped[dict] = mapped_column(JSON, default=dict)
    source_text: Mapped[str] = mapped_column(Text)
    source_html: Mapped[str] = mapped_column(Text)
    protected_text: Mapped[str | None] = mapped_column(Text)
    placeholders: Mapped[dict] = mapped_column(JSON, default=dict)
    translation: Mapped[str | None] = mapped_column(Text)
    # translate | keep | graphic | review
    action: Mapped[str] = mapped_column(String(16), default="translate")
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    fit_scale: Mapped[float | None] = mapped_column(Float)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    # traducción corregida a mano desde el admin
    edited: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())

    page: Mapped[Page] = relationship(back_populates="segments")


class ProtectedTerm(Base):
    __tablename__ = "protected_terms"

    id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(String(512))
    category: Mapped[str] = mapped_column(String(16), default="NAME")
    origin: Mapped[str] = mapped_column(String(16), default="manual")  # auto | manual
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))  # None = global


class GlossaryEntry(Base):
    __tablename__ = "glossary"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(512))
    target: Mapped[str] = mapped_column(String(512))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    origin: Mapped[str] = mapped_column(String(16), default="manual", server_default="manual")  # auto | manual
    category: Mapped[str | None] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)


class TranslationCache(Base):
    __tablename__ = "translation_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    translation: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PromptDraft(Base):
    """Borrador de prompt del playground. Nunca cambia el prompt de producción."""
    __tablename__ = "prompt_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    task: Mapped[str] = mapped_column(String(16))  # translate | correct
    name: Mapped[str] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PlaygroundRun(Base):
    """Evaluación de variantes (método, modelo, razonamiento, prompt) sobre un capítulo de un libro procesado."""
    __tablename__ = "playground_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    task: Mapped[str] = mapped_column(String(16))  # translate | correct
    scope: Mapped[str] = mapped_column(String(16), default="pages")  # page | pages | chapter | book
    pages: Mapped[str] = mapped_column(Text)  # normalizado: "12-18" o "3,7,12-15"
    chapter: Mapped[str | None] = mapped_column(Text)
    variants: Mapped[list] = mapped_column(JSON, default=list)  # con el texto del prompt copiado al lanzar
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_variant: Mapped[int | None] = mapped_column(Integer)
    results: Mapped[list] = mapped_column(JSON, default=list)
    # progreso para reanudar tras una pausa por cuota: {"caches": {etiqueta: {clave: salida}}, "done", "total"}
    state: Mapped[dict | None] = mapped_column(JSON)
    votes: Mapped[dict | None] = mapped_column(JSON)  # {"41": "A" | "tie"}: la mejor variante de cada página
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PlaygroundAttempt(Base):
    """Historial del playground: cada variante evaluada y cada «Probar en la pág.», con su configuración, su uso
    (tokens y costo estimado) y su salida. No se sobrescribe: las pruebas posteriores crean otro intento."""
    __tablename__ = "playground_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("playground_runs.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    label: Mapped[str] = mapped_column(String(4))
    kind: Mapped[str] = mapped_column(String(8))  # run | try
    pages: Mapped[str] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSON, default=dict)  # provider, model, thinking, prompt, prompt_name, prompt_text
    segments: Mapped[dict] = mapped_column(JSON, default=dict)  # {clave: {output, issues, fit...}}
    seconds: Mapped[float] = mapped_column(Float, default=0.0)
    calls: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    tokens_cache_hit: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Float)  # estimado con la tarifa punta; None = desconocido
    error: Mapped[str | None] = mapped_column(Text)
    pdf: Mapped[str | None] = mapped_column(String(1024))  # copia de las páginas de este intento
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StoredFile(Base):
    """Archivo en el almacenamiento S3. Solo se guarda la key; la URL se construye al responder."""
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(512), unique=True)
    original_name: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128))
    size: Mapped[int] = mapped_column(Integer)
    private: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    """Cuenta de acceso. La contraseña solo se guarda como hash Argon2id."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # siempre en minúsculas
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16), default="user")  # admin | user
    password_hash: Mapped[str] = mapped_column(String(255))
    # contraseña temporal (alta, reset o bootstrap): obliga a cambiarla y vence
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    temp_password_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuthSession(Base):
    """Sesión opaca: el navegador guarda el token; aquí solo su SHA-256 (y el del CSRF)."""
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="normal")  # normal | restricted (cambio obligatorio)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reauth_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(256))

    user: Mapped[User] = relationship()


class AuthRateLimit(Base):
    """Contador de intentos de login por ventana fija (por IP, por correo y total)."""
    __tablename__ = "auth_rate_limits"

    bucket: Mapped[str] = mapped_column(String(96), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer, default=0)


class AuthSecurityEvent(Base):
    """Bitácora de seguridad. Nunca guarda contraseñas, tokens ni CSRF."""
    __tablename__ = "auth_security_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(48), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    actor_id: Mapped[int | None] = mapped_column(Integer)
    ip: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
