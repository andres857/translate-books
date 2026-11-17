"use client";

/* Estimación del alcance elegido en el Playground (para la siguiente ejecución). */
import { useEffect, useRef, useState } from "react";
import { estimateRun, type Estimate, type PlaygroundScope, type VariantInput } from "@/lib/api";
import { toInput, type LocalVariant } from "./shared";

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
