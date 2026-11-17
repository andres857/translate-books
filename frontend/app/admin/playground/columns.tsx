/* Columnas de la mesa del Playground (original, producción y una por variante) y datos derivados para la
   barra y el panel: opciones de voto, páginas con avisos y estado de «probar esta página». Funciones puras. */
import { composeRun, jobPageImageUrl, runPageImageUrl, type PlaygroundBook, type PlaygroundRun, type PlaygroundTask, type RunPage, type VariantInput } from "@/lib/api";
import type { PanelColumn } from "./panel";
import { duration, fmtN, sameConfig, variantName, type LocalVariant } from "./shared";
import type { Column } from "./stage";

export type ColumnsInput = {
  run: PlaygroundRun | null;
  page: RunPage | null;
  pageNo: number | null;
  bookId: number | null;
  book: PlaygroundBook | null;
  variants: LocalVariant[];
  prodShown: boolean;
  task: PlaygroundTask;
  active: boolean;
  selVariant: LocalVariant | null;
  draftName: (prompt: VariantInput["prompt"]) => string;
  act: (fn: () => Promise<PlaygroundRun>) => void;
  tryPage: (target: LocalVariant) => void;
};

const warnBadge = (n: number | undefined) => n === undefined ? null : n > 0
  ? <span className="badge review">⚠ {n} {n === 1 ? "aviso" : "avisos"}</span>
  : <span className="badge ok">Sin avisos</span>;

export function buildColumns(c: ColumnsInput) {
  const { run, page, pageNo, bookId, book, variants, prodShown, task, active, selVariant, draftName, act, tryPage } = c;
  const resultFor = (label: string) => run?.results?.find((r) => r.label === label) ?? null;
  const runVariantFor = (label: string) => run?.variants.find((v) => v.label === label) ?? null;

  const columns: Column[] = [];
  if (pageNo !== null && bookId) {
    columns.push({
      id: "orig", tag: "EN", name: "Original",
      sub: <><span className="muted pg-ellipsis">{book?.original_name ?? run?.book}</span><span className="pg-meta">{page ? `${page.blocks.length} bloques` : ""}</span></>,
      image: run ? runPageImageUrl(run.id, pageNo, "orig") : jobPageImageUrl(bookId, pageNo, "original"),
    });
    if (prodShown) {
      columns.push({
        id: "prod", tag: "ES", name: "Producción",
        sub: <>{page?.vote === "prod" && <span className="badge info">Mejor</span>}{warnBadge(page?.metrics.prod?.warn_blocks)}<span className="pg-meta">Libro traducido</span></>,
        image: run ? runPageImageUrl(run.id, pageNo, "prod") : jobPageImageUrl(bookId, pageNo, "translated"),
      });
    }
    for (const v of variants) {
      const rv = runVariantFor(v.label);
      const res = rv ? resultFor(v.label) : null;
      const m = page?.metrics[v.label];
      const modified = !!rv && !sameConfig(v, rv);
      const trying = active && run?.trying?.label === v.label;
      const canTry = !!run && run.status === "done" && !!res && pageNo !== null;
      let placeholder: Column["placeholder"];
      if (!run || !rv) placeholder = { text: "Sin ejecutar: pulsa «Ejecutar» para evaluar esta variante." };
      else if (!res) {
        const i = run.variants.findIndex((x) => x.label === v.label);
        placeholder = {
          text: run.status === "running" && run.current_variant === i
            ? `Traduciendo… ${fmtN.format(run.blocks_done ?? 0)} / ${fmtN.format(run.blocks_total ?? 0)} bloques`
            : run.status === "queued" || run.status === "running" ? "En cola"
              : run.status === "paused" ? "En pausa: reanuda la evaluación para continuar." : "Esta variante no llegó a ejecutarse.",
        };
      } else if (task === "correct") placeholder = { text: "Los libros digitalizados se comparan por bloques: cambia la vista a «Bloques»." };
      else if (run.composing === v.label || (active && !res.composed && !res.compose_error)) placeholder = { text: "Maquetando el PDF de esta variante…" };
      else if (res.compose_error) placeholder = { text: res.compose_error, action: { label: "Volver a maquetar", onClick: () => act(() => composeRun(run.id)) } };
      else if (!res.composed) placeholder = {
        text: "Esta evaluación es anterior a la mesa de PDF: su texto está evaluado pero no tiene PDF maquetado.",
        action: { label: "Maquetar PDF", onClick: () => act(() => composeRun(run.id)) },
      };
      columns.push({
        // con la configuración cambiada, la cabecera dice con qué se generó lo que se ve
        id: v.label, tag: v.label, name: modified && rv ? variantName(rv) : variantName(v),
        notice: modified && res ? {
          text: `Configuración cambiada a ${variantName(v)}${String(v.prompt) !== String(rv!.prompt) ? ` · ${draftName(v.prompt)}` : ""}. Lo que ves es de la anterior.`,
          hint: canTry || trying ? null : active ? "Espera a que termine la evaluación en curso." : "La evaluación tiene que estar terminada.",
          action: canTry || trying ? { label: `Volver a traducir la pág. ${pageNo}`, onClick: () => tryPage(v), busy: trying } : undefined,
        } : undefined,
        sub: (
          <>
            {page?.vote === v.label && <span className="badge info">Mejor</span>}
            {res?.error && <span className="badge review" title={res.error}>Error</span>}
            {m?.stale && <span className="badge" title="Esta página se evaluó con la configuración anterior">config. anterior</span>}
            {modified && <span className="badge">modificada</span>}
            {warnBadge(m?.warn_blocks)}
            <span className="pg-meta">{res ? `${duration(res.seconds)} · ` : ""}{draftName(v.prompt)}</span>
          </>
        ),
        image: res?.composed && task === "translate" && run ? runPageImageUrl(run.id, pageNo, v.label, res.composed_at) : null,
        placeholder,
      });
    }
  }

  const panelColumns: PanelColumn[] = [
    ...(prodShown ? [{ id: "prod", tag: "ES", name: "Producción", result: null }] : []),
    ...variants.map((v) => ({ id: v.label, tag: v.label, name: variantName(v), result: runVariantFor(v.label) ? resultFor(v.label) : null })),
  ];

  const voteOptions = run ? [...variants.filter((v) => resultFor(v.label) && runVariantFor(v.label)).map((v) => v.label)] : [];

  const warnSet = new Set<number>();
  for (const id of [...(prodShown ? ["prod"] : []), ...variants.map((v) => v.label)]) {
    for (const n of run?.summary?.[id]?.warn_pages ?? []) warnSet.add(n);
  }
  const warnPages = [...warnSet].sort((a, b) => a - b);
  const nextWarn = pageNo === null ? undefined : warnPages.find((n) => n > pageNo) ?? warnPages[0];

  const selRv = selVariant ? runVariantFor(selVariant.label) : null;
  const tryState = {
    busy: active && run?.trying?.label === selVariant?.label,
    enabled: !!run && run.status === "done" && !!selRv && !!resultFor(selVariant?.label ?? "") && pageNo !== null,
    hint: !run ? "Ejecuta la evaluación primero: después podrás probar cambios página a página."
      : !selRv ? "Esta variante es nueva: pulsa «Ejecutar» para evaluarla con todo el alcance."
        : active ? "Espera a que termine la evaluación en curso."
          : run.status !== "done" ? "La evaluación tiene que estar terminada para probar una página."
            : "Solo vuelve a traducir esta página; el resto queda marcado como «configuración anterior» si cambias algo.",
  };
  const selModified = !!selVariant && !!selRv && !sameConfig(selVariant, selRv);

  return { columns, panelColumns, voteOptions, warnPages, nextWarn, tryState, selModified };
}
