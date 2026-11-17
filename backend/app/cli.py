"""CLI de desarrollo: traduce un PDF sin frontend ni API.

Uso:
  python -m app.cli translate libro.pdf --out salida/ [--pages 1-12,41] [--provider deepseek|fake] [--fake] [--protect "Kim Farley"]
  python -m app.cli epub <job_id>                      # EPUB para Kindle de un trabajo terminado
  python -m app.cli analyze libro.pdf [--pages 1-5]     # muestra segmentos detectados sin traducir
  python -m app.cli auth-recover --email admin@ejemplo.com [--name "Nombre"]   # recuperar el acceso de admin
  python -m app.cli active-jobs                         # trabajos en curso (antes de reiniciar el worker)
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from app.config import get_settings


def parse_pages(spec: str | None) -> set[int] | None:
    if not spec:
        return None
    pages: set[int] = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            pages.update(range(int(a), int(b) + 1))
        elif part.strip():
            pages.add(int(part))
    return pages


def migrate() -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(cfg, "head")


def cmd_analyze(args) -> None:
    import pymupdf

    from app.pipeline.analyze import analyze

    doc = pymupdf.open(args.pdf)
    only = parse_pages(args.pages)
    for info in analyze(doc):
        if only and info.number not in only:
            continue
        print(f"\n=== Página {info.number} [{info.kind}] imgs={info.image_count} vect={info.drawing_count} "
              f"{info.review_reasons}")
        for s in info.segments:
            print(f"  {s.key} {s.action:9} {s.block_type:8} {s.style.size:5.1f}pt {s.style.align:7} "
                  f"{s.style.font[:22]:22} | {s.html[:100]}")


def cmd_translate(args) -> None:
    from app.db.cache import SqlCache
    from app.db.session import SessionLocal
    from app.pipeline.runner import PipelineOptions, run_pipeline

    st = get_settings()
    migrate()
    from app import runtime_settings

    rs = runtime_settings.load()
    if args.fake:
        rs.provider = "fake"
    elif args.provider:
        rs.provider = args.provider
    translator = runtime_settings.make_translator(rs)
    print(f"Modo de traducción: {rs.provider} ({translator.model})")
    session = SessionLocal()
    t0 = time.time()
    last = {"stage": None}

    def progress(stage, done, total, page):
        if stage != last["stage"]:
            print(f"\n[{stage}]", end="", flush=True)
            last["stage"] = stage
        print(f"\r[{stage}] {done}/{total}" + (f" (página {page})" if page else "") + " " * 10, end="", flush=True)

    opts = PipelineOptions(min_font_scale=st.min_font_scale, min_font_size_pt=st.min_font_size_pt,
                           concurrency=rs.concurrency, batch_chars=st.translation_batch_chars,
                           batch_items=st.translation_batch_max_segments, fonts_dirs=st.fonts_dirs,
                           only_pages=parse_pages(args.pages), detect_names=rs.provider != "fake",
                           visual_check=not args.no_visual)
    terms = {t: "NAME" for t in args.protect or []}
    result = run_pipeline(Path(args.pdf), Path(args.out), translator, SqlCache(session), terms, {}, opts, progress)
    session.close()
    r = result.report
    print(f"\n\nListo en {time.time() - t0:.0f}s -> {result.output_pdf}")
    print(f"Reporte: {result.report_path}")
    print("Validaciones:", {k: ("OK" if v else "FALLA") for k, v in r["validaciones"].items()})
    print("Estadísticas:", r["estadisticas"])
    print(f"Páginas para revisión: {len(r['paginas_para_revision'])}")
    for p in r["paginas_para_revision"][:30]:
        print(f"  pág. {p['pagina']}: {'; '.join(p['motivos'])[:200]}")
    if args.epub:
        from app.pipeline.epub import build_epub, epub_path_for, pages_from_pipeline

        epub = build_epub(result.output_pdf, pages_from_pipeline(result.pages), result.title_es or result.title,
                          "", epub_path_for(result.output_pdf))
        print(f"EPUB para Kindle: {epub} ({epub.stat().st_size / 1e6:.1f} MB)")


def main(argv=None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("pdf")
    a.add_argument("--pages")
    t = sub.add_parser("translate")
    t.add_argument("pdf")
    t.add_argument("--out", default="data/outputs/cli")
    t.add_argument("--pages", help="solo traducir estas páginas, p. ej. 1-10,41")
    t.add_argument("--fake", action="store_true", help="traductor falso sin API (pruebas de maquetación)")
    t.add_argument("--provider", choices=["deepseek", "fake"],
                   help="modo de traducción (por defecto, el elegido en Ajustes)")
    t.add_argument("--protect", action="append", help="término protegido adicional")
    t.add_argument("--no-visual", action="store_true", help="omitir comparación visual (más rápido)")
    t.add_argument("--epub", action="store_true", help="generar también el EPUB para Kindle")
    e = sub.add_parser("epub", help="generar el EPUB para Kindle de un trabajo ya terminado (sin traducir)")
    e.add_argument("job_id", type=int)
    e.add_argument("--azw3", action="store_true", help="convertirlo también a AZW3 (requiere Calibre)")
    r = sub.add_parser("auth-recover", help="crear o reactivar una cuenta admin con contraseña temporal nueva")
    r.add_argument("--email", required=True)
    r.add_argument("--name", default="Administrador")
    sub.add_parser("active-jobs", help="lista los trabajos que no han terminado")
    args = ap.parse_args(argv)
    {"analyze": cmd_analyze, "translate": cmd_translate, "epub": cmd_epub, "auth-recover": cmd_auth_recover,
     "active-jobs": cmd_active_jobs}[args.cmd](args)


def cmd_auth_recover(args) -> None:
    """Recuperación local (requiere acceso al servidor): la contraseña temporal se muestra una sola vez."""
    from sqlalchemy import select

    from app.auth import events, sessions
    from app.auth import users as svc
    from app.db.models import User
    from app.db.session import session_scope

    migrate()
    with session_scope() as db:
        email = svc.normalize_email(args.email)
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user, temp = svc.create(db, email, args.name, "admin")
        else:
            user.role, user.active = "admin", True
            temp = svc.reset_password(db, user)
        sessions.revoke_all(db, user.id)
        events.record(db, "cli_recover", user_id=user.id)
    print(f"Cuenta admin: {email}")
    print(f"Contraseña temporal (vence en {get_settings().temp_password_hours:g} h, se pide cambiarla al entrar):")
    print(temp)


def cmd_active_jobs(_args) -> None:
    from app.db.models import Job
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        rows = db.query(Job).filter(Job.status.in_(("queued", "running", "paused"))).all()
        print("\n".join(f"{j.id} {j.status} {j.stage}" for j in rows) or "sin trabajos activos")


def cmd_epub(args) -> None:
    from app.db.models import Job
    from app.db.session import SessionLocal
    from app.pipeline.epub import build_epub_for_job

    migrate()
    with SessionLocal() as s:
        job = s.get(Job, args.job_id)
        if job is None or job.status != "done" or not job.output_path:
            sys.exit(f"El trabajo {args.job_id} no existe o no ha terminado.")
        path = build_epub_for_job(s, job)
        output_pdf = job.output_path
    print(f"EPUB: {path} ({path.stat().st_size / 1e6:.1f} MB)")
    if args.azw3:
        from app.pipeline.azw3 import azw3_path_for, build_azw3, ebook_convert_available

        if not ebook_convert_available():
            sys.exit("Falta Calibre (ebook-convert): sudo apt install calibre")
        azw3 = build_azw3(path, azw3_path_for(output_pdf))
        print(f"AZW3: {azw3} ({azw3.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    sys.exit(main())
