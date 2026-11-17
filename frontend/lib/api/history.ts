/* Historial del Playground. */
import { apiFetch, parse } from "./http";
import type { PlaygroundTask } from "./playground";
import type { Provider } from "./settings";

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
