/* Ajustes de traducción y estado del servicio. */
import { apiFetch, parse } from "./http";

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

/** Lo que `GET /api/settings` devuelve al rol user: solo lo que pinta el rótulo del método. */
export type MethodSettings = Pick<TranslationSettings, "provider" | "deepseek_model">;

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
export function methodLabel(s: MethodSettings): string {
  if (s.provider === "deepseek") return `API · ${s.deepseek_model || "DeepSeek"}`;
  return "Prueba sin API";
}

/** Vista completa: solo para el admin (el user recibe `MethodSettings`, ver `getMethodSettings`). */
export async function getSettings(): Promise<TranslationSettings> {
  return parse(await apiFetch("/api/settings", { cache: "no-store" }));
}

/** Método activo, válido para cualquier rol. */
export async function getMethodSettings(): Promise<MethodSettings> {
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
