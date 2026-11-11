"""EPUB 3 fluido para Kindle a partir de los segmentos traducidos (sin volver a "leer" el PDF).

- El texto sale de los segmentos: títulos → h1/h2/h3, cuerpo → párrafos (los que siguen en otra columna o
  página se unen), pies de foto → figcaption. Se descartan encabezados/pies de página, números de página y el
  índice impreso (el índice navegable se genera desde los títulos).
- Las figuras se recortan del PDF *traducido*, así gráficos, ruedas y etiquetas curvas salen ya en español.
- Páginas muy visuales (infografías, láminas, escaneadas): la página completa como imagen y debajo su texto
  en tamaño legible, para que también se pueda leer en un Kindle de tinta.

Send to Kindle acepta EPUB y lo convierte al formato Kindle; no hace falta MOBI/AZW.
"""
from __future__ import annotations

import html
import json
import re
import uuid
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from app.pipeline.translate import sanitize_html

IMAGE_WIDTH_PX = 1100
JPEG_QUALITY = 72
MARGIN_FRACTION = 0.075  # franja superior/inferior donde viven encabezados y pies de página
TERMINAL = tuple('.!?:;…»”")') + ("’",)


@dataclass
class Seg:
    key: str
    bbox: tuple[float, float, float, float]
    block_type: str
    action: str
    size: float
    html: str  # traducción (o el original si se conserva)


@dataclass
class EpubPage:
    number: int
    kind: str
    width: float
    height: float
    segments: list[Seg] = field(default_factory=list)


# ---------------------------------------------------------------- utilidades de texto

def to_xhtml(fragment: str) -> str:
    """HTML inline del pipeline → XHTML válido: solo <b>/<i>, <br/>; colores fuera."""
    s = sanitize_html(fragment or "")
    s = re.sub(r"</?span[^>]*>", "", s)
    s = re.sub(r"<br\s*/?>", "<br/>", s)
    return s.strip()


def plain(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", fragment or "")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text))).strip()


SPACED_RE = re.compile(r"^(?:\S(?: {1,3}|$))+$")


def collapse_spacing(xhtml: str) -> str:
    """'C O N T E N I D O' → 'CONTENIDO' (títulos con letras espaciadas; doble espacio = palabra)."""
    if "<" in xhtml or not SPACED_RE.match(xhtml) or len(xhtml) < 5 or "  " not in xhtml:
        return xhtml  # sin doble espacio no se sabe dónde termina cada palabra: se deja como está
    return " ".join(w.replace(" ", "") for w in re.split(r" {2,}", xhtml))


def has_letters(text: str) -> bool:
    return any(ch.isalpha() for ch in text)


def _rect(b) -> pymupdf.Rect:
    return pymupdf.Rect(*b)


def _area(r: pymupdf.Rect) -> float:
    return max(0.0, r.width) * max(0.0, r.height)


# ---------------------------------------------------------------- análisis por página

def body_size(pages: list[EpubPage]) -> float:
    weights: Counter = Counter()
    for p in pages:
        for s in p.segments:
            if s.block_type == "body":
                weights[round(s.size)] += len(plain(s.html))
    return float(weights.most_common(1)[0][0]) if weights else 10.0


def is_margin(seg: Seg, page: EpubPage, base: float) -> bool:
    """Encabezados/pies de página: franja superior o inferior, texto corto y pequeño (no títulos)."""
    if seg.size > base * 1.8:  # los títulos de capítulo arriba de la página son mucho más grandes
        return False
    r = _rect(seg.bbox)
    cy = (r.y0 + r.y1) / 2
    band = page.height * MARGIN_FRACTION
    return (cy < band or cy > page.height - band) and len(plain(seg.html)) < 70


def figure_regions(pdf_page: pymupdf.Page, page: EpubPage) -> list[pymupdf.Rect]:
    """Regiones de imágenes y dibujos que valen como figura (sin fondos de página, filetes ni cajas de texto)."""
    area = _area(pdf_page.rect)
    rects: list[pymupdf.Rect] = []
    for info in pdf_page.get_image_info():
        r = pymupdf.Rect(info["bbox"]) & pdf_page.rect
        if _area(r) > 0.02 * area and min(r.width, r.height) > 30:
            rects.append(r)
    try:
        clusters = pdf_page.cluster_drawings()
    except Exception:  # noqa: BLE001
        clusters = []
    for r in clusters:
        r = pymupdf.Rect(r) & pdf_page.rect
        if _area(r) < 0.03 * area or min(r.width, r.height) < 30:
            continue
        inside = sum(len(plain(s.html)) for s in page.segments
                     if s.block_type in ("body", "caption", "heading") and _rect(s.bbox) in r)
        if inside > 200:  # recuadro con texto corrido: el texto ya va como texto
            continue
        rects.append(r)
    # unir regiones que se tocan y extenderlas a las etiquetas que las cruzan
    merged: list[pymupdf.Rect] = []
    for r in sorted(rects, key=lambda x: -_area(x)):
        for m in merged:
            if m.intersects(r):
                m |= r
                break
        else:
            merged.append(pymupdf.Rect(r))
    for m in merged:
        for s in page.segments:
            sr = _rect(s.bbox)
            if s.block_type in ("curved", "label") and sr.intersects(m):
                m |= sr
    return [m & pdf_page.rect for m in merged]


def scan_figures(pdf_page: pymupdf.Page, page: EpubPage, min_area: float = 0.03,
                 min_dim: float = 50) -> list[pymupdf.Rect]:
    """Figuras en una página escaneada: zonas con tinta que no son texto reconocido."""
    import cv2
    import numpy as np

    dpi = 50
    k = 72.0 / dpi
    pix = pdf_page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    ink = (img < 170).astype(np.uint8)
    for s in page.segments:  # el texto reconocido no es figura
        x0, y0, x1, y1 = s.bbox
        ink[max(0, int(y0 / k) - 2):int(y1 / k) + 3, max(0, int(x0 / k) - 2):int(x1 / k) + 3] = 0
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    area = pdf_page.rect.width * pdf_page.rect.height
    rects = []
    for i in range(1, n):
        x, y, w, h, filled = stats[i]
        r = pymupdf.Rect(x * k, y * k, (x + w) * k, (y + h) * k)
        if _area(r) < min_area * area or min(r.width, r.height) < min_dim or filled < 0.05 * w * h:
            continue
        if r.width > 0.97 * pdf_page.rect.width and r.height > 0.97 * pdf_page.rect.height:
            continue  # borde o sombra del escaneo
        rects.append(r + (-4, -4, 4, 4))
    return [r & pdf_page.rect for r in rects]


def digit_ratio(text: str) -> float:
    chars = [c for c in text if not c.isspace()]
    return sum(c.isdigit() for c in chars) / max(len(chars), 1)


def is_visual(page: EpubPage, regions: list[pymupdf.Rect], scanned: bool = False) -> bool:
    text_chars = sum(len(plain(s.html)) for s in page.segments if s.block_type in ("body", "caption"))
    if scanned:
        # lámina, ilustración o tabla de números (el OCR de una tabla no se lee como texto fluido)
        allt = " ".join(plain(s.html) for s in page.segments)
        return text_chars < 150 or digit_ratio(allt) > 0.22
    if page.kind in ("image_only", "scanned"):
        return True
    page_area = page.width * page.height
    covered = sum(_area(r) for r in regions)
    return covered > 0.35 * page_area or (covered > 0.15 * page_area and text_chars < 600)


WORD_RE = re.compile(r"[^\W\d_]+")
SHORT_WORDS = {"a", "y", "o", "e", "u", "de", "la", "el", "en", "lo", "un", "al", "se", "su", "mi", "tu",
               "es", "of", "the", "to", "in", "on", "an", "as", "at", "by", "is", "it", "or"}
ROMAN_RE = re.compile(r"^[IVXL]+$")


def known_words(pages: list[EpubPage]) -> Counter:
    """Palabras del cuerpo del libro: sirven para reconocer títulos que el OCR leyó como basura."""
    words: Counter = Counter()
    for p in pages:
        for s in p.segments:
            if s.block_type == "body":
                words.update(w.lower() for w in WORD_RE.findall(plain(s.html)))
    return words


def _junk_token(t: str) -> bool:
    """Glifo de planeta/signo leído como letras: 'Ó', '))', "O'", 'Rh', 'Ó9'."""
    w = "".join(WORD_RE.findall(t))
    if ROMAN_RE.match(w) and w == t:
        return False
    return len(w) <= 2 and (w.lower() not in SHORT_WORDS or w != t)


def scan_heading(text: str, known: Counter) -> str | None:
    """Título de una página escaneada, limpio; None si no parece un título (basura OCR, tabla, frase)."""
    text = text.strip()
    if not text or text.endswith(("-", ",")) or text[:1].islower():
        return None  # renglón de un párrafo (p. ej. con una capitular grande)
    tokens = text.split()
    while len(tokens) > 1 and _junk_token(tokens[-1]) and not (")" in tokens[-1] and "(" in " ".join(tokens[:-1])):
        tokens.pop()
    while len(tokens) > 1 and _junk_token(tokens[0]):
        tokens.pop(0)
    text = " ".join(tokens).strip(" -—|=")
    if not text or len(text) > 90 or digit_ratio(text) > 0.15 or text[:1].islower():
        return None
    # los títulos no llevan frases dentro, fórmulas, celdas de tabla ni puntos guía del índice impreso
    if re.search(r"[,.;:] \S|[=+|]|\.\.", text) or text.endswith((".", ":", ";")):
        return None
    words = [w.lower() for w in WORD_RE.findall(text)]
    if not words or len(words) > 12 or sum(map(len, words)) < 4:
        return None
    good = sum(1 for w in words if w in SHORT_WORDS or known[w] >= 1 or len(w) >= 7)
    return text if good / len(words) >= 0.75 else None


PAGE_NO_RE = re.compile(r"\s+(\d{1,3})$")


def strip_page_number(xhtml: str, seg: Seg, page: EpubPage) -> str:
    """Tesseract a veces pega el número de página al primer/último renglón: '... el deseo de ser el 36'."""
    m = PAGE_NO_RE.search(xhtml)
    r = _rect(seg.bbox)
    if m and abs(int(m.group(1)) - page.number) <= 40 and (r.y0 < page.height * 0.15 or
                                                            r.y1 > page.height * 0.85):
        return xhtml[:m.start()]
    return xhtml


def render(pdf_page: pymupdf.Page, clip: pymupdf.Rect | None = None) -> bytes:
    r = clip or pdf_page.rect
    zoom = min(3.0, IMAGE_WIDTH_PX / max(r.width, 1))
    pix = pdf_page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=r, alpha=False)
    return pix.tobytes("jpg", jpg_quality=JPEG_QUALITY)


# ---------------------------------------------------------------- composición

class Book:
    def __init__(self, title: str, author: str, lang: str):
        self.title, self.author, self.lang = title, author, lang
        self.chapters: list[tuple[str, list[str]]] = []  # (archivo, bloques xhtml)
        self.nav: list[tuple[int, str, str]] = []  # (nivel, texto, href)
        self.images: list[tuple[str, bytes]] = []
        self._open_para: list[str] | None = None
        self._pending_figs: list[str] = []
        self._body: list[str] = []
        self._new_chapter()

    def _new_chapter(self) -> None:
        self._close_para()
        if self.chapters and not self.chapters[-1][1]:
            return
        self._body = []
        self.chapters.append((f"text/c{len(self.chapters) + 1:03d}.xhtml", self._body))

    def _close_para(self) -> None:
        if self._open_para is not None:
            self._body.append("<p>" + " ".join(self._open_para) + "</p>")
            self._open_para = None
        self._body.extend(self._pending_figs)
        self._pending_figs = []

    def image(self, data: bytes, alt: str = "", caption: str = "", full_page: bool = False) -> None:
        name = f"images/i{len(self.images) + 1:04d}.jpg"
        self.images.append((name, data))
        cls = "page" if full_page else "fig"
        cap = f"<figcaption>{caption}</figcaption>" if caption else ""
        block = f'<figure class="{cls}"><img src="../{name}" alt="{html.escape(alt)}"/>{cap}</figure>'
        if self._open_para is not None:
            self._pending_figs.append(block)  # no partir un párrafo que sigue en otra columna
        else:
            self._body.append(block)

    def heading(self, level: int, xhtml: str) -> None:
        if level == 1:
            self._new_chapter()
        self._close_para()
        anchor = f"h{len(self.nav) + 1}"
        self._body.append(f'<h{level} id="{anchor}">{xhtml}</h{level}>')
        self.nav.append((level, plain(xhtml), f"{self.chapters[-1][0]}#{anchor}"))

    def paragraph(self, xhtml: str, cls: str = "") -> None:
        text = plain(xhtml)
        if cls:
            self._close_para()
            self._body.append(f'<p class="{cls}">{xhtml}</p>')
            return
        if self._open_para is not None:
            prev = plain(self._open_para[-1])
            if prev.endswith("-") and text[:1].islower() and self._open_para[-1].rstrip().endswith("-"):
                self._open_para[-1] = self._open_para[-1].rstrip()[:-1] + xhtml  # palabra partida: "read-" + "ing"
                return
            if not prev.endswith(TERMINAL) or (text[:1].islower()):
                self._open_para.append(xhtml)  # el párrafo continúa en otra columna o página
                return
            self._close_para()
        self._open_para = [xhtml]

    def finish(self) -> None:
        self._close_para()


def compose(pdf: pymupdf.Document, pages: list[EpubPage], title: str, author: str, lang: str = "es",
            scanned: frozenset[int] | set[int] = frozenset()) -> Book:
    """`scanned`: páginas que vienen de un escaneo (modo digitalizar); su imagen de fondo es la página misma."""
    book = Book(title, author, lang)
    base = body_size(pages)
    known = known_words(pages) if scanned else Counter()
    for page in pages:
        if page.kind == "blank" or page.number > len(pdf):
            continue
        pdf_page = pdf[page.number - 1]
        if page.number == 1:
            book.cover = render(pdf_page)  # la portada ya va traducida
            if sum(len(plain(s.html)) for s in page.segments) < 300:
                continue  # portada: su texto ya está en la imagen
            # página 1 con texto corrido (documento sin portada): también como texto
        is_scan = page.number in scanned
        regions = scan_figures(pdf_page, page) if is_scan else figure_regions(pdf_page, page)
        visual = is_visual(page, regions, scanned=is_scan)
        segs = [s for s in page.segments
                if has_letters(plain(s.html)) and s.block_type != "toc" and not is_margin(s, page, base)]
        if visual:
            book.image(render(pdf_page), alt=f"Página {page.number}", full_page=True)
        else:
            keep: list[Seg] = []
            for s in segs:
                sr = _rect(s.bbox)
                in_fig = any(sr in r or (sr & r).get_area() > 0.6 * max(_area(sr), 1) for r in regions)
                if in_fig and (s.block_type in ("curved", "label") or len(plain(s.html)) < 40):
                    continue  # la etiqueta ya está dentro de la imagen de la figura
                keep.append(s)
            segs = keep
            figs = sorted(regions, key=lambda r: (r.y0, r.x0))
        emitted: set[int] = set()
        capitalize_next = False
        i = 0
        while i < len(segs):
            s = segs[i]
            if not visual:
                for k, r in enumerate(figs):
                    if k not in emitted and r.y0 <= _rect(s.bbox).y0:
                        emitted.add(k)
                        book.image(render(pdf_page, r), alt=f"Figura, página {page.number}")
            xhtml = to_xhtml(s.html)
            if is_scan:
                xhtml = strip_page_number(xhtml, s, page)
            if s.block_type == "heading" and len(plain(xhtml)) == 1 and plain(xhtml).isalpha():
                capitalize_next = True  # letra capitular: el párrafo siguiente ya trae el texto
                i += 1
                continue
            if capitalize_next and s.block_type == "body":
                xhtml = re.sub(r"^((?:<[^>]+>)*)(\w)", lambda m: m.group(1) + m.group(2).upper(), xhtml, count=1)
            capitalize_next = False
            if is_scan and (s.block_type == "heading" or s.size >= base * 1.3 and len(plain(xhtml)) <= 90):
                # escaneo: el tamaño medido es poco fiable; solo cuenta lo que el análisis marcó como título
                title = scan_heading(plain(xhtml), known)
                if title is None:
                    if len(plain(xhtml)) >= 25:
                        book.paragraph(xhtml)
                else:
                    level = 1 if s.size >= base * 2.2 else 2 if s.size >= base * 1.3 else 3
                    book.heading(level, html.escape(title, quote=False))
            elif is_scan:
                if s.block_type == "caption":
                    book.paragraph(xhtml, cls="caption")
                else:
                    book.paragraph(xhtml)
            elif s.block_type == "heading" or s.size >= base * 1.3:
                # títulos partidos en varios bloques ("THE SECRETS OF" + "ASTROLOGY")
                while (i + 1 < len(segs) and segs[i + 1].block_type == "heading"
                       and abs(segs[i + 1].size - s.size) < 0.6
                       and -s.size <= _rect(segs[i + 1].bbox).y0 - _rect(segs[i].bbox).y1 < s.size * 1.2):
                    i += 1
                    xhtml += " " + to_xhtml(segs[i].html)
                xhtml = collapse_spacing(xhtml)
                if len(plain(xhtml)) > 140:
                    book.paragraph(xhtml, cls="lead")  # cita destacada, no un título
                else:
                    level = 1 if s.size >= base * 2.2 else 2 if s.size >= base * 1.3 else 3
                    book.heading(level, xhtml)
            elif s.block_type == "caption":
                book.paragraph(xhtml, cls="caption")
            else:
                book.paragraph(xhtml)
            i += 1
        if not visual:
            for k, r in enumerate(figs):
                if k not in emitted:
                    book.image(render(pdf_page, r), alt=f"Figura, página {page.number}")
    book.finish()
    return book


# ---------------------------------------------------------------- empaquetado EPUB 3

CSS = """body{margin:0 4%;font-family:serif;line-height:1.45}
h1{font-size:1.6em;margin:1.2em 0 .6em;page-break-before:always;text-align:center}
h2{font-size:1.3em;margin:1.1em 0 .4em}
h3{font-size:1.05em;margin:1em 0 .3em}
p{margin:0 0 .6em;text-indent:0;text-align:justify}
p.lead{font-style:italic;font-size:1.1em;margin:1em 1.5em;text-align:left}
p.caption,figcaption{font-size:.85em;color:#444;text-align:left}
figure{margin:1em 0;text-align:center;page-break-inside:avoid}
figure img{max-width:100%;height:auto}
figure.page{page-break-before:always}
img.cover{width:100%;height:auto}
"""


def _xhtml_doc(title: str, lang: str, body: str) -> str:
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
            f'xml:lang="{lang}" lang="{lang}"><head><meta charset="utf-8"/><title>{html.escape(title)}</title>'
            '<link rel="stylesheet" type="text/css" href="../style.css"/></head>'
            f'<body>{body}</body></html>')


def write_epub(book: Book, out_path: Path, identifier: str) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".epub.tmp")
    t = html.escape(book.title)
    chapters = [(name, body) for name, body in book.chapters if body]
    cover = getattr(book, "cover", None)
    nav_items = [n for n in book.nav if n[0] == 1]
    upto2 = [n for n in book.nav if n[0] <= 2]
    if len(nav_items) < 3 or len(upto2) <= 120:  # con pocos títulos, también las secciones
        seen: set[str] = set()
        nav_items = [n for n in upto2 if not (n[1].lower() in seen or seen.add(n[1].lower()))]
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" '
                   'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                   '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                   '</rootfiles></container>')
        z.writestr("OEBPS/style.css", CSS)
        manifest = ['<item id="css" href="style.css" media-type="text/css"/>',
                    '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                    '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>']
        spine = []
        if cover:
            z.writestr("OEBPS/images/cover.jpg", cover)
            z.writestr("OEBPS/text/cover.xhtml", _xhtml_doc(book.title, book.lang,
                       f'<figure><img class="cover" src="../images/cover.jpg" alt="{t}"/></figure>'))
            manifest += ['<item id="cover-image" href="images/cover.jpg" media-type="image/jpeg" '
                         'properties="cover-image"/>',
                         '<item id="cover" href="text/cover.xhtml" media-type="application/xhtml+xml"/>']
            spine.append('<itemref idref="cover"/>')
        for k, (name, body) in enumerate(chapters, 1):
            z.writestr(f"OEBPS/{name}", _xhtml_doc(book.title, book.lang, "\n".join(body)))
            manifest.append(f'<item id="c{k:03d}" href="{name}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="c{k:03d}"/>')
        for k, (name, data) in enumerate(book.images, 1):
            z.writestr(f"OEBPS/{name}", data)
            manifest.append(f'<item id="img{k:04d}" href="{name}" media-type="image/jpeg"/>')
        first = chapters[0][0] if chapters else "text/cover.xhtml"
        entries = nav_items or [(1, book.title, first)]
        nav_li = "".join(f'<li><a href="{href}">{html.escape(text)}</a></li>' for _, text, href in entries)
        z.writestr("OEBPS/nav.xhtml", _xhtml_doc(book.title, book.lang,
                   f'<nav epub:type="toc" id="toc"><h1>Índice</h1><ol>{nav_li}</ol></nav>')
                   .replace('href="../style.css"', 'href="style.css"'))
        points = "".join(f'<navPoint id="n{k}" playOrder="{k}"><navLabel><text>{html.escape(text)}</text>'
                         f'</navLabel><content src="{href}"/></navPoint>'
                         for k, (_, text, href) in enumerate(entries, 1))
        z.writestr("OEBPS/toc.ncx",
                   '<?xml version="1.0" encoding="utf-8"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" '
                   f'version="2005-1"><head><meta name="dtb:uid" content="{identifier}"/></head>'
                   f'<docTitle><text>{t}</text></docTitle><navMap>{points}</navMap></ncx>')
        meta_cover = '<meta name="cover" content="cover-image"/>' if cover else ""
        z.writestr("OEBPS/content.opf",
                   '<?xml version="1.0" encoding="utf-8"?>'
                   '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">'
                   '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   f'<dc:identifier id="bookid">{identifier}</dc:identifier><dc:title>{t}</dc:title>'
                   f'<dc:language>{book.lang}</dc:language>'
                   + (f'<dc:creator>{html.escape(book.author)}</dc:creator>' if book.author else "")
                   + '<meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>'
                   + meta_cover + '</metadata>'
                   f'<manifest>{"".join(manifest)}</manifest>'
                   f'<spine toc="ncx">{"".join(spine)}</spine></package>')
    tmp.replace(out_path)
    return out_path


def build_epub(pdf_path: Path, pages: list[EpubPage], title: str, author: str, out_path: Path,
               book_id: str = "", lang: str = "es", scanned: frozenset[int] | set[int] = frozenset()) -> Path:
    with pymupdf.open(pdf_path) as pdf:
        book = compose(pdf, pages, title, author, lang, scanned)
    identifier = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, book_id or str(pdf_path)))
    return write_epub(book, out_path, identifier)


# ---------------------------------------------------------------- desde el pipeline o la base de datos

def pages_from_pipeline(infos) -> list[EpubPage]:
    """PageInfo del pipeline (CLI) → páginas para el EPUB."""
    out = []
    for info in infos:
        segs = [Seg(sg.key, tuple(sg.bbox), sg.block_type, sg.action, float(sg.style.size),
                    (sg.translation if sg.action == "translate" and sg.translation else sg.html) or "")
                for sg in sorted(info.segments, key=lambda x: x.key)]
        out.append(EpubPage(info.number, info.kind, info.width, info.height, segs))
    return out


def epub_path_for(output_pdf: str | Path) -> Path:
    return Path(output_pdf).with_suffix(".epub")


def build_epub_for_job(session, job) -> Path:
    """Genera (o regenera) el EPUB de un trabajo terminado a partir de sus segmentos guardados."""
    from sqlalchemy import select

    from app.db.models import Page

    doc = job.document
    pages: list[EpubPage] = []
    for p in session.scalars(select(Page).where(Page.job_id == job.id).order_by(Page.number)):
        segs = []
        for s in sorted(p.segments, key=lambda x: x.seg_key):
            style = s.style if isinstance(s.style, dict) else json.loads(s.style or "{}")
            text = s.translation if s.action == "translate" and s.translation else s.source_html or s.source_text
            segs.append(Seg(s.seg_key, tuple(s.bbox), s.block_type, s.action, float(style.get("size", 10)),
                            text or ""))
        pages.append(EpubPage(p.number, p.kind, p.width, p.height, segs))
    author = ""
    try:
        with pymupdf.open(doc.path) as src:
            author = (src.metadata or {}).get("author") or ""
    except Exception:  # noqa: BLE001
        pass
    options = job.options or {}
    digitize = options.get("mode") == "digitize"
    title = (doc.title if digitize else doc.title_es) or doc.title or Path(job.output_path).stem
    lang = {"en": "en", "es": "es"}.get(options.get("ocr_lang"), "en") if digitize else "es"
    scanned = set(options.get("ocr_pages") or []) if digitize else set()
    return build_epub(Path(job.output_path), pages, title, author, epub_path_for(job.output_path),
                      book_id=(doc.sha256 or str(job.id)) + ("-digital" if digitize else ""), lang=lang,
                      scanned=scanned)
