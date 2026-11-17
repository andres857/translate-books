"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getSummary, type JobSummary } from "@/lib/api";
import { IconArrowLeft, IconChevron, IconDownload, IconText, IconWarn } from "../../../components/art";
import { Compare } from "./compare";
import { Summary } from "./summary";
import { Terms } from "./terms";

type Tab = "summary" | "compare" | "terms";
// lo primero es ver el resultado: el libro página a página; el resumen técnico va al final
const TABS: { id: Tab; label: string }[] = [
  { id: "compare", label: "Libro" },
  { id: "terms", label: "Glosario y términos" },
  { id: "summary", label: "Resumen" },
];

const KIND: Record<string, string> = {
  digital: "digitales", scanned: "escaneadas", mixed: "mixtas", image_only: "solo imagen", blank: "en blanco",
};

export default function AdminJobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<JobSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("compare");
  const [page, setPage] = useState(1);
  const [details, setDetails] = useState(false);
  const [downloads, setDownloads] = useState(false);
  const downloadRef = useRef<HTMLDivElement>(null);

  // título de la pestaña con el nombre del libro (la metadata del segmento solo dice «Revisión del libro»)
  const bookTitle = data?.book.title;
  useEffect(() => {
    if (bookTitle) document.title = `${bookTitle} · Revisión · AstroBooks`;
  }, [bookTitle]);

  // el menú de formatos se cierra al hacer clic fuera o con Escape
  useEffect(() => {
    if (!downloads) return;
    const onDown = (e: MouseEvent) => {
      if (!downloadRef.current?.contains(e.target as Node)) setDownloads(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setDownloads(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [downloads]);

  const reload = useCallback(async () => {
    try {
      setData(await getSummary(id));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    reload();
  }, [reload]);

  // mientras el libro se procesa, el resumen se refresca solo
  const status = data?.job.status;
  useEffect(() => {
    if (!status || ["done", "failed", "cancelled"].includes(status)) return;
    const timer = setInterval(reload, 2500);
    return () => clearInterval(timer);
  }, [status, reload]);

  if (!data) {
    return (
      <main className="wide">
        <Link href="/" className="back"><IconArrowLeft width={16} height={16} /> Libros</Link>
        {error
          ? <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>
          : <section className="card"><p className="muted">Cargando…</p></section>}
      </main>
    );
  }

  const { job, book } = data;
  const ready = data.pages.length > 0 && Boolean(job.output_name);

  function tabKey(e: React.KeyboardEvent) {
    const i = TABS.findIndex((t) => t.id === tab);
    const next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : -1;
    if (next < 0 || next >= TABS.length) return;
    e.preventDefault();
    setTab(TABS[next].id);
    document.getElementById(`tab-${TABS[next].id}`)?.focus();
  }

  return (
    <main className="wide">
      <Link href="/" className="back"><IconArrowLeft width={16} height={16} /> Libros</Link>

      <div className="page-head book-head">
        <div>
          <h1>{book.title}</h1>
          <p className="book-meta">
            {[book.subtitle, book.author, `${job.page_count} págs.`,
              job.mode === "translate" ? `${book.source_lang} → ${book.target_lang}`
                : job.mode === "digitize" ? "digitalización" : "preparado para el Playground"]
              .filter(Boolean).join(" · ")}
            {" · "}
            <button type="button" className="link-btn" aria-expanded={details} onClick={() => setDetails((v) => !v)}>
              Detalles del archivo
            </button>
          </p>
        </div>
        {job.status === "done" && job.mode === "prepare" && (
          <Link className="btn" href="/admin/playground">Evaluar en el Playground</Link>
        )}
        {job.status === "done" && job.mode !== "prepare" && (
          <div className="row">
            <a className="btn secondary" href={`/api/jobs/${job.id}/report`}><IconText /> Ver reporte</a>
            <div className="split-btn" ref={downloadRef}>
              <a className="btn" href={`/api/jobs/${job.id}/download`}><IconDownload /> Descargar PDF</a>
              <button type="button" className="btn" aria-label="Otros formatos" aria-haspopup="menu"
                aria-expanded={downloads} onClick={() => setDownloads((v) => !v)}>
                <IconChevron width={16} height={16} />
              </button>
              {downloads && (
                <div className="split-pop" role="menu">
                  <a role="menuitem" href={`/api/jobs/${job.id}/download?format=epub`}>EPUB</a>
                  <a role="menuitem" href={`/api/jobs/${job.id}/download?format=azw3`}>AZW3 (Kindle)</a>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {details && (
        <section className="card file-details" aria-label="Detalles del archivo">
          <dl>
            <dt>Archivo original</dt><dd>{job.original_name}</dd>
            {job.output_name && <><dt>Archivo generado</dt><dd>{job.output_name}</dd></>}
            <dt>Páginas</dt>
            <dd>
              {job.page_count}
              {Object.keys(data.totals.by_kind).length > 0 && ` (${Object.entries(data.totals.by_kind)
                .map(([k, n]) => `${n} ${KIND[k] ?? k}`).join(", ")})`}
            </dd>
            <dt>Bloques de texto</dt><dd>{data.totals.segments}{data.totals.edited ? ` · ${data.totals.edited} corregidos a mano` : ""}</dd>
          </dl>
        </section>
      )}

      {error && <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>}
      {job.recompose_error && <div className="alert error" role="alert"><IconWarn /><span>{job.recompose_error}</span></div>}
      {job.status !== "done" && !job.recomposing && (
        <div className="alert" role="status">
          <IconWarn />
          <span>
            Este libro todavía no ha terminado ({Math.round(job.progress)}%).{" "}
            <Link href={`/jobs/${job.id}`}>Ver el progreso</Link>.
          </span>
        </div>
      )}

      <div className="tabs" role="tablist" aria-label="Secciones del libro" onKeyDown={tabKey}>
        {TABS.map((t) => (
          <button key={t.id} id={`tab-${t.id}`} role="tab" type="button" aria-selected={tab === t.id}
            aria-controls="tab-panel" tabIndex={tab === t.id ? 0 : -1} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      <div id="tab-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === "summary" && (
          <Summary data={data} onOpenPage={(n) => { setPage(n); setTab("compare"); }} />
        )}
        {tab === "compare" && (
          ready
            ? <Compare data={data} page={page} onPage={setPage} onChanged={reload} />
            : <section className="card empty-state"><p>La comparación estará disponible cuando el libro termine de procesarse.</p></section>
        )}
        {tab === "terms" && <Terms documentId={job.document_id} />}
      </div>
    </main>
  );
}
