export type StageState = "completed" | "in_progress" | "pending" | "error" | "cancelled" | "paused";

export type JobMode = "translate" | "digitize" | "prepare"; // prepare: solo extraer la información (Playground)
export type OcrLang = "en" | "es" | "auto";

export interface JobStatus {
  id: number;
  mode: JobMode;
  ocr_lang: OcrLang | null;
  status: "queued" | "running" | "paused" | "cancelled" | "done" | "failed";
  stage: string;
  progress: number;
  current_page: number | null;
  page_count: number;
  document_id: number;
  original_name: string;
  title_es: string | null;
  output_name: string | null;
  error: string | null;
  recomposing: boolean;
  recompose_error: string | null;
  stages: { key: string; label: string; state: StageState }[];
  review_pages: { page: number; reasons: string[] }[];
}

// ---------------------------------------------------------------- sesión
// El token de sesión vive en una cookie HttpOnly que JavaScript no ve. Aquí solo se guarda, en memoria,
// el token CSRF que devuelve /api/auth/me (nunca en localStorage ni en la URL).

let csrfToken: string | null = null;
export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

/** Lo emite parse() cuando el servidor dice que la sesión ya no vale o que falta cambiar la contraseña. */
export const AUTH_EVENT = "astrobooks:auth";

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** Encabezados que el backend exige: el de la aplicación siempre y el CSRF en escrituras. */
export function apiHeaders(method: string): Record<string, string> {
  const h: Record<string, string> = { "X-Requested-With": "traductor" };
  if (UNSAFE.has(method.toUpperCase()) && csrfToken) h["X-CSRF-Token"] = csrfToken;
  return h;
}

/** fetch hacia /api/* con la cookie de sesión, el encabezado de la aplicación y el CSRF. */
export function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  for (const [k, v] of Object.entries(apiHeaders(init.method ?? "GET"))) headers.set(k, v);
  return fetch(url, { ...init, headers, credentials: "same-origin" });
}

/** Error de la API con su código (`REAUTH_REQUIRED`, `LAST_ADMIN`…) además del mensaje. */
export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code: string | null) {
    super(message);
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg =
      res.status === 413
        ? "El archivo es demasiado grande para el límite configurado."
        : res.status >= 500
          ? "El servidor no pudo procesar la solicitud. Verifica que el servicio esté en funcionamiento e inténtalo de nuevo."
          : res.status === 429
            ? "Demasiados intentos. Espera unos minutos e inténtalo de nuevo."
            : "No pudimos completar la acción. Intenta de nuevo.";
    let code: string | null = null;
    try {
      const body = await res.json();
      if (typeof body.message === "string") msg = body.message;
      else if (typeof body.detail === "string") msg = body.detail;
      if (typeof body.code === "string") code = body.code;
    } catch {
      /* respuesta sin JSON */
    }
    if ((res.status === 401 && code === "UNAUTHENTICATED") || code === "PASSWORD_CHANGE_REQUIRED") {
      if (typeof window !== "undefined") window.dispatchEvent(new Event(AUTH_EVENT));
    }
    throw new ApiError(msg, res.status, code);
  }
  return res.json() as Promise<T>;
}

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

export async function getJob(id: string | number): Promise<JobStatus> {
  return parse(await apiFetch(`/api/jobs/${id}`, { cache: "no-store" }));
}

export async function jobAction(id: string | number, action: "cancel" | "resume"): Promise<JobStatus> {
  return parse(await apiFetch(`/api/jobs/${id}/${action}`, { method: "POST" }));
}

export type Provider = "deepseek" | "fake";

export interface TranslationSettings {
  provider: Provider;
  deepseek_model: string;
  deepseek_thinking: "disabled" | "low" | "high" | "max";
  deepseek_concurrency: number;
  deepseek_key_set: boolean;
  deepseek_key_hint: string;
  deepseek_models: string[];
}

type ReadOnly = "deepseek_key_set" | "deepseek_key_hint" | "deepseek_models";

/** Modelos de la API de chat de DeepSeek (el backend valida la misma lista). */
export const DEEPSEEK_MODELS: Record<string, string> = {
  "deepseek-flash": "DeepSeek Flash (V4.1, rápido y barato)",
  "deepseek-v4-pro": "DeepSeek V4 Pro (más capaz, ~3× el precio)",
};

/** Nombres antiguos que pudieron quedar guardados en evaluaciones viejas. */
export const MODEL_ALIASES: Record<string, string> = { "deepseek-pro": "deepseek-v4-pro", "deepseek-v4-flash": "deepseek-flash" };

/** Niveles de razonamiento: `thinking` + `reasoning_effort` de DeepSeek. */
export const THINKING_LEVELS: Record<TranslationSettings["deepseek_thinking"], string> = {
  disabled: "Desactivado (más rápido)", low: "Bajo", high: "Alto (más cuidadoso)", max: "Máximo (más lento y caro)",
};

export type SettingsChanges = Partial<Omit<TranslationSettings, ReadOnly>> & {
  deepseek_api_key?: string;
};

/** Evento para que la barra lateral refresque el método activo tras guardar. */
export const SETTINGS_EVENT = "astrobooks:settings";

/** Nombre corto del método activo, para la barra lateral y la cabecera de Admin. */
export function methodLabel(s: Pick<TranslationSettings, "provider" | "deepseek_model">): string {
  if (s.provider === "deepseek") return `API · ${s.deepseek_model || "DeepSeek"}`;
  return "Prueba sin API";
}

export async function getSettings(): Promise<TranslationSettings> {
  return parse(await apiFetch("/api/settings", { cache: "no-store" }));
}

export async function saveSettings(changes: SettingsChanges): Promise<TranslationSettings> {
  return parse(
    await apiFetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),
  );
}

export async function testSettings(): Promise<{ ok: boolean; provider: Provider; message: string }> {
  return parse(await apiFetch("/api/settings/test", { method: "POST" }));
}

export async function getHealth(): Promise<{
  translation_configured: boolean; provider: Provider; max_upload_mb: number; azw3_available: boolean;
}> {
  return parse(await apiFetch("/api/health", { cache: "no-store" }));
}

// ---------------------------------------------------------------- administración

export async function listJobs(): Promise<JobStatus[]> {
  return parse(await apiFetch("/api/jobs", { cache: "no-store" }));
}

/** Elimina el libro con todo lo suyo (páginas, traducciones, archivos, evaluaciones, glosario propio). */
export async function deleteJob(id: number): Promise<void> {
  await parse(await apiFetch(`/api/jobs/${id}`, { method: "DELETE" }));
}

export interface PageSummary {
  number: number;
  kind: string;
  needs_review: boolean;
  reasons: string[];
  segments: number;
  translated: number;
  edited: number;
  min_scale: number | null;
}

export interface BookInfo {
  title: string;
  subtitle: string | null;
  author: string | null;
  source_lang: string;
  target_lang: string;
}

export interface JobSummary {
  job: JobStatus;
  book: BookInfo;
  totals: { pages: number; ok: number; review: number; by_kind: Record<string, number>; segments: number; edited: number };
  checks: Record<string, boolean>;
  stats: Record<string, number>;
  warnings: string[];
  errors: string[];
  pages: PageSummary[];
}

export interface SegmentRow {
  key: string;
  bbox: [number, number, number, number];
  block_type: string;
  action: "translate" | "keep" | "graphic" | "review";
  source_html: string;
  translation: string | null;
  issues: string[];
  fit_scale: number | null;
  ocr_confidence: number | null;
  edited: boolean;
}

export interface PageSegments {
  number: number;
  width: number;
  height: number;
  kind: string;
  needs_review: boolean;
  reasons: string[];
  segments: SegmentRow[];
}

export async function getSummary(id: string | number): Promise<JobSummary> {
  return parse(await apiFetch(`/api/admin/jobs/${id}/summary`, { cache: "no-store" }));
}

export async function getSegments(id: string | number, page: number): Promise<PageSegments> {
  return parse(await apiFetch(`/api/admin/jobs/${id}/pages/${page}/segments`, { cache: "no-store" }));
}

export async function saveSegment(id: string | number, key: string, translation: string): Promise<SegmentRow> {
  return parse(
    await apiFetch(`/api/admin/jobs/${id}/segments/${encodeURIComponent(key)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ translation }),
    }),
  );
}

export interface BookChapter {
  title: string;
  title_es: string | null;
  level: number;
  pages: string;
  source: "toc" | "detected";
}

export async function listBookChapters(id: string | number): Promise<BookChapter[]> {
  return parse(await apiFetch(`/api/admin/jobs/${id}/chapters`, { cache: "no-store" }));
}

export async function recomposePage(id: string | number, page: number): Promise<JobStatus> {
  return parse(await apiFetch(`/api/admin/jobs/${id}/pages/${page}/recompose`, { method: "POST" }));
}

export interface ProtectedTerm { id: number; term: string; category: string; origin: string; document_id: number | null }
export interface GlossaryEntry {
  id: number; source: string; target: string; document_id: number | null;
  origin: "auto" | "manual"; category: string | null; note: string | null;
}
export interface GlossaryDiscovery {
  status: "idle" | "running" | "done" | "failed"; domain: string | null; done?: number; total?: number;
  count?: number; cost_usd?: number | null; error?: string;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: body === undefined ? undefined : { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export async function listTerms(documentId: number): Promise<ProtectedTerm[]> {
  return parse(await apiFetch(`/api/protected-terms?document_id=${documentId}`, { cache: "no-store" }));
}
export async function addTerm(term: string, category: string, documentId: number | null): Promise<{ id: number }> {
  return parse(await apiFetch("/api/protected-terms", json("POST", { term, category, document_id: documentId })));
}
export async function deleteTerm(id: number): Promise<{ ok: boolean }> {
  return parse(await apiFetch(`/api/protected-terms/${id}`, json("DELETE")));
}
export async function listGlossary(documentId: number): Promise<GlossaryEntry[]> {
  return parse(await apiFetch(`/api/glossary?document_id=${documentId}`, { cache: "no-store" }));
}
export async function addGlossary(source: string, target: string, documentId: number | null): Promise<{ id: number }> {
  return parse(await apiFetch("/api/glossary", json("POST", { source, target, document_id: documentId })));
}
export async function deleteGlossary(id: number): Promise<{ ok: boolean }> {
  return parse(await apiFetch(`/api/glossary/${id}`, json("DELETE")));
}
export async function editGlossary(id: number, patch: { target?: string; note?: string }): Promise<GlossaryEntry> {
  return parse(await apiFetch(`/api/glossary/${id}`, json("PATCH", patch)));
}
export async function glossaryDiscovery(documentId: number): Promise<GlossaryDiscovery> {
  return parse(await apiFetch(`/api/documents/${documentId}/glossary/discover`, { cache: "no-store" }));
}
export async function discoverGlossary(documentId: number): Promise<GlossaryDiscovery> {
  return parse(await apiFetch(`/api/documents/${documentId}/glossary/discover`, json("POST")));
}

// ------------------------------------------------------------------ Administración › Prompts y Playground

export type PromptTask = "translate" | "correct" | "shorten" | "names" | "glossary";
export type PlaygroundTask = "translate" | "correct";

export interface PromptInfo {
  title: string;
  mode: "translate" | "digitize";
  version: string;
  text: string;
  description: string;
  user_template: string;
  output: { deepseek: string };
}

export interface PromptDraft {
  id: number;
  task: PlaygroundTask;
  name: string;
  text: string;
  updated_at: string | null;
}

export interface PlaygroundBook {
  id: number;
  name: string;
  original_name: string;
  page_count: number;
  task: PlaygroundTask;
  prepared: boolean; // subido desde el Playground: analizado y sin traducir
  blocks: number;
  production: boolean; // tiene libro traducido para comparar
}

export interface Chapter {
  title: string;
  level: number;
  pages: string;
  source: "toc" | "detected";
}

export type PlaygroundScope = "page" | "pages" | "chapter" | "book";

export interface PlaygroundPageInfo {
  number: number;
  kind: string; // digital | scanned | mixed | image_only | blank | "" (no guardada)
  blocks: number;
}

export interface Estimate {
  scope: PlaygroundScope;
  pages: number;
  page_spec: string;
  blocks: number;
  chars: number;
  calls_per_variant: number;
  calls: number;
  variants: { label: string; seconds: number | null }[];
  seconds: number | null;
  paid: boolean;
  needs_confirm: boolean;
}

export interface RunRequest {
  job_id: number;
  scope: PlaygroundScope;
  pages: string;
  chapter?: string | null;
  variants: VariantInput[];
  confirm?: boolean;
}

export interface VariantInput {
  provider: Provider;
  model?: string;
  thinking?: string;
  prompt: number | "production";
}

export interface Variant extends Required<Omit<VariantInput, "prompt">> {
  label: string;
  prompt: number | "production";
  prompt_name: string;
  prompt_text: string | null;
}

export interface SegmentOutput {
  output: string | null;
  issues: string[];
  fit?: number | null; // escala de la maquetación (1 = cabe sin reducir)
  layout_issues?: string[];
}

export interface VariantResult {
  label: string;
  segments: Record<string, SegmentOutput>;
  seconds: number;
  calls: number;
  tokens_in: number;
  tokens_out: number;
  tokens_cache_hit?: number;
  cost_usd: number | null; // estimado con la tarifa punta de DeepSeek
  cost_kind: "unknown" | "estimate";
  error: string | null;
  composed?: boolean; // tiene su PDF maquetado
  composed_at?: number;
  compose_error?: string;
  stale_pages?: number[]; // páginas evaluadas con la configuración anterior
  pages?: Record<string, { needs_review: boolean; reasons: string[] }>;
}

export interface RunSummary {
  warn_blocks: number;
  warn_pages: number[];
  won: number;
}

export interface PlaygroundRun {
  id: number;
  job_id: number;
  task: PlaygroundTask;
  scope: PlaygroundScope;
  pages: string;
  chapter: string | null;
  variants: Variant[];
  status: "queued" | "running" | "paused" | "done" | "failed" | "cancelled";
  progress: number;
  current_variant: number | null;
  blocks_done: number | null;
  blocks_total: number | null;
  stage?: "translate" | "compose" | null;
  composing?: string | null;
  trying?: { label: string; page: number } | null;
  votes?: Record<string, string>;
  error: string | null;
  created_at: string | null;
  book: string | null;
  results?: VariantResult[];
  page_list?: number[];
  production?: boolean;
  summary?: Record<string, RunSummary>;
  segments?: { key: string; page: number; block_type: string; source: string; production: string | null }[];
}

export interface PageCell {
  output: string | null;
  warnings: string[];
  fit: number | null;
}

export interface PageBlock {
  key: string;
  bbox: number[];
  block_type: string;
  source: string;
  cols: Record<string, PageCell>;
}

export interface PageMetrics {
  warn_blocks: number;
  min_scale: number | null;
  length_pct: number;
  review: string[];
  stale: boolean;
}

export interface RunPage {
  number: number;
  width: number | null;
  height: number | null;
  blocks: PageBlock[];
  metrics: Record<string, PageMetrics>;
  vote: string | null;
}

export async function getPrompts(): Promise<Record<PromptTask, PromptInfo>> {
  return parse(await apiFetch("/api/admin/prompts", { cache: "no-store" }));
}

export async function listDrafts(): Promise<PromptDraft[]> {
  return parse(await apiFetch("/api/admin/prompt-drafts", { cache: "no-store" }));
}

export async function createDraft(d: Pick<PromptDraft, "task" | "name" | "text">): Promise<PromptDraft> {
  return parse(await apiFetch("/api/admin/prompt-drafts", json("POST", d)));
}

export async function updateDraft(id: number, d: Partial<Pick<PromptDraft, "name" | "text">>): Promise<PromptDraft> {
  return parse(await apiFetch(`/api/admin/prompt-drafts/${id}`, json("PUT", d)));
}

export async function deleteDraft(id: number): Promise<void> {
  await parse(await apiFetch(`/api/admin/prompt-drafts/${id}`, { method: "DELETE" }));
}

/** Elimina el libro y todo su análisis (páginas, bloques, evaluaciones y sus PDFs). */
export async function deletePlaygroundBook(jobId: number): Promise<void> {
  await parse(await apiFetch(`/api/admin/playground/books/${jobId}`, { method: "DELETE" }));
}

export async function listPlaygroundBooks(): Promise<PlaygroundBook[]> {
  return parse(await apiFetch("/api/admin/playground/books", { cache: "no-store" }));
}

export async function listChapters(jobId: number): Promise<Chapter[]> {
  return parse(await apiFetch(`/api/admin/playground/books/${jobId}/chapters`, { cache: "no-store" }));
}

/** Páginas del libro para el selector de alcance: tipo (digital, scanned…) y bloques extraídos. */
export async function listPlaygroundPages(jobId: number): Promise<PlaygroundPageInfo[]> {
  return parse(await apiFetch(`/api/admin/playground/books/${jobId}/pages`, { cache: "no-store" }));
}

export async function estimateRun(body: Omit<RunRequest, "chapter" | "confirm">): Promise<Estimate> {
  return parse(await apiFetch("/api/admin/playground/estimate", json("POST", body)));
}

export async function createRun(body: RunRequest): Promise<PlaygroundRun> {
  return parse(await apiFetch("/api/admin/playground/runs", json("POST", body)));
}

export async function resumeRun(id: number): Promise<PlaygroundRun> {
  return parse(await apiFetch(`/api/admin/playground/runs/${id}/resume`, { method: "POST" }));
}

export async function listRuns(): Promise<PlaygroundRun[]> {
  return parse(await apiFetch("/api/admin/playground/runs", { cache: "no-store" }));
}

export async function getRun(id: number): Promise<PlaygroundRun> {
  return parse(await apiFetch(`/api/admin/playground/runs/${id}`, { cache: "no-store" }));
}

export async function cancelRun(id: number): Promise<PlaygroundRun> {
  return parse(await apiFetch(`/api/admin/playground/runs/${id}/cancel`, { method: "POST" }));
}

export async function getRunPage(id: number, page: number): Promise<RunPage> {
  return parse(await apiFetch(`/api/admin/playground/runs/${id}/pages/${page}`, { cache: "no-store" }));
}

/** Imagen de una página: original, producción o el PDF maquetado de una variante. v cambia al recomponer. */
export function runPageImageUrl(id: number, page: number, col: string, v?: number | string): string {
  return `/api/admin/playground/runs/${id}/pages/${page}/image?col=${encodeURIComponent(col)}&dpi=110${v ? `&v=${v}` : ""}`;
}

export function jobPageImageUrl(jobId: number, page: number, version: "original" | "translated", dpi = 110): string {
  return `/api/jobs/${jobId}/pages/${page}/preview?version=${version}&dpi=${dpi}`;
}

export async function voteRunPage(id: number, page: number, vote: string | null): Promise<{ votes: Record<string, string> }> {
  return parse(await apiFetch(`/api/admin/playground/runs/${id}/votes/${page}`, json("PUT", { vote })));
}

export async function tryVariantPage(id: number, label: string, page: number, variant: VariantInput): Promise<PlaygroundRun> {
  return parse(await apiFetch(`/api/admin/playground/runs/${id}/variants/${label}/try`, json("POST", { page, variant })));
}

export async function composeRun(id: number): Promise<PlaygroundRun> {
  return parse(await apiFetch(`/api/admin/playground/runs/${id}/compose`, { method: "POST" }));
}

// ------------------------------------------------------------------ historial del playground

export interface HistoryBook {
  job_id: number;
  book: string | null;
  attempts: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  last: string | null;
}

export interface AttemptConfig {
  provider: Provider;
  model: string;
  thinking: string;
  prompt: number | "production";
  prompt_name: string;
  prompt_text?: string | null;
}

export interface Attempt {
  id: number;
  run_id: number;
  job_id: number;
  label: string;
  kind: "run" | "try";
  pages: string;
  config: AttemptConfig;
  seconds: number;
  calls: number;
  tokens_in: number;
  tokens_out: number;
  tokens_cache_hit: number;
  cost_usd: number | null;
  error: string | null;
  snapshot: boolean; // tiene copia propia del PDF
  blocks: number;
  created_at: string | null;
  won_pages?: number[];
}

export interface AttemptDetail extends Omit<Attempt, "blocks"> {
  book: string | null;
  task: PlaygroundTask;
  page_list: number[];
  blocks: { key: string; page: number; block_type: string; source: string; output: string | null; warnings: string[] }[];
}

export async function getHistoryBooks(): Promise<HistoryBook[]> {
  return parse(await apiFetch("/api/admin/playground/history", { cache: "no-store" }));
}

export async function getHistory(jobId: number): Promise<{ job_id: number; book: string | null; attempts: Attempt[] }> {
  return parse(await apiFetch(`/api/admin/playground/history/${jobId}`, { cache: "no-store" }));
}

export async function getAttempt(id: number): Promise<AttemptDetail> {
  return parse(await apiFetch(`/api/admin/playground/attempts/${id}`, { cache: "no-store" }));
}

export function attemptImageUrl(id: number, page: number, dpi = 110): string {
  return `/api/admin/playground/attempts/${id}/pages/${page}/image?dpi=${dpi}`;
}

/** Costo estimado en USD; con céntimos de céntimo para pruebas pequeñas. */
export function fmtUsd(v: number | null | undefined): string {
  if (v === null || v === undefined) return "sin tarifa";
  if (v === 0) return "$0";
  return v < 0.01 ? `≈$${v.toFixed(4)}` : `≈$${v.toFixed(2)}`;
}

// ---------------------------------------------------------------- login y cuentas

export type Role = "admin" | "user";

export interface AuthUser {
  id: number;
  email: string;
  name: string;
  role: Role;
  active: boolean;
  must_change_password: boolean;
  temp_password_expires_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AuthState {
  user: AuthUser;
  csrf_token: string;
  session: {
    kind: "normal" | "restricted"; // restricted: solo puede cambiar la contraseña temporal
    expires_at: string;
    idle_timeout_minutes: number;
    reauth_until: string | null;
  };
}

const jsonBody = (method: string, body: unknown): RequestInit => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

/** Sesión actual, o null si no hay (sin avisar a AUTH_EVENT: es la propia consulta del proveedor). */
export async function getMe(): Promise<AuthState | null> {
  const res = await apiFetch("/api/auth/me", { cache: "no-store" });
  if (res.status === 401) return null;
  return parse(res);
}

export async function login(email: string, password: string): Promise<AuthState> {
  return parse(await apiFetch("/api/auth/login", jsonBody("POST", { email, password })));
}

export async function logout(): Promise<void> {
  await parse(await apiFetch("/api/auth/logout", { method: "POST" }));
}

export async function changePassword(current_password: string, new_password: string): Promise<AuthState> {
  return parse(await apiFetch("/api/auth/change-password", jsonBody("POST", { current_password, new_password })));
}

export async function reauthenticate(password: string): Promise<AuthState> {
  return parse(await apiFetch("/api/auth/reauthenticate", jsonBody("POST", { password })));
}

export interface UserPage { items: AuthUser[]; total: number; page: number; page_size: number }
export interface TempPassword { user: AuthUser; temporary_password: string }

export async function listUsers(page = 1, pageSize = 50): Promise<UserPage> {
  return parse(await apiFetch(`/api/users?page=${page}&page_size=${pageSize}`, { cache: "no-store" }));
}

export async function createUser(body: { email: string; name: string; role: Role }): Promise<TempPassword> {
  return parse(await apiFetch("/api/users", jsonBody("POST", body)));
}

export async function updateUser(id: number, patch: { name?: string; role?: Role; active?: boolean }): Promise<AuthUser> {
  return parse(await apiFetch(`/api/users/${id}`, jsonBody("PATCH", patch)));
}

export async function resetUserPassword(id: number): Promise<TempPassword> {
  return parse(await apiFetch(`/api/users/${id}/reset-password`, { method: "POST" }));
}
