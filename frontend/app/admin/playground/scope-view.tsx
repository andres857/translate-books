"use client";

/* Vista inicial del Playground (una página, no un modal): elegir el libro y la parte que se va a evaluar (capítulo, intervalo
   de páginas, una página, una lista o el libro completo) sobre una cuadrícula de miniaturas. Hasta que el alcance es
   válido no se entra en la mesa; desde la mesa, «Cambiar» vuelve aquí. Funciona también con libros escaneados sin capítulos: se define un intervalo «10–20». */
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import {
  jobPageImageUrl, listPlaygroundPages, type Chapter, type Estimate, type PlaygroundBook, type PlaygroundPageInfo,
  type PlaygroundScope,
} from "@/lib/api";
import { IconWarn } from "../../components/art";
import { duration, fmtN, formatPages, parsePages } from "./shared";

type Mode = "chapter" | "range" | "page" | "list" | "book";
const MODES: { id: Mode; title: string }[] = [
  { id: "chapter", title: "Capítulo" }, { id: "range", title: "Intervalo" }, { id: "page", title: "Una página" },
  { id: "list", title: "Lista" }, { id: "book", title: "Libro completo" },
];
const RANGE_RE = /^\s*(\d+)\s*-\s*(\d+)\s*$/;
const SCANNED = new Set(["scanned", "mixed"]); // texto por OCR; «image_only» son ilustraciones o páginas sin texto

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

function modeOf(v: ScopeValue): Mode {
  if (v.scope === "chapter") return "chapter";
  if (v.scope === "book") return "book";
  if (v.scope === "page") return "page";
  return v.pagesSpec.trim() === "" || RANGE_RE.test(v.pagesSpec) ? "range" : "list";
}

export function ScopeView(p: Props) {
  const grid = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<Mode>(() => modeOf(p.value));
  const [pages, setPages] = useState<PlaygroundPageInfo[]>([]);
  const [anchor, setAnchor] = useState<number | null>(null);
  const [bookQuery, setBookQuery] = useState("");
  const book = p.books.find((b) => b.id === p.bookId) ?? null;
  const q = bookQuery.trim().toLocaleLowerCase("es");
  const visibleBooks = q ? p.books.filter((b) => `${b.name} ${b.original_name}`.toLocaleLowerCase("es").includes(q)) : p.books;
  const count = book?.page_count ?? pages.length;

  // el alcance cambia desde fuera (capítulos detectados al elegir libro): la pestaña lo sigue
  useEffect(() => {
    const scopeOf = (m: Mode): PlaygroundScope => (m === "range" || m === "list" ? "pages" : m === "page" ? "page" : m);
    setMode((m) => (scopeOf(m) === p.value.scope ? m : modeOf(p.value)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.value.scope]);

  useEffect(() => {
    setPages([]);
    setAnchor(null);
    if (p.bookId === null) return;
    let alive = true;
    listPlaygroundPages(p.bookId).then((x) => { if (alive) setPages(x); }).catch(() => undefined);
    return () => { alive = false; };
  }, [p.bookId]);

  const range = RANGE_RE.exec(p.value.pagesSpec);
  const from = range ? range[1] : (parsePages(p.value.pagesSpec)[0]?.toString() ?? "");
  const to = range ? range[2] : "";
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
    else if (m === "range") {
      const sel = [...selected].sort((a, b) => a - b);
      const spec = sel.length ? `${sel[0]}-${sel[sel.length - 1]}` : `1-${Math.min(10, count || 1)}`;
      p.onChange({ scope: "pages", pagesSpec: spec });
    } else p.onChange({ scope: "pages", pagesSpec: formatPages([...selected]) });
  }

  function setRange(a: string, b: string) {
    const clean = (x: string) => x.replace(/\D/g, "");
    const x = clean(a);
    const y = clean(b);
    p.onChange({ scope: "pages", pagesSpec: x && y ? `${x}-${y}` : x || y });
  }

  function clickThumb(n: number, e: MouseEvent) {
    if (mode === "page") {
      p.onChange({ scope: "page", onePage: String(n) });
      return;
    }
    if (mode === "list") {
      const next = new Set(selected);
      if (next.has(n)) next.delete(n);
      else next.add(n);
      p.onChange({ scope: "pages", pagesSpec: formatPages([...next]) });
      return;
    }
    // intervalo: clic marca el inicio, mayús+clic (o el segundo clic) el final
    if (mode !== "range") setMode("range");
    const start = anchor ?? (e.shiftKey && mode === "range" && from ? Number(from) : null);
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
  const summary = p.estimateError ? <span className="error-text">{p.estimateError}</span>
    : p.estimate ? (
      <>
        <strong>{p.estimate.pages} {p.estimate.pages === 1 ? "página" : "páginas"}</strong>
        {p.estimate.scope !== "book" && p.estimate.page_spec ? ` (${p.estimate.page_spec.replace(/,/g, ", ")})` : ""}
        {" · "}{fmtN.format(p.estimate.blocks)} bloques · ~{fmtN.format(p.estimate.calls_per_variant)} llamadas por variante
        {p.estimate.seconds !== null ? ` · ~${duration(p.estimate.seconds)}` : ""}
        {p.estimate.blocks === 0 && <span className="error-text"> · sin texto que evaluar en estas páginas</span>}
      </>
    ) : p.bookId ? "Elige qué parte del libro evaluar" : "Elige o sube un libro";

  const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") p.onBack?.(); };

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
          {lostOcr > 0 && (
            <div className="alert" role="note">
              <IconWarn />
              <span>
                {fmtN.format(lostOcr)} {lostOcr === 1 ? "página escaneada no tiene" : "páginas escaneadas no tienen"} texto
                extraído (en gris): comprueba que el OCR (Tesseract) está instalado y vuelve a preparar el libro.
              </span>
            </div>
          )}
          {book && (
            <section className="pg-book-summary" aria-label="Resumen del libro" aria-live="polite">
              <strong className="pg-ellipsis" title={book.name}>{book.name}</strong>
              <dl>
                <dt>Páginas</dt><dd>{fmtN.format(book.page_count)}</dd>
                <dt>Bloques</dt><dd>{fmtN.format(book.blocks)}</dd>
                <dt>Capítulos</dt>
                <dd>{p.chapters.length ? `${p.chapters.length} · ${p.chapters[0]?.source === "detected" ? "detectados" : "índice"}` : "ninguno"}</dd>
                <dt>Escaneadas</dt><dd>{pages.length ? (scanned === pages.length && scanned > 0 ? "todo el libro" : fmtN.format(scanned)) : "…"}</dd>
                <dt>Sin texto</dt><dd>{pages.length ? fmtN.format(empty) : "…"}</dd>
                <dt>Producción</dt><dd>{book.production ? "sí, para comparar" : "no"}</dd>
              </dl>
            </section>
          )}
        </aside>

        <section className="card pg-start-main" aria-labelledby="pg-scope-title">
          {/* cabecera fija al desplazar: el resumen y «Continuar» siguen a la vista con cientos de miniaturas */}
          <div className="pg-scope-head">
            <div className="stack">
              <h2 id="pg-scope-title">Alcance</h2>
              <span className="muted pg-estimate" aria-live="polite">
                {summary}
                {emptySelected > 0 && p.estimate && p.estimate.blocks > 0 ? ` · ${emptySelected} sin texto` : ""}
              </span>
            </div>
            <button type="button" className="btn" disabled={!valid} onClick={p.onContinue}>Continuar al playground</button>
          </div>

          <div className="tabs pg-modes" role="radiogroup" aria-label="Cómo elegir las páginas">
            {MODES.map((m) => (
              <button key={m.id} type="button" role="radio" aria-checked={mode === m.id} onClick={() => pickMode(m.id)}>{m.title}</button>
            ))}
          </div>

          <div className="pg-scope-mode">
            {mode === "chapter" && (p.chapters.length ? (
              <ul className="pg-chapters" role="listbox" aria-label="Capítulos">
                {p.chapters.map((c, i) => (
                  <li key={c.title + c.pages}>
                    <button type="button" role="option" aria-selected={p.value.chapter === String(i)}
                      className={c.level > 1 ? "sub" : ""} onClick={() => pickChapter(i)}>
                      <span>{c.title}</span><small>págs. {c.pages}</small>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="alert" role="note">
                <IconWarn />
                <div className="stack">
                  <span>No se detectaron capítulos: el PDF no tiene índice{scanned > 0 ? " y es escaneado" : ""}, o los títulos no se distinguen del texto.</span>
                  <div className="row"><button type="button" className="btn secondary" onClick={() => pickMode("range")}>Definir un intervalo de páginas</button></div>
                </div>
              </div>
            ))}
            {mode === "range" && (
              <div className="pg-scope-fields">
                <label className="control">Desde
                  <input className="pg-num" type="text" inputMode="numeric" value={from} onChange={(e) => setRange(e.target.value, to)} />
                </label>
                <label className="control">Hasta
                  <input className="pg-num" type="text" inputMode="numeric" value={to} onChange={(e) => setRange(from, e.target.value)} />
                </label>
                <span className="muted">
                  {anchor !== null ? `Inicio en la pág. ${anchor}: pulsa la página final.` : "O pulsa la primera y la última página en las miniaturas."}
                </span>
              </div>
            )}
            {mode === "page" && (
              <div className="pg-scope-fields">
                <label className="control">Página
                  <input className="pg-num" type="text" inputMode="numeric" value={p.value.onePage}
                    onChange={(e) => p.onChange({ scope: "page", onePage: e.target.value.replace(/\D/g, "") })} />
                </label>
                <span className="muted">o pulsa una miniatura</span>
              </div>
            )}
            {mode === "list" && (
              <div className="pg-scope-fields pg-grow">
                <label className="control">Páginas
                  <input className="pg-spec" type="text" value={p.value.pagesSpec} placeholder="3, 7, 12-15"
                    onChange={(e) => p.onChange({ scope: "pages", pagesSpec: e.target.value })} />
                </label>
                <span className="muted">o pulsa miniaturas para añadirlas o quitarlas · máx. 80</span>
              </div>
            )}
            {mode === "book" && <span className="muted">Las {fmtN.format(count)} páginas. Se pedirá confirmación antes de ejecutar.</span>}
          </div>

          <div ref={grid} className="pg-thumbs" aria-label="Páginas del libro">
            {p.bookId !== null && Array.from({ length: count }, (_, i) => i + 1).map((n) => {
              const x = info.get(n);
              const cls = ["pg-thumb", selected.has(n) ? "sel" : "", anchor === n ? "anchor" : "", x?.blocks === 0 ? "empty" : ""].join(" ");
              return (
                <button key={n} type="button" data-page={n} className={cls} aria-pressed={selected.has(n)}
                  title={`Página ${n}${x ? ` · ${x.blocks} bloques` : ""}`} onClick={(e) => clickThumb(n, e)}>
                  <img src={jobPageImageUrl(p.bookId!, n, "original", 36)} alt="" loading="lazy" decoding="async" />
                  <span className="pg-thumb-n">{n}</span>
                  {x && SCANNED.has(x.kind) && <span className="pg-thumb-tag">OCR</span>}
                  {x?.blocks === 0 && <span className="pg-thumb-tag">sin texto</span>}
                </button>
              );
            })}
          </div>
        </section>
      </div>
    </>
  );
}
