"use client";

/* Mesa del Playground: barra de vista, columnas de PDF (o estados vacíos) y el panel de la columna elegida.
   El estado (vista, avisos, panel, selección) vive en la página; aquí solo se presenta. */
import type { ReactNode } from "react";
import type { RunPage } from "@/lib/api";
import type { ColId } from "./shared";
import { Stage, type Column } from "./stage";

export function Mesa(m: {
  panelOpen: boolean; onTogglePanel: () => void;
  view: "page" | "blocks"; onView: (v: "page" | "blocks") => void;
  hiWarn: boolean; onHiWarn: (v: boolean) => void;
  columns: Column[];
  /** no hay libros para evaluar */
  noBooks: boolean;
  /** sin páginas que mostrar: el motivo (null = hay página) */
  emptyText: string | null;
  onUpload: () => void;
  page: RunPage | null; col: ColId; sel: string | null; loading: boolean;
  onSelect: (c: ColId, b: string | null) => void;
  panel: ReactNode;
}) {
  return (
    <div className={`pg-body${m.panelOpen ? "" : " no-panel"}`}>
      <div className="pg-stage">
        <div className="pg-stage-bar">
          <div className="seg-control" role="radiogroup" aria-label="Vista">
            <button type="button" role="radio" aria-checked={m.view === "page"} onClick={() => m.onView("page")}>Página PDF</button>
            <button type="button" role="radio" aria-checked={m.view === "blocks"} onClick={() => m.onView("blocks")}>Bloques</button>
          </div>
          <label className="toggle"><input type="checkbox" checked={m.hiWarn} onChange={(e) => m.onHiWarn(e.target.checked)} /> Resaltar avisos</label>
          <span className="pg-spacer" />
          <span className="muted">{m.columns.length} columnas</span>
          <button className="btn ghost" type="button" aria-pressed={m.panelOpen} onClick={m.onTogglePanel}>
            {m.panelOpen ? "Ocultar panel" : "Mostrar panel"}
          </button>
        </div>
        {m.noBooks ? (
          <div className="pg-empty-state">
            <div className="stack">
              <p className="muted">Sube un libro para evaluar: solo se analiza y se separa por capítulos, sin traducir nada.</p>
              <button type="button" className="btn" onClick={m.onUpload}>Subir libro</button>
            </div>
          </div>
        ) : m.emptyText !== null ? (
          <div className="pg-empty-state">
            <p className="muted">{m.emptyText}</p>
          </div>
        ) : (
          <Stage columns={m.columns} page={m.page} view={m.view} hiWarn={m.hiWarn} selCol={m.col} selBlock={m.sel}
            loading={m.loading} onSelect={m.onSelect} />
        )}
      </div>
      {m.panelOpen && m.panel}
    </div>
  );
}
