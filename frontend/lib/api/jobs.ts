/* Libros (trabajos): estado, acciones, lista y borrado. */
import { apiFetch, parse } from "./http";

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

export async function getJob(id: string | number): Promise<JobStatus> {
  return parse(await apiFetch(`/api/jobs/${id}`, { cache: "no-store" }));
}

export async function jobAction(id: string | number, action: "cancel" | "resume"): Promise<JobStatus> {
  return parse(await apiFetch(`/api/jobs/${id}/${action}`, { method: "POST" }));
}

export async function listJobs(): Promise<JobStatus[]> {
  return parse(await apiFetch("/api/jobs", { cache: "no-store" }));
}

/** Elimina el libro con todo lo suyo (páginas, traducciones, archivos, evaluaciones, glosario propio). */
export async function deleteJob(id: number): Promise<void> {
  await parse(await apiFetch(`/api/jobs/${id}`, { method: "DELETE" }));
}
