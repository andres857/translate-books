"""Glosario descubierto de un libro: guardarlo, cargarlo y volver a generarlo bajo demanda."""
from __future__ import annotations

import logging
import threading
import time

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Document, GlossaryEntry, Job, Page, ProtectedTerm, Segment
from app.db.session import SessionLocal
from app.pipeline.glossary import GlossaryProposal
from app.pipeline.protect import Protector

log = logging.getLogger(__name__)


def entries_for(s: Session, doc_id: int) -> list[GlossaryEntry]:
    """Las entradas globales y las de ese libro."""
    return list(s.scalars(select(GlossaryEntry).where(
        (GlossaryEntry.document_id.is_(None)) | (GlossaryEntry.document_id == doc_id))))


def effective_glossary(s: Session, doc_id: int) -> tuple[dict[str, str], bool]:
    """(glosario para traducir, ¿el libro ya tiene glosario descubierto?). Lo manual gana a lo descubierto."""
    rows = entries_for(s, doc_id)
    auto = {g.source: g.target for g in rows if g.origin == "auto"}
    manual = {g.source: g.target for g in rows if g.origin != "auto"}
    taken = {k.lower() for k in manual}
    has_auto = any(g.origin == "auto" and g.document_id == doc_id for g in rows)
    return {**{k: v for k, v in auto.items() if k.lower() not in taken}, **manual}, has_auto


def save_auto(s: Session, doc: Document, domain: str, proposals: list[GlossaryProposal]) -> int:
    """Sustituye las entradas descubiertas del libro; las manuales no se tocan ni se duplican."""
    s.execute(delete(GlossaryEntry).where(GlossaryEntry.document_id == doc.id, GlossaryEntry.origin == "auto"))
    taken = {g.source.lower() for g in entries_for(s, doc.id)}
    n = 0
    for p in proposals:
        if p.source.lower() in taken:
            continue
        s.add(GlossaryEntry(source=p.source, target=p.target, document_id=doc.id, origin="auto",
                            category=p.category or None, note=p.note or None))
        taken.add(p.source.lower())
        n += 1
    if domain:
        doc.domain = domain
    return n


def source_job(s: Session, doc: Document) -> Job | None:
    """El último trabajo terminado del libro con bloques guardados (traducido o preparado)."""
    return s.scalars(select(Job).where(Job.document_id == doc.id, Job.status == "done",
                                       Job.pages.any()).order_by(Job.id.desc())).first()


def saved_segments(s: Session, job: Job):
    from app.playground import to_segments

    rows = s.execute(select(Page.number, Segment).join(Segment, Segment.page_id == Page.id)
                     .where(Page.job_id == job.id, Segment.action == "translate")
                     .order_by(Page.number, Segment.id)).all()
    return to_segments([(n, r) for n, r in rows])


# ----------------------------------------------------------------------------- bajo demanda (en segundo plano)

_status: dict[int, dict] = {}
_lock = threading.Lock()


def status(doc_id: int) -> dict:
    with _lock:
        return dict(_status.get(doc_id) or {"status": "idle"})


def start_discovery(doc_id: int) -> bool:
    """Lanza el descubrimiento en un hilo; False si ya hay uno en marcha para ese libro."""
    with _lock:
        if (_status.get(doc_id) or {}).get("status") == "running":
            return False
        _status[doc_id] = {"status": "running", "done": 0, "total": 0, "started": time.time()}
    threading.Thread(target=_discover, args=(doc_id,), daemon=True).start()
    return True


def _set(doc_id: int, **kw) -> None:
    with _lock:
        _status[doc_id] = {**(_status.get(doc_id) or {}), **kw}


def _discover(doc_id: int) -> None:
    from app import runtime_settings
    from app.pipeline.runner import discover_book_glossary
    from app.pipeline.translate import UsageMeter
    from app.worker import friendly_error

    try:
        with SessionLocal() as s:
            doc = s.get(Document, doc_id)
            job = source_job(s, doc)
            if job is None:
                raise ValueError("NO_SEGMENTS")
            segments = saved_segments(s, job)
            terms = {t.term: t.category for t in s.scalars(select(ProtectedTerm).where(
                (ProtectedTerm.document_id.is_(None)) | (ProtectedTerm.document_id == doc.id)))}
            rs = runtime_settings.load()
            translator = runtime_settings.make_translator(rs)
            translator.meter = UsageMeter()
            domain, proposals = discover_book_glossary(
                segments, Protector(terms), translator, doc.title or "", rs.concurrency,
                lambda d, t: _set(doc_id, done=d, total=t))
            n = save_auto(s, doc, domain, proposals)
            s.commit()
            usage = translator.meter.snapshot()
        _set(doc_id, status="done", count=n, domain=domain, cost_usd=usage.get("cost_usd"),
             tokens_in=usage.get("tokens_in"), tokens_out=usage.get("tokens_out"))
        log.info("Glosario del libro %s: %s términos (%s)", doc_id, n, domain)
    except Exception as e:  # noqa: BLE001
        log.exception("Descubrimiento de glosario del libro %s falló", doc_id)
        msg = ("Primero analiza o traduce el libro: no hay bloques guardados." if "NO_SEGMENTS" in str(e)
               else friendly_error(e))
        _set(doc_id, status="failed", error=msg)
