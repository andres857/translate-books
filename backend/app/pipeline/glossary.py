"""Glosario del libro: descubrimiento (minería local + terminólogo con el modelo) y aplicación al traducir.

- match_glossary: qué entradas aparecen en un texto (palabra completa, la locución más larga primero).
- form_present: si la traducción contiene la forma aprobada (admite género y número del español).
- mine_candidates: términos repetidos del libro con sus frases de ejemplo, sin llamar a ninguna API.
- discover_glossary: el modelo elige de esos candidatos los que necesitan una traducción fija.
"""
from __future__ import annotations

import html
import logging
import re
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.pipeline.types import Segment

log = logging.getLogger(__name__)

TAG_RE = re.compile(r"<[^>]*>")
PLACEHOLDER_RE = re.compile(r"__[A-Z]+_\d{3}__")


def plain(text: str | None) -> str:
    """Texto sin etiquetas ni entidades HTML (los marcadores protegidos se conservan)."""
    return html.unescape(TAG_RE.sub(" ", text or ""))


# ----------------------------------------------------------------------------- coincidencias

_pattern_cache: dict[str, re.Pattern] = {}


def _source_pattern(source: str) -> re.Pattern:
    p = _pattern_cache.get(source)
    if p is None:
        words = [re.escape(w) for w in re.split(r"[\s\-‐‑]+", source.strip()) if w]
        p = re.compile(r"(?<!\w)" + r"[\s\-‐‑]+".join(words) + r"(?!\w)", re.I)
        _pattern_cache[source] = p
    return p


def match_glossary(text: str, glossary: dict[str, str]) -> dict[str, str]:
    """Entradas del glosario presentes en text: palabra completa, sin distinguir mayúsculas, espacio y guion
    equivalentes ("Co-rules" = "co rules"); si dos se solapan gana la más larga ("Sun sign" antes que "Sun")."""
    if not glossary or not text:
        return {}
    text = plain(text)
    found = []
    for source in glossary:
        if not source.strip():
            continue
        for m in _source_pattern(source).finditer(text):
            found.append((m.start(), m.end(), source))
    occupied: list[tuple[int, int]] = []
    selected: dict[str, str] = {}
    for start, end, source in sorted(found, key=lambda x: (-(x[1] - x[0]), x[0])):
        if any(start < b and end > a for a, b in occupied):
            continue
        occupied.append((start, end))
        selected[source] = glossary[source]
    return dict(sorted(selected.items()))


# ----------------------------------------------------------------------------- formas del español

WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
INVARIABLE = frozenset("a al de del el la las los un una unos unas en con por para sin y o que se su sus es".split())


def forms(word: str) -> set[str]:
    """Variantes de género y número de una palabra aprobada (nunca sinónimos)."""
    word = unicodedata.normalize("NFC", word.casefold())
    if word in INVARIABLE or len(word) < 4:
        return {word}
    singular = word
    if word.endswith(("os", "as")):
        singular = word[:-1]
    elif word.endswith("es") and len(word) > 5:
        singular = word[:-2]
    elif word.endswith("s") and word[-2] in "aeiou":
        singular = word[:-1]
    variants = {word, singular}
    if re.search(r"(?:ic|ad|id|iv|os|ari|an|án|in|ólog)[oa]$", singular):
        stem = singular[:-1]
        variants.update(stem + e for e in ("o", "a", "os", "as"))
    elif singular.endswith(("a", "e", "i", "o", "u")):
        variants.add(singular + "s")
        if singular.endswith("e"):
            variants.add(singular + "n")  # rige / rigen
    elif singular.endswith("z"):
        variants.add(singular[:-1] + "ces")
    elif not singular.endswith("s"):
        variants.add(singular + "es")
    return variants


def form_present(text: str, approved: str) -> bool:
    """La traducción contiene la forma aprobada (o su femenino/plural); los espacios pueden variar."""
    text = unicodedata.normalize("NFC", plain(text))
    approved = unicodedata.normalize("NFC", approved.strip())
    if not approved:
        return True
    pieces, cursor = [], 0
    for m in WORD.finditer(approved):
        pieces.append(re.escape(approved[cursor:m.start()]))
        pieces.append("(?:" + "|".join(re.escape(w) for w in sorted(forms(m.group()))) + ")")
        cursor = m.end()
    pieces.append(re.escape(approved[cursor:]))
    pattern = "".join(pieces).replace(r"\ ", r"\s+")
    return bool(re.search(r"(?<!\w)" + pattern + r"(?!\w)", text, re.I))


def missing_terms(source_text: str, translation: str, glossary: dict[str, str]) -> list[str]:
    """Destinos del glosario que deberían estar en la traducción y no están."""
    return [target for target in match_glossary(source_text, glossary).values()
            if target.strip() and not form_present(translation, target)]


# ----------------------------------------------------------------------------- minería local

STOPWORDS = frozenset("""
a about above after again against all also am an and any are as at be because been before being below between
both but by can could did do does doing down during each either even ever every few for from further had has
have having he her here hers herself him himself his how however i if in into is it its itself just let like
may me might more most much must my myself no nor not now of off often on once one only or other our ours
ourselves out over own per rather same she should since so some such than that the their theirs them
themselves then there these they this those through thus to too under until up upon us very via was we were
what when where whether which while who whom whose why will with within without would yet you your yours
yourself yourselves s t don isn aren wasn weren hasn haven doesn didn won wouldn shouldn can't it's
""".split())

# dentro de una locución se admiten "of", "the"... ("Head of the Dragon"), pero no estas palabras, que unen frases
INNER_BREAK = frozenset("and or but nor that which who is are was were be been has have had will would can".split())
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'’]*(?:[\-‐‑][A-Za-z][A-Za-z'’]*)*")
# frases: los signos de puntuación y los marcadores protegidos cortan las locuciones
BREAK_RE = re.compile(r"__[A-Z]+_\d{3}__|[.,;:!?()\[\]{}\"“”/|•·–—…]+|\s[-‐‑]\s|\n")
MAX_N = 4


@dataclass
class Candidate:
    term: str
    count: int
    pages: list[int] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    score: float = 0.0

    def to_payload(self) -> dict:
        return {"term": self.term, "count": self.count, "examples": self.examples}


def _snippet(text: str, term: str, width: int = 160) -> str:
    m = _source_pattern(term).search(text)
    if not m:
        return text[:width]
    start = max(0, m.start() - (width - len(term)) // 2)
    out = text[start:start + width].strip()
    return ("…" if start else "") + out + ("…" if start + width < len(text) else "")


def mine_candidates(segments: list[Segment], limit: int = 600, min_count: int = 2) -> list[Candidate]:
    """Términos repetidos (1 a 4 palabras) con frecuencia, páginas y frases de ejemplo. Puntúan más las
    palabras con mayúscula o guion y lo que aparece en títulos y campos de fichas."""
    counts: Counter[str] = Counter()
    forms_seen: dict[str, Counter[str]] = defaultdict(Counter)
    pages: dict[str, set[int]] = defaultdict(set)
    texts: dict[str, list[str]] = defaultdict(list)
    bonus: Counter[str] = Counter()
    for s in segments:
        if s.action != "translate":
            continue
        text = re.sub(r"\s+", " ", PLACEHOLDER_RE.sub(" | ", plain(s.protected or s.html or s.text))).strip()
        if not text:
            continue
        prominent = s.role == "field" or s.block_type == "heading"
        seen_here: set[str] = set()
        for chunk in BREAK_RE.split(text):
            words = TOKEN_RE.findall(chunk)
            for n in range(1, MAX_N + 1):
                for i in range(len(words) - n + 1):
                    gram = words[i:i + n]
                    if gram[0].lower() in STOPWORDS or gram[-1].lower() in STOPWORDS:
                        continue
                    if n > 2 and any(w.lower() in INNER_BREAK for w in gram[1:-1]):
                        continue
                    if n == 1 and len(gram[0]) < 3:
                        continue
                    form = " ".join(gram)
                    key = form.lower()
                    if key in seen_here:
                        continue  # una vez por segmento: un párrafo que repite la palabra no la vuelve término
                    seen_here.add(key)
                    counts[key] += 1
                    forms_seen[key][form] += 1
                    pages[key].add(s.page_no)
                    if len(texts[key]) < 2:
                        texts[key].append(text)
                    if prominent:
                        bonus[key] += 1
    # una locución que solo aparece dentro de otra más larga (misma frecuencia) es redundante
    keys = [k for k, c in counts.items() if c >= min_count]
    by_len = sorted(keys, key=lambda k: -len(k.split()))
    redundant: set[str] = set()
    longer: list[str] = []
    for k in by_len:
        n = len(k.split())
        for big in longer:
            if len(big.split()) > n and counts[big] >= counts[k] * 0.9 and re.search(
                    r"(?<!\w)" + re.escape(k) + r"(?!\w)", big):
                redundant.add(k)
                break
        longer.append(k)
    out = []
    for k in keys:
        if k in redundant:
            continue
        form = forms_seen[k].most_common(1)[0][0]
        words = form.split()
        cap = sum(1 for w in words if w[:1].isupper()) / len(words)
        hyphen = 1 if any(re.search(r"[\-‐‑]", w) for w in words) else 0
        score = counts[k] * (1 + 0.35 * (len(words) - 1)) * (1 + cap + hyphen) + 6 * bonus[k]
        if len(words) == 1 and not cap and not hyphen:
            score *= 0.5  # palabra suelta en minúscula: casi siempre vocabulario general ("life", "world")
        out.append(Candidate(term=form, count=counts[k], pages=sorted(pages[k])[:5],
                             examples=[_snippet(t, form) for t in texts[k]], score=round(score, 2)))
    out.sort(key=lambda c: (-c.score, c.term.lower()))
    return out[:limit]


# ----------------------------------------------------------------------------- terminólogo

GLOSSARY_BATCH = 80
NAME_CATEGORIES = {"name", "nombre", "nombre propio", "persona", "brand", "marca"}


@dataclass
class GlossaryProposal:
    source: str
    target: str
    category: str = ""
    note: str = ""


def discover_glossary(candidates: list[Candidate], title: str, translator, concurrency: int = 4,
                      protected: set[str] | None = None,
                      on_progress=None) -> tuple[str, list[GlossaryProposal]]:
    """El modelo elige de los candidatos los términos con traducción fija. Devuelve (dominio, entradas)."""
    extract = getattr(translator, "extract_glossary", None)
    if not candidates or extract is None:
        return "", []
    batches = [candidates[i:i + GLOSSARY_BATCH] for i in range(0, len(candidates), GLOSSARY_BATCH)]
    known = {c.term.lower(): c.term for c in candidates}
    protected_l = {p.lower() for p in (protected or set())}
    done = [0]

    def run(batch: list[Candidate]) -> dict:
        try:
            return extract({"book_title": title, "candidates": [c.to_payload() for c in batch]}) or {}
        except Exception as e:
            if type(e).__name__ == "FatalAPIError":
                raise
            log.warning("Descubrimiento de glosario: un lote falló: %s", e)
            return {}
        finally:
            done[0] += 1
            if on_progress:
                on_progress(done[0], len(batches))

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        results = list(pool.map(run, batches))
    domains: Counter[str] = Counter()
    entries: dict[str, GlossaryProposal] = {}
    for res in results:
        if isinstance(res.get("domain"), str) and res["domain"].strip():
            domains[res["domain"].strip()[:128]] += 1
        for t in res.get("terms") or []:
            if not isinstance(t, dict):
                continue
            source = str(t.get("source") or "").strip()
            target = str(t.get("target") or "").strip()
            category = str(t.get("category") or "").strip()[:32]
            key = source.lower()
            if not source or not target or key not in known or key in protected_l or key in entries:
                continue
            if category.lower() in NAME_CATEGORIES:
                continue  # los nombres propios van a términos protegidos, no al glosario
            entries[key] = GlossaryProposal(known[key], target[:512], category,
                                            str(t.get("note") or "").strip()[:500])
    domain = domains.most_common(1)[0][0] if domains else ""
    return domain, sorted(entries.values(), key=lambda e: e.source.lower())
