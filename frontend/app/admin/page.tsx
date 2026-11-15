"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getSettings, listJobs, methodLabel, type JobStatus } from "@/lib/api";
import { IconWarn } from "../components/art";

const STATUS: Record<JobStatus["status"], { text: string; kind: string }> = {
  queued: { text: "En cola", kind: "" },
  running: { text: "En curso", kind: "info" },
  paused: { text: "En pausa", kind: "" },
  cancelled: { text: "Cancelado", kind: "review" },
  failed: { text: "Con error", kind: "review" },
  done: { text: "Terminado", kind: "ok" },
};

export default function AdminPage() {
  const [jobs, setJobs] = useState<JobStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [method, setMethod] = useState<string | null>(null);

  useEffect(() => {
    getSettings().then((s) => setMethod(methodLabel(s))).catch(() => setMethod(null));
  }, []);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const list = await listJobs();
        if (!alive) return;
        setJobs(list);
        setError(null);
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
      if (alive) timer = setTimeout(tick, 5000);
    };
    tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, []);

  return (
    <main>
      <div className="page-head">
        <div>
          <h1>Administración</h1>
          <p>Libros procesados: resumen de páginas, comparación con el original, correcciones y glosario.</p>
        </div>
        <div className="row">
          {method && (
            <Link className="btn ghost" href="/admin/settings" title="Cambiar el método de traducción">
              Método: {method}
            </Link>
          )}
          <Link className="btn" href="/">Subir un libro</Link>
        </div>
      </div>

      {error && <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>}

      {jobs === null && !error && <section className="card"><p>Cargando…</p></section>}
      {jobs?.length === 0 && (
        <section className="card"><p>Todavía no hay libros. Sube el primero desde Inicio.</p></section>
      )}
      {jobs && jobs.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="num">N.º</th>
                <th>Libro</th>
                <th>Tipo</th>
                <th>Estado</th>
                <th className="num">Páginas</th>
                <th className="num">Para revisar</th>
                <th><span className="muted">Acciones</span></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td className="num">{j.id}</td>
                  <td className="wrap">
                    <Link href={`/admin/jobs/${j.id}`}>{j.title_es || j.original_name.replace(/\.pdf$/i, "")}</Link>
                    {j.title_es && <div className="muted">{j.original_name}</div>}
                  </td>
                  <td>{j.mode === "digitize" ? "Digitalización" : j.mode === "prepare" ? "Preparado para el Playground" : "Traducción"}</td>
                  <td>
                    <span className={`badge ${STATUS[j.status].kind}`}>
                      {STATUS[j.status].text}{j.status === "running" ? ` · ${Math.round(j.progress)}%` : ""}
                    </span>
                  </td>
                  <td className="num">{j.page_count}</td>
                  <td className="num">{j.status === "done" ? j.review_pages.length : "—"}</td>
                  <td>
                    <div className="row">
                      <Link className="btn secondary" href={`/admin/jobs/${j.id}`}>Abrir</Link>
                      {j.status !== "done" && <Link className="btn ghost" href={`/jobs/${j.id}`}>Progreso</Link>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
