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
  original_name: string;
  title_es: string | null;
  output_name: string | null;
  error: string | null;
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
}

export type SettingsChanges = Partial<Omit<TranslationSettings, "deepseek_key_set" | "deepseek_key_hint" | "claude_available">> & {
  deepseek_api_key?: string;
};

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

export async function getHealth(): Promise<{ translation_configured: boolean; provider: Provider; max_upload_mb: number }> {
  return parse(await fetch("/api/health", { cache: "no-store" }));
}
