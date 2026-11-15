"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getHealth, uploadBook, type JobMode, type OcrLang } from "@/lib/api";
import { IconArrowRight, IconInfo, IconUpload, IconWarn } from "./components/art";

export default function UploadPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [rights, setRights] = useState(false);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [maxMb, setMaxMb] = useState(200);
  const [configured, setConfigured] = useState(true);
  const [mode, setMode] = useState<JobMode>("translate");
  const [ocrLang, setOcrLang] = useState<OcrLang>("en");
  const [correct, setCorrect] = useState(true);

  useEffect(() => {
    getHealth()
      .then((h) => {
        setMaxMb(h.max_upload_mb);
        setConfigured(h.translation_configured);
      })
      .catch(() => setError("No pudimos conectar con el servidor. Verifica que esté en funcionamiento."));
  }, []);

  function pick(f: File | undefined | null) {
    setError(null);
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) return setError("Solo se admiten archivos PDF.");
    if (f.size > maxMb * 1024 * 1024) return setError(`El archivo supera el límite de ${maxMb} MB.`);
    setFile(f);
  }

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const job = await uploadBook(file, rights, { mode, ocrLang, correct });
      router.push(`/jobs/${job.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <main>
      <div className="page-head">
        <div>
          <h1>Traductor de libros</h1>
          <p>Sube un libro en PDF en inglés y recibe su versión en español con el mismo diseño.</p>
        </div>
      </div>

      {!configured && (
        <div className="alert" role="status">
          <IconWarn />
          <span>
            El modo de traducción elegido aún no está listo. Revísalo en <Link href="/admin/settings">Configuración</Link>.
          </span>
        </div>
      )}

      <section className="card" aria-labelledby="upload-title">
        <h2 id="upload-title">Elige tu libro</h2>

        <div
          className={`dropzone ${drag ? "active" : ""}`}
          role="button"
          tabIndex={0}
          aria-label="Zona para arrastrar y soltar el PDF o seleccionarlo"
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            pick(e.dataTransfer.files?.[0]);
          }}
        >
          <IconUpload />
          {file ? (
            <p><span className="file-chip">{file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB</span></p>
          ) : (
            <p><strong>Arrastra el PDF aquí</strong> o <strong>haz clic para seleccionarlo</strong></p>
          )}
          <p className="muted">{file ? "Haz clic para elegir otro archivo" : `Tamaño máximo: ${maxMb} MB`}</p>
          <input ref={inputRef} type="file" accept="application/pdf,.pdf" hidden onChange={(e) => pick(e.target.files?.[0])} />
        </div>

        <div className="modes" role="radiogroup" aria-label="Qué hacer con el libro">
          <button type="button" role="radio" aria-checked={mode === "translate"}
            className={`mode ${mode === "translate" ? "on" : ""}`} onClick={() => setMode("translate")}>
            <strong>Traducir al español</strong>
            <span>PDF en español con el mismo diseño, y versión para Kindle.</span>
          </button>
          <button type="button" role="radio" aria-checked={mode === "digitize"}
            className={`mode ${mode === "digitize" ? "on" : ""}`} onClick={() => setMode("digitize")}>
            <strong>Solo digitalizar</strong>
            <span>Convierte un PDF escaneado en uno con texto seleccionable y buscable, y versión para Kindle. Sin traducir.</span>
          </button>
        </div>

        {mode === "translate" ? (
          <div className="form-grid">
            <label className="control">
              Idioma de origen
              <select defaultValue="en"><option value="en">Inglés</option></select>
            </label>
            <label className="control">
              Idioma de destino
              <select defaultValue="es"><option value="es">Español</option></select>
            </label>
          </div>
        ) : (
          <div className="form-grid">
            <label className="control">
              Idioma del libro
              <select value={ocrLang} onChange={(e) => setOcrLang(e.target.value as OcrLang)}>
                <option value="en">Inglés</option>
                <option value="es">Español</option>
                <option value="auto">Inglés y español</option>
              </select>
            </label>
            <label className="check">
              <input type="checkbox" checked={correct} onChange={(e) => setCorrect(e.target.checked)} />
              <span>
                Corregir errores del OCR con el modelo de <Link href="/admin/settings">Configuración</Link> (mejora el texto
                del EPUB; el PDF conserva la capa de OCR original).
              </span>
            </label>
          </div>
        )}

        <div className="alert">
          <IconInfo />
          <span>
            Funciona mejor con PDF digitales (exportados desde un programa de diseño). Los PDF escaneados pueden
            requerir más revisión. No se admiten PDF protegidos con contraseña.
          </span>
        </div>

        <label className="check">
          <input type="checkbox" checked={rights} onChange={(e) => setRights(e.target.checked)} />
          <span>Confirmo que tengo derechos para traducir y usar este libro.</span>
        </label>

        {error && (
          <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>
        )}

        <div className="row">
          <button className="btn" disabled={!file || !rights || busy} onClick={submit}>
            {busy ? "Subiendo…" : mode === "translate" ? "Traducir libro" : "Digitalizar libro"} {!busy && <IconArrowRight />}
          </button>
        </div>
      </section>
    </main>
  );
}
