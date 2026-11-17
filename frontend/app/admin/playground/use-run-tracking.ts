"use client";

/* Seguimiento de la evaluación abierta del Playground. */
import { useEffect, type Dispatch, type SetStateAction } from "react";
import { getRun, type PlaygroundRun } from "@/lib/api";

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
