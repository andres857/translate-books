"use client";

/* Pestaña Libro: índice por capítulos (izquierda) y visor de páginas con original y traducción (derecha).
   Debajo del visor, el texto por bloque para corregir la traducción y recomponer la página. */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getJob, getSegments, listBookChapters, recomposePage, saveSegment, type BookChapter,
  type JobSummary, type PageSegments, type PageSummary, type SegmentRow,
} from "@/lib/api";
import {
  IconArrowLeft, IconArrowRight, IconChevron, IconMinus, IconPlus, IconRefresh, IconWarn,
} from "../../../components/art";

const ZOOMS = [60, 80, 100, 130, 170];
const ACTION: Record<SegmentRow["action"], string> = {
  translate: "Traducido", keep: "Se conserva", graphic: "Gráfico", review: "Sin traducir",
};

function plain(html: string | null): string {
  return (html ?? "").replace(/<br\s*\/?>/g, "\n").replace(/<[^>]+>/g, "")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
}

// títulos escritos todo en mayúsculas («THE ZODIAC SIGNS») → «The zodiac signs»; los demás, tal cual
const sentence = (t: string) =>
  t === t.toUpperCase() && t !== t.toLowerCase() ? t.charAt(0) + t.slice(1).toLowerCase() : t;

const range = (r: string): [number, number] => {
  const [a, b] = r.split("-").map(Number);
  return [a, b || a];
};

type Part = { title: string | null; pages: PageSummary[] };
type Group = { title: string; original: string | null; first: number; last: number; parts: Part[] };

/* agrupa las páginas por capítulo (nivel superior del índice) y, dentro, por sección (segundo nivel).
   El título se muestra traducido cuando se encontró su encabezado traducido; si no, el original.
   Las páginas fuera de todo capítulo van a «Inicio» o «Final». */
function groupPages(pages: PageSummary[], chapters: BookChapter[]): Group[] {
  if (!chapters.length) return [];
  const name = (c: BookChapter) => sentence(c.title_es || c.title);
  const top = Math.min(...chapters.map((c) => c.level));
  const tops = chapters.filter((c) => c.level === top).map((c) => ({ c, r: range(c.pages) }));
  const subs = chapters.filter((c) => c.level > top).map((c) => ({ c, r: range(c.pages) }));
  const groups: Group[] = [];
  const add = (title: string, original: string | null, list: PageSummary[], inner: typeof subs) => {
    if (!list.length) return;
    const parts: Part[] = [];
    for (const p of list) {
      const sub = [...inner].reverse().find((x) => x.r[0] <= p.number && p.number <= x.r[1]);
      const label = sub ? name(sub.c) : null;
      const lastPart = parts[parts.length - 1];
      if (lastPart && lastPart.title === label) lastPart.pages.push(p);
      else parts.push({ title: label, pages: [p] });
    }
    groups.push({ title, original, first: list[0].number, last: list[list.length - 1].number, parts });
  };
  const first = tops.length ? tops[0].r[0] : Infinity;
  add("Inicio", null, pages.filter((p) => p.number < first), []);
  tops.forEach(({ c, r }) => add(name(c), c.title_es ? sentence(c.title) : null,
    pages.filter((p) => p.number >= r[0] && p.number <= r[1]), subs.filter((x) => x.r[0] >= r[0] && x.r[0] <= r[1])));
  const last = tops.length ? Math.max(...tops.map((t) => t.r[1])) : 0;
  add("Final", null, pages.filter((p) => p.number > last && p.number >= first), []);
  return groups;
}

// la vista del libro muestra el resultado tal cual: la evaluación de calidad se hace en el Playground
type PageState = "ok" | "empty" | "pending";
const STATE_LABEL: Record<PageState, string> = { ok: "Traducida", empty: "Sin texto", pending: "Pendiente" };

const SHOW_KEY = "compare-sheets";
const UNSAVED_NOTICE = "Tienes correcciones sin guardar en esta página: guárdalas antes de cambiar de página. "
  + "Para descartarlas, elige otra página en el índice o con las flechas de la barra.";
const UNSAVED_CONFIRM = "Tienes correcciones sin guardar en esta página. ¿Cambiar de página y descartarlas?";
type Show = "both" | "original" | "translated";

export function Compare({ data, page, onPage, onChanged }: {
  data: JobSummary; page: number; onPage: (n: number) => void; onChanged: () => void;
}) {
  const { job, book } = data;
  const total = data.pages.length;
  const editable = job.mode === "translate";
  const [info, setInfo] = useState<PageSegments | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [zoom, setZoom] = useState(2);
  const [show, setShow] = useState<Show>("both");
  const [hover, setHover] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [unsaved, setUnsaved] = useState(false); // aviso: se intentó cambiar de página con borradores
  const listRef = useRef<HTMLDivElement>(null);
  const [chapters, setChapters] = useState<BookChapter[] | null>(null);
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const [pageText, setPageText] = useState(String(page));

  useEffect(() => {
    try {
      const v = localStorage.getItem(SHOW_KEY);
      if (v === "both" || v === "original" || v === "translated") setShow(v);
    } catch { /* vista por defecto */ }
  }, []);

  function chooseShow(v: Show) {
    setShow(v);
    try { localStorage.setItem(SHOW_KEY, v); } catch { /* ignorar */ }
  }

  useEffect(() => {
    listBookChapters(job.id).then(setChapters).catch(() => setChapters([]));
  }, [job.id]);

  const groups = useMemo(() => groupPages(data.pages, chapters ?? []), [data.pages, chapters]);
  const current = groups.findIndex((g) => page >= g.first && page <= g.last);
  const currentPart = current >= 0 ? groups[current].parts.find((p) => p.pages.some((x) => x.number === page)) : null;
  const allOpen = groups.length > 0 && groups.every((_, i) => open[i]);
  const noText = data.pages.filter((p) => p.segments === 0).length;

  const stateOf = (p: PageSummary): PageState =>
    p.segments === 0 ? "empty" : job.mode === "translate" && p.translated === 0 ? "pending" : "ok";

  // el capítulo de la página actual se despliega solo
  useEffect(() => {
    if (current >= 0) setOpen((o) => (o[current] ? o : { ...o, [current]: true }));
  }, [current]);

  useEffect(() => setPageText(String(page)), [page]);

  // correcciones escritas y sin guardar: cambiar de página las descartaría (ver go() y los efectos de
  // teclado y rueda). La ref deja que esos efectos lo consulten sin volver a registrarse.
  // solo cuentan los bloques cuyo texto difiere del guardado (escribir y volver al original no bloquea)
  const hasDrafts = (info?.segments ?? []).some((x) => drafts[x.key] !== undefined && drafts[x.key] !== (x.translation ?? ""));
  const draftsRef = useRef(hasDrafts);
  draftsRef.current = hasDrafts;

  /** Cambio de página pedido por el usuario (índice, flechas de la barra, campo): con borradores, se confirma. */
  function go(n: number) {
    if (n === page) return;
    if (draftsRef.current && !window.confirm(UNSAVED_CONFIRM)) {
      setPageText(String(page));
      return;
    }
    onPage(n);
  }

  function goTo(e?: React.FormEvent) {
    e?.preventDefault();
    const n = Number(pageText);
    if (Number.isInteger(n) && n >= 1 && n <= total) go(n);
    else setPageText(String(page));
  }

  function toggleAll() {
    setOpen(allOpen ? (current >= 0 ? { [current]: true } : {}) : Object.fromEntries(groups.map((_, i) => [i, true])));
  }

  const load = useCallback(async () => {
    try {
      setInfo(await getSegments(job.id, page));
      setError(null);
    } catch (e) {
      setInfo(null);
      setError((e as Error).message);
    }
  }, [job.id, page]);

  useEffect(() => {
    setDrafts({});
    setNotice(null);
    setUnsaved(false);
    load();
  }, [load]);

  // ← y → cambian de página, salvo al escribir en un campo
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && ["TEXTAREA", "INPUT", "SELECT", "BUTTON"].includes(el.tagName)) return;
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      if (draftsRef.current) return setUnsaved(true); // gesto automático: no se pregunta, se avisa
      if (e.key === "ArrowLeft" && page > 1) onPage(page - 1);
      if (e.key === "ArrowRight" && page < total) onPage(page + 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [page, total, onPage]);

  // rueda del ratón sobre las hojas: desplaza la página ampliada y, al llegar al borde, pasa a la siguiente
  // o a la anterior. Una pausa breve evita saltar varias páginas con un solo gesto (trackpads, ruedas libres).
  const sheetsRef = useRef<HTMLDivElement>(null);
  const turn = useRef({ until: 0, dir: 0 });
  useEffect(() => {
    const el = sheetsRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (e.ctrlKey || Math.abs(e.deltaY) < Math.abs(e.deltaX) || e.deltaY === 0) return;
      const down = e.deltaY > 0;
      const atEdge = down ? el.scrollTop + el.clientHeight >= el.scrollHeight - 2 : el.scrollTop <= 1;
      if (!atEdge) return; // todavía queda hoja por recorrer: desplazamiento normal
      e.preventDefault();
      if (draftsRef.current) return setUnsaved(true);
      const now = Date.now();
      if (now < turn.current.until) return;
      const next = page + (down ? 1 : -1);
      if (next < 1 || next > total) return;
      turn.current = { until: now + 450, dir: down ? 1 : -1 };
      onPage(next);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [page, total, onPage]);

  // al pasar con la rueda, la hoja nueva empieza arriba (hacia delante) o abajo (hacia atrás)
  useEffect(() => {
    const el = sheetsRef.current;
    if (!el) return;
    el.scrollTop = turn.current.dir < 0 ? el.scrollHeight : 0;
    turn.current.dir = 0;
  }, [page]);

  useEffect(() => {
    listRef.current?.querySelector('[aria-current="true"]')?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [page, open]);

  async function save(seg: SegmentRow) {
    const text = drafts[seg.key];
    if (text === undefined) return;
    setBusy(seg.key);
    try {
      const saved = await saveSegment(job.id, seg.key, text);
      setInfo((cur) => cur && { ...cur, segments: cur.segments.map((s) => (s.key === saved.key ? saved : s)) });
      setDrafts(({ [seg.key]: _, ...rest }) => rest);
      setNotice("Corrección guardada. Recompón la página para verla en el PDF.");
      setError(null);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function recompose() {
    setBusy("recompose");
    setNotice(null);
    setError(null);
    try {
      let st = await recomposePage(job.id, page);
      while (st.status === "queued" || st.status === "running") {
        await new Promise((r) => setTimeout(r, 1200));
        st = await getJob(job.id);
      }
      if (st.status !== "done" || st.recompose_error) {
        setError(st.recompose_error ?? st.error ?? "No se pudo recomponer la página.");
      } else {
        setNotice(`Página ${page} recompuesta. Los archivos para Kindle se regeneran en la próxima descarga.`);
      }
      setVersion((v) => v + 1);
      await load();
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const dpi = ZOOMS[zoom] >= 130 ? 150 : 100;
  const src = (v: "original" | "translated") =>
    `/api/jobs/${job.id}/pages/${page}/preview?version=${v}&dpi=${dpi}&v=${version}`;
  const marked = info?.segments.find((s) => s.key === hover);
  const mark = marked && info ? {
    left: `${(marked.bbox[0] / info.width) * 100}%`,
    top: `${(marked.bbox[1] / info.height) * 100}%`,
    width: `${((marked.bbox[2] - marked.bbox[0]) / info.width) * 100}%`,
    height: `${((marked.bbox[3] - marked.bbox[1]) / info.height) * 100}%`,
  } : null;
  const edited = info?.segments.filter((s) => s.edited).length ?? 0;
  const dirty = Object.keys(drafts).length;
  const blocks = info?.segments.filter((s) => s.action !== "graphic") ?? [];
  const translatedLabel = job.mode === "digitize" ? "Digitalizado" : "Traducción";
  const caption = (v: "original" | "translated") =>
    v === "original" ? `Original · ${book.source_lang}` : job.mode === "translate" ? `Traducción · ${book.target_lang}` : translatedLabel;
  const tiles = (list: PageSummary[]) => (
    <div className="page-tiles">
      {list.map((p) => {
        const st = stateOf(p);
        return (
          <button key={p.number} type="button" className={`page-tile ${st}`} aria-current={p.number === page}
            onClick={() => go(p.number)} aria-label={`Página ${p.number}, ${STATE_LABEL[st].toLowerCase()}`}
            title={`Página ${p.number} · ${STATE_LABEL[st]}`}>
            {p.number}
          </button>
        );
      })}
    </div>
  );

  return (
    <div className="compare">
      <aside className="book-index" aria-labelledby="index-title">
        <div className="index-head">
          <h2 id="index-title">Índice</h2>
          {noText > 0 && <span className="muted">{noText} págs. sin texto</span>}
        </div>
        <ul className="index-legend" aria-label="Leyenda">
          {(["ok", "empty", "pending"] as const).map((st) => (
            <li key={st}>
              <span className={`page-tile sample ${st}`} aria-hidden="true" />
              {STATE_LABEL[st]}
            </li>
          ))}
        </ul>
        <div className="index-scroll" ref={listRef}>
          {chapters === null && <p className="muted">Cargando índice…</p>}
          {chapters !== null && groups.length === 0 && tiles(data.pages)}
          {groups.map((g, i) => (
            <div key={i} className={`chapter ${i === current ? "current" : ""}`}>
              <button type="button" className="chapter-head" aria-expanded={!!open[i]}
                onClick={() => setOpen((o) => ({ ...o, [i]: !o[i] }))}>
                <IconChevron className="chev" width={14} height={14} />
                <span className="chapter-title">
                  <strong>{g.title}</strong>
                  {g.original && g.original.toLowerCase() !== g.title.toLowerCase() && (
                    <span className="muted" lang="en">{g.original}</span>
                  )}
                </span>
                <span className="chapter-range">{g.first === g.last ? `p. ${g.first}` : `pp. ${g.first}–${g.last}`}</span>
              </button>
              {open[i] && (
                <div className="chapter-body">
                  {g.parts.map((part, j) => (
                    <div key={j} className="chapter-part">
                      {(part.title || g.parts.length > 1) && (
                        <div className="chapter-sub">{part.title ?? "Apertura"}</div>
                      )}
                      {tiles(part.pages)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
        {groups.length > 1 && (
          <button type="button" className="link-btn" onClick={toggleAll}>
            {allOpen ? "Plegar el índice" : `Ver los ${chapters?.length ?? groups.length} capítulos`}
          </button>
        )}
      </aside>

      <div className="viewer">
        <section className="viewer-card" aria-label="Visor de páginas">
          <div className="viewer-bar">
            <div className="row">
              <button type="button" className="btn secondary icon" disabled={page <= 1} onClick={() => go(page - 1)}
                aria-label="Página anterior"><IconArrowLeft /></button>
              <form className="page-field" onSubmit={goTo}>
                <label htmlFor="page-field">Página</label>
                <input id="page-field" type="text" inputMode="numeric" value={pageText}
                  onChange={(e) => setPageText(e.target.value.replace(/\D/g, ""))} onBlur={() => goTo()}
                  onFocus={(e) => e.target.select()} aria-describedby="page-total" />
                <span id="page-total">de {total}</span>
              </form>
              <button type="button" className="btn secondary icon" disabled={page >= total} onClick={() => go(page + 1)}
                aria-label="Página siguiente"><IconArrowRight /></button>
              {current >= 0 && (
                <nav className="crumbs" aria-label="Ubicación en el libro">
                  <span>{groups[current].title}</span>
                  {currentPart?.title && <><span aria-hidden="true">›</span><span>{currentPart.title}</span></>}
                </nav>
              )}
            </div>
            <div className="row">
              <div className="seg-control" role="group" aria-label="Qué se muestra">
                <button type="button" aria-pressed={show === "original"} onClick={() => chooseShow("original")}>Original</button>
                <button type="button" aria-pressed={show === "both"} onClick={() => chooseShow("both")}>Comparar</button>
                <button type="button" aria-pressed={show === "translated"} onClick={() => chooseShow("translated")}>
                  {translatedLabel}
                </button>
              </div>
              <button type="button" className="btn secondary icon" disabled={zoom === 0} onClick={() => setZoom(zoom - 1)}
                aria-label="Reducir"><IconMinus /></button>
              <span className="zoom-value" aria-live="polite">{ZOOMS[zoom]}%</span>
              <button type="button" className="btn secondary icon" disabled={zoom === ZOOMS.length - 1}
                onClick={() => setZoom(zoom + 1)} aria-label="Ampliar"><IconPlus /></button>
            </div>
          </div>

          {/* las dos hojas comparten un único contenedor con desplazamiento: se mueven juntas */}
          <div className="sheets" ref={sheetsRef} tabIndex={0} role="group" aria-label={`Página ${page}`}>
            <div className={`sheets-inner ${show === "both" ? "" : "single"}`}
              style={{ "--layout-zoom": `${ZOOMS[zoom]}%` } as React.CSSProperties}>
              {(["original", "translated"] as const).filter((v) => show === "both" || show === v).map((v) => (
                <figure key={v} className="sheet">
                  <figcaption>{caption(v)}</figcaption>
                  <div className="paper">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={src(v)} alt={`Página ${page}, ${v === "original" ? "original" : "resultado"}`}
                      width={info?.width} height={info?.height} />
                    {mark && <div className="mark" style={mark} />}
                  </div>
                </figure>
              ))}
            </div>
          </div>
          <p className="viewer-hint">
            ← → o la rueda del ratón para cambiar de página{show === "both" ? " · en Comparar, el desplazamiento y el zoom van sincronizados" : ""}
          </p>
        </section>

        {error && <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>}
        {notice && <div className="alert ok" role="status"><IconRefresh /><span>{notice}</span></div>}
        {unsaved && hasDrafts && <div className="alert" role="status"><IconWarn /><span>{UNSAVED_NOTICE}</span></div>}

        <section className="card" aria-labelledby="blocks-title">
          <div className="card-head">
            <div>
              <h2 id="blocks-title">Texto por bloque</h2>
              <p className="muted">
                {blocks.length} bloque(s){edited ? ` · ${edited} corregido(s) a mano` : ""}
                {editable ? " · se admiten <b> e <i> para negrita y cursiva" : ""}
              </p>
            </div>
            {editable && (
              <button type="button" className="btn" onClick={recompose}
                disabled={busy !== null || dirty > 0 || edited === 0}
                title={dirty > 0 ? "Guarda primero los cambios pendientes" : edited === 0 ? "Corrige y guarda algún bloque primero" : undefined}>
                <IconRefresh /> {busy === "recompose" ? "Recomponiendo…" : "Recomponer página"}
              </button>
            )}
          </div>

          {!info && !error && <p className="muted">Cargando…</p>}
          {info && blocks.length === 0 && <p className="muted">Esta página no tiene texto.</p>}
          <div className="blocks">
            {blocks.map((s) => {
              const canEdit = editable && (s.action === "translate" || s.action === "review");
              const value = drafts[s.key] ?? s.translation ?? "";
              const changed = drafts[s.key] !== undefined && drafts[s.key] !== (s.translation ?? "");
              return (
                <div key={s.key} className={`block ${canEdit ? "" : "kept"}`}
                  onMouseEnter={() => setHover(s.key)} onMouseLeave={() => setHover(null)}
                  onFocus={() => setHover(s.key)} onBlur={() => setHover(null)}>
                  <div>
                    <div className="meta">
                      <span className="muted">{s.key} · {s.block_type}</span>
                      <span className={`badge ${s.action === "review" ? "review" : ""}`}>{ACTION[s.action]}</span>
                      {s.edited && <span className="badge info">Editado</span>}
                      {s.fit_scale && s.fit_scale < 0.999 && <span className="badge">Escala {Math.round(s.fit_scale * 100)}%</span>}
                    </div>
                    <p className="src" lang="en">{plain(s.source_html)}</p>
                  </div>
                  <div>
                    {canEdit ? (
                      <>
                        <textarea lang="es" aria-label={`Traducción del bloque ${s.key}`} value={value}
                          rows={Math.min(10, Math.max(2, Math.ceil(value.length / 70)))}
                          onChange={(e) => setDrafts({ ...drafts, [s.key]: e.target.value })} />
                        {changed && (
                          <div className="row">
                            <button type="button" className="btn" disabled={busy !== null || !value.trim()} onClick={() => save(s)}>
                              {busy === s.key ? "Guardando…" : "Guardar"}
                            </button>
                            <button type="button" className="btn ghost"
                              onClick={() => setDrafts(({ [s.key]: _, ...rest }) => rest)}>Descartar</button>
                          </div>
                        )}
                      </>
                    ) : (
                      <p className="muted">Este bloque se conserva tal cual.</p>
                    )}
                    {s.issues.length > 0 && <ul className="issues">{s.issues.map((x, i) => <li key={i}>{x}</li>)}</ul>}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}
