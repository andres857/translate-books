"use client";

import { useState } from "react";
import type { JobSummary } from "@/lib/api";
import { IconCheck, IconWarn, IconX } from "../../../components/art";

const KIND: Record<string, string> = {
  blank: "Vacía", digital: "Digital", scanned: "Escaneada", mixed: "Mixta", image_only: "Solo imagen",
};

const CHECK: Record<string, string> = {
  mismo_numero_de_paginas: "Mismo número de páginas",
  mismas_dimensiones: "Mismas dimensiones",
  paginas_vacias_conservadas: "Páginas vacías conservadas",
  imagenes_conservadas: "Imágenes conservadas",
  graficos_vectoriales_conservados: "Gráficos vectoriales conservados",
  terminos_protegidos_intactos: "Términos protegidos intactos",
  sin_marcadores_residuales: "Sin marcadores residuales",
  traduccion_completa: "Traducción completa",
  elementos_conservados_intactos: "Elementos conservados intactos",
};

const STAT: Record<string, string> = {
  segmentos_a_traducir: "Bloques a traducir",
  desde_cache: "Desde caché",
  traducidos: "Traducidos ahora",
  fallidos: "Fallidos",
  llamadas_api: "Llamadas al modelo",
  segmentos_reducidos: "Bloques reducidos",
};

type Filter = "all" | "ok" | "review";

export function Summary({ data, onOpenPage }: { data: JobSummary; onOpenPage: (n: number) => void }) {
  const [filter, setFilter] = useState<Filter>("all");
  const { totals } = data;
  const rows = data.pages.filter((p) => filter === "all" || (filter === "review") === p.needs_review);
  const pct = totals.pages ? Math.round((totals.ok / totals.pages) * 100) : 0;
  const checks = Object.entries(data.checks);
  const stats = Object.entries(data.stats).filter(([k]) => STAT[k]);

  if (data.pages.length === 0) {
    return <section className="card"><p>Aún no hay páginas procesadas para este libro.</p></section>;
  }

  return (
    <div className="viewer">
      <div className="stats">
        <div className="stat"><span>Páginas</span><strong>{totals.pages}</strong></div>
        <div className="stat"><span>Correctas</span><strong>{totals.ok}</strong></div>
        <div className="stat"><span>Para revisar</span><strong>{totals.review}</strong></div>
        <div className="stat"><span>Páginas correctas</span><strong>{pct}%</strong></div>
        <div className="stat"><span>Bloques de texto</span><strong>{totals.segments}</strong></div>
        <div className="stat"><span>Corregidos a mano</span><strong>{totals.edited}</strong></div>
      </div>

      {checks.length > 0 && (
        <section className="card" aria-labelledby="checks-title">
          <h2 id="checks-title">Validaciones del libro</h2>
          <ul className="checks">
            {checks.map(([key, ok]) => (
              <li key={key} className={ok ? "yes" : "no"}>
                {ok ? <IconCheck /> : <IconX />}
                <span>{CHECK[key] ?? key.replace(/_/g, " ")}{ok ? "" : " · no se cumple"}</span>
              </li>
            ))}
          </ul>
          {stats.length > 0 && (
            <p className="muted">{stats.map(([k, v]) => `${STAT[k]}: ${v}`).join(" · ")}</p>
          )}
        </section>
      )}

      {(data.errors.length > 0 || data.warnings.length > 0) && (
        <div className="alert">
          <IconWarn />
          <div>
            <strong>Avisos del proceso</strong>
            <ul>
              {[...data.errors, ...data.warnings].slice(0, 30).map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        </div>
      )}

      <section className="card" aria-labelledby="pages-title">
        <div className="card-head">
          <h2 id="pages-title">Páginas</h2>
          <div className="seg-control" role="group" aria-label="Filtrar páginas">
            {([["all", `Todas (${totals.pages})`], ["ok", `Correctas (${totals.ok})`], ["review", `Para revisar (${totals.review})`]] as [Filter, string][])
              .map(([id, label]) => (
                <button key={id} type="button" aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>
              ))}
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="num">Página</th>
                <th>Tipo</th>
                <th>Estado</th>
                <th className="num">Bloques</th>
                <th className="num">Escala mín.</th>
                <th>Motivos</th>
                <th><span className="muted">Acciones</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.number}>
                  <td className="num">{p.number}</td>
                  <td>{KIND[p.kind] ?? p.kind}</td>
                  <td>
                    <span className={`badge ${p.needs_review ? "review" : "ok"}`}>
                      {p.needs_review ? "Para revisar" : "Correcta"}
                    </span>
                    {p.edited > 0 && <> <span className="badge info">Editada</span></>}
                  </td>
                  <td className="num">{p.segments}</td>
                  <td className="num">{p.min_scale ? `${Math.round(p.min_scale * 100)}%` : "—"}</td>
                  <td className="wrap">
                    {p.reasons.length > 0 ? <ul>{p.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul> : "—"}
                  </td>
                  <td><button type="button" className="btn secondary" onClick={() => onOpenPage(p.number)}>Comparar</button></td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={7}>No hay páginas con este filtro.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
