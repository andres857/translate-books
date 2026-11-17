"use client";

/* Controles fijos de la mesa del Playground: evaluación abierta, alcance, páginas, voto, variantes,
   estimación, confirmación y progreso. Solo presentación: el estado y las acciones vienen de la página. */
import type { ReactNode } from "react";
import { cancelRun, resumeRun, type Estimate, type PlaygroundRun, type PlaygroundScope, type RunPage, type VariantInput } from "@/lib/api";
import { IconWarn } from "../../components/art";
import { duration, fmtN, MAX_VARIANTS, variantName, type ColId, type LocalVariant } from "./shared";

const STATUS_TEXT: Record<PlaygroundRun["status"], string> = {
  queued: "en cola", running: "en curso", paused: "en pausa", done: "terminada", failed: "con error", cancelled: "cancelada",
};
const SCOPE_TEXT: Record<PlaygroundScope, string> = { page: "Página", pages: "Páginas", chapter: "Capítulo", book: "Libro completo" };

export function Controls(c: {
  run: PlaygroundRun | null; runs: PlaygroundRun[]; bookId: number | null; bookName: string | null; scopeLabel: string;
  onScope: () => void; onOpenRun: (value: string) => void;
  idx: number; pageNo: number | null; pageList: number[]; onGoTo: (i: number) => void;
  warnPages: number[]; nextWarn: number | undefined;
  voteOptions: string[]; prodShown: boolean; prodAvailable: boolean; page: RunPage | null; onVote: (value: string) => void;
  busy: boolean; ready: boolean; active: boolean; onStart: (confirmed?: boolean) => void;
  variants: LocalVariant[]; col: ColId; onToggleProd: () => void; onOpenVariant: (label: string) => void;
  onRemoveVariant: (label: string) => void; onAddVariant: () => void; draftName: (prompt: VariantInput["prompt"]) => string;
  columnsCount: number; estimate: Estimate | null; estimateError: string | null;
  statusArea: ReactNode; confirming: boolean; onCancelConfirm: () => void; scope: PlaygroundScope;
  act: (fn: () => Promise<PlaygroundRun>) => void;
}) {
  const { run, estimate } = c;
  const usesApi = c.variants.some((v) => v.provider === "deepseek");
  return (
    <header className="pg-controls" aria-label="Controles de evaluación">
      <div className="pg-bar">
        <div className="pg-title">
          <strong>Playground</strong>
          <span>{run ? `Evaluación n.º ${run.id} · ${STATUS_TEXT[run.status]}` : "Nueva evaluación"}</span>
        </div>
        <button type="button" className="pg-scope-btn" title="Cambiar el libro o la parte que se evalúa" onClick={c.onScope}>
          <span className="pg-ellipsis"><strong>{c.bookName ?? "Sin libro"}</strong> · {c.scopeLabel}</span>
          <span className="pg-scope-change">Cambiar</span>
        </button>
        <label className="sr-only" htmlFor="pg-run">Evaluación</label>
        <select id="pg-run" className="pg-history" value={run?.id ?? ""} onChange={(e) => c.onOpenRun(e.target.value)}>
          <option value="">Nueva evaluación</option>
          {c.runs.filter((r) => !c.bookId || r.job_id === c.bookId).map((r) => (
            <option key={r.id} value={r.id}>
              N.º {r.id} · {SCOPE_TEXT[r.scope ?? "pages"]} {r.scope === "book" ? "" : r.pages} · {r.variants.length} var. · {STATUS_TEXT[r.status]}
            </option>
          ))}
        </select>
        <span className="pg-spacer" />
        <div className="pg-pager" aria-label="Página actual">
          <button className="btn secondary pg-icon" type="button" aria-label="Página anterior" disabled={c.idx <= 0}
            onClick={() => c.onGoTo(c.idx - 1)}>‹</button>
          <output>{c.pageNo === null ? "Sin páginas" : `Pág. ${c.pageNo} · ${c.idx + 1}/${c.pageList.length}`}</output>
          <button className="btn secondary pg-icon" type="button" aria-label="Página siguiente" disabled={c.idx >= c.pageList.length - 1}
            onClick={() => c.onGoTo(c.idx + 1)}>›</button>
          {c.warnPages.length > 0 && c.nextWarn !== undefined && (
            <button className="btn ghost" type="button" title="Ir a la siguiente página con avisos"
              onClick={() => c.onGoTo(c.pageList.indexOf(c.nextWarn!))}>
              ⚠ {c.warnPages.length}
            </button>
          )}
        </div>
        {c.voteOptions.length + (c.prodShown ? 1 : 0) >= 2 && c.pageNo !== null && (
          <>
            <span className="pg-eyebrow">Mejor</span>
            <div className="seg-control" role="radiogroup" aria-label="Mejor columna en esta página">
              {[...(c.prodShown ? ["prod"] : []), ...c.voteOptions, "tie"].map((o) => (
                <button key={o} type="button" role="radio" aria-checked={c.page?.vote === o} onClick={() => c.onVote(o)}>
                  {o === "tie" ? "Empate" : o === "prod" ? "Prod." : o}
                </button>
              ))}
            </div>
          </>
        )}
        <button className="btn" type="button" disabled={c.busy || !c.ready || !!c.estimateError || c.active} onClick={() => c.onStart()}>
          {c.busy ? "Enviando…" : c.active ? "En curso…" : "Ejecutar"}
        </button>
      </div>

      <div className="pg-bar">
        <span className="pg-eyebrow">Variantes</span>
        <div className="pg-chips">
          {c.prodAvailable && (
            <button type="button" className={`pg-chip pg-chip-toggle${c.prodShown ? " shown" : ""}`} aria-pressed={c.prodShown}
              title={c.prodShown ? "Ocultar la columna de producción" : "Mostrar la traducción de producción como referencia"}
              onClick={c.onToggleProd}>
              <span className="variant-tag plain">ES</span>Producción
            </button>
          )}
          {c.variants.map((v) => (
            <div key={v.label} className={`pg-chip${c.col === v.label ? " on" : ""}`}>
              <button type="button" className="pg-chip-open" aria-pressed={c.col === v.label}
                title={`Configurar la variante ${v.label} en el panel`}
                onClick={() => c.onOpenVariant(v.label)}>
                <span className="variant-tag">{v.label}</span>
                <span>{variantName(v)}</span>
                <small>{c.draftName(v.prompt)}</small>
              </button>
              {c.variants.length > 1 && (
                <button type="button" className="pg-chip-x" aria-label={`Quitar variante ${v.label}`} onClick={() => c.onRemoveVariant(v.label)}>×</button>
              )}
            </div>
          ))}
          {c.variants.length < MAX_VARIANTS && (
            <button type="button" className="pg-chip pg-chip-add" onClick={c.onAddVariant}>+ Variante</button>
          )}
        </div>
        <span className="muted">
          {c.variants.length === 1 ? "Añade una variante para comparar dos configuraciones" : `${c.columnsCount} PDF en la mesa · máx. ${MAX_VARIANTS} variantes`}
        </span>
        <span className="pg-spacer" />
        <span className="muted pg-estimate" aria-live="polite">
          {c.estimateError ? <span className="error-text">{c.estimateError}</span>
            : estimate ? (
              <>
                {estimate.pages} {estimate.pages === 1 ? "página" : "páginas"} · {fmtN.format(estimate.blocks)} bloques
                · ~{fmtN.format(estimate.calls_per_variant)} {estimate.calls_per_variant === 1 ? "llamada" : "llamadas"} por variante
                {estimate.seconds !== null ? ` · ~${duration(estimate.seconds)}` : ""}
                {estimate.needs_confirm ? " · pide confirmación" : ""}
              </>
            ) : c.ready ? "Calculando…" : "Elige qué evaluar"}
        </span>
      </div>

      {c.statusArea}
      {c.confirming && estimate && (
        <div className="alert" role="alertdialog" aria-labelledby="pg-confirm">
          <IconWarn />
          <div className="stack">
            <strong id="pg-confirm">¿Evaluar {c.scope === "book" ? "el libro completo" : `${estimate.pages} páginas`}?</strong>
            <span>
              Son {fmtN.format(estimate.blocks)} bloques y unas {fmtN.format(estimate.calls)} llamadas en total
              {estimate.seconds !== null ? `, alrededor de ${duration(estimate.seconds)}` : ""}.
              {usesApi && " Consume saldo de DeepSeek: si se agota, la evaluación se pausa y podrás reanudarla tras recargar."}
            </span>
            <div className="row">
              <button type="button" className="btn" onClick={() => c.onStart(true)}>Confirmar y ejecutar</button>
              <button type="button" className="btn ghost" onClick={c.onCancelConfirm}>Volver</button>
            </div>
          </div>
        </div>
      )}
      {run && (c.active || run.status === "paused") && (
        <div className="pg-status" aria-live="polite">
          <div className="progress" aria-label="Progreso"><div style={{ width: `${run.progress}%` }} /></div>
          <span className="muted">
            {run.trying ? `Probando la variante ${run.trying.label} en la pág. ${run.trying.page}` : ""}
            {run.status === "queued" ? (run.trying ? " · en cola" : "En cola: el worker la ejecuta cuando no hay libros pendientes.")
              : run.stage === "compose" ? `${run.trying ? " · " : ""}Maquetando el PDF de la variante ${run.composing ?? ""}…`
                : run.blocks_total ? `${run.trying ? " · " : ""}${run.current_variant !== null && !run.trying ? `Variante ${run.variants[run.current_variant]?.label}: ` : ""}${fmtN.format(run.blocks_done ?? 0)} / ${fmtN.format(run.blocks_total)} bloques` : ""}
            {run.variants.length > 1 && !run.trying ? ` · ${run.results?.length ?? 0} de ${run.variants.length} variantes terminadas` : ""}
          </span>
          {run.status === "paused" && <button type="button" className="btn" onClick={() => c.act(() => resumeRun(run.id))}>Reanudar</button>}
          <button type="button" className="btn secondary" onClick={() => c.act(() => cancelRun(run.id))}>Cancelar</button>
        </div>
      )}
      {run?.error && (
        <div className="alert error" role="alert"><IconWarn /><span>{run.error}</span></div>
      )}
    </header>
  );
}
