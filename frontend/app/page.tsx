"use client";

/* Libros: todos los libros subidos (traducidos, digitalizados o preparados para el Playground), con buscador,
   eliminación con confirmación y el formulario para subir uno nuevo. */
import { Fragment, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { deleteJob, getSettings, listJobs, methodLabel, type JobStatus } from "@/lib/api";
import { UploadBook } from "./components/upload-book";
import { IconTrash, IconUpload, IconWarn, IconX } from "./components/art";

const STATUS: Record<JobStatus["status"], { text: string; kind: string }> = {
  queued: { text: "En cola", kind: "" },
  running: { text: "En curso", kind: "info" },
  paused: { text: "En pausa", kind: "" },
  cancelled: { text: "Cancelado", kind: "review" },
  failed: { text: "Con error", kind: "review" },
  done: { text: "Terminado", kind: "ok" },
};

const MODE: Record<string, string> = { digitize: "Digitalización", prepare: "Preparado para el Playground" };

const bookName = (j: JobStatus) => j.title_es || j.original_name.replace(/\.pdf$/i, "");
const fold = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export default function BooksPage() {
  const [jobs, setJobs] = useState<JobStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [method, setMethod] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [uploading, setUploading] = useState(false);
  const [confirm, setConfirm] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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

  const shown = useMemo(() => {
    const q = fold(query.trim());
    if (!jobs || !q) return jobs ?? [];
    return jobs.filter((j) => fold(`${j.id} ${bookName(j)} ${j.original_name}`).includes(q));
  }, [jobs, query]);

  async function remove(j: JobStatus) {
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteJob(j.id);
      setJobs((list) => list?.filter((x) => x.id !== j.id) ?? null);
      setConfirm(null);
      setNotice(`Se eliminó «${bookName(j)}».`);
    } catch (e) {
      setDeleteError((e as Error).message);
    } finally {
      setDeleting(false);
    }
  }

  function askDelete(id: number) {
    setConfirm((c) => (c === id ? null : id));
    setDeleteError(null);
    setNotice(null);
  }

  const busy = (j: JobStatus) => j.status === "queued" || j.status === "running";

  return (
    <main>
      <div className="page-head">
        <div>
          <h1>Libros</h1>
          <p>Libros subidos: traducción, comparación con el original, correcciones y glosario.</p>
        </div>
        <div className="row">
          {method && (
            <Link className="btn ghost" href="/admin/settings" title="Cambiar el método de traducción">
              Método: {method}
            </Link>
          )}
          {!uploading && (
            <button type="button" className="btn" onClick={() => setUploading(true)}>
              <IconUpload /> Subir un libro
            </button>
          )}
        </div>
      </div>

      {(uploading || jobs?.length === 0) && (
        <UploadBook onClose={jobs?.length ? () => setUploading(false) : undefined} />
      )}

      {error && <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>}
      {notice && <div className="alert ok" role="status"><span>{notice}</span></div>}

      {jobs === null && !error && <section className="card"><p>Cargando…</p></section>}
      {jobs && jobs.length > 0 && (
        <>
          <div className="books-tools">
            <label className="control books-search">
              <span className="sr-only">Buscar libros</span>
              <input type="search" placeholder="Buscar por título, archivo o número" value={query}
                onChange={(e) => setQuery(e.target.value)} />
            </label>
            <span className="muted" aria-live="polite">
              {query.trim() ? `${shown.length} de ${jobs.length} libros` : `${jobs.length} libros`}
            </span>
          </div>
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
                {shown.map((j) => (
                  <Fragment key={j.id}>
                    <tr>
                      <td className="num">{j.id}</td>
                      <td className="wrap">
                        <Link href={`/admin/jobs/${j.id}`}>{bookName(j)}</Link>
                        {j.title_es && <div className="muted">{j.original_name}</div>}
                      </td>
                      <td>{MODE[j.mode] ?? "Traducción"}</td>
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
                          <button type="button" className="btn ghost book-del" aria-label={`Eliminar ${bookName(j)}`}
                            aria-expanded={confirm === j.id} disabled={busy(j)}
                            title={busy(j) ? "Detén el proceso antes de eliminarlo" : "Eliminar"}
                            onClick={() => askDelete(j.id)}>
                            <IconTrash />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {confirm === j.id && (
                      <tr className="book-confirm-row">
                        <td colSpan={7}>
                          <div className="alert error" role="alertdialog" aria-labelledby={`del-${j.id}`}
                            onKeyDown={(e) => { if (e.key === "Escape") setConfirm(null); }}>
                            <IconWarn />
                            <div>
                              <strong id={`del-${j.id}`}>¿Eliminar «{bookName(j)}»?</strong>
                              <p className="muted">
                                Se borran sus páginas, traducciones, PDF y EPUB generados, evaluaciones del Playground,
                                glosario y términos propios. No se puede deshacer.
                              </p>
                              {deleteError && <p className="error-text">{deleteError}</p>}
                              <div className="row">
                                <button type="button" className="btn danger" disabled={deleting} autoFocus
                                  onClick={() => remove(j)}>
                                  <IconTrash /> {deleting ? "Eliminando…" : "Eliminar"}
                                </button>
                                <button type="button" className="btn secondary" disabled={deleting}
                                  onClick={() => setConfirm(null)}>
                                  <IconX /> Cancelar
                                </button>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
                {shown.length === 0 && (
                  <tr><td colSpan={7}>Ningún libro coincide con «{query.trim()}».</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
