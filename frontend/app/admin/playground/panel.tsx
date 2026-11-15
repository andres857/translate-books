"use client";

/* Panel derecho: depende de la columna seleccionada. Con una variante, su configuración (método, modelo,
   razonamiento y prompt) y «Probar en la pág. N»; con el original o producción, el resumen de la evaluación. */
import { useEffect, useState } from "react";
import {
  createDraft, updateDraft, type PlaygroundRun, type PlaygroundTask, type PromptDraft, type Provider, type RunPage,
  type VariantInput, type VariantResult,
} from "@/lib/api";
import { blockId, DEFAULTS, fmtN, plain, THINKING, variantName, type ColId, type LocalVariant } from "./shared";

export interface PanelColumn {
  id: ColId;
  tag: string;
  name: string;
  result: VariantResult | null; // solo variantes ejecutadas
}

interface Props {
  col: ColId;
  columns: PanelColumn[]; // columnas de resultados (producción y variantes) en orden
  page: RunPage | null;
  sel: string | null;
  onClearSel: () => void;
  variant: LocalVariant | null;
  modified: boolean;
  onChange: (changes: Partial<VariantInput>) => void;
  task: PlaygroundTask;
  drafts: PromptDraft[];
  productionPrompt: string;
  onDraftSaved: (d: PromptDraft) => void;
  onError: (msg: string) => void;
  tryState: { enabled: boolean; hint: string | null; busy: boolean };
  onTry: () => void;
  run: PlaygroundRun | null;
  pageCount: number;
}

function cost(r: VariantResult): string {
  return r.cost_usd === null ? "sin tarifa" : `$${r.cost_usd.toFixed(4)}`;
}

/** Fila de métrica con una celda por columna; resalta el mejor valor de la página y apaga el peor. */
function Row({ name, cols, values, better, focus }: {
  name: string; cols: PanelColumn[]; values: (number | null)[]; better: "min" | "max" | null; focus: ColId;
}) {
  const nums = values.filter((x): x is number => x !== null);
  const best = better && nums.length > 1 ? (better === "min" ? Math.min(...nums) : Math.max(...nums)) : null;
  const worst = better && nums.length > 1 ? (better === "min" ? Math.max(...nums) : Math.min(...nums)) : null;
  return (
    <div className="pg-prop">
      <span>{name}</span>
      <div className="pg-vals" style={{ gridTemplateColumns: `repeat(${Math.min(cols.length, 3)}, minmax(0, 1fr))` }}>
        {cols.map((c, i) => {
          const v = values[i];
          const cls = best === null || v === null || best === worst ? "" : v === best ? "best" : v === worst ? "worse" : "";
          return (
            <div key={c.id} className={`pg-val ${cls}${c.id === focus ? " focus" : ""}`}>
              <span className={`variant-tag sm${c.id === "prod" ? " plain" : ""}`}>{c.tag}</span>
              {v === null ? "—" : fmtN.format(v)}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function Panel(p: Props) {
  const { col, columns, page, sel, variant, task } = p;
  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [draftText, setDraftText] = useState("");
  const taskDrafts = p.drafts.filter((d) => d.task === task);
  const draft = variant && typeof variant.prompt === "number" ? taskDrafts.find((d) => d.id === variant.prompt) ?? null : null;

  useEffect(() => { setEditing(false); }, [col]);
  useEffect(() => {
    setDraftName(draft?.name ?? "");
    setDraftText(draft?.text ?? p.productionPrompt);
  }, [draft?.id, draft?.name, draft?.text, p.productionPrompt]);

  const block = sel && page ? page.blocks.find((b) => b.key === sel) ?? null : null;
  const dataCols = columns.filter((c) => page?.metrics[c.id]);
  const metric = (k: "warn_blocks" | "min_scale" | "length_pct") => dataCols.map((c) => page?.metrics[c.id]?.[k] ?? null);
  const head = col === "orig"
    ? { tag: "EN", name: "Original", sub: page ? `Página ${page.number} · ${page.blocks.length} bloques · solo lectura` : "Solo lectura" }
    : col === "prod"
      ? { tag: "ES", name: "Producción", sub: "La traducción actual del libro · solo lectura" }
      : { tag: variant?.label ?? col, name: `Variante ${variant?.label ?? col}`, sub: variant ? variantName(variant) : "" };

  async function saveDraft() {
    if (!variant) return;
    if (!draftName.trim() || !draftText.trim()) {
      p.onError("El borrador necesita nombre y texto.");
      return;
    }
    try {
      const saved = draft
        ? await updateDraft(draft.id, { name: draftName, text: draftText })
        : await createDraft({ task, name: draftName, text: draftText });
      p.onDraftSaved(saved);
      p.onChange({ prompt: saved.id });
      setEditing(false);
    } catch (e) {
      p.onError((e as Error).message);
    }
  }

  return (
    <aside className="pg-panel" aria-label="Configuración de la columna seleccionada">
      <div className="pg-panel-head">
        <span className={`variant-tag${col === "orig" || col === "prod" ? " plain" : " on"}`}>{head.tag}</span>
        <div>
          <span className="pg-panel-name">{head.name}</span>
          <small>{head.sub}</small>
        </div>
      </div>
      <div className="pg-panel-body">
        {variant && (
          <section className="pg-section pg-form">
            <h3>Configuración{p.modified ? <span className="badge">modificada · sin ejecutar</span> : null}</h3>
            <label className="control">
              Método
              <select value={variant.provider}
                onChange={(e) => p.onChange({ ...DEFAULTS[e.target.value as Provider], prompt: variant.prompt })}>
                <option value="deepseek">API de DeepSeek</option>
                <option value="fake">Prueba sin API</option>
                <option disabled>OpenAI (próximamente)</option>
              </select>
            </label>
            {variant.provider === "deepseek" && (
              <>
                <label className="control">
                  Modelo
                  <input value={variant.model ?? ""} list="pg-models" onChange={(e) => p.onChange({ model: e.target.value })} />
                  <datalist id="pg-models"><option value="deepseek-flash" /><option value="deepseek-pro" /></datalist>
                </label>
                <label className="control">
                  Razonamiento
                  <select value={variant.thinking || "disabled"} onChange={(e) => p.onChange({ thinking: e.target.value })}>
                    {Object.entries(THINKING).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
                  </select>
                </label>
              </>
            )}
            <label className="control">
              Prompt
              <select value={String(variant.prompt)} onChange={(e) => {
                const v = e.target.value;
                if (v === "__new") {
                  p.onChange({ prompt: "production" });
                  setDraftName("");
                  setDraftText(p.productionPrompt);
                  setEditing(true);
                  return;
                }
                p.onChange({ prompt: v === "production" ? "production" : Number(v) });
              }}>
                <option value="production">Producción</option>
                {taskDrafts.map((d) => <option key={d.id} value={d.id}>Borrador: {d.name}</option>)}
                <option value="__new">+ Nuevo borrador desde producción</option>
              </select>
            </label>
            <div className="row">
              <button type="button" className="btn secondary" aria-expanded={editing} onClick={() => setEditing(!editing)}>
                {editing ? "Cerrar editor" : draft ? "Editar prompt" : "Ver prompt"}
              </button>
              <button type="button" className="btn" disabled={!p.tryState.enabled || p.tryState.busy} onClick={p.onTry}>
                {p.tryState.busy ? "Probando…" : `Probar en la pág. ${page?.number ?? ""}`}
              </button>
            </div>
            {p.tryState.hint && <p className="muted">{p.tryState.hint}</p>}
            {editing && (
              <div className="pg-form">
                {(draft || variant.prompt === "production") && (
                  <label className="control">
                    Nombre del borrador
                    <input value={draftName} placeholder="p. ej. Más literal" onChange={(e) => setDraftName(e.target.value)} />
                  </label>
                )}
                <label className="control">
                  Texto del prompt
                  <textarea className="mono" value={draftText} onChange={(e) => setDraftText(e.target.value)} />
                </label>
                <p className="muted">
                  {draft
                    ? "Producción no cambia. Conserva la forma de respuesta JSON del prompt de producción."
                    : "El prompt de producción no se modifica: al guardar se crea un borrador con este texto."}
                  {task === "correct" && <> Puedes usar <code>{"{lang}"}</code> para el idioma del libro.</>}
                </p>
                <div className="row">
                  <button type="button" className="btn secondary" onClick={saveDraft}
                    disabled={!draftName.trim()}>
                    {draft ? "Guardar borrador" : "Guardar como borrador"}
                  </button>
                  <button type="button" className="btn ghost" onClick={() => setDraftText(p.productionPrompt)}>
                    Restaurar producción
                  </button>
                </div>
              </div>
            )}
          </section>
        )}

        <section className="pg-section">
          <h3>{block ? blockId(block.key) : "Bloque"}</h3>
          {!block ? (
            <p className="muted">Pulsa un bloque de la página para comparar ese texto entre todas las columnas.</p>
          ) : (
            <div className="pg-cmp">
              <div className="pg-src">{plain(block.source)}</div>
              {columns.filter((c) => block.cols[c.id]).map((c) => {
                const cell = block.cols[c.id];
                return (
                  <div key={c.id} className="pg-out">
                    <span className={`variant-tag sm${c.id === "prod" ? " plain" : ""}`}>{c.tag}</span>
                    <div>
                      {cell.output ? plain(cell.output) : <span className="muted">Sin resultado</span>}
                      {cell.warnings.length > 0 && <ul className="pg-issues">{cell.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
                    </div>
                  </div>
                );
              })}
              <button type="button" className="btn secondary" onClick={p.onClearSel}>Quitar selección</button>
            </div>
          )}
        </section>

        {page && dataCols.length > 0 && (
          <section className="pg-section">
            <h3>Página {page.number}{variant ? `: ${variant.label} frente a las demás` : " por columna"}</h3>
            <div className="pg-props">
              <Row name="Bloques con avisos" cols={dataCols} values={metric("warn_blocks")} better="min" focus={col} />
              <Row name="Escala mínima" cols={dataCols} values={metric("min_scale")} better="max" focus={col} />
              <Row name="Longitud frente al original (%)" cols={dataCols} values={metric("length_pct")} better={null} focus={col} />
            </div>
            {dataCols.map((c) => {
              const m = page.metrics[c.id];
              return m.review.length > 0 || m.stale ? (
                <p key={c.id} className="muted">
                  <strong>{c.tag}:</strong> {m.stale ? "evaluada con la configuración anterior. " : ""}
                  {m.review.length > 0 ? `Pide revisión: ${m.review.join(" · ")}` : ""}
                </p>
              ) : null;
            })}
            <p className="muted">Verde, el mejor valor de la página; gris, el peor. Subrayada, la columna seleccionada.</p>
          </section>
        )}

        {p.run && (col === "orig" || col === "prod" || !variant) && (
          <section className="pg-section">
            <h3>Toda la evaluación ({fmtN.format(p.pageCount)} {p.pageCount === 1 ? "página" : "páginas"})</h3>
            <div className="pg-props">
              {columns.map((c) => {
                const s = p.run?.summary?.[c.id];
                const r = c.result;
                return (
                  <div key={c.id} className="pg-prop">
                    <span>{c.name}</span>
                    <div className="pg-val">
                      <span className={`variant-tag sm${c.id === "prod" ? " plain" : ""}`}>{c.tag}</span>
                      <span className="pg-sum">
                        {s ? `${s.won} ${s.won === 1 ? "página ganada" : "páginas ganadas"} · ${fmtN.format(s.warn_blocks)} bloques con avisos en ${s.warn_pages.length} págs.` : "Sin ejecutar"}
                      </span>
                    </div>
                    {r && (
                      <span>
                        {fmtN.format(r.seconds)} s · {fmtN.format(r.calls)} llamadas · {fmtN.format(r.tokens_in)} / {fmtN.format(r.tokens_out)} tokens · {cost(r)}
                        {r.error ? ` · error: ${r.error}` : ""}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="muted">Selecciona la columna de una variante para cambiar su configuración y su prompt.</p>
          </section>
        )}
      </div>
    </aside>
  );
}
