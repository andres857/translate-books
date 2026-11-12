"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getJob, getSegments, recomposePage, saveSegment, type JobSummary, type PageSegments, type SegmentRow,
} from "@/lib/api";
import { IconArrowLeft, IconArrowRight, IconMinus, IconPlus, IconRefresh, IconWarn } from "../../../components/art";

const ZOOMS = [60, 80, 100, 130, 170];
const ACTION: Record<SegmentRow["action"], string> = {
  translate: "Traducido", keep: "Se conserva", graphic: "Gráfico", review: "Sin traducir",
};

function plain(html: string | null): string {
  return (html ?? "").replace(/<br\s*\/?>/g, "\n").replace(/<[^>]+>/g, "")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
}

export function Compare({ data, page, onPage, onChanged }: {
  data: JobSummary; page: number; onPage: (n: number) => void; onChanged: () => void;
}) {
  const { job } = data;
  const total = data.pages.length;
  const editable = job.mode === "translate";
  const [info, setInfo] = useState<PageSegments | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [zoom, setZoom] = useState(2);
  const [side, setSide] = useState<"original" | "translated">("translated");
  const [hover, setHover] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

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
    load();
  }, [load]);

  // ← y → cambian de página, salvo al escribir en un campo
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && ["TEXTAREA", "INPUT", "SELECT", "BUTTON"].includes(el.tagName)) return;
      if (e.key === "ArrowLeft" && page > 1) onPage(page - 1);
      if (e.key === "ArrowRight" && page < total) onPage(page + 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [page, total, onPage]);

  useEffect(() => {
    listRef.current?.querySelector('[aria-current="true"]')?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [page]);

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

  return (
    <div className="compare">
      <div className="pages-list" ref={listRef} role="group" aria-label="Páginas">
        {data.pages.map((p) => (
          <button key={p.number} type="button" aria-current={p.number === page} onClick={() => onPage(p.number)}
            title={p.needs_review ? "Para revisar" : "Correcta"}>
            <span>Página {p.number}</span>
            <span className={`dot ${p.needs_review ? "review" : p.segments ? "" : "none"}`}
              aria-label={p.needs_review ? "para revisar" : "correcta"} role="img" />
          </button>
        ))}
      </div>

      <div className="viewer">
        <div className="toolbar">
          <div className="row">
            <button type="button" className="btn secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}
              aria-label="Página anterior"><IconArrowLeft /></button>
            <strong>Página {page} de {total}</strong>
            <button type="button" className="btn secondary" disabled={page >= total} onClick={() => onPage(page + 1)}
              aria-label="Página siguiente"><IconArrowRight /></button>
            {info && (
              <span className={`badge ${info.needs_review ? "review" : "ok"}`}>
                {info.needs_review ? "Para revisar" : "Correcta"}
              </span>
            )}
          </div>
          <div className="row">
            <div className="seg-control narrow-only" role="group" aria-label="Versión que se muestra">
              <button type="button" aria-pressed={side === "original"} onClick={() => setSide("original")}>Original</button>
              <button type="button" aria-pressed={side === "translated"} onClick={() => setSide("translated")}>Traducción</button>
            </div>
            <button type="button" className="btn secondary" disabled={zoom === 0} onClick={() => setZoom(zoom - 1)}
              aria-label="Reducir"><IconMinus /></button>
            <span className="muted" aria-live="polite">{ZOOMS[zoom]}%</span>
            <button type="button" className="btn secondary" disabled={zoom === ZOOMS.length - 1}
              onClick={() => setZoom(zoom + 1)} aria-label="Ampliar"><IconPlus /></button>
          </div>
        </div>

        {info && info.reasons.length > 0 && (
          <div className="alert">
            <IconWarn />
            <div>
              <strong>Motivos de revisión</strong>
              <ul>{info.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
          </div>
        )}

        {/* las dos hojas comparten un único contenedor con desplazamiento: se mueven juntas */}
        <div className="sheets" tabIndex={0} role="group" aria-label={`Original y traducción de la página ${page}`}>
          <div className="sheets-inner single" style={{ width: `${ZOOMS[zoom]}%` }}>
            {(["original", "translated"] as const).map((v) => (
              <figure key={v} className={`sheet ${side === v ? "" : "hidden-narrow"}`}>
                <figcaption>{v === "original" ? "Original" : job.mode === "digitize" ? "Digitalizado" : "Traducción"}</figcaption>
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

        {error && <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>}
        {notice && <div className="alert ok" role="status"><IconRefresh /><span>{notice}</span></div>}

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

          {!info && !error && <p>Cargando…</p>}
          {info && blocks.length === 0 && <p>Esta página no tiene texto.</p>}
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
