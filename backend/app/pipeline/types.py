"""Estructuras en memoria del pipeline (independientes de la BD para poder probarlas y usarlas desde la CLI)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Style:
    font: str = ""
    size: float = 10.0
    color: str = "#000000"
    bold: bool = False
    italic: bool = False
    serif: bool = False
    mono: bool = False
    align: str = "left"  # left | center | right | justify
    line_height: float = 1.2  # múltiplo del tamaño de fuente
    # fuentes usadas por fragmentos inline: {"bold": "Font-Bold", "italic": ..., "bolditalic": ...}
    variants: dict = field(default_factory=dict)
    # tamaño relativo de los fragmentos <b> (títulos integrados más grandes que el cuerpo)
    bold_scale: float = 1.0

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["variants"] = dict(self.variants)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Style:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Segment:
    key: str  # p041_s03
    page_no: int  # 1-based
    bbox: tuple[float, float, float, float]
    line_rects: list[tuple[float, float, float, float]]  # zonas a borrar (por span)
    style: Style
    text: str  # texto plano original
    html: str  # texto con <b>/<i> inline, escapado
    baseline: float | None = None  # línea base de la primera línea (para alinear verticalmente)
    rotation: int = 0  # 0 = horizontal; 90 = vertical ascendente; 270 = vertical descendente
    origin: tuple[float, float] | None = None  # origen de la primera letra (texto rotado)
    block_type: str = "body"  # body | heading | toc | caption | table | ocr
    action: str = "translate"  # translate | keep | graphic | review
    protected: str | None = None
    placeholders: dict[str, str] = field(default_factory=dict)
    translation: str | None = None  # html traducido y restaurado
    issues: list[str] = field(default_factory=list)
    fit_scale: float | None = None
    ocr_confidence: float | None = None
    path: list[tuple[float, float]] | None = None  # texto curvo: polilínea de la línea base original
    small_chars: dict[str, tuple[float, float]] | None = None  # texto curvo: separadores (tamaño, desplazamiento)
    edited: bool = False  # traducción corregida a mano desde el admin: no se acorta ni se reescribe con el modelo
    natural_width: bool = False  # modo digitalizar: la fuente nueva usa su ancho natural (sin condensar al original)
    role: str | None = None  # "field": campo de ficha ("Etiqueta <b>valor</b>"); "figure": texto dentro de una ilustración


@dataclass
class PageInfo:
    number: int  # 1-based
    width: float
    height: float
    rotation: int
    kind: str  # blank | digital | scanned | mixed | image_only
    image_count: int = 0
    drawing_count: int = 0
    text_chars: int = 0
    segments: list[Segment] = field(default_factory=list)
    needs_review: bool = False
    review_reasons: list[str] = field(default_factory=list)

    def flag(self, reason: str) -> None:
        self.needs_review = True
        if reason not in self.review_reasons:
            self.review_reasons.append(reason)


def key_index(key: str) -> int:
    """Número final de un id de bloque ("p129_s008" -> 8); 0 si no tiene esa forma."""
    tail = key.rsplit("_s", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def ensure_unique_keys(info: "PageInfo") -> list[str]:
    """Las traducciones se guardan por id: si dos bloques de la página comparten id, uno pisa al otro.
    Renumera los repetidos con ids libres y marca la página para revisión. Devuelve los ids que se repetían."""
    seen: set[str] = set()
    dups: list[str] = []
    next_idx = max((key_index(sg.key) for sg in info.segments), default=0)
    for sg in info.segments:
        if sg.key in seen:
            dups.append(sg.key)
            next_idx += 1
            sg.key = f"p{info.number:03d}_s{next_idx:03d}"
        seen.add(sg.key)
    if dups:
        info.flag(f"Bloques con id repetido renumerados: {', '.join(sorted(set(dups)))}")
    return dups
