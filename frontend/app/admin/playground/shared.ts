/* Utilidades de la mesa del Playground: textos, etiquetas, páginas y métricas. */
import { MODEL_ALIASES } from "@/lib/api";
import type { PageBlock, PageCell, PageMetrics, PageSegments, RunPage, Variant, VariantInput } from "@/lib/api";

export const MAX_VARIANTS = 4;
export const LABELS = ["A", "B", "C", "D"];
export const WARN_SCALE = 0.8; // igual que el backend: por debajo se avisa de que el texto no cabe
export const fmtN = new Intl.NumberFormat("es");

/** Columna de la mesa: el original, la traducción de producción o una variante (su letra). */
export type ColId = "orig" | "prod" | string;

/** Variante del espacio de trabajo: su letra no cambia al quitar otras columnas. */
export type LocalVariant = VariantInput & { label: string };

export const THINKING: Record<string, string> = {
  disabled: "sin razonamiento", low: "razonamiento bajo", high: "razonamiento alto", max: "razonamiento máximo",
};

export const DEFAULTS: Record<"deepseek" | "fake", VariantInput> = {
  deepseek: { provider: "deepseek", model: "deepseek-flash", thinking: "disabled", prompt: "production" },
  fake: { provider: "fake", prompt: "production" },
};

const ENTITIES: Record<string, string> = { "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&amp;": "&" };

export function plain(html: string | null | undefined): string {
  return (html ?? "")
    .replace(/<br\s*\/?>/g, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&(lt|gt|quot|#39|amp);/g, (m) => ENTITIES[m] ?? m);
}

export function variantName(v: Pick<VariantInput, "provider" | "model" | "thinking">): string {
  if ((v.provider as string) === "claude") return `Suscripción de Claude (retirado) · ${v.model}`; // historial antiguo
  if (v.provider === "deepseek") return `DeepSeek · ${v.model || "deepseek"} · ${THINKING[v.thinking || "disabled"] ?? v.thinking}`;
  return "Prueba sin API";
}

/** ID vigente del modelo (evaluaciones viejas guardaron `deepseek-pro`, que la API no acepta). */
export function modelId(model: string | null | undefined): string {
  return (model && (MODEL_ALIASES[model] ?? model)) || "deepseek-flash";
}

export function sameConfig(a: VariantInput, b: Variant | VariantInput): boolean {
  const norm = (v: VariantInput) => [v.provider, v.provider === "deepseek" ? modelId(v.model) : "fake",
    v.provider === "deepseek" ? v.thinking || "disabled" : "", String(v.prompt ?? "production")].join("|");
  return norm(a) === norm(b);
}

export function toInput(v: Variant | LocalVariant): VariantInput {
  return v.provider === "deepseek"
    ? { provider: "deepseek", model: modelId(v.model), thinking: v.thinking, prompt: v.prompt }
    : { provider: "fake", prompt: v.prompt };
}

/** «3,7,12-14» → [3, 7, 12, 13, 14] */
export function parsePages(spec: string | undefined | null): number[] {
  const out = new Set<number>();
  for (const part of (spec ?? "").split(",")) {
    const m = part.trim().match(/^(\d+)(?:\s*-\s*(\d+))?$/);
    if (!m) continue;
    const a = Number(m[1]);
    const b = Number(m[2] ?? m[1]);
    for (let n = a; n <= b && n - a < 5000; n++) out.add(n);
  }
  return [...out].sort((x, y) => x - y);
}

/** [3, 7, 12, 13, 14] → «3, 7, 12-14» */
export function formatPages(pages: number[]): string {
  const sorted = [...new Set(pages)].sort((x, y) => x - y);
  const out: string[] = [];
  for (let i = 0; i < sorted.length; i++) {
    let j = i;
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j] + 1) j++;
    out.push(j > i ? `${sorted[i]}-${sorted[j]}` : String(sorted[i]));
    i = j;
  }
  return out.join(", ");
}

export function duration(seconds: number): string {
  if (seconds < 90) return `${Math.max(1, Math.round(seconds))} s`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1)} h`;
}

function warningsOf(issues: string[], fit: number | null, output: string | null): string[] {
  const out = [...issues];
  if (fit !== null && fit < WARN_SCALE) out.push(`escala ${fit.toFixed(2).replace(".", ",")}: el texto no cabe en su caja`);
  if (!output) out.push("sin resultado");
  return out;
}

/** Antes de ejecutar: la página del libro con su traducción de producción (sin variantes todavía). */
export function pageFromSegments(data: PageSegments, withProduction: boolean): RunPage {
  const blocks: PageBlock[] = data.segments
    .filter((s) => s.action === "translate")
    .map((s) => ({
      key: s.key, bbox: s.bbox, block_type: s.block_type, source: s.source_html,
      cols: (withProduction
        ? { prod: { output: s.translation, fit: s.fit_scale, warnings: warningsOf(s.issues, s.fit_scale, s.translation) } }
        : {}) as Record<string, PageCell>,
    }));
  const metrics: Record<string, PageMetrics> = {};
  if (withProduction) {
    metrics.prod = { ...metricsOf(blocks, "prod"), review: data.needs_review ? data.reasons : [], stale: false };
  }
  return { number: data.number, width: data.width, height: data.height, blocks, metrics, vote: null };
}

function metricsOf(blocks: PageBlock[], col: string): Pick<PageMetrics, "warn_blocks" | "min_scale" | "length_pct"> {
  const fits = blocks.map((b) => b.cols[col]?.fit).filter((x): x is number => typeof x === "number");
  const src = blocks.reduce((n, b) => n + plain(b.source).length, 0) || 1;
  const out = blocks.reduce((n, b) => n + plain(b.cols[col]?.output).length, 0);
  return {
    warn_blocks: blocks.filter((b) => (b.cols[col]?.warnings.length ?? 0) > 0).length,
    min_scale: fits.length ? Math.round(Math.min(...fits) * 100) / 100 : null,
    length_pct: Math.round(100 * (out / src - 1)),
  };
}

export function blockId(key: string): string {
  return key.replace(/^p0*(\d+)_s0*(\d+).*$/, "p$1 · bloque $2");
}
