import type { UploadProgress } from "@/lib/api";

const fmtMb = new Intl.NumberFormat("es", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const mb = (bytes: number) => fmtMb.format(bytes / 1024 / 1024);

/** Barra de subida con el progreso real de bytes; tras el 100 %, «Comprobando…» con barra indeterminada. */
export function UploadProgressBar({ name, progress, label = "Comprobando el PDF…" }: {
  name: string;
  progress: UploadProgress | null;
  label?: string;
}) {
  const checking = progress?.phase === "checking";
  const loaded = progress?.phase === "upload" ? progress.loaded : 0;
  const total = progress?.phase === "upload" ? progress.total : 0;
  const pct = checking ? 100 : total ? Math.min(100, Math.floor((loaded / total) * 100)) : 0;
  return (
    <div className="upload-progress" aria-live="polite">
      <div className="upload-progress-head">
        <strong title={name}>{name}</strong>
        <span>{checking ? label : `${pct} %`}</span>
      </div>
      <div className={`progress${checking ? " indeterminate" : ""}`} role="progressbar" aria-label={`Subida de ${name}`}
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={checking ? undefined : pct}
        aria-valuetext={checking ? label : `${pct} %`}>
        <div style={checking ? undefined : { width: `${pct}%` }} />
      </div>
      <span className="muted">
        {checking ? "Archivo subido. El servidor lo está validando." : total ? `${mb(loaded)} de ${mb(total)} MB` : "Preparando la subida…"}
      </span>
    </div>
  );
}
