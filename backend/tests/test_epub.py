"""EPUB fluido para Kindle generado desde los segmentos traducidos."""
import re
import zipfile
from xml.dom import minidom

from app.pipeline.epub import EpubPage, Seg, build_epub, collapse_spacing, to_xhtml
from app.pipeline.runner import PipelineOptions, run_pipeline
from app.pipeline.translate import FakeTranslator

from .conftest import OUT


class MemCache:
    def __init__(self):
        self.d = {}

    def get(self, k):
        return self.d.get(k)

    def set(self, k, v, model):
        self.d[k] = v


def test_xhtml_helpers():
    assert to_xhtml('Hola<br>mundo <span style="color:#ff0000">rojo</span> & <b>b</b>') == \
        "Hola<br/>mundo rojo &amp; <b>b</b>"
    assert collapse_spacing("A C E R C A  D E L  L I B R O") == "ACERCA DEL LIBRO"
    assert collapse_spacing("Aries") == "Aries"


def test_paragraphs_join_and_margins_dropped(tmp_path, sample_pdf):
    seg = lambda k, y, t, typ="body", size=10.0: Seg(k, (40, y, 380, y + 20), typ, "translate", size, t)
    pages = [EpubPage(1, "digital", 420, 595, []),
             EpubPage(2, "digital", 420, 595, [seg("p002_s001", 10, "Capítulo 3", size=10),  # encabezado
                                               seg("p002_s002", 80, "Los planetas", "heading", 28),
                                               seg("p002_s003", 120, "El texto empieza aquí y"),
                                               seg("p002_s004", 575, "15")]),
             EpubPage(3, "digital", 420, 595, [seg("p003_s001", 60, "sigue en la otra página.")])]
    out = build_epub(sample_pdf, pages, "Libro", "Autora", tmp_path / "x.epub")
    z = zipfile.ZipFile(out)
    body = "".join(z.read(n).decode() for n in z.namelist() if n.startswith("OEBPS/text/c"))
    assert "<h1" in body and "Los planetas" in body
    assert "El texto empieza aquí y sigue en la otra página." in body
    assert "Capítulo 3" not in body and ">15<" not in body


def test_epub_from_pipeline_is_valid(sample_pdf):
    out_dir = OUT / "epub"
    result = run_pipeline(sample_pdf, out_dir, FakeTranslator(), MemCache(), {}, {},
                          PipelineOptions(detect_names=False), lambda *a: None)
    from app.pipeline.epub import epub_path_for, pages_from_pipeline

    path = build_epub(result.output_pdf, pages_from_pipeline(result.pages), "Libro", "", epub_path_for(result.output_pdf))
    z = zipfile.ZipFile(path)
    names = z.namelist()
    assert names[0] == "mimetype" and z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
    assert z.read("mimetype") == b"application/epub+zip"
    for n in names:
        if n.endswith((".xhtml", ".opf", ".ncx", ".xml")):
            minidom.parseString(z.read(n))  # XML bien formado
    opf = z.read("OEBPS/content.opf").decode()
    assert 'properties="cover-image"' in opf and "<dc:language>es</dc:language>" in opf
    for href in re.findall(r'href="([^"]+)"', opf):
        assert f"OEBPS/{href}" in names  # todo lo declarado existe
    assert z.read("OEBPS/nav.xhtml").decode().count("<li>") >= 1


def test_scan_headings_cleaned():
    from collections import Counter

    from app.pipeline.epub import scan_heading

    known = Counter({"mercurio": 3, "luna": 2, "planos": 1, "esfera": 1, "celeste": 1, "figura": 1})
    assert scan_heading("MERCURIO Ó", known) == "MERCURIO"
    assert scan_heading("La Luna ))", known) == "La Luna"
    assert scan_heading("Planos de la Esfera Celeste (Figura A)", known) == "Planos de la Esfera Celeste (Figura A)"
    assert scan_heading("ar] tia Pro —", known) is None  # basura OCR de un título decorativo
    assert scan_heading("TU = TE - Delta T", known) is None
    assert scan_heading("vi tud de miras, habilidad para ordenar y tiene intere-", known) is None
    assert scan_heading("EL ZODIACO Y SUS SIGNOS ........ 12", known) is None
