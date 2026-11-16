"""Prueba end-to-end con PDF sintético y traductor falso que alarga el texto (simula el español)."""
import pymupdf

from app.pipeline.analyze import analyze
from app.pipeline.runner import PipelineOptions, run_pipeline
from app.pipeline.translate import DictCache, FakeTranslator

from .conftest import OUT


def test_analyze_classifies_pages(sample_pdf):
    pages = analyze(pymupdf.open(sample_pdf))
    assert pages[0].kind in ("digital", "mixed") and pages[0].segments  # portada: texto sobre imagen
    assert pages[1].kind == "blank"
    toc = pages[2]
    keep = [s.text for s in toc.segments if s.action == "keep"]
    assert "12" in keep and "180" in keep  # números de página del índice se conservan
    assert any(s.text == "Sun signs" and s.action == "translate" for s in toc.segments)
    p4 = pages[3]
    assert any(s.text == "41" and s.action == "keep" for s in p4.segments)
    # dos columnas => dos párrafos distintos, no mezclados
    bodies = [s for s in p4.segments if s.block_type in ("body", "caption") and len(s.text) > 200]
    assert len(bodies) == 2


def test_full_pipeline_preserves_layout(sample_pdf):
    out = OUT / "pipeline"
    opts = PipelineOptions(detect_names=False)
    res = run_pipeline(sample_pdf, out, FakeTranslator(0.3), DictCache(),
                       {"Kim Farley": "NAME", "Carole Taylor": "NAME", "Jane Ewart": "NAME"}, {}, opts)
    r = res.report
    v = r["validaciones"]
    assert v["mismo_numero_de_paginas"] and v["mismas_dimensiones"]
    assert v["paginas_vacias_conservadas"] and v["imagenes_conservadas"]
    assert v["graficos_vectoriales_conservados"] and v["terminos_protegidos_intactos"]
    assert v["sin_marcadores_residuales"] and v["traduccion_completa"]
    assert res.output_pdf.name.endswith("(ES).pdf")

    out_doc = pymupdf.open(res.output_pdf)
    orig = pymupdf.open(sample_pdf)
    assert len(out_doc) == len(orig)
    text = " ".join(pg.get_text() for pg in out_doc)
    assert "978-0-7440-2366-4" in text.replace("\n", "")
    assert "Kim Farley" in text and "Carole Taylor" in text
    assert " ES" in text  # se insertó la "traducción"
    assert out_doc[1].get_text().strip() == ""  # vacía sigue vacía
    # todo el contenido traducido está presente (nunca se corta texto)
    for p in res.pages:
        for s in p.segments:
            if s.action == "translate":
                words = [w for w in s.text.split() if w.isalpha()][:3]
                page_text = out_doc[p.number - 1].get_text().replace("\n", " ")
                for w in words:
                    assert w in page_text, (s.key, w)


def test_ensure_unique_keys_renumbers_duplicates_and_flags_page():
    from app.pipeline.types import PageInfo, Segment, Style, ensure_unique_keys

    def seg(key):
        return Segment(key=key, page_no=129, bbox=(0, 0, 10, 10), line_rects=[], style=Style(), text="x", html="x")

    info = PageInfo(number=129, width=100, height=100, rotation=0, kind="digital",
                    segments=[seg("p129_s001"), seg("p129_s008"), seg("p129_s008"), seg("p129_s009")])
    assert ensure_unique_keys(info) == ["p129_s008"]
    keys = [s.key for s in info.segments]
    assert keys == ["p129_s001", "p129_s008", "p129_s010", "p129_s009"]
    assert info.needs_review and "p129_s008" in info.review_reasons[0]
    assert ensure_unique_keys(info) == []  # sin repetidos no cambia nada


def _fact_sheet_pdf():
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=500)
    y = 60
    for label, value in [("Rules", "Co-rules Scorpio"), ("Day of the week", None), (None, "No allotted day"),
                         ("Metal", "Plutonium"), ("Colours", "Maroon,"), (None, "dark red")]:
        x = 40
        if label:
            page.insert_text((x, y), label, fontname="helv", fontsize=14)
            x += pymupdf.get_text_length(label, "helv", 14) + 8
        if value:
            page.insert_text((x, y), value, fontname="hebo", fontsize=14)
        y += 17
    # párrafo normal con palabras en negrita al inicio de línea: no es una ficha
    for line in ["Pluto takes about 248 years", "to orbit the Sun and is", "linked with transformation."]:
        page.insert_text((40, y + 40), line, fontname="helv", fontsize=14)
        y += 17
    page.insert_text((40, y + 60), "Note", fontname="helv", fontsize=14)
    return doc


def test_fact_sheet_is_split_into_fields():
    from app.pipeline.analyze import classify_page, extract_segments

    doc = _fact_sheet_pdf()
    page = doc[0]
    segs = extract_segments(page, classify_page(page, 1))
    fields = [s for s in segs if s.role == "field"]
    assert [s.text.replace("\n", " ").split() for s in fields] == [
        ["Rules", "Co-rules", "Scorpio"], ["Day", "of", "the", "week", "No", "allotted", "day"],
        ["Metal", "Plutonium"], ["Colours", "Maroon,", "dark", "red"]]
    assert all("<b>" in s.html for s in fields)
    body = [s for s in segs if "orbit" in s.text]
    assert body and body[0].role is None


def test_field_segments_are_sent_with_field_type():
    from app.pipeline.translate import _item
    from app.pipeline.types import Segment, Style

    s = Segment(key="p001_s001", page_no=1, bbox=(0, 0, 1, 1), line_rects=[], style=Style(), text="Metal Silver",
                html="Metal <b>Silver</b>", block_type="body", role="field", protected="Metal <b>Silver</b>")
    assert _item(s)["type"] == "field"
    s.role = None
    assert _item(s)["type"] == "body"


def test_mark_figures_only_marks_text_inside_pictures():
    from app.pipeline.analyze import mark_figures
    from app.pipeline.types import Segment, Style

    def seg(key, bbox, role=None, action="translate"):
        return Segment(key=key, page_no=1, bbox=bbox, line_rects=[], style=Style(), text="x", html="x",
                       role=role, action=action)

    inside, outside, field, keep = (seg("a", (10, 10, 20, 20)), seg("b", (300, 300, 320, 320)),
                                    seg("c", (12, 12, 18, 18), role="field"), seg("d", (12, 12, 18, 18), action="keep"))
    mark_figures([inside, outside, field, keep], [pymupdf.Rect(0, 0, 100, 100)])
    assert (inside.role, outside.role, field.role, keep.role) == ("figure", None, "field", None)


def test_page_context_is_sent_once_per_batch_for_figure_pages():
    from app.pipeline.translate import Protector, translate_segments
    from app.pipeline.types import Segment, Style

    class Spy(FakeTranslator):
        def __init__(self):
            super().__init__(expansion=0)
            self.contexts = []

        def translate_batch(self, items, context):
            self.contexts.append(context)
            return super().translate_batch(items, context)

    def seg(key, page, text, role=None):
        return Segment(key=key, page_no=page, bbox=(0, 0, 1, 1), line_rects=[], style=Style(), text=text,
                       html=text, role=role)

    segs = [seg("p129_s001", 129, "Rules Co-rules Scorpio", "field"), seg("p129_s002", 129, "POWER", "figure"),
            seg("p020_s001", 20, "Astrology belongs to a magical mindset.")]
    spy = Spy()
    translate_segments(segs, spy, DictCache(), Protector(), concurrency=1)
    pages = {k: v for c in spy.contexts for k, v in (c.get("page_context") or {}).items()}
    assert pages == {"129": "Rules Co-rules Scorpio / POWER"}
