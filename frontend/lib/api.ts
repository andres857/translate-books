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

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg =
      res.status === 413
        ? "El archivo es demasiado grande para el límite configurado."
        : res.status >= 500
          ? "El servidor no pudo procesar la solicitud. Verifica que el servicio esté en funcionamiento e inténtalo de nuevo."
          : "No pudimos completar la acción. Intenta de nuevo.";
    try {
      const body = await res.json();
      if (typeof body.detail === "string") msg = body.detail;
    } catch {
      /* respuesta sin JSON */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export async function uploadBook(
  file: File,
  rightsConfirmed: boolean,
  opts: { mode: JobMode; ocrLang: OcrLang; correct: boolean } = { mode: "translate", ocrLang: "en", correct: false },
): Promise<JobStatus> {
  const form = new FormData();
  form.append("file", file);
  form.append("rights_confirmed", String(rightsConfirmed));
  form.append("source_lang", "en");
  form.append("target_lang", "es");
  form.append("mode", opts.mode);
  form.append("ocr_lang", opts.ocrLang);
  form.append("correct_ocr", String(opts.correct));
  let res: Response;
  try {
    res = await fetch("/api/jobs", { method: "POST", body: form });
  } catch {
    throw new Error("Se perdió la conexión mientras se subía el libro. Revisa que el servicio esté activo e inténtalo de nuevo.");
  }
  return parse(res);
}

export async function getJob(id: string | number): Promise<JobStatus> {
  return parse(await fetch(`/api/jobs/${id}`, { cache: "no-store" }));
}

export async function jobAction(id: string | number, action: "cancel" | "resume"): Promise<JobStatus> {
  return parse(await fetch(`/api/jobs/${id}/${action}`, { method: "POST" }));
}

export type Provider = "deepseek" | "fake";

export interface TranslationSettings {
  provider: Provider;
  deepseek_model: string;
  deepseek_thinking: "disabled" | "low" | "high" | "max";
  deepseek_concurrency: number;
  deepseek_key_set: boolean;
  deepseek_key_hint: string;
}

type ReadOnly = "deepseek_key_set" | "deepseek_key_hint";

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
  return parse(await fetch("/api/settings", { cache: "no-store" }));
}

export async function saveSettings(changes: SettingsChanges): Promise<TranslationSettings> {
  return parse(
    await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),
  );
}

export async function testSettings(): Promise<{ ok: boolean; provider: Provider; message: string }> {
  return parse(await fetch("/api/settings/test", { method: "POST" }));
}

export async function getHealth(): Promise<{
  translation_configured: boolean; provider: Provider; max_upload_mb: number; azw3_available: boolean;
}> {
  return parse(await fetch("/api/health", { cache: "no-store" }));
}

// ---------------------------------------------------------------- administración

export async function listJobs(): Promise<JobStatus[]> {
  return parse(await fetch("/api/jobs", { cache: "no-store" }));
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

export interface JobSummary {
  job: JobStatus;
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
  return parse(await fetch(`/api/admin/jobs/${id}/summary`, { cache: "no-store" }));
}

export async function getSegments(id: string | number, page: number): Promise<PageSegments> {
  return parse(await fetch(`/api/admin/jobs/${id}/pages/${page}/segments`, { cache: "no-store" }));
}

export async function saveSegment(id: string | number, key: string, translation: string): Promise<SegmentRow> {
  return parse(
    await fetch(`/api/admin/jobs/${id}/segments/${encodeURIComponent(key)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ translation }),
    }),
  );
}

export async function recomposePage(id: string | number, page: number): Promise<JobStatus> {
  return parse(await fetch(`/api/admin/jobs/${id}/pages/${page}/recompose`, { method: "POST" }));
}

export interface ProtectedTerm { id: number; term: string; category: string; origin: string; document_id: number | null }
export interface GlossaryEntry { id: number; source: string; target: string; document_id: number | null }

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: body === undefined ? undefined : { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export async function listTerms(documentId: number): Promise<ProtectedTerm[]> {
  return parse(await fetch(`/api/protected-terms?document_id=${documentId}`, { cache: "no-store" }));
}
export async function addTerm(term: string, category: string, documentId: number | null): Promise<{ id: number }> {
  return parse(await fetch("/api/protected-terms", json("POST", { term, category, document_id: documentId })));
}
export async function deleteTerm(id: number): Promise<{ ok: boolean }> {
  return parse(await fetch(`/api/protected-terms/${id}`, json("DELETE")));
}
export async function listGlossary(documentId: number): Promise<GlossaryEntry[]> {
  return parse(await fetch(`/api/glossary?document_id=${documentId}`, { cache: "no-store" }));
}
export async function addGlossary(source: string, target: string, documentId: number | null): Promise<{ id: number }> {
  return parse(await fetch("/api/glossary", json("POST", { source, target, document_id: documentId })));
}
export async function deleteGlossary(id: number): Promise<{ ok: boolean }> {
  return parse(await fetch(`/api/glossary/${id}`, json("DELETE")));
}

// ------------------------------------------------------------------ Administración › Prompts y Playground

export type PromptTask = "translate" | "correct" | "shorten" | "names";
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
  cost_usd: number | null;
  cost_kind: "unknown";
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
  return parse(await fetch("/api/admin/prompts", { cache: "no-store" }));
}

export async function listDrafts(): Promise<PromptDraft[]> {
  return parse(await fetch("/api/admin/prompt-drafts", { cache: "no-store" }));
}

export async function createDraft(d: Pick<PromptDraft, "task" | "name" | "text">): Promise<PromptDraft> {
  return parse(await fetch("/api/admin/prompt-drafts", json("POST", d)));
}

export async function updateDraft(id: number, d: Partial<Pick<PromptDraft, "name" | "text">>): Promise<PromptDraft> {
  return parse(await fetch(`/api/admin/prompt-drafts/${id}`, json("PUT", d)));
}

export async function deleteDraft(id: number): Promise<void> {
  await parse(await fetch(`/api/admin/prompt-drafts/${id}`, { method: "DELETE" }));
}

export async function listPlaygroundBooks(): Promise<PlaygroundBook[]> {
  return parse(await fetch("/api/admin/playground/books", { cache: "no-store" }));
}

export async function listChapters(jobId: number): Promise<Chapter[]> {
  return parse(await fetch(`/api/admin/playground/books/${jobId}/chapters`, { cache: "no-store" }));
}

/** Páginas del libro para el selector de alcance: tipo (digital, scanned…) y bloques extraídos. */
export async function listPlaygroundPages(jobId: number): Promise<PlaygroundPageInfo[]> {
  return parse(await fetch(`/api/admin/playground/books/${jobId}/pages`, { cache: "no-store" }));
}

export async function estimateRun(body: Omit<RunRequest, "chapter" | "confirm">): Promise<Estimate> {
  return parse(await fetch("/api/admin/playground/estimate", json("POST", body)));
}

export async function createRun(body: RunRequest): Promise<PlaygroundRun> {
  return parse(await fetch("/api/admin/playground/runs", json("POST", body)));
}

export async function resumeRun(id: number): Promise<PlaygroundRun> {
  return parse(await fetch(`/api/admin/playground/runs/${id}/resume`, { method: "POST" }));
}

export async function listRuns(): Promise<PlaygroundRun[]> {
  return parse(await fetch("/api/admin/playground/runs", { cache: "no-store" }));
}

export async function getRun(id: number): Promise<PlaygroundRun> {
  return parse(await fetch(`/api/admin/playground/runs/${id}`, { cache: "no-store" }));
}

export async function cancelRun(id: number): Promise<PlaygroundRun> {
  return parse(await fetch(`/api/admin/playground/runs/${id}/cancel`, { method: "POST" }));
}

export async function getRunPage(id: number, page: number): Promise<RunPage> {
  return parse(await fetch(`/api/admin/playground/runs/${id}/pages/${page}`, { cache: "no-store" }));
}

/** Imagen de una página: original, producción o el PDF maquetado de una variante. v cambia al recomponer. */
export function runPageImageUrl(id: number, page: number, col: string, v?: number | string): string {
  return `/api/admin/playground/runs/${id}/pages/${page}/image?col=${encodeURIComponent(col)}&dpi=110${v ? `&v=${v}` : ""}`;
}

export function jobPageImageUrl(jobId: number, page: number, version: "original" | "translated", dpi = 110): string {
  return `/api/jobs/${jobId}/pages/${page}/preview?version=${version}&dpi=${dpi}`;
}

export async function voteRunPage(id: number, page: number, vote: string | null): Promise<{ votes: Record<string, string> }> {
  return parse(await fetch(`/api/admin/playground/runs/${id}/votes/${page}`, json("PUT", { vote })));
}

export async function tryVariantPage(id: number, label: string, page: number, variant: VariantInput): Promise<PlaygroundRun> {
  return parse(await fetch(`/api/admin/playground/runs/${id}/variants/${label}/try`, json("POST", { page, variant })));
}

export async function composeRun(id: number): Promise<PlaygroundRun> {
  return parse(await fetch(`/api/admin/playground/runs/${id}/compose`, { method: "POST" }));
}
