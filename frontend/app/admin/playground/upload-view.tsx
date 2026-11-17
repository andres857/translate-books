"use client";

/* Vista de subida del Playground (página propia con cabecera y tarjeta) y la franja de estado de la
   preparación que se ve en la vista de alcance o encima de la mesa. El estado vive en usePreparation. */
import { useRef, type ReactNode } from "react";
import { UploadProgressBar } from "@/app/components/upload-progress";
import { IconCheck, IconHourglass, IconUpload, IconWarn, IconX } from "../../components/art";
import { fmtN } from "./shared";
import type { Preparation } from "./use-preparation";

export type Notice = { kind: "ok" | "error"; text: string } | null;

export function UploadView({ p, notice }: { p: Preparation; notice: Notice }) {
  const { prep, prepDone, file, uploading } = p;
  const fileRef = useRef<HTMLInputElement>(null); // el input oculto de archivo; la zona lo abre al pulsar
  const prepFailed = prep?.status === "failed" || prep?.status === "cancelled";
  const prepStage = prep?.stages.find((st) => st.state === "in_progress")?.label ?? (prep?.status === "queued" ? "En cola" : "…");
  return (
    <>
      <div className="page-head">
        <div>
          <h1>{prepDone ? "Libro listo para evaluar" : prep ? "Preparando el libro" : "Subir un libro para evaluar"}</h1>
          <p>
            Solo se prepara: se analiza el PDF, se separa por capítulos y se protegen números, glifos y términos.
            No se traduce nada ni se gasta saldo hasta que pulses «Ejecutar».
          </p>
        </div>
        <button type="button" className="btn secondary" disabled={uploading !== false} onClick={p.closeUpload}>Volver al alcance</button>
      </div>
      <section className="card pg-upload-card" aria-label="Libro nuevo">
        {prepDone ? (
          <section className="pg-upload-box pg-upload-result" aria-live="polite" aria-labelledby="pg-prep-done">
            <span className="pg-upload-icon ok"><IconCheck /></span>
            <div className="stack pg-upload-text">
              <strong id="pg-prep-done">Libro preparado sin traducir</strong>
              <span className="muted pg-ellipsis" title={prepDone.name}>{prepDone.name}</span>
            </div>
            <dl className="pg-upload-stats">
              <div><dt>Páginas</dt><dd>{fmtN.format(prepDone.pages)}</dd></div>
              <div><dt>Bloques</dt><dd>{fmtN.format(prepDone.blocks)}</dd></div>
              <div><dt>Capítulos</dt><dd>{prepDone.chapters ? fmtN.format(prepDone.chapters) : "—"}</dd></div>
            </dl>
            <span className="muted pg-upload-text">
              {prepDone.chapters
                ? `${prepDone.detected ? "Capítulos detectados por los títulos. " : ""}Elige un capítulo o un intervalo de páginas.`
                : "No se detectaron capítulos: define un intervalo de páginas para evaluar."}
            </span>
          </section>
        ) : prep ? (
          <section className="pg-upload-box" aria-live="polite" aria-labelledby="pg-prep-title">
            <div className="stack">
              <strong id="pg-prep-title" className="pg-ellipsis" title={prep.original_name}>Preparando «{prep.original_name}»</strong>
              <div className="pct">{prepFailed ? "—" : `${Math.round(prep.progress)} %`}
                <small>{prepFailed ? "detenido" : `${prepStage}${prep.current_page ? ` · pág. ${prep.current_page} de ${prep.page_count}` : ""}`}</small>
              </div>
              <div className="progress" aria-label="Preparación"><div style={{ width: `${prep.progress}%` }} /></div>
            </div>
            <ul className="stages">
              {prep.stages.map((st) => (
                <li key={st.key} className={st.state}>
                  <span className="name">{st.label}</span>
                  {st.state !== "pending" && (
                    <span className={`badge ${st.state}`}>
                      {st.state === "completed" ? <IconCheck /> : st.state === "in_progress" ? <IconHourglass /> : <IconX />}
                      {st.state === "completed" ? "Completado" : st.state === "in_progress" ? "En progreso" : st.state === "paused" ? "En pausa" : "Error"}
                    </span>
                  )}
                </li>
              ))}
            </ul>
            {prepFailed && (
              <div className="alert error" role="alert">
                <IconWarn />
                <span>{prep.error ?? "No se pudo preparar el libro."}</span>
              </div>
            )}
          </section>
        ) : uploading !== false && file ? (
          <section className="pg-upload-box">
            <UploadProgressBar name={file.name} progress={uploading} />
          </section>
        ) : (
        <div className="pg-upload-box">
          <div
            className={`dropzone ${p.drag ? "active" : ""}`}
            role="button"
            tabIndex={0}
            aria-label="Zona para arrastrar y soltar el PDF o seleccionarlo"
            onClick={() => fileRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileRef.current?.click(); }
            }}
            onDragOver={(e) => { e.preventDefault(); p.setDrag(true); }}
            onDragLeave={() => p.setDrag(false)}
            onDrop={(e) => { e.preventDefault(); p.setDrag(false); p.setFile(e.dataTransfer.files?.[0] ?? null); }}
          >
            <IconUpload />
            {file ? (
              <p><span className="file-chip">{file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB</span></p>
            ) : (
              <p><strong>Arrastra el PDF aquí</strong> o <strong>haz clic para seleccionarlo</strong></p>
            )}
            <p className="muted">{file ? "Haz clic para elegir otro archivo" : "Solo archivos PDF"}</p>
            <input ref={fileRef} id="pg-file" type="file" accept="application/pdf,.pdf" hidden
              onChange={(e) => p.setFile(e.target.files?.[0] ?? null)} />
          </div>
          <label className="check">
            <input type="checkbox" checked={p.rights} onChange={(e) => p.setRights(e.target.checked)} />
            <span>Tengo derechos de uso sobre este libro</span>
          </label>
          {notice?.kind === "error" && (
            <div className="alert error" role="alert">
              <IconWarn />
              <span>{notice.text}</span>
            </div>
          )}
        </div>
        )}
      <div className="pg-upload-actions">
        {prepDone ? (
          <>
            <span className="muted">Sin traducir · no se ha gastado saldo</span>
            <span className="pg-spacer" />
            <button type="button" className="btn secondary" onClick={() => p.setPrepDone(null)}>Subir otro libro</button>
            <button type="button" className="btn" onClick={p.closeUpload}>Elegir qué evaluar</button>
          </>
        ) : prep ? (
          <>
            <span className="muted">{prepFailed ? "La preparación se ha detenido" : "Puedes volver: la preparación sigue en segundo plano"}</span>
            <span className="pg-spacer" />
            {prepFailed ? (
              <>
                <button type="button" className="btn secondary" onClick={() => { p.setPrep(null); p.closeUpload(); }}>Cancelar</button>
                <button type="button" className="btn" onClick={() => p.setPrep(null)}>Probar de nuevo</button>
              </>
            ) : null}
          </>
        ) : (
          <>
            <span className="muted">{uploading !== false ? "No cierres esta página hasta que termine la subida"
              : file ? (p.rights ? "Listo para preparar" : "Confirma que tienes derechos de uso") : "Elige un PDF"}</span>
            <span className="pg-spacer" />
            <button type="button" className="btn secondary" disabled={uploading !== false} onClick={p.closeUpload}>Cancelar</button>
            <button type="button" className="btn" disabled={!file || !p.rights || uploading !== false} onClick={p.prepareUpload}>
              {uploading !== false ? "Subiendo…" : "Preparar libro"}
            </button>
          </>
        )}
      </div>
      </section>
    </>
  );
}

/** Progreso de la preparación y avisos (columna de libros de la vista inicial o encima de la mesa). */
export function PrepArea({ p, notice, onCloseNotice }: { p: Preparation; notice: Notice; onCloseNotice: () => void }): ReactNode {
  const { prep } = p;
  return (
    <>
        {prep && (
          <div className="pg-status" aria-live="polite">
            <div className="progress" aria-label="Preparación"><div style={{ width: `${prep.progress}%` }} /></div>
            <span className="muted">
              Preparando «{prep.original_name}»: {prep.stages.find((s) => s.state === "in_progress")?.label ?? (prep.status === "queued" ? "en cola" : "…")}
              {prep.current_page ? ` · pág. ${prep.current_page} de ${prep.page_count}` : ""} · sin traducir
            </span>
            {(prep.status === "failed" || prep.status === "cancelled") && (
              <button type="button" className="btn ghost" onClick={() => p.setPrep(null)}>Cerrar</button>
            )}
          </div>
        )}
        {notice && (
          <div className={`alert ${notice.kind === "ok" ? "ok" : "error"}`} role={notice.kind === "ok" ? "status" : "alert"}>
            {notice.kind === "ok" ? <IconCheck /> : <IconWarn />}
            <span>{notice.text}</span>
            <button type="button" className="btn ghost" onClick={onCloseNotice}>Cerrar</button>
          </div>
        )}
    </>
  );
}
