/* Subida de libros: directa a S3 con URL prefirmada y, si no, a través del backend (con progreso). */
import { apiFetch, apiHeaders, parse } from "./http";
import type { JobMode, JobStatus, OcrLang } from "./jobs";

/** Progreso de una subida: bytes enviados y, al terminar, la comprobación en el servidor. */
export type UploadProgress = { phase: "upload"; loaded: number; total: number } | { phase: "checking" };

type XhrResult = { status: number; body: string };
const LOST = "Se perdió la conexión mientras se subía el libro. Revisa que el servicio esté activo e inténtalo de nuevo.";

/** fetch no informa del progreso de subida: XMLHttpRequest sí (upload.onprogress). Rechaza solo por fallo de red. */
function xhrSend(method: string, url: string, body: XMLHttpRequestBodyInit, headers: Record<string, string>,
  onUpload?: (loaded: number, total: number) => void, onUploaded?: () => void): Promise<XhrResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url);
    for (const [k, v] of Object.entries(headers)) xhr.setRequestHeader(k, v);
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onUpload?.(e.loaded, e.total); };
    xhr.upload.onload = () => onUploaded?.();
    xhr.onload = () => resolve({ status: xhr.status, body: xhr.responseText });
    xhr.onerror = () => reject(new Error(LOST));
    xhr.onabort = () => reject(new Error(LOST));
    xhr.send(body);
  });
}

function xhrParse<T>(r: XhrResult): Promise<T> {
  return parse<T>(new Response(r.body || null, { status: r.status, headers: { "Content-Type": "application/json" } }));
}

/**
 * Sube el libro directo al almacenamiento S3 con URL prefirmada (progreso real de bytes) y registra el job.
 * Si el almacenamiento no responde, se sube como antes a través del backend (también con progreso).
 */
export async function uploadBook(
  file: File,
  rightsConfirmed: boolean,
  opts: { mode: JobMode; ocrLang: OcrLang; correct: boolean } = { mode: "translate", ocrLang: "en", correct: false },
  onProgress?: (p: UploadProgress) => void,
): Promise<JobStatus> {
  const progress = (loaded: number, total: number) => onProgress?.({ phase: "upload", loaded, total });
  const checking = () => onProgress?.({ phase: "checking" });
  const json = { "Content-Type": "application/json" };

  let presign: { url: string; key: string; headers: Record<string, string> } | null = null;
  let res: Response | null = null;
  try {
    res = await apiFetch("/api/jobs/presign", { method: "POST", headers: json,
      body: JSON.stringify({ filename: file.name, size: file.size }) });
  } catch {
    res = null; // sin red hasta el backend: lo intentará el respaldo
  }
  if (res?.ok) presign = await res.json();
  else if (res && (res.status === 400 || res.status === 413)) await parse(res); // lanza el mensaje del servidor

  if (presign) {
    let put: XhrResult | null = null;
    try {
      put = await xhrSend("PUT", presign.url, file, presign.headers, progress);
    } catch {
      put = null; // S3 inalcanzable desde el navegador: respaldo
    }
    if (put && put.status >= 200 && put.status < 300) {
      checking();
      let done: Response;
      try {
        done = await apiFetch("/api/jobs/from-upload", { method: "POST", headers: json, body: JSON.stringify({
          key: presign.key, filename: file.name, rights_confirmed: rightsConfirmed, source_lang: "en",
          target_lang: "es", mode: opts.mode, ocr_lang: opts.ocrLang, correct_ocr: opts.correct }) });
      } catch {
        throw new Error(LOST);
      }
      return parse(done);
    }
  }

  // respaldo: multipart a través del backend
  const form = new FormData();
  form.append("file", file);
  form.append("rights_confirmed", String(rightsConfirmed));
  form.append("source_lang", "en");
  form.append("target_lang", "es");
  form.append("mode", opts.mode);
  form.append("ocr_lang", opts.ocrLang);
  form.append("correct_ocr", String(opts.correct));
  progress(0, file.size);
  return xhrParse(await xhrSend("POST", "/api/jobs", form, apiHeaders("POST"), progress, checking));
}
