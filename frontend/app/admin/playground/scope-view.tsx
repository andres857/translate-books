"use client";

/* Vista inicial del Playground (una página, no un modal): elegir el libro y la parte que se va a evaluar (capítulo, intervalo
   de páginas, una página, una lista o el libro completo) sobre una cuadrícula de miniaturas. Hasta que el alcance es
   válido no se entra en la mesa; desde la mesa, «Cambiar» vuelve aquí. Funciona también con libros escaneados sin capítulos: se define un intervalo «10–20». */
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import {
  jobPageImageUrl, listPlaygroundPages, type Chapter, type Estimate, type PlaygroundBook, type PlaygroundPageInfo,
  type PlaygroundScope,
} from "@/lib/api";
import { IconArrowLeft, IconArrowRight, IconWarn, IconX, IconZoom } from "../../components/art";
import { duration, fmtN, parsePages } from "./shared";

type Mode = "chapter" | "range" | "page" | "book";
// modos del panel de alcance; el capítulo no tiene botón: se elige en la lista de capítulos del mismo panel
const MODES: { id: Mode; title: string }[] = [
  { id: "range", title: "Intervalo" }, { id: "page", title: "Una página" }, { id: "book", title: "Libro completo" },
];
const RANGE_RE = /^\s*(\d+)\s*-\s*(\d+)\s*$/;
const SCANNED = new Set(["scanned", "mixed"]); // texto por OCR; «image_only» son ilustraciones o páginas sin texto
const KIND: Record<string, string> = {
  digital: "Digital: texto del PDF", scanned: "Escaneada: texto por OCR", mixed: "Mixta: texto del PDF y OCR",
  image_only: "Solo imagen", blank: "En blanco", "": "Sin analizar",
};
// tamaño de la galería: ancho mínimo de la miniatura (clase) y resolución con que se pide la imagen
type Size = "s" | "m" | "l";
const SIZES: { id: Size; title: string; dpi: number }[] = [
  { id: "s", title: "Pequeñas", dpi: 36 }, { id: "m", title: "Medianas", dpi: 56 }, { id: "l", title: "Grandes", dpi: 84 },
];
const SIZE_KEY = "pg-thumb-size";
function storedSize(): Size {
  try {
    const v = localStorage.getItem(SIZE_KEY);
    return v === "m" || v === "l" ? v : "s";
  } catch { return "s"; }
}

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
  chapters: Chapter[];
  value: ScopeValue;
  onChange: (v: Partial<ScopeValue>) => void;
  estimate: Estimate | null;
  estimateError: string | null;
  onContinue: () => void; // entra en la mesa con el alcance elegido
  onBack?: () => void; // ya hay una mesa abierta: volver a ella sin cambiar nada
  upload: ReactNode; // progreso de preparación y avisos, en la columna de libros
  uploadAction: ReactNode; // botón «Subir un libro nuevo», arriba a la derecha junto al título
}

// «12-13» → «12–13 · 2 págs.»; una sola página → «12»
function pageRange(spec: string): string {
  const n = parsePages(spec).length;
  const txt = spec.replace(/-/g, "–").replace(/,\s*/g, ", ");
  return n > 1 ? `${txt} · ${n} págs.` : txt;
}

function modeOf(v: ScopeValue): Mode {
  if (v.scope === "chapter") return "chapter";
  if (v.scope === "book") return "book";
  if (v.scope === "page") return "page";
  return "range"; // una lista suelta de una evaluación antigua se muestra como intervalo (de la primera a la última)
}

export function ScopeView(p: Props) {
  const grid = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<Mode>(() => modeOf(p.value));
  const [pages, setPages] = useState<PlaygroundPageInfo[]>([]);
  const [anchor, setAnchor] = useState<number | null>(null);
  const [bookQuery, setBookQuery] = useState("");
  const [onlySelected, setOnlySelected] = useState(false); // galería: solo las páginas que entran en el alcance
  const [size, setSize] = useState<Size>("s");
  const [preview, setPreview] = useState<number | null>(null); // página abierta en el visor junto a la galería
  const card = useRef<HTMLElement>(null);
  const head = useRef<HTMLDivElement>(null);

  useEffect(() => { setSize(storedSize()); }, []);
  function pickSize(v: Size) {
    setSize(v);
    try { localStorage.setItem(SIZE_KEY, v); } catch { /* sin almacenamiento: solo para esta visita */ }
  }

  // el visor es fijo bajo la cabecera de la tarjeta, que también es fija: su alto varía con el nombre del libro
  useEffect(() => {
    const h = head.current;
    const c = card.current;
    if (!h || !c) return;
    const ro = new ResizeObserver(() => c.style.setProperty("--layout-scope-head", `${h.offsetHeight}px`));
    ro.observe(h);
    return () => ro.disconnect();
  }, []);
  const book = p.books.find((b) => b.id === p.bookId) ?? null;
  const q = bookQuery.trim().toLocaleLowerCase("es");
  const visibleBooks = q ? p.books.filter((b) => `${b.name} ${b.original_name}`.toLocaleLowerCase("es").includes(q)) : p.books;
  const count = book?.page_count ?? pages.length;

  // el alcance cambia desde fuera (capítulos detectados al elegir libro): la pestaña lo sigue
  useEffect(() => {
    const scopeOf = (m: Mode): PlaygroundScope => (m === "range" ? "pages" : m === "page" ? "page" : m);
    setMode((m) => (scopeOf(m) === p.value.scope ? m : modeOf(p.value)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.value.scope]);

  useEffect(() => {
    setPages([]);
    setAnchor(null);
    setPreview(null);
    if (p.bookId === null) return;
    let alive = true;
    listPlaygroundPages(p.bookId).then((x) => { if (alive) setPages(x); }).catch(() => undefined);
    return () => { alive = false; };
  }, [p.bookId]);

  const range = RANGE_RE.exec(p.value.pagesSpec);
  const specPages = parsePages(p.value.pagesSpec);
  const from = range ? range[1] : (specPages.length ? String(Math.min(...specPages)) : "");
  const to = range ? range[2] : (specPages.length > 1 ? String(Math.max(...specPages)) : "");
  const chapterInfo = p.value.chapter === "" ? null : p.chapters[Number(p.value.chapter)] ?? null;

  const selected = useMemo(() => {
    const spec = mode === "book" ? `1-${count}` : mode === "page" ? p.value.onePage
      : mode === "chapter" ? chapterInfo?.pages ?? "" : p.value.pagesSpec;
    return new Set(parsePages(spec));
  }, [mode, count, p.value.onePage, p.value.pagesSpec, chapterInfo]);

  const info = useMemo(() => new Map(pages.map((x) => [x.number, x])), [pages]);
  const scanned = pages.filter((x) => SCANNED.has(x.kind)).length;
  const empty = pages.filter((x) => x.blocks === 0).length;
  const lostOcr = pages.filter((x) => x.blocks === 0 && SCANNED.has(x.kind)).length; // escaneadas sin texto: falló el OCR
  const emptySelected = [...selected].filter((n) => info.get(n)?.blocks === 0).length;

  function pickMode(m: Mode) {
    setMode(m);
    setAnchor(null);
    if (m === "chapter") p.onChange({ scope: "chapter" });
    else if (m === "book") p.onChange({ scope: "book" });
    else if (m === "page") p.onChange({ scope: "page", onePage: p.value.onePage || "1" });
    else {
      const sel = [...selected].sort((a, b) => a - b);
      const spec = sel.length ? `${sel[0]}-${sel[sel.length - 1]}` : `1-${Math.min(10, count || 1)}`;
      p.onChange({ scope: "pages", pagesSpec: spec });
    }
  }

  function setRange(a: string, b: string) {
    const clean = (x: string) => x.replace(/\D/g, "");
    const x = clean(a);
    const y = clean(b);
    p.onChange({ scope: "pages", pagesSpec: x && y ? `${x}-${y}` : x || y });
  }

  function clickThumb(n: number, e?: MouseEvent) {
    if (mode === "page") {
      p.onChange({ scope: "page", onePage: String(n) });
      return;
    }
    // intervalo: clic marca el inicio, mayús+clic (o el segundo clic) el final
    if (mode !== "range") setMode("range");
    const start = anchor ?? (e?.shiftKey && mode === "range" && from ? Number(from) : null);
    if (start !== null) {
      const [a, b] = start <= n ? [start, n] : [n, start];
      p.onChange({ scope: "pages", pagesSpec: `${a}-${b}` });
      setAnchor(null);
    } else {
      p.onChange({ scope: "pages", pagesSpec: `${n}-${n}` });
      setAnchor(n);
    }
  }

  function pickChapter(i: number) {
    p.onChange({ scope: "chapter", chapter: String(i) });
    const first = parsePages(p.chapters[i]?.pages)[0];
    if (first) grid.current?.querySelector(`[data-page="${first}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  const valid = !!p.bookId && !!p.estimate && !p.estimateError && (p.estimate.blocks > 0);
  const nSel = [...selected].filter((n) => n >= 1 && n <= count).length;
  const shown = onlySelected && nSel ? [...selected].filter((n) => n >= 1 && n <= count).sort((a, b) => a - b)
    : Array.from({ length: count }, (_, i) => i + 1);
  const pagesWord = (n: number) => `${fmtN.format(n)} ${n === 1 ? "página" : "páginas"}`;
  const continueLabel = valid && p.estimate ? `Evaluar ${p.estimate.scope === "book" ? "el libro completo" : `${p.estimate.pages === 1 ? "esta página" : `estas ${fmtN.format(p.estimate.pages)} páginas`}`}` : "Evaluar";
  // qué entra en el proceso: recuento inmediato de la selección y, cuando llega, la estimación del servidor
  const details = p.estimateError ? <span className="error-text">{p.estimateError}</span>
    : p.estimate ? (
      <>
        {" · "}{fmtN.format(p.estimate.blocks)} bloques · ~{fmtN.format(p.estimate.calls_per_variant)} llamadas por variante
        {p.estimate.seconds !== null ? ` · ~${duration(p.estimate.seconds)}` : ""}
        {p.estimate.blocks === 0 && <span className="error-text"> · sin texto que evaluar en estas páginas</span>}
        {emptySelected > 0 && p.estimate.blocks > 0 ? ` · ${emptySelected} sin texto` : ""}
      </>
    ) : null;

  const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") p.onBack?.(); };
  const sizeDpi = SIZES.find((z) => z.id === size)?.dpi ?? 36;

  // visor: recorre las páginas que se ven en la galería (todas, o solo las del alcance)
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
    const inScope = selected.has(n);
    if (mode === "page") return inScope ? <span className="muted">Es la página que se evalúa.</span>
      : <button type="button" className="btn" onClick={() => clickThumb(n)}>Evaluar esta página</button>;
    if (mode === "range") return <button type="button" className="btn secondary" onClick={() => clickThumb(n)}>{anchor === null ? "Empezar el intervalo aquí" : `Terminar el intervalo aquí (desde la pág. ${anchor})`}</button>;
    return <span className="muted">Para elegir páginas sueltas, cambia a «Intervalo» o «Una página».</span>;
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Playground</h1>
          <p>¿Con qué parte del libro trabajamos? Elige el libro y define el alcance: un capítulo, un intervalo de páginas, una página suelta o una lista.</p>
        </div>
        <div className="row">
          {p.onBack && <button type="button" className="btn secondary" onClick={p.onBack}>Volver a la mesa</button>}
          {p.uploadAction}
        </div>
      </div>

      <div className="pg-start" onKeyDown={onKey}>
        <aside className="pg-start-side" aria-label="Libros">
          <div className="hist-side-head">
            <strong>Libros</strong>
            <span className="muted">{p.books.length}</span>
          </div>
          {p.books.length > 6 && (
            <input type="search" className="pg-book-search" placeholder="Buscar libro" aria-label="Buscar libro"
              value={bookQuery} onChange={(e) => setBookQuery(e.target.value)} />
          )}
          <ul className="pg-books" role="listbox" aria-label="Libro que se evalúa">
            {p.books.length === 0 && <li className="muted">Aún no hay libros preparados: sube uno.</li>}
            {visibleBooks.length === 0 && p.books.length > 0 && <li className="muted">Ningún libro coincide.</li>}
            {visibleBooks.map((b) => (
              <li key={b.id}>
                <button type="button" role="option" aria-selected={b.id === p.bookId}
                  title={`${b.name} · ${fmtN.format(b.page_count)} págs.`} className="pg-book" onClick={() => p.onBook(b.id)}>
                  {b.name}
                </button>
              </li>
            ))}
          </ul>
          {p.upload}

          {/* índice del libro activo: elegir un capítulo lo pone como alcance, desde cualquier pestaña */}
          {book && (
            <div className="pg-toc">
              <div className="hist-side-head">
                <strong>Capítulos</strong>
                <span className="muted">{p.chapters.length ? `${fmtN.format(p.chapters.length)} · págs. del PDF` : ""}</span>
              </div>
              {p.chapters.length ? (
                <ul className="pg-chapters" role="listbox" aria-label="Capítulos">
                  {p.chapters.map((c, i) => (
                    <li key={c.title + c.pages}>
                      <button type="button" role="option" aria-selected={mode === "chapter" && p.value.chapter === String(i)}
                        title={`${c.title} · págs. ${pageRange(c.pages)}`}
                        className={`lvl-${Math.min(Math.max(c.level, 1), 3)}`} onClick={() => pickChapter(i)}>
                        <span className="pg-chapter-title">{c.title}</span>
                        <small>{parsePages(c.pages).length > 1 ? pageRange(c.pages) : `pág. ${c.pages}`}</small>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="muted pg-toc-empty">Sin capítulos detectados{scanned > 0 ? " (libro escaneado)" : ""}: usa un intervalo de páginas.</span>
              )}
            </div>
          )}
        </aside>

        <section ref={card} className="card pg-start-main" aria-labelledby="pg-scope-title">
          {/* cabecera fija al desplazar: el libro activo y «Evaluar» siguen a la vista con cientos de miniaturas */}
          <div ref={head} className="pg-scope-head">
            <div className="pg-book-head">
              <h2 id="pg-scope-title" className="pg-ellipsis" title={book?.name}>{book ? book.name : "Elige un libro"}</h2>
              {book ? (
                <div className="pg-book-meta" aria-live="polite">
                  <span>{pagesWord(book.page_count)}</span>
                  <span>{fmtN.format(book.blocks)} bloques de texto</span>
                  <span>{p.chapters.length
                    ? `${fmtN.format(p.chapters.length)} capítulos (${p.chapters[0]?.source === "detected" ? "detectados por los títulos" : "del índice del PDF"})`
                    : "sin capítulos"}</span>
                  {scanned > 0 && <span>{scanned === pages.length ? "escaneado: todo por OCR" : `${fmtN.format(scanned)} por OCR`}</span>}
                  {empty > 0 && <span className="badge review" title="Páginas sin texto extraído: no se traducen"><IconWarn /> {fmtN.format(empty)} sin texto</span>}
                  {book.production && <span className="badge" title="Ya hay una traducción de producción con la que comparar">con traducción para comparar</span>}
                </div>
              ) : (
                <span className="muted">Elige un libro en la columna de la izquierda o sube uno nuevo.</span>
              )}
            </div>
            <button type="button" className="btn" disabled={!valid} onClick={p.onContinue}>{continueLabel}</button>
          </div>

          {lostOcr > 0 && (
            <div className="alert" role="note">
              <IconWarn />
              <span>
                {fmtN.format(lostOcr)} {lostOcr === 1 ? "página escaneada no tiene" : "páginas escaneadas no tienen"} texto
                extraído (en gris): comprueba que el OCR (Tesseract) está instalado y vuelve a preparar el libro.
              </span>
            </div>
          )}

          <div className="pg-scope-bar">
          <div className="tabs pg-modes" role="radiogroup" aria-label="Cómo elegir las páginas">
            {MODES.map((m) => (
              <button key={m.id} type="button" role="radio" aria-checked={mode === m.id} onClick={() => pickMode(m.id)}>{m.title}</button>
            ))}
          </div>

          <div className="pg-scope-mode">
            {mode === "range" && (<>
              <div className="pg-scope-fields">
                <label className="control">Desde
                  <input className="pg-num" type="text" inputMode="numeric" value={from} onChange={(e) => setRange(e.target.value, to)} />
                </label>
                <label className="control">Hasta
                  <input className="pg-num" type="text" inputMode="numeric" value={to} onChange={(e) => setRange(from, e.target.value)} />
                </label>
              </div>
              <span className="muted">
                {anchor !== null ? `Inicio en la pág. ${anchor}: pulsa la página final.` : "O pulsa la primera y la última página en las miniaturas."}
              </span>
            </>)}
            {mode === "page" && (<>
              <div className="pg-scope-fields">
                <label className="control">Página
                  <input className="pg-num" type="text" inputMode="numeric" value={p.value.onePage}
                    onChange={(e) => p.onChange({ scope: "page", onePage: e.target.value.replace(/\D/g, "") })} />
                </label>
              </div>
              <span className="muted">O pulsa una miniatura.</span>
            </>)}
            {mode === "book" && <span className="muted">Las {fmtN.format(count)} páginas. Se pedirá confirmación antes de ejecutar.</span>}
            {mode === "chapter" && (
              <span className="muted">
                {chapterInfo
                  ? <>Capítulo: <strong>{chapterInfo.title}</strong> · págs. {pageRange(chapterInfo.pages)}</>
                  : "Elige un capítulo en la lista de la columna izquierda."}
              </span>
            )}
          </div>
          </div>

          {p.bookId !== null && (
            <div className="pg-gallery-bar">
              <span className="muted pg-estimate" aria-live="polite">
                {nSel ? <><strong>{fmtN.format(nSel)} de {pagesWord(count)}</strong> en el alcance</> : <strong>Ninguna página elegida</strong>}
                {details}
              </span>
              <div className="row">
                <label className="check">
                  <input type="checkbox" checked={onlySelected} disabled={!nSel} onChange={(e) => setOnlySelected(e.target.checked)} />
                  <span>Solo las del alcance</span>
                </label>
                <div className="pg-size" role="radiogroup" aria-label="Tamaño de las miniaturas">
                  {SIZES.map((z) => (
                    <button key={z.id} type="button" role="radio" aria-checked={size === z.id} onClick={() => pickSize(z.id)}>{z.title}</button>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className={preview !== null ? "pg-gallery open" : "pg-gallery"} onKeyDown={galleryKey}>
            <div ref={grid} className={`pg-thumbs size-${size}${nSel ? " has-sel" : ""}`} aria-label="Páginas del libro">
              {p.bookId !== null && shown.map((n) => {
                const x = info.get(n);
                const cls = ["pg-thumb", selected.has(n) ? "sel" : "", anchor === n ? "anchor" : "", x?.blocks === 0 ? "empty" : "",
                  preview === n ? "viewing" : ""].join(" ");
                return (
                  <div key={n} className="pg-thumb-cell">
                    <button type="button" data-page={n} className={cls} aria-pressed={selected.has(n)}
                      title={`Página ${n}${x ? ` · ${x.blocks} bloques${SCANNED.has(x.kind) ? " · OCR" : ""}` : ""}${selected.has(n) ? " · en el alcance" : ""} · doble clic para ampliar`}
                      onClick={(e) => clickThumb(n, e)} onDoubleClick={() => setPreview(n)}>
                      <img src={jobPageImageUrl(p.bookId!, n, "original", sizeDpi)} alt="" loading="lazy" decoding="async" />
                      <span className="pg-thumb-n">{n}</span>
                      {x && (SCANNED.has(x.kind) || x.blocks === 0) && (
                        <span className="pg-thumb-tags">
                          {x.blocks === 0 && <span className="pg-thumb-tag warn">sin texto</span>}
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
    </>
  );
}
