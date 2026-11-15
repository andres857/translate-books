"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getSummary, type JobSummary } from "@/lib/api";
import { IconArrowLeft, IconDownload, IconWarn } from "../../../components/art";
import { Compare } from "./compare";
import { Summary } from "./summary";
import { Terms } from "./terms";

type Tab = "summary" | "compare" | "terms";
const TABS: { id: Tab; label: string }[] = [
  { id: "summary", label: "Resumen" },
  { id: "compare", label: "Comparar" },
  { id: "terms", label: "Glosario y términos" },
];

export default function AdminJobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<JobSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [page, setPage] = useState(1);

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
      <main>
        <Link href="/admin" className="back"><IconArrowLeft width={16} height={16} /> Administración</Link>
        {error
          ? <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>
          : <section className="card"><p>Cargando…</p></section>}
      </main>
    );
  }

  const { job } = data;
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
      <Link href="/admin" className="back"><IconArrowLeft width={16} height={16} /> Administración</Link>

      <div className="page-head">
        <div>
          <h1>{job.title_es || job.original_name.replace(/\.pdf$/i, "")}</h1>
          <p>
            {job.original_name} · {job.page_count} páginas ·{" "}
            {job.mode === "digitize" ? "digitalización" : job.mode === "prepare" ? "preparado para el Playground (sin traducir)" : "traducción EN → ES"}
          </p>
        </div>
        {job.status === "done" && job.mode === "prepare" && (
          <Link className="btn" href="/admin/playground">Evaluar en el Playground</Link>
        )}
        {job.status === "done" && job.mode !== "prepare" && (
          <div className="row">
            <a className="btn" href={`/api/jobs/${job.id}/download`}><IconDownload /> PDF</a>
            <a className="btn secondary" href={`/api/jobs/${job.id}/download?format=epub`}>EPUB</a>
            <a className="btn secondary" href={`/api/jobs/${job.id}/download?format=azw3`}>AZW3</a>
            <a className="btn ghost" href={`/api/jobs/${job.id}/report`}>Reporte</a>
          </div>
        )}
      </div>

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
            : <section className="card"><p>La comparación estará disponible cuando el libro termine de procesarse.</p></section>
        )}
        {tab === "terms" && <Terms documentId={job.document_id} />}
      </div>
    </main>
  );
}
