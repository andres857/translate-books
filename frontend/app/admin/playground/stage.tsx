"use client";

/* Mesa de comparación: una columna por PDF (original, producción y variantes) con scroll lateral. Cada página es
   la imagen real del PDF; encima, una capa con la caja de cada bloque para resaltar y comparar entre columnas. */
import { useState, type ReactNode } from "react";
import type { PageBlock, RunPage } from "@/lib/api";
import { blockId, plain, type ColId } from "./shared";

export interface Column {
  id: ColId;
  tag: string;
  name: string;
  sub: ReactNode; // insignias y datos de la segunda línea de la cabecera
  image: string | null; // null: no hay PDF que mostrar (ver placeholder)
  placeholder?: { text: string; action?: { label: string; onClick: () => void } };
}

interface Props {
  columns: Column[];
  page: RunPage | null;
  view: "page" | "blocks";
  hiWarn: boolean;
  selCol: ColId;
  selBlock: string | null;
  onSelect: (col: ColId, block: string | null) => void;
  loading: boolean;
}

function textOf(b: PageBlock, col: ColId): string | null {
  return col === "orig" ? b.source : b.cols[col]?.output ?? null;
}

function warningsOf(b: PageBlock, col: ColId): string[] {
  return col === "orig" ? [] : b.cols[col]?.warnings ?? [];
}

export function Stage({ columns, page, view, hiWarn, selCol, selBlock, onSelect, loading }: Props) {
  const [hover, setHover] = useState<string | null>(null);
  const [broken, setBroken] = useState<Record<string, boolean>>({});
  const ratio = page?.width && page?.height ? `${page.width} / ${page.height}` : undefined;

  const pick = (col: ColId, key: string) => onSelect(col, selBlock === key && selCol === col ? null : key);

  return (
    <div className="pg-table" aria-busy={loading}>
      {columns.map((c) => {
        const on = selCol === c.id;
        const hasData = c.id === "orig" || !!page?.metrics[c.id];
        return (
          <section key={c.id} className={`pg-col${on ? " on" : ""}`} aria-label={c.name}>
            <div className="pg-col-head" role="button" tabIndex={0} aria-pressed={on}
              onClick={() => onSelect(c.id, null)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(c.id, null); } }}>
              <span className={`variant-tag${c.id === "orig" || c.id === "prod" ? " plain" : ""}`}>{c.tag}</span>
              <span className="pg-name" title={c.name}>{c.name}</span>
              <span className="pg-sub">{c.sub}</span>
            </div>

            {view === "page" ? (
              c.image && !broken[c.image] ? (
                <div className="pg-sheet" style={{ aspectRatio: ratio }}>
                  {/* eslint-disable-next-line @next/next/no-img-element -- PNG que genera la API al vuelo */}
                  <img src={c.image} alt={`Página ${page?.number ?? ""}: ${c.name}`} loading="lazy"
                    onError={() => setBroken((b) => ({ ...b, [c.image!]: true }))} />
                  {page?.width && page.height && hasData && page.blocks.map((b) => {
                    const [x0, y0, x1, y1] = b.bbox;
                    const warn = warningsOf(b, c.id);
                    const cls = ["pg-blk", warn.length ? "warn" : "", hover === b.key ? "hl" : "",
                      selBlock === b.key ? "sel" : "", hiWarn && !warn.length ? "dim" : ""].filter(Boolean).join(" ");
                    return (
                      <button key={b.key} type="button" className={cls}
                        style={{
                          left: `${(100 * x0) / page.width!}%`, top: `${(100 * y0) / page.height!}%`,
                          width: `${(100 * (x1 - x0)) / page.width!}%`, height: `${(100 * (y1 - y0)) / page.height!}%`,
                        }}
                        title={warn.length ? warn.join(" · ") : plain(textOf(b, c.id)).slice(0, 160)}
                        aria-label={`${blockId(b.key)}${warn.length ? `, ${warn.length} aviso(s)` : ""}`}
                        onMouseEnter={() => setHover(b.key)} onMouseLeave={() => setHover(null)}
                        onClick={() => pick(c.id, b.key)} />
                    );
                  })}
                </div>
              ) : (
                <div className="pg-sheet pg-empty" style={{ aspectRatio: ratio }}>
                  <p>{c.image ? "No se pudo cargar la imagen de esta página." : c.placeholder?.text ?? "Sin PDF"}</p>
                  {c.placeholder?.action && (
                    <button type="button" className="btn secondary" onClick={c.placeholder.action.onClick}>
                      {c.placeholder.action.label}
                    </button>
                  )}
                </div>
              )
            ) : (
              <div className="pg-cards">
                {!page || !hasData ? (
                  <p className="muted">{c.placeholder?.text ?? (loading ? "Cargando…" : "Sin bloques")}</p>
                ) : page.blocks.length === 0 ? (
                  <p className="muted">Esta página no tiene bloques de texto para evaluar.</p>
                ) : page.blocks.map((b) => {
                  const warn = warningsOf(b, c.id);
                  const text = textOf(b, c.id);
                  return (
                    <div key={b.key} role="button" tabIndex={0}
                      className={["pg-card", hover === b.key ? "hl" : "", selBlock === b.key ? "sel" : "",
                        hiWarn && !warn.length ? "dim" : ""].filter(Boolean).join(" ")}
                      onMouseEnter={() => setHover(b.key)} onMouseLeave={() => setHover(null)}
                      onClick={() => pick(c.id, b.key)}
                      onKeyDown={(e) => { if (e.key === "Enter") pick(c.id, b.key); }}>
                      <div className="pg-card-k">
                        <span>{b.key}</span><span>{b.block_type}</span>
                        {warn.length > 0 && <span className="badge review">⚠ {warn.length}</span>}
                      </div>
                      <div className={text ? "pg-card-t" : "pg-card-t missing"}>{text ? plain(text) : "Sin resultado"}</div>
                      {warn.length > 0 && <ul className="pg-issues">{warn.map((w) => <li key={w}>{w}</li>)}</ul>}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
