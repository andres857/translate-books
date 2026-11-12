export type StageState = "completed" | "in_progress" | "pending" | "error" | "cancelled" | "paused";

export type JobMode = "translate" | "digitize";
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

export type Provider = "deepseek" | "claude" | "fake";

export interface TranslationSettings {
  provider: Provider;
  deepseek_model: string;
  deepseek_thinking: "disabled" | "low" | "high" | "max";
  claude_model: "sonnet" | "opus";
  claude_concurrency: number;
  deepseek_concurrency: number;
  deepseek_key_set: boolean;
  deepseek_key_hint: string;
  claude_available: boolean;
  /** token = token de `claude setup-token` · session = login de Claude Code en el equipo · none */
  claude_auth: "token" | "session" | "none";
  claude_token_set: boolean;
  claude_token_hint: string;
}

type ReadOnly = "deepseek_key_set" | "deepseek_key_hint" | "claude_available" | "claude_auth" | "claude_token_set" | "claude_token_hint";

export type SettingsChanges = Partial<Omit<TranslationSettings, ReadOnly>> & {
  deepseek_api_key?: string;
  claude_oauth_token?: string;
};

/** Evento para que la barra lateral refresque el método activo tras guardar. */
export const SETTINGS_EVENT = "astrobooks:settings";

/** Nombre corto del método activo, para la barra lateral y la cabecera de Admin. */
export function methodLabel(s: Pick<TranslationSettings, "provider" | "claude_model" | "deepseek_model">): string {
  if (s.provider === "claude") return `Suscripción · ${s.claude_model === "opus" ? "Opus" : "Sonnet"}`;
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
  output: { deepseek: string; claude: string };
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
}

export interface Chapter {
  title: string;
  level: number;
  pages: string;
}

export interface VariantInput {
  provider: Provider;
  model?: string;
  thinking?: string;
  effort?: string;
  prompt: number | "production";
}

export interface Variant extends Required<Omit<VariantInput, "prompt">> {
  label: string;
  prompt: number | "production";
  prompt_name: string;
  prompt_text: string | null;
}

export interface VariantResult {
  label: string;
  segments: Record<string, { output: string | null; issues: string[] }>;
  seconds: number;
  calls: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number | null;
  cost_kind: "api_equivalent" | "unknown";
  error: string | null;
}

export interface PlaygroundRun {
  id: number;
  job_id: number;
  task: PlaygroundTask;
  pages: string;
  chapter: string | null;
  variants: Variant[];
  status: "queued" | "running" | "done" | "failed" | "cancelled";
  progress: number;
  current_variant: number | null;
  error: string | null;
  created_at: string | null;
  book: string | null;
  results?: VariantResult[];
  segments?: { key: string; page: number; block_type: string; source: string; production: string | null }[];
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

export async function createRun(body: { job_id: number; pages: string; chapter?: string | null; variants: VariantInput[] }): Promise<PlaygroundRun> {
  return parse(await fetch("/api/admin/playground/runs", json("POST", body)));
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
