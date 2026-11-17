"""Modo digitalizar: PDF escaneado → PDF con texto seleccionable (OCRmyPDF) + corrección opcional + EPUB."""
import io
import zipfile

import pymupdf
import pytest
from PIL import Image

from app.pipeline.digitize import (DigitizeOptions, book_title, check_correction, correct_segments,
                                   ocrmypdf_available, run_digitize)
from app.pipeline.translate import FakeTranslator
from app.pipeline.types import Segment, Style

from .conftest import LOREM, OUT

needs_ocr = pytest.mark.skipif(not ocrmypdf_available(), reason="OCRmyPDF/Tesseract no instalados")


class MemCache(dict):
    def get(self, k):
        return dict.get(self, k)

    def set(self, k, v, model):
        self[k] = v


def scanned_pdf(path):
    """PDF solo-imagen: texto renderizado como foto (como un escaneo)."""
    text = pymupdf.open()
    p = text.new_page(width=420, height=595)
    p.insert_textbox(pymupdf.Rect(50, 60, 370, 120), "THE PLANETS", fontsize=26, fontname="hebo")
    p.insert_textbox(pymupdf.Rect(50, 140, 370, 560), LOREM * 3, fontsize=12, fontname="tiro")
    pix = p.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    out = pymupdf.open()
    q = out.new_page(width=420, height=595)
    q.insert_image(q.rect, stream=buf.getvalue())
    out.save(path)
    return path


def seg(key, text):
    return Segment(key=key, page_no=1, bbox=(0, 0, 100, 20), line_rects=[], style=Style(), text=text, html=text)


def test_check_correction():
    assert check_correction("youre not looking", "you’re not looking") == []
    assert "la corrección cambia números" in check_correction("born in 1982", "born in 1928")
    assert check_correction("abc " * 30, "abc " * 10)  # recorta demasiado
    assert check_correction("x", "")


def test_correct_segments_rejects_bad_and_caches():
    class Fixer(FakeTranslator):
        model = "fixer"

        def correct_batch(self, items, context):
            self.calls += 1
            return {it["id"]: {"id": it["id"], "text": it["text"].replace("youre", "you’re").replace("1982", "1983")}
                    for it in items}

    cache, tr = MemCache(), Fixer()
    segs = [seg("a", "youre kind"), seg("b", "since 1982"), seg("c", "fine")]
    stats = correct_segments(segs, tr, cache, "en")
    assert segs[0].translation == "you’re kind"
    assert segs[1].translation is None and "la corrección cambia números" in segs[1].issues
    assert (stats.corrected, stats.unchanged, stats.rejected) == (1, 1, 1)
    again = [seg("a", "youre kind")]
    calls = tr.calls
    correct_segments(again, tr, cache, "en")
    assert again[0].translation == "you’re kind" and tr.calls == calls  # desde caché


def test_book_title():
    assert book_title("Mi Libro (Autora) (z-library.sk, 1lib.sk).pdf") == "Mi Libro (Autora)"


@needs_ocr
def test_run_digitize_makes_text_selectable():
    src = scanned_pdf(OUT / "escaneado.pdf")
    assert not pymupdf.open(src)[0].get_text().strip()
    result = run_digitize(src, OUT / "digital", DigitizeOptions(lang="en", correct=True), FakeTranslator(),
                          MemCache(), display_name="Planetas (z-lib.sk).pdf")
    out = pymupdf.open(result.output_pdf)
    text = out[0].get_text()
    assert "planets" in text.lower() and "zodiac" in text.lower()
    # PDF digital de verdad: texto visible con fuentes reales, sin la foto del escaneo debajo
    assert out[0].get_images() == []
    fonts = {f[3] for f in out[0].get_fonts()}
    assert fonts and not any("GlyphLess" in f for f in fonts)
    spans = [sp for b in out[0].get_text("dict")["blocks"] for l in b.get("lines", []) for sp in l["spans"]]
    assert spans and all(sp["alpha"] == 255 for sp in spans if sp["text"].strip())
    assert any(sg.block_type == "heading" for sg in result.pages[0].segments)  # "THE PLANETS" (negrita)
    assert result.output_pdf.name == "Planetas (digital).pdf"
    assert result.report["estadisticas"]["paginas_ocr_lista"] == [1]
    assert result.report["validaciones"] == {"mismo_numero_de_paginas": True, "mismas_dimensiones": True}
    from app.pipeline.epub import build_epub, epub_path_for, pages_from_pipeline

    epub = build_epub(result.output_pdf, pages_from_pipeline(result.pages), result.title, "",
                      epub_path_for(result.output_pdf), lang="en", scanned={1})
    z = zipfile.ZipFile(epub)
    body = "".join(z.read(n).decode() for n in z.namelist() if n.startswith("OEBPS/text/c"))
    assert "zodiac" in body and 'class="page"' not in body  # texto fluido, no la foto de la página
    assert result.output_pdf.stat().st_size < src.stat().st_size  # más liviano que el escaneo


@needs_ocr
def test_digitize_job_via_api(tmp_path, monkeypatch):
    import os

    os.environ["FAKE_TRANSLATOR"] = "true"
    os.environ["DATA_DIR"] = str(tmp_path)
    from app.config import get_settings

    get_settings.cache_clear()
    from app.cli import migrate

    migrate()
    from .conftest import admin_client

    from app import worker
    from app.main import app

    c = admin_client(app)
    while worker.claim_job():  # la BD de pruebas es compartida: no dejar trabajos en cola de otras pruebas
        pass
    data = scanned_pdf(tmp_path / "s.pdf").read_bytes()
    r = c.post("/api/jobs", files={"file": ("escaneo.pdf", data, "application/pdf")},
               data={"rights_confirmed": "true", "mode": "digitize", "ocr_lang": "en", "correct_ocr": "true"})
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["mode"] == "digitize" and [s["key"] for s in job["stages"]] == \
        ["upload", "analyze", "ocr", "correct", "compose", "validate", "done"]
    assert worker.claim_job() == job["id"]
    worker.process(job["id"])
    status = c.get(f"/api/jobs/{job['id']}").json()
    assert status["status"] == "done", status
    pdf = c.get(f"/api/jobs/{job['id']}/download")
    assert pdf.status_code == 200 and "planets" in pymupdf.open(stream=pdf.content)[0].get_text().lower()
    epub = c.get(f"/api/jobs/{job['id']}/download?format=epub")
    assert epub.status_code == 200 and epub.headers["content-type"] == "application/epub+zip"
    get_settings.cache_clear()
