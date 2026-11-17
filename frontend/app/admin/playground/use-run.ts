"use client";

/* Evaluación del Playground: seguimiento de la que está abierta y estimación de la siguiente. */
import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { estimateRun, getRun, type Estimate, type PlaygroundRun, type PlaygroundScope, type VariantInput } from "@/lib/api";
import { toInput, type LocalVariant } from "./shared";

/** Mientras la evaluación abierta está en cola o en curso, se consulta cada 2 s. */
export function useRunTracking(run: PlaygroundRun | null, setRun: Dispatch<SetStateAction<PlaygroundRun | null>>,
  refreshRuns: () => void) {
  useEffect(() => {
    if (!run || (run.status !== "queued" && run.status !== "running")) return;
    const id = run.id;
    const timer = setTimeout(async () => {
      try {
        const next = await getRun(id);
        setRun((cur) => (cur?.id === id ? next : cur));
        if (next.status !== "queued" && next.status !== "running") refreshRuns();
      } catch {
        /* se reintenta en el siguiente ciclo */
      }
    }, 2000);
    return () => clearTimeout(timer);
  }, [run, setRun, refreshRuns]);
}

/** Estimación del alcance elegido (para la siguiente ejecución). `onInputsChange` se llama cada vez que cambia
 *  algo que la invalida (p. ej. para cerrar la confirmación pendiente). */
export function useEstimate({ ready, bookId, scope, spec, variants, onInputsChange }: {
  ready: boolean; bookId: number | null; scope: PlaygroundScope; spec: string; variants: LocalVariant[];
  onInputsChange: () => void;
}) {
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [estimateError, setEstimateError] = useState<string | null>(null);
  const changed = useRef(onInputsChange);
  useEffect(() => { changed.current = onInputsChange; });

  const variantsKey = JSON.stringify(variants.map(toInput));
  useEffect(() => {
    changed.current();
    if (!ready || !bookId) {
      setEstimate(null);
      setEstimateError(null);
      return;
    }
    let alive = true;
    const timer = setTimeout(() => {
      estimateRun({ job_id: bookId, scope, pages: spec, variants: JSON.parse(variantsKey) as VariantInput[] })
        .then((e) => { if (alive) { setEstimate(e); setEstimateError(null); } })
        .catch((e) => { if (alive) { setEstimate(null); setEstimateError((e as Error).message); } });
    }, 400);
    return () => { alive = false; clearTimeout(timer); };
  }, [bookId, scope, spec, variantsKey, ready]);

  return { estimate, estimateError };
}
