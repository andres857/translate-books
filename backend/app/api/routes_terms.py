from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import glossary_service
from app.db.models import Document, GlossaryEntry, ProtectedTerm
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["terms"])


# Las que ofrece la vista de términos (frontend/app/admin/jobs/[id]/terms.tsx, CATEGORY). Solo letras: la categoría
# forma el marcador __CATEGORIA_000__ del Protector (PLACEHOLDER_RE solo reconoce [A-Z]+).
TermCategory = Literal["NAME", "BRAND", "CODE", "TERM"]


class TermIn(BaseModel):
    term: str = Field(min_length=2, max_length=512)
    category: TermCategory = "NAME"
    document_id: int | None = None

    @field_validator("category", mode="before")
    @classmethod
    def _upper(cls, v: object) -> object:
        """Se sigue aceptando en minúsculas ("term" → "TERM"), como antes de validar la lista."""
        return v.strip().upper() if isinstance(v, str) else v


class GlossaryIn(BaseModel):
    source: str = Field(min_length=1, max_length=512)
    target: str = Field(min_length=1, max_length=512)
    document_id: int | None = None
    note: str | None = Field(default=None, max_length=500)


class GlossaryPatch(BaseModel):
    target: str | None = Field(default=None, min_length=1, max_length=512)
    note: str | None = Field(default=None, max_length=500)


def _glossary_row(g: GlossaryEntry) -> dict:
    return {"id": g.id, "source": g.source, "target": g.target, "document_id": g.document_id,
            "origin": g.origin or "manual", "category": g.category, "note": g.note}


def _check_document(db: Session, document_id: int | None) -> None:
    if document_id is not None and db.get(Document, document_id) is None:
        raise HTTPException(400, "Ese libro no existe.")


def _commit_new(db: Session) -> None:
    """Guarda una entrada nueva; si el índice único la rechaza (ya existe), 409 sin el texto de la BD."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ese término ya existe.") from None


@router.get("/protected-terms")
def list_terms(document_id: int | None = None, db: Session = Depends(get_db)):
    """Sin document_id: todos. Con document_id: los globales y los de ese libro."""
    q = select(ProtectedTerm)
    if document_id is not None:
        q = q.where((ProtectedTerm.document_id.is_(None)) | (ProtectedTerm.document_id == document_id))
    return [{"id": t.id, "term": t.term, "category": t.category, "origin": t.origin, "document_id": t.document_id}
            for t in db.scalars(q.order_by(ProtectedTerm.term))]


@router.post("/protected-terms")
def add_term(body: TermIn, db: Session = Depends(get_db)):
    _check_document(db, body.document_id)
    t = ProtectedTerm(term=body.term.strip(), category=body.category, origin="manual",
                      document_id=body.document_id)
    db.add(t)
    _commit_new(db)
    return {"id": t.id}


@router.delete("/protected-terms/{term_id}")
def delete_term(term_id: int, db: Session = Depends(get_db)):
    t = db.get(ProtectedTerm, term_id)
    if not t:
        raise HTTPException(404, "Término no encontrado.")
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.get("/glossary")
def list_glossary(document_id: int | None = None, db: Session = Depends(get_db)):
    q = select(GlossaryEntry)
    if document_id is not None:
        q = q.where((GlossaryEntry.document_id.is_(None)) | (GlossaryEntry.document_id == document_id))
    return [_glossary_row(g) for g in db.scalars(q.order_by(GlossaryEntry.source))]


@router.post("/glossary")
def add_glossary(body: GlossaryIn, db: Session = Depends(get_db)):
    _check_document(db, body.document_id)
    g = GlossaryEntry(source=body.source.strip(), target=body.target.strip(), document_id=body.document_id,
                      origin="manual", note=(body.note or "").strip() or None)
    db.add(g)
    _commit_new(db)
    return {"id": g.id}


@router.delete("/glossary/{entry_id}")
def delete_glossary(entry_id: int, db: Session = Depends(get_db)):
    g = db.get(GlossaryEntry, entry_id)
    if not g:
        raise HTTPException(404, "Entrada no encontrada.")
    db.delete(g)
    db.commit()
    return {"ok": True}


@router.patch("/glossary/{entry_id}")
def edit_glossary(entry_id: int, body: GlossaryPatch, db: Session = Depends(get_db)):
    """Corregir una entrada; una descubierta que se corrige pasa a manual (ya no se sustituye al redescubrir)."""
    g = db.get(GlossaryEntry, entry_id)
    if not g:
        raise HTTPException(404, "Entrada no encontrada.")
    if body.target is not None and body.target.strip() != g.target:
        g.target, g.origin = body.target.strip(), "manual"
    if body.note is not None:
        g.note = body.note.strip() or None
    db.commit()
    return _glossary_row(g)


@router.get("/documents/{document_id}/glossary/discover")
def discover_status(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Ese libro no existe.")
    return {**glossary_service.status(document_id), "domain": doc.domain}


@router.post("/documents/{document_id}/glossary/discover", status_code=202)
def discover(document_id: int, db: Session = Depends(get_db)):
    """Vuelve a generar el glosario descubierto del libro con el modelo (sustituye solo las entradas 'auto')."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Ese libro no existe.")
    if glossary_service.source_job(db, doc) is None:
        raise HTTPException(409, "Primero analiza o traduce el libro: no hay bloques guardados.")
    if not glossary_service.start_discovery(document_id):
        raise HTTPException(409, "Ya se está generando el glosario de este libro.")
    return glossary_service.status(document_id)
