"""Digitalizar un PDF escaneado (sin traducir): PDF con texto seleccionable y buscable + EPUB para Kindle.

1. analyze: qué páginas no tienen texto (escaneadas o imagen).
2. ocr: OCRmyPDF añade una capa de texto invisible sobre la imagen original (que no se toca), endereza y
   rota las páginas; las que ya tienen texto se dejan igual (--skip-text).
3. extract: los párrafos se leen de la capa nueva con el mismo análisis que un PDF digital.
4. correct (opcional): el modelo corrige errores de reconocimiento; se usa en el EPUB. La capa del PDF
   conserva el texto del OCR con sus posiciones exactas (buscar y seleccionar).
5. validate: mismas páginas y medidas; páginas que siguen sin texto (ilustraciones) en el reporte.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pymupdf

from app.pipeline.analyze import analyze
from app.pipeline.runner import INVALID_FN_RE, Cancelled, PipelineResult
from app.pipeline.translate import CORRECT_PROMPT_VERSION, NUM_RE, TAG_RE, _batches, sanitize_html
from app.pipeline.types import PageInfo, Segment

log = logging.getLogger(__name__)

TESSERACT_LANGS = {"en": "eng", "es": "spa", "auto": "eng+spa"}
OCR_SECONDS_PER_PAGE = 0.4  # estimación para la barra de progreso (enderezar, 4 procesos en paralelo)


@dataclass
class DigitizeOptions:
    lang: str = "en"  # en | es | auto
    correct: bool = False
    concurrency: int = 4
    batch_chars: int = 3000
    batch_items: int = 40


def ocrmypdf_available() -> bool:
    return shutil.which("ocrmypdf") is not None and shutil.which("tesseract") is not None


def digital_filename(title: str, fallback: str) -> str:
    name = re.sub(r"\s+", " ", INVALID_FN_RE.sub("", title).strip(" .")) or fallback
    return f"{name[:150].rstrip()} (digital).pdf"


def run_ocrmypdf(src: Path, dst: Path, lang: str, pages_hint: int,
                 tick: Callable[[str, int, int, int | None], None]) -> None:
    jobs = max(1, min(8, os.cpu_count() or 1))
    # solo preparar las imágenes (rotar y enderezar); el OCR con maquetación lo hace ocr_page_segments
    cmd = ["ocrmypdf", "--skip-text", "-l", TESSERACT_LANGS.get(lang, "eng"), "--rotate-pages", "--deskew",
           "--tesseract-timeout", "0", "--jobs", str(jobs), "--output-type", "pdf", "--optimize", "0",
           str(src), str(dst)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    started = time.time()
    estimate = max(5.0, pages_hint * OCR_SECONDS_PER_PAGE * 4 / jobs)
    try:
        while proc.poll() is None:
            done = min(0.95, (time.time() - started) / estimate)
            tick("ocr", int(done * 1000), 1000, None)  # lanza Cancelled si se pidió detener
            time.sleep(1)
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    err = proc.stderr.read() if proc.stderr else ""
    if proc.returncode not in (0,):
        raise RuntimeError(f"OCRmyPDF falló (código {proc.returncode}): {err.strip()[-500:]}")


# ---------------------------------------------------------------- OCR con maquetación (bloques, párrafos, líneas)

OCR_DPI = 300


def ocr_page_segments(img, number: int, lang: str, page_width: float) -> list[Segment]:
    """Tesseract en modo maquetación (--psm 3) → un segmento por párrafo, con sus líneas y alineación."""
    import html as _html
    import statistics

    import pytesseract

    from app.pipeline.types import Style

    k = 72.0 / OCR_DPI
    data = pytesseract.image_to_data(img, lang=TESSERACT_LANGS.get(lang, "eng"), config="--psm 3",
                                     output_type=pytesseract.Output.DICT)
    paras: dict[tuple, dict[int, list]] = {}
    for i, word in enumerate(data["text"]):
        word = (word or "").strip()
        conf = float(data["conf"][i])
        if not word or conf < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i])
        box = pymupdf.Rect(data["left"][i] * k, data["top"][i] * k, (data["left"][i] + data["width"][i]) * k,
                           (data["top"][i] + data["height"][i]) * k)
        paras.setdefault(key, {}).setdefault(data["line_num"][i], []).append((word, box, conf))
    segs: list[Segment] = []
    for key in sorted(paras):
        lines = []
        for ln in sorted(paras[key]):
            words = paras[key][ln]
            rect = pymupdf.Rect(words[0][1])
            for _, b, _ in words[1:]:
                rect |= b
            lines.append((" ".join(w for w, _, _ in words), rect, [c for _, _, c in words]))
        confs = [c for _, _, cs in lines for c in cs]
        text = ""
        for t, _, _ in lines:
            if text.endswith("-") and t[:1].islower() and len(text) > 1 and text[-2].isalpha():
                text = text[:-1] + t  # palabra partida al final de la línea
            else:
                text = f"{text} {t}" if text else t
        letters = sum(ch.isalpha() for ch in text)
        mean_conf = statistics.mean(confs)
        if (letters == 0 and not text.strip().isdigit()) or mean_conf < 35 or (letters < 3 and mean_conf < 60):
            continue  # ruido de ilustraciones, sombras o manchas
        rects = [r for _, r, _ in lines]
        bbox = pymupdf.Rect(rects[0])
        for r in rects[1:]:
            bbox |= r
        if len(rects) > 1:
            pitch = statistics.median(b.y0 - a.y0 for a, b in zip(rects, rects[1:], strict=False))
            size = max(5.0, pitch / 1.2)
        else:
            size = max(5.0, rects[0].height * 0.82)
        align = "left"
        if len(rects) > 2:
            rights = [r.x1 for r in rects[:-1]]
            lefts = [r.x0 for r in rects[1:]]
            if max(rights) - min(rights) < 0.6 * size:
                align = "justify"
            elif max(lefts) - min(lefts) > 1.5 * size:
                centers = [(r.x0 + r.x1) / 2 for r in rects]
                if max(centers) - min(centers) < 0.6 * size:
                    align = "center"
        elif abs((bbox.x0 + bbox.x1) / 2 - page_width / 2) < 0.03 * page_width and bbox.width < 0.7 * page_width:
            align = "center"
        style = Style(font="", size=round(size, 2), color="#1a1a1a", serif=True, align=align, line_height=1.2)
        segs.append(Segment(key=f"p{number:03d}_s{len(segs) + 1:03d}", page_no=number, bbox=tuple(bbox),
                            line_rects=[tuple(r) for r in rects], style=style, text=text, html=_html.escape(text, quote=False),
                            block_type="body", action="translate", ocr_confidence=round(mean_conf, 1)))
    return merge_continuations(segs)


TERMINAL_PUNCT = tuple(".!?:;…»”\")")


def merge_continuations(segs: list[Segment]) -> list[Segment]:
    """Tesseract a veces parte un párrafo en dos: se unen si el segundo sigue en minúscula justo debajo."""
    out: list[Segment] = []
    for sg in segs:
        prev = out[-1] if out else None
        if prev is not None and sg.text[:1].islower() and not prev.text.rstrip().endswith(TERMINAL_PUNCT):
            a, b = pymupdf.Rect(prev.bbox), pymupdf.Rect(sg.bbox)
            overlap = min(a.x1, b.x1) - max(a.x0, b.x0)
            if overlap > 0.6 * min(a.width, b.width) and -2 <= b.y0 - a.y1 < 1.6 * prev.style.size:
                if prev.text.endswith("-") and len(prev.text) > 1 and prev.text[-2].isalpha():
                    prev.text = prev.text[:-1] + sg.text
                else:
                    prev.text = f"{prev.text} {sg.text}"
                prev.html = html_escape(prev.text)
                prev.line_rects = prev.line_rects + sg.line_rects
                prev.bbox = tuple(a | b)
                if prev.style.align == "left" and len(prev.line_rects) > 2:
                    rights = [r[2] for r in prev.line_rects[:-1]]
                    if max(rights) - min(rights) < 0.6 * prev.style.size:
                        prev.style.align = "justify"
                continue
        out.append(sg)
    for i, sg in enumerate(out, 1):
        sg.key = f"{sg.key[:5]}s{i:03d}"
    return out


def html_escape(text: str) -> str:
    import html as _html

    return _html.escape(text, quote=False)


def ocr_pages(doc: pymupdf.Document, numbers: list[int], lang: str, tick) -> dict[int, list[Segment]]:
    """OCR en paralelo (Tesseract es un proceso externo); el render se hace en este hilo, en serie."""
    from concurrent.futures import ThreadPoolExecutor

    from PIL import Image

    result: dict[int, list[Segment]] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(8, os.cpu_count() or 1))) as pool:
        futures = {}
        ahead = 8

        def submit(j: int) -> None:
            if j < len(numbers):
                n = numbers[j]
                page = doc[n - 1]
                pix = page.get_pixmap(dpi=OCR_DPI, colorspace=pymupdf.csGRAY, alpha=False)
                img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                futures[n] = pool.submit(ocr_page_segments, img, n, lang, page.rect.width)

        for j in range(ahead):
            submit(j)
        for i, n in enumerate(numbers):
            tick("ocr", i, len(numbers), n)
            submit(i + ahead)
            result[n] = futures.pop(n).result()
    tick("ocr", len(numbers), len(numbers))
    return result


def classify_blocks(pages: list[PageInfo], body_size: float) -> None:
    """Títulos: una línea corta en negrita/cursiva o claramente más grande que el cuerpo."""
    for info in pages:
        for sg in info.segments:
            short = len(sg.line_rects) == 1 and len(sg.text) < 90
            if short and (sg.style.bold or sg.style.italic or sg.style.size > 1.25 * body_size) \
                    and any(ch.isalpha() for ch in sg.text):
                sg.block_type = "heading"


# ---------------------------------------------------------------- corrección con el modelo

@dataclass
class CorrectionStats:
    total: int = 0
    cached: int = 0
    corrected: int = 0
    unchanged: int = 0
    rejected: int = 0
    api_calls: int = 0


def _numbers(text: str) -> Counter:
    return Counter(NUM_RE.findall(TAG_RE.sub(" ", text)))


def check_correction(original: str, corrected: str) -> list[str]:
    """Una corrección de OCR no cambia cifras, etiquetas ni la longitud de forma notable."""
    issues = []
    a, b = TAG_RE.sub("", original), TAG_RE.sub("", corrected)
    if not b.strip():
        issues.append("corrección vacía")
    elif abs(len(b) - len(a)) > 8 and not 0.8 <= len(b) / max(len(a), 1) <= 1.2:
        issues.append("la corrección cambia demasiado la longitud")
    if _numbers(original) != _numbers(corrected):
        issues.append("la corrección cambia números")
    for tag in ("<b>", "<i>", "<br>"):
        if original.count(tag) != corrected.count(tag):
            issues.append("la corrección cambia el formato")
            break
    return issues


def correct_key(model: str, lang: str, text: str) -> str:
    return hashlib.sha256(f"{CORRECT_PROMPT_VERSION}|{model}|{lang}|{text}".encode()).hexdigest()


def correct_segments(segments: list[Segment], translator, cache, lang: str, concurrency: int = 4,
                     max_chars: int = 3000, max_items: int = 40,
                     on_progress: Callable[[int, int], None] | None = None,
                     should_stop: Callable[[], bool] | None = None) -> CorrectionStats:
    """Guarda la corrección en seg.translation (lo que usa el EPUB). Si no pasa la validación, el
    segmento conserva el texto del OCR."""
    stats = CorrectionStats(total=len(segments))
    todo: list[Segment] = []
    for s in segments:
        s.protected = s.html  # _batches mide por este campo
        hit = cache.get(correct_key(translator.model, lang, s.html))
        if hit is not None:
            s.translation = hit
            stats.cached += 1
        else:
            todo.append(s)
    done = stats.cached
    if on_progress:
        on_progress(done, stats.total)

    def run(batch: list[Segment]):
        try:
            return batch, translator.correct_batch([{"id": s.key, "text": s.html} for s in batch], {"lang": lang})
        except Exception as e:  # noqa: BLE001
            return batch, e

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = [pool.submit(run, b) for b in _batches(todo, max_chars, max_items)]
        for fut in as_completed(futures):
            if should_stop and should_stop():
                for f in futures:
                    f.cancel()
                raise Cancelled()
            batch, out = fut.result()
            stats.api_calls += 1
            if isinstance(out, Exception):
                from app.pipeline.translate import FatalAPIError

                if isinstance(out, FatalAPIError):
                    raise out
                log.warning("Corrección de OCR falló en un lote: %s", out)
                stats.rejected += len(batch)
            else:
                for s in batch:
                    text = sanitize_html(str((out.get(s.key) or {}).get("text") or ""))
                    issues = check_correction(s.html, text) if text else ["sin respuesta"]
                    if issues:
                        s.rejected_text = text  # el playground la muestra junto al motivo del rechazo
                        s.issues.extend(issues)
                        stats.rejected += 1
                        continue
                    s.translation = text
                    cache.set(correct_key(translator.model, lang, s.html), text, translator.model)
                    if text == s.html:
                        stats.unchanged += 1
                    else:
                        stats.corrected += 1
            done += len(batch)
            if on_progress:
                on_progress(done, stats.total)
    return stats


# ---------------------------------------------------------------- PDF digital (texto real, sin la foto del escaneo)

FIGURE_DPI = 170
STYLE_DPI = 200
SHEARS = [round(-0.15 + 0.05 * i, 2) for i in range(12)]  # -0.15 … 0.40


def _stroke(ink) -> float:
    """Grosor medio del trazo: longitud media de los tramos horizontales de tinta (negrita ≈ +20 %)."""
    import numpy as np

    starts = int((np.diff(np.pad(ink, ((0, 0), (1, 1))), axis=1) == 1).sum())
    return float(ink.sum()) / max(1, starts)


def _slant(ink) -> float:
    """Inclinación de los trazos: la que deja las columnas verticales más 'nítidas' (cursiva ≈ 0.2–0.3)."""
    import cv2
    import numpy as np

    h, w = ink.shape
    if h < 8 or w < 20 or ink.sum() < 40:
        return 0.0
    src = ink.astype(np.float32)
    scores = []
    for shear in SHEARS:
        m = np.float32([[1, shear, -shear * h / 2], [0, 1, 0]])
        col = cv2.warpAffine(src, m, (w, h)).sum(axis=0)
        scores.append(float((col ** 2).sum()))
    base = scores[SHEARS.index(0.0)]
    best = max(range(len(SHEARS)), key=scores.__getitem__)
    return SHEARS[best] if base and scores[best] >= 1.01 * base else 0.0


def restyle_from_scan(src: pymupdf.Page, info: PageInfo, body_size: float) -> None:
    """El OCR no sabe de negritas, cursivas ni tamaños exactos: se miden en la imagen del escaneo.
    - tamaño: el cuerpo de texto se iguala al tamaño dominante del libro (los títulos conservan el suyo);
    - negrita: trazo claramente más grueso que el del cuerpo de la página;
    - cursiva: trazos inclinados."""
    import numpy as np

    pix = src.get_pixmap(dpi=STYLE_DPI, colorspace=pymupdf.csGRAY, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    k = STYLE_DPI / 72.0
    measures: dict[str, tuple[float, float]] = {}
    for sg in info.segments:
        strokes, slants = [], []
        for r in (sg.line_rects or [sg.bbox])[:3]:
            x0, y0, x1, y1 = (int(v * k) for v in r)
            ink = (img[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] < 140).astype(np.uint8)
            if ink.size and ink.sum() > 20:
                strokes.append(_stroke(ink))
                slants.append(_slant(ink))
        if strokes:
            measures[sg.key] = (float(np.median(strokes)), float(np.median(slants)))
    body = [measures[s.key][0] for s in info.segments if s.key in measures and len(s.text) > 80]
    ref = float(np.median(body)) if body else None
    for sg in info.segments:
        single = len(sg.line_rects) <= 1
        if abs(sg.style.size - body_size) <= 0.2 * body_size or (single and sg.style.size < body_size):
            # una sola línea: su altura subestima el tamaño; los títulos no son más pequeños que el cuerpo
            sg.style.size = body_size
        if sg.key in measures:
            stroke, slant = measures[sg.key]
            sg.style.bold = bool(ref and stroke > 1.18 * ref)
            sg.style.italic = slant >= 0.15


def is_tabular(info: PageInfo) -> bool:
    """Tablas (coordenadas, efemérides): muchas cifras y bloques cortos; no se pueden recomponer como párrafos."""
    text = " ".join(sg.text for sg in info.segments)
    digits = sum(ch.isdigit() for ch in text)
    letters = sum(ch.isalpha() for ch in text)
    return digits > 0.3 * max(1, digits + letters)


def image_page(page: pymupdf.Page, src: pymupdf.Page, info: PageInfo) -> None:
    """La página como imagen del escaneo (enderezado) + su texto invisible, seleccionable y buscable."""
    pix = src.get_pixmap(dpi=FIGURE_DPI, alpha=False)
    page.insert_image(page.rect, stream=pix.tobytes("jpg", jpg_quality=80))
    for sg in info.segments:
        sg.action = "keep"
        for k, r in enumerate(sg.line_rects or [sg.bbox]):
            r = pymupdf.Rect(r)
            text = sg.text if len(sg.line_rects) <= 1 else (sg.text if k == 0 else "")
            if text:
                page.insert_text((r.x0, r.y1 - 1), text, fontsize=max(4, min(sg.style.size, r.height)),
                                 fontname="helv", render_mode=3)


def body_size_of(pages: list[PageInfo], ocr_set: set[int]) -> float:
    sizes: Counter = Counter()
    for info in pages:
        if info.number in ocr_set:
            for sg in info.segments:
                sizes[round(sg.style.size * 2) / 2] += len(sg.text)
    return sizes.most_common(1)[0][0] if sizes else 10.0


def compose_digital(ocr_doc: pymupdf.Document, pages: list[PageInfo], ocr_set: set[int], out_path: Path,
                    work_dir: Path, fonts_dirs: str = "", on_page=None, restyled: bool = False) -> None:
    """Crea el PDF digital: en cada página escaneada, fondo blanco + figuras recortadas del escaneo + el texto
    reconocido escrito con una fuente real en su posición (motor de maquetación de la traducción).
    Las páginas que ya tenían texto digital se copian tal cual."""
    from app.pipeline.epub import EpubPage, Seg, scan_figures
    from app.pipeline.fonts import FontResolver
    from app.pipeline.rebuild import rebuild

    out = pymupdf.open()
    targets: list[PageInfo] = []
    body_size = body_size_of(pages, ocr_set)
    for info in pages:
        src = ocr_doc[info.number - 1]
        if info.number not in ocr_set:
            out.insert_pdf(ocr_doc, from_page=info.number - 1, to_page=info.number - 1)
            continue
        page = out.new_page(width=src.rect.width, height=src.rect.height)
        ep = EpubPage(info.number, info.kind, src.rect.width, src.rect.height,
                      [Seg(sg.key, tuple(sg.bbox), sg.block_type, sg.action, sg.style.size, sg.html)
                       for sg in info.segments])
        text_chars = sum(len(sg.text) for sg in info.segments)
        # lámina, portada, ilustración con poco texto o tabla: la página entera como imagen (el texto, invisible)
        if text_chars < 150 or is_tabular(info):
            image_page(page, src, info)
            if on_page:
                on_page(info.number)
            continue
        # también símbolos pequeños (glifos de planetas en el margen); el texto ya está enmascarado
        figures = scan_figures(src, ep, min_area=0.0012, min_dim=10)
        for r in figures:
            pix = src.get_pixmap(dpi=FIGURE_DPI, clip=r, alpha=False)
            page.insert_image(r, stream=pix.tobytes("jpg", jpg_quality=85))
        if not restyled:
            restyle_from_scan(src, info, body_size)
        inside = [sg for sg in info.segments  # texto de una tabla o ilustración: ya está en la imagen
                  if any(abs(pymupdf.Rect(sg.bbox) & r) > 0.6 * max(abs(pymupdf.Rect(sg.bbox)), 1) for r in figures)]
        inside_ids = {id(sg) for sg in inside}
        for sg in inside:
            sg.action = "keep"
            r = pymupdf.Rect(sg.bbox)
            page.insert_text((r.x0, r.y1 - 1), sg.text, fontsize=max(4, min(sg.style.size, r.height)),
                             fontname="helv", render_mode=3)  # invisible: seleccionable y buscable
        for sg in info.segments:
            if id(sg) in inside_ids:
                continue
            # la fuente del OCR (GlyphLessFont) no tiene glifos visibles: fuente libre serif equivalente
            sg.style.font, sg.style.variants = "LiberationSerif", {}
            sg.style.serif, sg.style.mono, sg.style.color = True, False, "#1a1a1a"
            sg.natural_width = True
            sg.action = "translate"
            sg.translation = sg.translation or sg.html
            sg.block_type = "body" if sg.block_type == "ocr" else sg.block_type
        targets.append(info)
        if on_page:
            on_page(info.number)
    # Liberation Serif (métricas de Times) y, si falta, Noto Serif: fuentes libres del sistema
    system = ("/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/noto")
    dirs = ":".join(d for d in (fonts_dirs, *system) if d)
    fonts = FontResolver(out, work_dir / "_fonts", dirs)
    rebuild(out, targets, fonts, 0.6, 5.0)
    # plan B: si el texto nuevo se superpone (tablas sin líneas, maquetación compleja), esa página conserva el
    # escaneo con su texto seleccionable en lugar de quedar ilegible
    for info in targets:
        if any("superponen" in r for r in info.review_reasons):
            i = info.number - 1
            out.delete_page(i)
            src = ocr_doc[i]
            page = out.new_page(pno=i, width=src.rect.width, height=src.rect.height)
            image_page(page, src, info)
            info.review_reasons = [r for r in info.review_reasons if "superponen" not in r]
            info.flag("Maquetación compleja: la página conserva la imagen del escaneo (texto seleccionable)")
    if len(ocr_set) == len(pages):
        # solo fuentes nuestras: incrustar únicamente los caracteres usados (las originales de InDesign no se
        # recortan nunca; ver runner.py)
        out.subset_fonts()
    out.save(out_path, garbage=3, deflate=True)
    out.close()
    shutil.rmtree(work_dir / "_fonts", ignore_errors=True)


# ---------------------------------------------------------------- orquestación

def book_title(name: str) -> str:
    """Título legible desde el nombre del archivo: sin extensión ni sufijos de descarga entre paréntesis."""
    stem = Path(name).stem
    stem = re.sub(r"\s*\((?:z-lib|[^)]*\.(?:sk|org|com|net))[^)]*\)", "", stem, flags=re.I)
    return re.sub(r"[_\s]+", " ", stem).strip() or "libro"


def run_digitize(input_pdf: Path, out_dir: Path, options: DigitizeOptions, translator=None, cache=None,
                 progress=None, should_stop: Callable[[], bool] | None = None,
                 display_name: str = "", fonts_dirs: str = "") -> PipelineResult:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}
    current = {"stage": None, "t": time.time()}

    def tick(stage: str, done: int, total: int, page: int | None = None):
        if stage != current["stage"]:
            now = time.time()
            if current["stage"]:
                timings[current["stage"]] = round(timings.get(current["stage"], 0) + now - current["t"], 1)
            current["stage"], current["t"] = stage, now
        if should_stop and should_stop():
            raise Cancelled()
        if progress:
            progress(stage, done, total, page)

    with pymupdf.open(input_pdf) as src:
        if src.is_encrypted:
            raise ValueError("El PDF está protegido con contraseña")
        tick("analyze", 0, len(src))
        before = analyze(src)
        title_meta = src.metadata.get("title") or ""
        page_count = len(src)
    needs_ocr = [p.number for p in before if p.kind in ("image_only", "scanned", "mixed")]
    tick("analyze", page_count, page_count)

    tmp_pdf = out_dir / "_ocr.pdf"
    warnings: list[str] = []
    if needs_ocr:
        if not ocrmypdf_available():
            raise RuntimeError("OCR_MISSING: falta OCRmyPDF/Tesseract en este equipo")
        run_ocrmypdf(Path(input_pdf), tmp_pdf, options.lang, len(needs_ocr), tick)
    else:
        shutil.copyfile(input_pdf, tmp_pdf)
        warnings.append("El PDF ya tenía texto digital en todas sus páginas; no hizo falta OCR.")
    tick("ocr", 1, 1)

    doc = pymupdf.open(tmp_pdf)
    ocr_set = set(needs_ocr)
    found = ocr_pages(doc, needs_ocr, options.lang, tick) if needs_ocr else {}
    pages: list[PageInfo] = before
    for info in pages:
        if info.number in ocr_set:
            info.segments = found.get(info.number, [])
            info.kind = "scanned"
    still_empty = [n for n in needs_ocr if not found.get(n)]
    body_size = body_size_of(pages, ocr_set)
    for n in needs_ocr:  # negrita, cursiva y tamaño medidos en la imagen
        restyle_from_scan(doc[n - 1], pages[n - 1], body_size)
    classify_blocks([pages[n - 1] for n in needs_ocr], body_size)
    # el título impreso de un escaneo suele estar en una imagen sin texto: mejor el metadato o el nombre del archivo
    title = (title_meta or book_title(display_name or Path(input_pdf).name)).strip()

    stats = CorrectionStats()
    if options.correct and translator is not None:
        targets = [s for p in pages if p.number in ocr_set for s in p.segments
                   if s.action == "translate" and any(ch.isalpha() for ch in s.text)]
        stats = correct_segments(targets, translator, cache, options.lang, options.concurrency,
                                 options.batch_chars, options.batch_items,
                                 on_progress=lambda d, t: tick("correct", d, t), should_stop=should_stop)

    tick("compose", 0, max(1, len(needs_ocr)))
    out_pdf = out_dir / digital_filename(title, Path(input_pdf).stem)
    if needs_ocr:
        done = [0]

        def on_page(n: int) -> None:
            done[0] += 1
            tick("compose", done[0], len(needs_ocr), n)

        compose_digital(doc, pages, ocr_set, out_pdf, out_dir, fonts_dirs, on_page=on_page, restyled=True)
    else:
        shutil.copyfile(input_pdf, out_pdf)
    tick("validate", 0, 1)
    with pymupdf.open(input_pdf) as a, pymupdf.open(out_pdf) as b:
        same_pages = len(a) == len(b)
        same_size = same_pages and all(abs(a[i].rect.width - b[i].rect.width) < 1 and
                                       abs(a[i].rect.height - b[i].rect.height) < 1 for i in range(len(a)))
        with_text = sum(1 for pg in b if pg.get_text().strip())
    doc.close()
    tmp_pdf.unlink(missing_ok=True)
    for n in still_empty:
        pages[n - 1].flag("Sin texto reconocible (ilustración o página en blanco)")
    report = {
        "modo": "digitalizar",
        "archivo_original": Path(input_pdf).name,
        "archivo_digital": out_pdf.name,
        "titulo": title,
        "idioma_ocr": options.lang,
        "validaciones": {"mismo_numero_de_paginas": same_pages, "mismas_dimensiones": same_size},
        "estadisticas": {
            "paginas": page_count,
            "paginas_con_ocr": len(needs_ocr),
            "paginas_ocr_lista": needs_ocr,
            "paginas_con_texto": with_text,
            "paginas_ocr_sin_texto": still_empty,
            "correccion_con_modelo": options.correct and translator is not None,
            "segmentos_corregidos": stats.corrected,
            "segmentos_sin_cambios": stats.unchanged + stats.cached,
            "correcciones_rechazadas": stats.rejected,
            "llamadas_api": stats.api_calls,
        },
        "paginas_para_revision": [{"pagina": p.number, "motivos": p.review_reasons} for p in pages if p.needs_review],
        "advertencias": warnings,
    }
    timings[current["stage"]] = round(time.time() - current["t"], 1)
    report["tiempos_por_etapa_s"] = timings
    report_path = out_dir / "reporte-digitalizacion.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tick("validate", 1, 1)
    return PipelineResult(out_pdf, report_path, report, pages, title, title)
