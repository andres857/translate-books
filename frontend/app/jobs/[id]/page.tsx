"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, getHealth, getJob, jobAction, type JobStatus, type StageState } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { IconArrowLeft, IconCheck, IconDownload, IconHourglass, IconRefresh, IconWarn, IconX } from "../../components/art";

const STATE_TEXT: Record<StageState, string> = {
  completed: "Completado",
  in_progress: "En progreso",
  pending: "Pendiente",
  error: "Error",
  cancelled: "Cancelado",
  paused: "En pausa",
};

const STAGE_MESSAGE: Record<string, string> = {
  analyze: "Estamos analizando las páginas del libro.",
  ocr: "Estamos buscando texto dentro de las imágenes.",
  protect: "Estamos identificando nombres, códigos y términos que no deben cambiar.",
  translate: "Estamos traduciendo el contenido.",
  rebuild: "Estamos colocando la traducción en cada página.",
  validate: "Estamos revisando que el libro traducido esté completo.",
};

const DIGITIZE_MESSAGE: Record<string, string> = {
  analyze: "Estamos analizando qué páginas necesitan reconocimiento de texto.",
  ocr: "Estamos reconociendo el texto de las páginas escaneadas (OCR).",
  correct: "El modelo está corrigiendo errores de reconocimiento.",
  compose: "Estamos escribiendo el texto con fuentes reales en cada página.",
  validate: "Estamos revisando el PDF digital.",
};

// estados en los que el trabajo no avanza solo: se deja de consultar (reanudar vuelve a «queued» y reinicia el
// sondeo). `paused` hoy solo lo usan las evaluaciones del Playground, pero el backend lo acepta al reanudar.
const FINAL: JobStatus["status"][] = ["done", "failed", "cancelled", "paused"];

function BadgeIcon({ state }: { state: StageState }) {
  if (state === "completed") return <IconCheck />;
  if (state === "in_progress") return <IconHourglass />;
  if (state === "error" || state === "cancelled") return <IconX />;
  return null;
}

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { isAdmin } = useAuth();
  const { id } = use(params);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(false); // 404/403: no existe o no es de este usuario
  const [azw3, setAzw3] = useState(true);

  useEffect(() => {
    getHealth().then((h) => setAzw3(h.azw3_available)).catch(() => undefined);
  }, []);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const j = await getJob(id);
        if (!alive) return;
        setJob(j);
        setError(null);
        if (!FINAL.includes(j.status)) timer = setTimeout(tick, 1500);
      } catch (e) {
        if (!alive) return;
        // no existe o no es tuyo: reintentar no lo va a cambiar. Solo se reintenta ante red caída o 5xx
        if (e instanceof ApiError && (e.status === 404 || e.status === 403)) {
          setMissing(true);
          return;
        }
        setError((e as Error).message);
        timer = setTimeout(tick, 4000);
      }
    };
    tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [id, job?.status === "queued"]); // eslint-disable-line react-hooks/exhaustive-deps

  async function act(action: "cancel" | "resume") {
    try {
      setJob(await jobAction(id, action));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (missing) {
    return (
      <main>
        <Link href="/" className="back"><IconArrowLeft width={16} height={16} /> Libros</Link>
        <section className="card">
          <h1>No encontramos ese libro</h1>
          <p className="muted">Puede que se haya eliminado o que no esté en tu lista.</p>
          <p><Link className="btn secondary" href="/">Ir a Libros</Link></p>
        </section>
      </main>
    );
  }

  if (!job) {
    return (
      <main>
        <section className="card"><p>{error ?? "Cargando…"}</p></section>
      </main>
    );
  }

  const done = job.status === "done";
  const active = job.status === "queued" || job.status === "running";
  const stopped = job.status === "cancelled" || job.status === "failed" || job.status === "paused";
  const message =
    job.recomposing ? "Estamos recomponiendo una página corregida." :
    job.status === "queued" ? "Tu libro está en la cola y comenzará en breve." :
    job.status === "cancelled" ? "El proceso fue cancelado. Puedes reanudarlo cuando quieras." :
    job.status === "failed" ? "El proceso se detuvo." :
    job.status === "paused" ? "El proceso está en pausa." :
    (job.mode === "digitize" ? DIGITIZE_MESSAGE : STAGE_MESSAGE)[job.stage] ?? "Procesando…";

  return (
    <main>
      <Link href="/" className="back"><IconArrowLeft width={16} height={16} /> Libros</Link>

      <div className="page-head">
        <div>
          <h1>{done ? "Tu libro está listo" : job.mode === "digitize" ? "Digitalizando tu libro" : "Traduciendo tu libro"}</h1>
          <p>{job.original_name.replace(/\.pdf$/i, "")}{job.page_count ? ` · ${job.page_count} páginas` : ""}</p>
        </div>
        {isAdmin && <Link className="btn secondary" href={`/admin/jobs/${job.id}`}>Ver en administración</Link>}
      </div>

      {error && <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>}
      {job.error && <div className="alert error" role="alert"><IconWarn /><span>{job.error}</span></div>}

      {!done && (
        <section className="card" aria-live="polite">
          <h2>{message}</h2>
          <div className={`progress ${active ? "" : "idle"}`} role="progressbar" aria-valuenow={job.progress}
            aria-valuemin={0} aria-valuemax={100} aria-label="Avance del proceso">
            <div style={{ width: `${Math.max(job.progress, active ? 3 : 0)}%` }} />
          </div>
          <p className="pct">
            {Math.round(job.progress)}%
            {job.current_page ? <small>página {job.current_page} de {job.page_count}</small> : null}
          </p>
          <div className="row">
            {active && (
              <button className="btn secondary" onClick={() => act("cancel")}><IconX /> Cancelar</button>
            )}
            {stopped && (
              <button className="btn" onClick={() => act("resume")}><IconRefresh /> Reanudar</button>
            )}
          </div>
          <p className="muted">
            Puede tardar unos minutos. Puedes cerrar esta ventana y volver más tarde a esta misma dirección: el
            proceso sigue en curso.
          </p>
        </section>
      )}

      {done && (
        <section className="card">
          <div className="result">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/api/jobs/${job.id}/pages/1/preview?version=translated&dpi=60`} alt="Portada del libro" />
            <div>
              <h2>Resultado</h2>
              <dl className="facts">
                <div><dt>Archivo</dt><dd>{job.output_name}</dd></div>
                <div><dt>Páginas</dt><dd>{job.page_count}</dd></div>
                <div><dt>Páginas para revisar</dt><dd>{job.review_pages.length}</dd></div>
              </dl>
              <div className="row">
                <a className="btn" href={`/api/jobs/${job.id}/download`}><IconDownload /> Descargar PDF</a>
                <a className="btn secondary" href={`/api/jobs/${job.id}/download?format=epub`}><IconDownload /> Kindle (EPUB)</a>
                <a className="btn secondary" href={azw3 ? `/api/jobs/${job.id}/download?format=azw3` : undefined}
                  aria-disabled={!azw3}><IconDownload /> Kindle (AZW3)</a>
                <a className="btn ghost" href={`/api/jobs/${job.id}/report`}>Descargar reporte</a>
              </div>
              {!azw3 && (
                <p className="muted">
                  El AZW3 necesita Calibre en el equipo del servidor (<code>sudo apt install calibre</code>).
                </p>
              )}
              <p className="muted">
                Para leerlo en tu Kindle: copia el AZW3 por USB, o envía el EPUB con{" "}
                <a href="https://www.amazon.com/sendtokindle" target="_blank" rel="noreferrer">Send to Kindle</a>{" "}
                (web, hasta 200 MB) o por correo a tu dirección @kindle.com (hasta 50 MB). La primera descarga del
                EPUB o del AZW3 puede tardar unos segundos.
              </p>
            </div>
          </div>
          {job.review_pages.length > 0 && (
            <div className="alert">
              <IconWarn />
              <div>
                <strong>Páginas que conviene revisar:</strong>
                <ul>
                  {job.review_pages.slice(0, 20).map((p) => (
                    <li key={p.page}>Página {p.page}: {p.reasons.join("; ")}</li>
                  ))}
                </ul>
                {job.review_pages.length > 20 && <p>… y {job.review_pages.length - 20} más.</p>}
                {isAdmin && <p><Link href={`/admin/jobs/${job.id}`}>Revisarlas en administración</Link></p>}
              </div>
            </div>
          )}
        </section>
      )}

      <section className="card">
        <h2>Etapas</h2>
        <ul className="stages">
          {job.stages.map((s) => (
            <li key={s.key} className={s.state}>
              <span className="name">{s.label}</span>
              <span className={`badge ${s.state}`}><BadgeIcon state={s.state} /> {STATE_TEXT[s.state]}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
