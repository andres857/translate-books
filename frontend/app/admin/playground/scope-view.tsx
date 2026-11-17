"use client";

/* Vista inicial del Playground (una página, no un modal), en tres pasos:
   1 · el libro, en un desplegable con buscador arriba (con su resumen y avisos al lado);
   2 · el alcance, en tarjetas de opción a la izquierda (capítulo, intervalo, páginas sueltas o libro completo);
   3 · la revisión de páginas, en una galería de miniaturas con filtros a la derecha.
   Una barra fija abajo resume lo que se va a procesar, deja elegir el método de la primera evaluación y la lanza.
   Funciona también con libros escaneados sin capítulos: se define un intervalo «10–20». */
import { useEffect, useMemo, useRef, useState, useSyncExternalStore, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import {
  DEEPSEEK_MODELS, jobPageImageUrl, listPlaygroundPages, type Chapter, type Estimate, type PlaygroundBook, type PlaygroundPageInfo,
  type PlaygroundScope,
} from "@/lib/api";
import { IconArrowLeft, IconArrowRight, IconCheck, IconChevron, IconTrash, IconWarn, IconX, IconZoom } from "../../components/art";
import { duration, fmtN, formatPages, parsePages } from "./shared";

type Mode = "chapter" | "range" | "loose" | "book";
const RANGE_RE = /^\s*(\d+)\s*(?:-\s*(\d+))?\s*$/;
const SCANNED = new Set(["scanned", "mixed"]); // texto por OCR; «image_only» son ilustraciones o páginas sin texto
const KIND: Record<string, string> = {
  digital: "Digital: texto del PDF", scanned: "Escaneada: texto por OCR", mixed: "Mixta: texto del PDF y OCR",
  image_only: "Solo imagen", blank: "En blanco", "": "Sin analizar",
};
// tamaño de la galería: ancho mínimo de la miniatura (clase) y resolución con que se pide la imagen
type Size = "s" | "m" | "l";
const SIZES: { id: Size; title: string; label: string; dpi: number }[] = [
  { id: "s", title: "S", label: "Miniaturas pequeñas", dpi: 36 },
  { id: "m", title: "M", label: "Miniaturas medianas", dpi: 56 },
  { id: "l", title: "L", label: "Miniaturas grandes", dpi: 84 },
];
const SIZE_KEY = "pg-thumb-size";
const subscribeNothing = () => () => {};
function storedSize(): Size {
  try {
    const v = localStorage.getItem(SIZE_KEY);
    return v === "s" || v === "l" ? v : "m";
  } catch { return "m"; }
}
type Filter = "all" | "scope" | "empty" | "ocr";

export interface ScopeValue {
  scope: PlaygroundScope;
  onePage: string;
  pagesSpec: string;
  chapter: string; // índice en la lista de capítulos
}

interface Props {
  books: PlaygroundBook[];
  bookId: number | null;
  onBook: (id: number) => void;
  onDeleteBook: (b: PlaygroundBook) => Promise<void>; // tras confirmar: borra el libro y su análisis
  chapters: Chapter[];
  value: ScopeValue;
  onChange: (v: Partial<ScopeValue>) => void;
  estimate: Estimate | null;
  estimateError: string | null;
  method: string; // «fake» o el modelo de DeepSeek de la primera variante
  onMethod: (m: string) => void;
  variantCount: number; // con más de una variante, el método se configura en la mesa
  busy: boolean;
  onContinue: () => void; // entra en la mesa y lanza la evaluación con el alcance elegido
  onBack?: () => void; // ya hay una mesa abierta: volver a ella sin cambiar nada
  upload: ReactNode; // progreso de preparación y avisos
  uploadAction: ReactNode; // botón «Subir un libro nuevo»
}

const pagesWord = (n: number) => `${fmtN.format(n)} ${n === 1 ? "página" : "páginas"}`;
const pagShort = (n: number) => `${fmtN.format(n)} ${n === 1 ? "pág." : "págs."}`;
const dash = (spec: string) => spec.replace(/-/g, "–");

function modeOf(v: ScopeValue): Mode {
  if (v.scope === "chapter") return "chapter";
  if (v.scope === "book") return "book";
  if (v.scope === "page") return "loose";
  return RANGE_RE.test(v.pagesSpec) || !v.pagesSpec.trim() ? "range" : "loose";
}

export function ScopeView(p: Props) {
  const grid = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<Mode>(() => modeOf(p.value));
  const [pages, setPages] = useState<PlaygroundPageInfo[]>([]);
  const [anchor, setAnchor] = useState<number | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  // tamaño de miniaturas: el guardado se lee en el navegador sin desajustar la hidratación
  const storedThumbSize = useSyncExternalStore(subscribeNothing, storedSize, () => "m" as Size);
  const [chosenSize, setSize] = useState<Size | null>(null);
  const size: Size = chosenSize ?? storedThumbSize;
  const [preview, setPreview] = useState<number | null>(null); // página abierta en el visor junto a la galería
  // lo último elegido en cada modo, para mostrar su recuento y recuperarlo al volver a él
  const [rangeSpec, setRangeSpec] = useState(() => (modeOf(p.value) === "range" ? p.value.pagesSpec : ""));
  const [looseSpec, setLooseSpec] = useState(() => (p.value.scope === "page" ? p.value.onePage
    : modeOf(p.value) === "loose" ? p.value.pagesSpec : ""));

  function pickSize(v: Size) {
    setSize(v);
    try { localStorage.setItem(SIZE_KEY, v); } catch { /* sin almacenamiento: solo para esta visita */ }
  }

  const book = p.books.find((b) => b.id === p.bookId) ?? null;
  const count = book?.page_count ?? pages.length;

  // Ajustes en el render (no en efectos), en el mismo orden que tenían los efectos:
  // 1) el alcance cambia desde fuera (capítulos detectados al elegir libro): el modo lo sigue
  const [scopeSeen, setScopeSeen] = useState(p.value.scope);
  if (scopeSeen !== p.value.scope) {
    setScopeSeen(p.value.scope);
    const scopeOf = (m: Mode): PlaygroundScope[] => (m === "range" ? ["pages"] : m === "loose" ? ["pages", "page"] : [m]);
    setMode((m) => (scopeOf(m).includes(p.value.scope) ? m : modeOf(p.value)));
  }
  // 2) el intervalo elegido fuera se copia al modo que corresponde
  const specKey = `${p.value.pagesSpec}|${p.value.scope}|${mode}`;
  const [specSeen, setSpecSeen] = useState<string | null>(null);
  if (specSeen !== specKey) {
    setSpecSeen(specKey);
    if (p.value.scope === "pages" && mode === "range") setRangeSpec(p.value.pagesSpec);
    if (p.value.scope === "pages" && mode === "loose") setLooseSpec(p.value.pagesSpec);
  }
  // 3) otro libro (y al montar): galería, filtros e intervalos recordados vuelven a empezar
  const [bookSeen, setBookSeen] = useState<number | null | undefined>(undefined);
  if (bookSeen !== p.bookId) {
    setBookSeen(p.bookId);
    setPages([]);
    setAnchor(null);
    setPreview(null);
    setFilter("all");
    setRangeSpec("");
    setLooseSpec("");
  }

  useEffect(() => {
    if (p.bookId === null) return;
    let alive = true;
    listPlaygroundPages(p.bookId).then((x) => { if (alive) setPages(x); }).catch(() => undefined);
    return () => { alive = false; };
  }, [p.bookId]);

  const range = RANGE_RE.exec(rangeSpec);
  const from = range ? range[1] : "";
  const to = range ? range[2] ?? range[1] : "";
  const chapterInfo = p.value.chapter === "" ? null : p.chapters[Number(p.value.chapter)] ?? null;

  const specOf = (m: Mode) => (m === "book" ? `1-${count}` : m === "chapter" ? chapterInfo?.pages ?? ""
    : m === "range" ? rangeSpec : looseSpec);
  const inBook = (ns: number[]) => ns.filter((n) => n >= 1 && n <= count);
  const selected = useMemo(() => new Set(inBook(parsePages(specOf(mode)))),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- specOf e inBook se recrean en cada render y solo usan estos valores
    [mode, count, rangeSpec, looseSpec, chapterInfo]);
  const countOf = (m: Mode) => inBook(parsePages(specOf(m))).length;

  const info = useMemo(() => new Map(pages.map((x) => [x.number, x])), [pages]);
  const scanned = pages.filter((x) => SCANNED.has(x.kind)).length;
  const empty = pages.filter((x) => x.blocks === 0).length;
  const lostOcr = pages.filter((x) => x.blocks === 0 && SCANNED.has(x.kind)).length; // escaneadas sin texto: falló el OCR
  const emptySelected = [...selected].filter((n) => info.get(n)?.blocks === 0).length;
  const nSel = selected.size;

  function pickMode(m: Mode) {
    if (m === mode) return;
    setMode(m);
    setAnchor(null);
    if (m === "chapter") p.onChange({ scope: "chapter", chapter: p.value.chapter || (p.chapters.length ? "0" : "") });
    else if (m === "book") p.onChange({ scope: "book" });
    else if (m === "range") {
      const sel = [...selected].sort((a, b) => a - b);
      const spec = rangeSpec || (sel.length ? `${sel[0]}-${sel[sel.length - 1]}` : `1-${Math.min(10, count || 1)}`);
      setRangeSpec(spec);
      p.onChange({ scope: "pages", pagesSpec: spec });
    } else {
      setLooseSpec(looseSpec);
      p.onChange({ scope: "pages", pagesSpec: looseSpec });
    }
  }

  function setRange(a: string, b: string) {
    const x = a.replace(/\D/g, "");
    const y = b.replace(/\D/g, "");
    const spec = x && y ? `${x}-${y}` : x || y;
    setRangeSpec(spec);
    p.onChange({ scope: "pages", pagesSpec: spec });
  }

  function clickThumb(n: number, e?: MouseEvent) {
    if (mode === "loose") {
      const cur = new Set(parsePages(looseSpec));
      if (cur.has(n)) cur.delete(n); else cur.add(n);
      const spec = formatPages([...cur]).replace(/\s+/g, "");
      setLooseSpec(spec);
      p.onChange({ scope: "pages", pagesSpec: spec });
      return;
    }
    // intervalo (también desde capítulo o libro): clic marca el inicio, el segundo clic (o mayús+clic) el final
    if (mode !== "range") setMode("range");
    const start = anchor ?? (e?.shiftKey && mode === "range" && from ? Number(from) : null);
    let spec: string;
    if (start !== null) {
      const [a, b] = start <= n ? [start, n] : [n, start];
      spec = `${a}-${b}`;
      setAnchor(null);
    } else {
      spec = `${n}-${n}`;
      setAnchor(n);
    }
    setRangeSpec(spec);
    p.onChange({ scope: "pages", pagesSpec: spec });
  }

  function pickChapter(i: string) {
    p.onChange({ scope: "chapter", chapter: i });
    const first = parsePages(p.chapters[Number(i)]?.pages)[0];
    if (first) requestAnimationFrame(() => grid.current?.querySelector(`[data-page="${first}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" }));
  }

  const all = Array.from({ length: count }, (_, i) => i + 1);
  const isEmpty = (n: number) => info.get(n)?.blocks === 0;
  const isOcr = (n: number) => SCANNED.has(info.get(n)?.kind ?? "");
  const shown = filter === "scope" ? all.filter((n) => selected.has(n)) : filter === "empty" ? all.filter(isEmpty)
    : filter === "ocr" ? all.filter(isOcr) : all;
  const FILTERS: { id: Filter; title: string }[] = [
    { id: "all", title: "Todas" }, { id: "scope", title: `En alcance (${fmtN.format(nSel)})` },
    { id: "empty", title: `Sin texto (${fmtN.format(empty)})` }, { id: "ocr", title: `OCR (${fmtN.format(scanned)})` },
  ];

  const valid = !!p.bookId && !!p.estimate && !p.estimateError && p.estimate.blocks > 0;
  const nEval = p.estimate?.pages ?? nSel;
  const continueLabel = mode === "book" ? "Evaluar el libro completo" : nEval ? `Evaluar ${pagesWord(nEval)}` : "Evaluar";
  const scopeText = mode === "book" ? "Libro completo"
    : mode === "chapter" ? (chapterInfo ? `Capítulo «${chapterInfo.title}» · págs. ${dash(chapterInfo.pages)}` : "Elige un capítulo")
      : mode === "range" ? (rangeSpec ? `Intervalo · págs. ${dash(rangeSpec)}` : "Indica el intervalo")
        : looseSpec ? `Páginas sueltas · ${dash(looseSpec).replace(/,/g, ", ")}` : "Pulsa las miniaturas para elegir páginas";
  // qué entra en el proceso: la estimación del servidor cuando llega
  const details = p.estimateError ? <span className="error-text">{p.estimateError}</span>
    : p.estimate ? (
      <>
        {fmtN.format(p.estimate.blocks)} bloques · ~{fmtN.format(p.estimate.calls_per_variant)} {p.estimate.calls_per_variant === 1 ? "llamada" : "llamadas"} por variante
        {p.estimate.seconds !== null ? ` · ~${duration(p.estimate.seconds)}` : ""}
        {p.estimate.blocks === 0 && <span className="error-text"> · sin texto que evaluar</span>}
      </>
    ) : nSel ? "Calculando…" : null;

  const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && preview === null) p.onBack?.(); };
  const sizeDpi = SIZES.find((z) => z.id === size)?.dpi ?? 56;

  // visor: recorre las páginas que se ven en la galería
  const prevOf = (n: number) => { const i = shown.indexOf(n); return i > 0 ? shown[i - 1] : null; };
  const nextOf = (n: number) => { const i = shown.indexOf(n); return i >= 0 && i < shown.length - 1 ? shown[i + 1] : null; };
  function move(dir: -1 | 1) {
    if (preview === null) return;
    const n = dir < 0 ? prevOf(preview) : nextOf(preview);
    if (n === null) return;
    setPreview(n);
    grid.current?.querySelector(`[data-page="${n}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  function galleryKey(e: KeyboardEvent) {
    if (preview === null || (e.target as HTMLElement).tagName === "INPUT") return;
    if (e.key === "ArrowLeft") { e.preventDefault(); move(-1); }
    else if (e.key === "ArrowRight") { e.preventDefault(); move(1); }
    else if (e.key === "Escape") { e.stopPropagation(); setPreview(null); }
  }
  // lo que se puede hacer con la página abierta depende de cómo se está eligiendo el alcance
  function previewAction(n: number) {
    if (mode === "loose") return <button type="button" className="btn secondary" onClick={() => clickThumb(n)}>{selected.has(n) ? "Quitar de la selección" : "Añadir a la selección"}</button>;
    return <button type="button" className="btn secondary" onClick={() => clickThumb(n)}>{anchor === null ? "Empezar un intervalo aquí" : `Terminar el intervalo aquí (desde la pág. ${anchor})`}</button>;
  }

  const option = (m: Mode, title: string, hint: string, body?: ReactNode) => {
    const n = countOf(m);
    return (
      <div className={`pg-opt${mode === m ? " on" : ""}`}>
        <label className="pg-opt-head">
          <input type="radio" name="pg-mode" checked={mode === m} onChange={() => pickMode(m)} />
          <span className="pg-opt-text"><strong>{title}</strong><small>{hint}</small></span>
          {n > 0 && <span className="pg-opt-n">{pagShort(n)}</span>}
        </label>
        {mode === m && body && <div className="pg-opt-body">{body}</div>}
      </div>
    );
  };

  return (
    <div className="pg-start" onKeyDown={onKey}>
      <div className="pg-start-top">
        <span className="pg-eyebrow">Playground · Evaluar traducción · <strong>{p.books.length} {p.books.length === 1 ? "libro" : "libros"}</strong></span>
        <div className="row">
          {p.onBack && <button type="button" className="btn secondary" onClick={p.onBack}>Volver a la mesa</button>}
          {p.uploadAction}
        </div>
      </div>

      {/* 1 · libro */}
      <div className="pg-book-line">
        <BookPicker books={p.books} book={book} chapters={p.chapters.length} onBook={p.onBook} onDelete={p.onDeleteBook} />
        {book && (
          <div className="pg-book-meta" aria-live="polite">
            <span>{fmtN.format(book.blocks)} bloques{scanned > 0 ? ` · ${scanned === pages.length ? "todo por OCR" : `${fmtN.format(scanned)} por OCR`}` : ""}</span>
            {empty > 0 && (
              <button type="button" className="pg-warn-chip" onClick={() => setFilter("empty")} title="Ver las páginas sin texto extraído: no se traducen">
                <IconWarn /> {pagesWord(empty)} sin texto · ver
              </button>
            )}
            {book.production && <span className="badge" title="Ya hay una traducción de producción con la que comparar">con traducción para comparar</span>}
          </div>
        )}
      </div>
      {p.upload}

      {lostOcr > 0 && (
        <div className="alert" role="note">
          <IconWarn />
          <span>
            {fmtN.format(lostOcr)} {lostOcr === 1 ? "página escaneada no tiene" : "páginas escaneadas no tienen"} texto
            extraído: comprueba que el OCR (Tesseract) está instalado y vuelve a preparar el libro.
          </span>
        </div>
      )}

      {!book ? (
        <div className="card"><span className="muted">Elige un libro en el desplegable de arriba o sube uno nuevo.</span></div>
      ) : (
        <div className="pg-start-body">
          {/* 2 · alcance */}
          <section className="card pg-scope-card" aria-labelledby="pg-scope-title">
            <div>
              <h3 id="pg-scope-title">2 · Alcance</h3>
              <span className="muted">¿Qué parte del libro vas a evaluar?</span>
            </div>
            <div className="pg-opts" role="radiogroup" aria-labelledby="pg-scope-title">
              {p.chapters.length > 0 && option("chapter", "Un capítulo",
                `${p.chapters[0]?.source === "detected" ? "Detectados por los títulos" : "Del índice del PDF"} · ${fmtN.format(p.chapters.length)} capítulos`,
                <>
                  <label className="control">Capítulo
                    <select value={p.value.chapter} onChange={(e) => pickChapter(e.target.value)}>
                      {p.value.chapter === "" && <option value="">Elige un capítulo</option>}
                      {p.chapters.map((c, i) => (
                        <option key={c.title + c.pages} value={String(i)}>
                          {"  ".repeat(Math.min(Math.max(c.level, 1), 3) - 1)}{c.title} · {dash(c.pages)}
                        </option>
                      ))}
                    </select>
                  </label>
                  {chapterInfo && <span className="muted">Equivale a las págs. {dash(chapterInfo.pages)} ({pagShort(countOf("chapter"))}).</span>}
                </>)}
              {option("range", "Un intervalo", "De una página a otra", (
                <>
                  <div className="pg-range">
                    <label className="control">Desde
                      <input type="text" inputMode="numeric" value={from} onChange={(e) => setRange(e.target.value, to)} />
                    </label>
                    <span aria-hidden>–</span>
                    <label className="control">Hasta
                      <input type="text" inputMode="numeric" value={to} onChange={(e) => setRange(from, e.target.value)} />
                    </label>
                  </div>
                  <span className="muted">
                    {anchor !== null ? `Inicio en la pág. ${anchor}: pulsa la página final.` : "O haz clic en la primera y luego en la última miniatura."}
                  </span>
                </>
              ))}
              {option("loose", "Páginas sueltas", "Las eliges en las miniaturas", (
                <>
                  <label className="control">Páginas
                    <input type="text" placeholder="3, 7, 12-14" value={looseSpec.replace(/,/g, ", ")} onChange={(e) => {
                      const spec = e.target.value.replace(/[^\d,\-\s]/g, "").replace(/\s+/g, "");
                      setLooseSpec(spec);
                      p.onChange({ scope: "pages", pagesSpec: spec });
                    }} />
                  </label>
                  <span className="muted">Cada clic en una miniatura la añade o la quita.</span>
                </>
              ))}
              {option("book", "Libro completo", "El alcance más costoso", (
                <span className="muted">Las {fmtN.format(count)} páginas. Se pedirá confirmación antes de ejecutar.</span>
              ))}
              {p.chapters.length === 0 && (
                <span className="muted pg-opt-note">Sin capítulos detectados{scanned > 0 ? " (libro escaneado)" : ""}: usa un intervalo.</span>
              )}
            </div>
          </section>

          {/* 3 · revisar páginas */}
          <section className="card pg-review" aria-labelledby="pg-review-title">
            <div className="pg-review-head">
              <h3 id="pg-review-title">3 · Revisar páginas</h3>
              <div className="row">
                <div className="pg-size" role="radiogroup" aria-label="Qué páginas mostrar">
                  {FILTERS.map((f) => (
                    <button key={f.id} type="button" role="radio" aria-checked={filter === f.id} onClick={() => setFilter(f.id)}>{f.title}</button>
                  ))}
                </div>
                <div className="pg-size" role="radiogroup" aria-label="Tamaño de las miniaturas">
                  {SIZES.map((z) => (
                    <button key={z.id} type="button" role="radio" aria-checked={size === z.id} aria-label={z.label} title={z.label}
                      onClick={() => pickSize(z.id)}>{z.title}</button>
                  ))}
                </div>
              </div>
            </div>

            <div className={preview !== null ? "pg-gallery open" : "pg-gallery"} onKeyDown={galleryKey}>
              <div ref={grid} className={`pg-thumbs size-${size}${nSel ? " has-sel" : ""}`} aria-label="Páginas del libro">
                {shown.length === 0 && <span className="muted">Ninguna página en este filtro.</span>}
                {p.bookId !== null && shown.map((n) => {
                  const x = info.get(n);
                  const cls = ["pg-thumb", selected.has(n) ? "sel" : "", anchor === n ? "anchor" : "", x?.blocks === 0 ? "empty" : "",
                    preview === n ? "viewing" : ""].join(" ");
                  return (
                    <div key={n} className="pg-thumb-cell">
                      <button type="button" data-page={n} className={cls} aria-pressed={selected.has(n)}
                        title={`Página ${n}${x ? ` · ${x.blocks} bloques${SCANNED.has(x.kind) ? " · OCR" : ""}` : ""}${selected.has(n) ? " · en el alcance" : ""} · doble clic para ampliar`}
                        onClick={(e) => clickThumb(n, e)} onDoubleClick={() => setPreview(n)}>
                        {/* eslint-disable-next-line @next/next/no-img-element -- PNG que genera la API al vuelo */}
                        <img src={jobPageImageUrl(p.bookId!, n, "original", sizeDpi)} alt="" loading="lazy" decoding="async" />
                        <span className="pg-thumb-n">{n}</span>
                        {selected.has(n) && <span className="pg-thumb-check" aria-hidden><IconCheck /></span>}
                        {x && (SCANNED.has(x.kind) || x.blocks === 0) && (
                          <span className="pg-thumb-tags">
                            {x.blocks === 0 && <span className="pg-thumb-tag warn"><IconWarn /> sin texto</span>}
                            {SCANNED.has(x.kind) && <span className="pg-thumb-tag">OCR</span>}
                          </span>
                        )}
                      </button>
                      <button type="button" className="pg-thumb-zoom" aria-label={`Ampliar la página ${n}`} title="Ampliar"
                        onClick={() => setPreview(n)}><IconZoom /></button>
                    </div>
                  );
                })}
              </div>

              {preview !== null && p.bookId !== null && (
                <aside className="pg-preview" aria-label={`Página ${preview}`}>
                  <div className="pg-preview-head">
                    <strong>Página {preview} <span className="muted">de {fmtN.format(count)}</span></strong>
                    <div className="row">
                      <button type="button" className="btn secondary pg-icon" aria-label="Página anterior" disabled={prevOf(preview) === null}
                        onClick={() => move(-1)}><IconArrowLeft /></button>
                      <button type="button" className="btn secondary pg-icon" aria-label="Página siguiente" disabled={nextOf(preview) === null}
                        onClick={() => move(1)}><IconArrowRight /></button>
                      <button type="button" className="btn ghost pg-icon" aria-label="Cerrar el visor" onClick={() => setPreview(null)}><IconX /></button>
                    </div>
                  </div>
                  {/* eslint-disable-next-line @next/next/no-img-element -- PNG que genera la API al vuelo */}
                  <img className="pg-preview-img" src={jobPageImageUrl(p.bookId, preview, "original")} alt={`Página ${preview} del libro`} />
                  <dl className="pg-preview-meta">
                    <dt>Tipo</dt><dd>{KIND[info.get(preview)?.kind ?? ""] ?? info.get(preview)?.kind}</dd>
                    <dt>Bloques de texto</dt>
                    <dd>{info.get(preview) ? (info.get(preview)!.blocks === 0 ? "ninguno: no se traduce" : fmtN.format(info.get(preview)!.blocks)) : "…"}</dd>
                    <dt>Alcance</dt><dd>{selected.has(preview) ? "entra en la evaluación" : "fuera de la evaluación"}</dd>
                  </dl>
                  {previewAction(preview)}
                </aside>
              )}
            </div>
          </section>
        </div>
      )}

      {/* barra fija: resumen de lo que se procesa, método de la primera evaluación y botón */}
      {book && (
        <div className="pg-run-bar" aria-live="polite">
          <div className="pg-run-sum">
            <strong className="pg-run-n">{nSel ? pagesWord(nSel) : "Ninguna página"}</strong>
            <span className="pg-ellipsis" title={scopeText}>{scopeText}</span>
            {emptySelected > 0 && (
              <span className="pg-run-warn"><IconWarn /> {emptySelected} {emptySelected === 1 ? "página sin texto" : "páginas sin texto"} en el alcance</span>
            )}
          </div>
          <div className="pg-run-act">
            {p.variantCount > 1 ? (
              <span className="muted">{p.variantCount} variantes · se configuran en la mesa</span>
            ) : (
              <label className="pg-method">
                <span>Método:</span>
                <select value={p.method} onChange={(e) => p.onMethod(e.target.value)}>
                  {Object.keys(DEEPSEEK_MODELS).map((m) => <option key={m} value={m}>{m}</option>)}
                  <option value="fake">prueba sin API</option>
                </select>
              </label>
            )}
            <span className="muted pg-run-est">{details}</span>
            <button type="button" className="btn pg-run-go" disabled={!valid || p.busy} onClick={p.onContinue}>{continueLabel}</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* Desplegable del libro: muestra el elegido con su resumen; al abrirse, buscador, lista y papelera por libro. */
function BookPicker(p: {
  books: PlaygroundBook[]; book: PlaygroundBook | null; chapters: number;
  onBook: (id: number) => void; onDelete: (b: PlaygroundBook) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [confirmDel, setConfirmDel] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [delError, setDelError] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: globalThis.MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  // al cerrar el selector se limpian búsqueda y confirmación (ajuste en el render, no en un efecto)
  const [openSeen, setOpenSeen] = useState(open);
  if (openSeen !== open) {
    setOpenSeen(open);
    if (!open) { setQ(""); setConfirmDel(null); setDelError(null); }
  }

  const needle = q.trim().toLocaleLowerCase("es");
  const visible = needle ? p.books.filter((b) => `${b.name} ${b.original_name}`.toLocaleLowerCase("es").includes(needle)) : p.books;

  return (
    <div className="pg-picker" ref={box} onKeyDown={(e) => { if (e.key === "Escape" && open && !deleting) { e.stopPropagation(); setOpen(false); } }}>
      <button type="button" className="pg-picker-btn" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="pg-picker-text">
          <strong className="pg-ellipsis">{p.book ? p.book.name : "Elige un libro"}</strong>
          <small>{p.book
            ? `${pagShort(p.book.page_count)} · ${p.chapters ? `${fmtN.format(p.chapters)} capítulos` : "sin capítulos"}${p.book.name !== p.book.original_name ? ` · ${p.book.original_name}` : ""}`
            : `${p.books.length} ${p.books.length === 1 ? "libro preparado" : "libros preparados"}`}</small>
        </span>
        <IconChevron />
      </button>
      {open && (
        <div className="pg-picker-pop">
          <input type="search" placeholder="Buscar libro" aria-label="Buscar libro" autoFocus value={q} onChange={(e) => setQ(e.target.value)} />
          <ul className="pg-books" role="listbox" aria-label="Libro que se evalúa">
            {p.books.length === 0 && <li className="muted">Aún no hay libros preparados: sube uno.</li>}
            {visible.length === 0 && p.books.length > 0 && <li className="muted">Ningún libro coincide.</li>}
            {visible.map((b) => (
              <li key={b.id} className="pg-book-row">
                <button type="button" role="option" aria-selected={b.id === p.book?.id}
                  title={`${b.name} · ${fmtN.format(b.page_count)} págs.`} className="pg-book"
                  onClick={() => { p.onBook(b.id); setOpen(false); }}>
                  {b.name} <small className="muted">· {pagShort(b.page_count)}</small>
                </button>
                <button type="button" className="btn ghost pg-icon pg-book-del" aria-label={`Eliminar ${b.name}`}
                  title="Eliminar libro" aria-expanded={confirmDel === b.id}
                  onClick={() => { setDelError(null); setConfirmDel(confirmDel === b.id ? null : b.id); }}>
                  <IconTrash />
                </button>
                {confirmDel === b.id && (
                  <div className="alert error pg-book-confirm" role="alertdialog" aria-labelledby={`pg-del-${b.id}`}>
                    <IconWarn />
                    <div>
                      <strong id={`pg-del-${b.id}`}>¿Eliminar «{b.name}»?</strong>
                      <p>Se borra todo su análisis: páginas y bloques, las evaluaciones del playground con su historial
                        y PDFs, y el PDF subido si ningún otro libro lo usa. No se puede deshacer.</p>
                      {delError && <p role="alert">{delError}</p>}
                      <div className="pg-book-confirm-actions">
                        <button type="button" className="btn" autoFocus disabled={deleting} onClick={async () => {
                          setDeleting(true);
                          setDelError(null);
                          try {
                            await p.onDelete(b);
                            setConfirmDel(null);
                          } catch (e) {
                            setDelError((e as Error).message);
                          } finally {
                            setDeleting(false);
                          }
                        }}>
                          <IconTrash /> {deleting ? "Eliminando…" : "Eliminar"}
                        </button>
                        <button type="button" className="btn secondary" disabled={deleting} onClick={() => setConfirmDel(null)}>
                          Cancelar
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
