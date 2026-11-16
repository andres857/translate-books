"""Glosario: coincidencias, formas del español, minería local, descubrimiento y aplicación al traducir."""
from app.pipeline.glossary import (Candidate, discover_glossary, form_present, match_glossary, mine_candidates,
                                   missing_terms)
from app.pipeline.protect import Protector
from app.pipeline.translate import DictCache, FakeTranslator, cache_key, translate_segments
from app.pipeline.types import Segment, Style


def seg(key, page, text, role=None, block_type="body"):
    return Segment(key=key, page_no=page, bbox=(0, 0, 1, 1), line_rects=[], style=Style(), text=text, html=text,
                   role=role, block_type=block_type)


def test_match_glossary_uses_whole_words_and_longest_phrase():
    g = {"Sun": "Sol", "Sun sign": "signo solar", "Co-rules": "Corregente de", "rules": "Rige"}
    assert match_glossary("Every Sunday", g) == {}
    assert match_glossary("Your Sun sign and the Sun", g) == {"Sun": "Sol", "Sun sign": "signo solar"}
    assert match_glossary("Your <b>Sun sign</b>", g) == {"Sun sign": "signo solar"}
    # espacio y guion equivalentes; "rules" dentro de "Co-rules" no cuenta aparte
    assert match_glossary("Jupiter co rules Pisces", g) == {"Co-rules": "Corregente de"}
    assert match_glossary("Rules <b>Scorpio</b> Co-rules <b>Pisces</b>", g) == {"Co-rules": "Corregente de",
                                                                               "rules": "Rige"}


def test_form_present_accepts_gender_and_number_not_synonyms():
    assert form_present("Los corregentes de Piscis", "corregente")
    assert form_present("Corregente de <b>Escorpio</b>", "Corregente de")
    assert form_present("las casas angulares", "casa angular")
    assert not form_present("Corrige Escorpio", "Corregente de")
    assert missing_terms("Co-rules Scorpio", "Corrige Escorpio", {"Co-rules": "Corregente de"}) == ["Corregente de"]
    assert missing_terms("Co-rules Scorpio", "Corregente de Escorpio", {"Co-rules": "Corregente de"}) == []


def test_mine_candidates_counts_repeated_terms_with_examples():
    segs = [seg(f"p{n:03d}_s001", n, f"Mars co-rules Scorpio and the Ruling planet of the sign {n}.") for n in (1, 2, 3)]
    segs += [seg("p004_s001", 4, "Ruling planet", role="field"), seg("p005_s001", 5, "once only here"),
             seg("p006_s001", 6, "Jupiter co-rules Pisces.")]
    cands = {c.term.lower(): c for c in mine_candidates(segs)}
    assert "ruling planet" in cands and cands["ruling planet"].count == 4
    assert cands["ruling planet"].pages == [1, 2, 3, 4]
    assert cands["co-rules"].count == 4  # aparece con planetas distintos: es un término en sí
    assert "scorpio and the ruling" not in cands  # "and" une dos frases, no forma locución
    assert "once only here" not in cands  # aparece una sola vez
    assert "the" not in cands and "and the" not in cands  # palabras vacías
    assert all(len(c.examples) <= 2 and all(len(e) <= 162 for e in c.examples) for c in cands.values())
    # "ruling" solo aparece dentro de "Ruling planet" con la misma frecuencia: redundante
    assert "ruling" not in cands


def test_discover_glossary_filters_and_dedupes_model_output():
    class Terminologist(FakeTranslator):
        def __init__(self):
            super().__init__()
            self.payloads = []

        def extract_glossary(self, payload):
            self.payloads.append(payload)
            return {"domain": "astrología occidental", "terms": [
                {"source": "Co-rules", "target": "Corregente de", "category": "regencia", "note": "regencia compartida"},
                {"source": "co-rules", "target": "Co-rige", "category": "", "note": ""},  # duplicado
                {"source": "Invented", "target": "Inventado", "category": "", "note": ""},  # no era candidato
                {"source": "Carole Taylor", "target": "Carole Taylor", "category": "nombre propio", "note": ""},
                {"source": "Ruling planet", "target": "", "category": "", "note": ""},  # sin destino
            ]}

    cands = [Candidate("Co-rules", 12), Candidate("Carole Taylor", 3), Candidate("Ruling planet", 20)]
    t = Terminologist()
    domain, entries = discover_glossary(cands, "The Secrets of Astrology", t, concurrency=1)
    assert domain == "astrología occidental"
    assert [(e.source, e.target, e.category) for e in entries] == [("Co-rules", "Corregente de", "regencia")]
    assert t.payloads[0]["book_title"] == "The Secrets of Astrology"
    assert t.payloads[0]["candidates"][0] == {"term": "Co-rules", "count": 12, "examples": []}


def test_cache_key_only_depends_on_matching_entries():
    base = {"Co-rules": "Corregente de"}
    k = cache_key("m", "Co-rules Scorpio", base)
    assert cache_key("m", "Co-rules Scorpio", {**base, "Sun sign": "signo solar"}) == k
    assert cache_key("m", "Co-rules Scorpio", {"Co-rules": "Corregente"}) != k


def test_missing_glossary_term_is_retried_then_flagged():
    class Stubborn(FakeTranslator):
        def __init__(self, fix_on_retry):
            super().__init__(expansion=0)
            self.fix, self.contexts = fix_on_retry, []

        def translate_batch(self, items, context):
            self.contexts.append(context)
            ok = self.fix and len(self.contexts) > 1
            return {it["id"]: {"id": it["id"], "translation": "Corregente de Escorpio" if ok else "Corrige Escorpio",
                               "issues": []} for it in items}

    g = {"Co-rules": "Corregente de", "Sun": "Sol"}
    t = Stubborn(fix_on_retry=True)
    s = seg("p129_s001", 129, "Co-rules Scorpio", role="field")
    translate_segments([s], t, DictCache(), Protector(), glossary=g, concurrency=1, domain="astrología")
    assert t.contexts[0]["glossary"] == {"Co-rules": "Corregente de"}  # solo lo que aparece
    assert t.contexts[0]["domain"] == "astrología"
    assert len(t.contexts) == 2 and s.translation == "Corregente de Escorpio" and s.issues == []

    t = Stubborn(fix_on_retry=False)
    s = seg("p129_s001", 129, "Co-rules Scorpio", role="field")
    translate_segments([s], t, DictCache(), Protector(), glossary=g, concurrency=1)
    assert len(t.contexts) == 2  # un solo reintento: después se acepta con aviso
    assert s.translation == "Corrige Escorpio" and "glosario: falta «Corregente de»" in s.issues
