"use client";

import { useMemo, useState } from "react";
import type { PlaygroundRun, Variant, VariantResult } from "@/lib/api";
import { IconWarn } from "../../components/art";

const ENTITIES: Record<string, string> = { "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&amp;": "&" };

export function plain(html: string | null | undefined): string {
  return (html ?? "")
    .replace(/<br\s*\/?>/g, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&(lt|gt|quot|#39|amp);/g, (m) => ENTITIES[m] ?? m);
}

export function variantLabel(v: Pick<Variant, "provider" | "model" | "thinking" | "effort">): string {
  if (v.provider === "claude") {
    return `Suscripción · ${v.model === "opus" ? "Opus" : "Sonnet"}${v.effort ? ` · esfuerzo ${v.effort}` : ""}`;
  }
  if (v.provider === "deepseek") {
    const thinking = v.thinking && v.thinking !== "disabled" ? ` · razonamiento ${v.thinking}` : "";
    return `API · ${v.model || "deepseek"}${thinking}`;
  }
  return "Prueba sin API";
}

function cost(r: VariantResult): string {
  if (r.cost_usd === null) return "—";
  const usd = `$${r.cost_usd.toFixed(4)}`;
  return r.cost_kind === "api_equivalent" ? `${usd} equiv.` : usd;
}

const fmt = new Intl.NumberFormat("es");

export function Summary({ run }: { run: PlaygroundRun }) {
  const results = run.results ?? [];
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Var.</th>
            <th>Método y modelo</th>
            <th>Prompt</th>
            <th className="num">Tiempo</th>
            <th className="num">Llamadas</th>
            <th className="num">Tokens entrada / salida</th>
            <th className="num" title="Suscripción: costo equivalente de API que informa Claude Code (no se cobra). DeepSeek: sin tarifa configurada.">
              USD
            </th>
            <th className="num">Con avisos</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>
          {run.variants.map((v, i) => {
            const r = results[i];
            const issues = r ? Object.values(r.segments).filter((s) => s.issues.length > 0).length : 0;
            const running = !r && run.status === "running" && run.current_variant === i;
            return (
              <tr key={v.label}>
                <td><span className="variant-tag">{v.label}</span></td>
                <td>{variantLabel(v)}</td>
                <td className="wrap">{v.prompt_name}</td>
                <td className="num-cell">{r ? `${r.seconds} s` : "—"}</td>
                <td className="num-cell">{r ? r.calls : "—"}</td>
                <td className="num-cell">{r ? `${fmt.format(r.tokens_in)} / ${fmt.format(r.tokens_out)}` : "—"}</td>
                <td className="num-cell">{r ? cost(r) : "—"}</td>
                <td className="num-cell">{r ? issues : "—"}</td>
                <td className="wrap">
                  {r?.error ? (
                    <span className="badge review">Error</span>
                  ) : r ? (
                    <span className="badge ok">Listo</span>
                  ) : running ? (
                    <span className="badge info">En curso</span>
                  ) : (
                    <span className="badge">{run.status === "cancelled" ? "Cancelada" : "En espera"}</span>
                  )}
                  {r?.error && <div className="muted">{r.error}</div>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function Columns({ run }: { run: PlaygroundRun }) {
  const [onlyDiff, setOnlyDiff] = useState(false);
  const [onlyIssues, setOnlyIssues] = useState(false);
  const [withProduction, setWithProduction] = useState(false);
  const [page, setPage] = useState<number | "all">("all");
  const [focus, setFocus] = useState<string>("all");
  const segments = useMemo(() => run.segments ?? [], [run.segments]);
  const results = run.results ?? [];
  const pages = useMemo(() => [...new Set(segments.map((s) => s.page))], [segments]);
  const shown = run.variants
    .map((v, i) => ({ v, r: results[i] }))
    .filter(({ v }) => focus === "all" || focus === v.label);

  const rows = segments.filter((s) => {
    if (page !== "all" && s.page !== page) return false;
    const outs = results.map((r) => plain(r.segments[s.key]?.output).trim());
    if (onlyDiff && new Set(outs).size <= 1) return false;
    if (onlyIssues && !results.some((r) => (r.segments[s.key]?.issues ?? []).length > 0)) return false;
    return true;
  });
  const cols = 1 + (withProduction ? 1 : 0) + shown.length;
  const productionTitle = run.task === "correct" ? "Corrección actual del libro" : "Traducción actual del libro";

  return (
    <section className="card" aria-labelledby="cols-title">
      <div className="card-head">
        <h2 id="cols-title">Salida por bloque</h2>
        <span className="muted">{rows.length} de {segments.length} bloques</span>
      </div>
      <div className="row">
        <label className="toggle">
          <input type="checkbox" checked={onlyDiff} onChange={(e) => setOnlyDiff(e.target.checked)} /> Solo diferencias
        </label>
        <label className="toggle">
          <input type="checkbox" checked={onlyIssues} onChange={(e) => setOnlyIssues(e.target.checked)} /> Solo con avisos
        </label>
        <label className="toggle">
          <input type="checkbox" checked={withProduction} onChange={(e) => setWithProduction(e.target.checked)} /> Mostrar la
          versión actual del libro
        </label>
        <label className="toggle">
          Página
          <select value={page} onChange={(e) => setPage(e.target.value === "all" ? "all" : Number(e.target.value))}>
            <option value="all">Todas</option>
            {pages.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label className="toggle">
          Variantes
          <select value={focus} onChange={(e) => setFocus(e.target.value)}>
            <option value="all">Todas</option>
            {run.variants.map((v) => <option key={v.label} value={v.label}>{v.label}</option>)}
          </select>
        </label>
      </div>

      {rows.length === 0 ? (
        <p className="muted">{results.length === 0 ? "Aún no hay resultados." : "Ningún bloque cumple los filtros."}</p>
      ) : (
        <div className="cols">
          <div className="cols-grid" style={{ "--cols": cols } as React.CSSProperties}>
            <div className="head">Original</div>
            {withProduction && <div className="head">{productionTitle}</div>}
            {shown.map(({ v }) => (
              <div key={v.label} className="head">{v.label} · {variantLabel(v)} · {v.prompt_name}</div>
            ))}
            {rows.map((s) => {
              const outs = results.map((r) => plain(r.segments[s.key]?.output).trim());
              const differs = new Set(outs).size > 1;
              return (
                <Row key={s.key} label={`Pág. ${s.page} · ${s.key} · ${s.block_type}`}>
                  <div className="text" lang={run.task === "correct" ? undefined : "en"}>{plain(s.source)}</div>
                  {withProduction && (
                    <div className="text">{plain(s.production) || <span className="missing">Sin versión</span>}</div>
                  )}
                  {shown.map(({ v, r }) => {
                    const item = r?.segments[s.key];
                    return (
                      <div key={v.label} className={differs ? "diff" : undefined}>
                        {item?.output ? (
                          <div className="text">{plain(item.output)}</div>
                        ) : (
                          <span className="missing">{r ? "Sin resultado" : "Pendiente"}</span>
                        )}
                        {item && item.issues.length > 0 && (
                          <ul className="issues">{item.issues.map((i) => <li key={i}>{i}</li>)}</ul>
                        )}
                      </div>
                    );
                  })}
                </Row>
              );
            })}
          </div>
        </div>
      )}
      {results.some((r) => r.error) && (
        <div className="alert" role="status"><IconWarn /><span>Hay variantes con error: revisa el resumen.</span></div>
      )}
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <div className="row-label">{label}</div>
      {children}
    </>
  );
}
