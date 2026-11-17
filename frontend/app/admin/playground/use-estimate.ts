"use client";

/* Estimación del alcance elegido en el Playground (para la siguiente ejecución). */
import { useEffect, useState } from "react";
import { estimateRun, type Estimate, type PlaygroundScope, type VariantInput } from "@/lib/api";
import { toInput, type LocalVariant } from "./shared";

/** Estimación del alcance elegido (para la siguiente ejecución). `onInputsChange` se llama cada vez que cambia
 *  algo que la invalida (p. ej. para cerrar la confirmación pendiente). */
export function useEstimate({ ready, bookId, scope, spec, variants, onInputsChange }: {
  ready: boolean; bookId: number | null; scope: PlaygroundScope; spec: string; variants: LocalVariant[];
  onInputsChange: () => void;
}) {
  const [result, setResult] = useState<{ estimate: Estimate | null; error: string | null } | null>(null);
  const variantsKey = JSON.stringify(variants.map(toInput));

  // ajustes en el render de la página (este hook es suyo), no en un efecto: cada cambio de entradas avisa
  // y, sin alcance válido, la estimación anterior desaparece
  const inputsKey = `${ready}|${bookId}|${scope}|${spec}|${variantsKey}`;
  const [inputsSeen, setInputsSeen] = useState<string | null>(null);
  if (inputsSeen !== inputsKey) {
    setInputsSeen(inputsKey);
    onInputsChange();
  }
  if ((!ready || !bookId) && result !== null) setResult(null);

  // la petición, con una espera breve para no pedir en cada tecla; mientras, se sigue viendo la anterior
  useEffect(() => {
    if (!ready || !bookId) return;
    let alive = true;
    const timer = setTimeout(() => {
      estimateRun({ job_id: bookId, scope, pages: spec, variants: JSON.parse(variantsKey) as VariantInput[] })
        .then((e) => { if (alive) setResult({ estimate: e, error: null }); })
        .catch((e) => { if (alive) setResult({ estimate: null, error: (e as Error).message }); });
    }, 400);
    return () => { alive = false; clearTimeout(timer); };
  }, [bookId, scope, spec, variantsKey, ready]);

  return { estimate: result?.estimate ?? null, estimateError: result?.error ?? null };
}
