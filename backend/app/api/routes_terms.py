from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import Document, GlossaryEntry, ProtectedTerm
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["terms"])


class TermIn(BaseModel):
    term: str = Field(min_length=2, max_length=512)
    category: str = "NAME"
    document_id: int | None = None


class GlossaryIn(BaseModel):
    source: str = Field(min_length=1, max_length=512)
    target: str = Field(min_length=1, max_length=512)
    document_id: int | None = None


def _check_document(db: Session, document_id: int | None) -> None:
    if document_id is not None and db.get(Document, document_id) is None:
        raise HTTPException(400, "Ese libro no existe.")


@router.get("/protected-terms")
def list_terms(document_id: int | None = None, db: Session = Depends(get_db)):
    """Sin document_id: todos. Con document_id: los globales y los de ese libro."""
    q = db.query(ProtectedTerm)
    if document_id is not None:
        q = q.filter((ProtectedTerm.document_id.is_(None)) | (ProtectedTerm.document_id == document_id))
    return [{"id": t.id, "term": t.term, "category": t.category, "origin": t.origin, "document_id": t.document_id}
            for t in q.order_by(ProtectedTerm.term)]


@router.post("/protected-terms")
def add_term(body: TermIn, db: Session = Depends(get_db)):
    _check_document(db, body.document_id)
    t = ProtectedTerm(term=body.term.strip(), category=body.category.upper(), origin="manual",
                      document_id=body.document_id)
    db.add(t)
    db.commit()
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
    q = db.query(GlossaryEntry)
    if document_id is not None:
        q = q.filter((GlossaryEntry.document_id.is_(None)) | (GlossaryEntry.document_id == document_id))
    return [{"id": g.id, "source": g.source, "target": g.target, "document_id": g.document_id}
            for g in q.order_by(GlossaryEntry.source)]


@router.post("/glossary")
def add_glossary(body: GlossaryIn, db: Session = Depends(get_db)):
    _check_document(db, body.document_id)
    g = GlossaryEntry(source=body.source.strip(), target=body.target.strip(), document_id=body.document_id)
    db.add(g)
    db.commit()
    return {"id": g.id}


@router.delete("/glossary/{entry_id}")
def delete_glossary(entry_id: int, db: Session = Depends(get_db)):
    g = db.get(GlossaryEntry, entry_id)
    if not g:
        raise HTTPException(404, "Entrada no encontrada.")
    db.delete(g)
    db.commit()
    return {"ok": True}
