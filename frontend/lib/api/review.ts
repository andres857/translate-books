/* Revisión de un libro (administración): resumen, bloques, capítulos, recomposición, glosario y términos. */
import { apiFetch, json, parse } from "./http";
import type { JobStatus } from "./jobs";

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
