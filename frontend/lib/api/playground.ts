/* Administración › Prompts y Playground. */
import { apiFetch, json, parse } from "./http";
import type { Provider } from "./settings";

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
