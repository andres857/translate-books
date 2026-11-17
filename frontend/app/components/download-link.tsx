"use client";

/* Enlace de descarga de un libro. Antes de navegar comprueba que el trabajo siga terminado: si se está
   recomponiendo o la sesión caducó, avisa en la página (o vuelve al login) en vez de abrir el JSON de error
   del API. La descarga en sí es un enlace normal: el archivo no pasa por la memoria de la pestaña. */
import { useState, type MouseEvent, type ReactNode } from "react";
import { getJob, type JobStatus } from "@/lib/api";

export const NOT_READY = "El libro traducido todavía no está listo: se está procesando o recomponiendo. Inténtalo de nuevo en unos segundos.";

export function DownloadLink({ jobId, href, className, role, disabled, onProblem, children }: {
  jobId: number;
  href: string;
  className?: string;
  role?: string;
  /** p. ej. mientras se recompone una página: sin enlace y con aspecto deshabilitado */
  disabled?: boolean;
  /** mensaje para mostrar (null = todo bien) y, si se consultó, el estado actual del trabajo */
  onProblem: (message: string | null, job?: JobStatus) => void;
  children: ReactNode;
}) {
  const [checking, setChecking] = useState(false);

  async function click(e: MouseEvent<HTMLAnchorElement>) {
    // abrir en otra pestaña o guardar como: se respeta el gesto del navegador
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    if (checking) return;
    setChecking(true);
    try {
      const job = await getJob(jobId); // un 401 ya lleva al login (AUTH_EVENT en parse())
      if (job.status !== "done" || job.recomposing) {
        onProblem(NOT_READY, job);
        return;
      }
      onProblem(null, job);
      window.location.assign(href);
    } catch (err) {
      onProblem((err as Error).message);
    } finally {
      setChecking(false);
    }
  }

  const off = disabled || checking;
  return (
    <a className={className} role={role} href={disabled ? undefined : href} aria-disabled={off || undefined}
      onClick={disabled ? undefined : click}>
      {children}
    </a>
  );
}
