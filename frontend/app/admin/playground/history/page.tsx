"use client";

/* Historial del playground, agrupado por libro: cada variante evaluada y cada «Probar en la pág.», con su
   configuración, los tokens que gastó, el costo estimado y su salida (PDF y bloques), para volver a verlos. */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  attemptImageUrl, fmtUsd, getAttempt, getHistory, getHistoryBooks,
  type Attempt, type AttemptDetail, type HistoryBook,
} from "@/lib/api";
import { IconArrowLeft, IconArrowRight, IconWarn } from "../../../components/art";
import { blockId, fmtN, plain, THINKING, variantName } from "../shared";

const fmtDate = new Intl.DateTimeFormat("es", { dateStyle: "medium", timeStyle: "short" });
const when = (iso: string | null) => (iso ? fmtDate.format(new Date(iso)) : "—");
const secs = (s: number) => (s >= 90 ? `${fmtN.format(Math.round(s / 60))} min` : `${fmtN.format(Math.round(s))} s`);

function setQuery(book: number | null, attempt: number | null) {
  const q = new URLSearchParams();
  if (book) q.set("book", String(book));
  if (attempt) q.set("attempt", String(attempt));
  window.history.replaceState(null, "", `${window.location.pathname}${q.size ? `?${q}` : ""}`);
}

function reuseHref(a: Attempt | AttemptDetail): string {
  const { provider, model, thinking, prompt } = a.config;
  const use = provider === "deepseek" ? { label: a.label, provider, model, thinking, prompt } : { label: a.label, provider, prompt };
  return `/admin/playground?run=${a.run_id}&use=${encodeURIComponent(JSON.stringify(use))}`;
}

function kindLabel(a: Attempt): string {
  return a.kind === "try" ? `Prueba · pág. ${a.pages}` : `Evaluación · págs. ${a.pages}`;
}

export default function PlaygroundHistoryPage() {
  const [books, setBooks] = useState<HistoryBook[] | null>(null);
  const [bookId, setBookId] = useState<number | null>(null);
  const [attempts, setAttempts] = useState<Attempt[] | null>(null);
  const [selId, setSelId] = useState<number | null>(null);
  const [detail, setDetail] = useState<AttemptDetail | null>(null);
  const [pageIdx, setPageIdx] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    getHistoryBooks()
      .then((b) => {
        setBooks(b);
        const wanted = Number(q.get("book"));
        setBookId(b.some((x) => x.job_id === wanted) ? wanted : b[0]?.job_id ?? null);
        const at = Number(q.get("attempt"));
        if (at) setSelId(at);
      })
      .catch((e) => setError((e as Error).message));
  }, []);

  useEffect(() => {
    if (bookId === null) return;
    setAttempts(null);
    getHistory(bookId).then((h) => setAttempts(h.attempts)).catch((e) => setError((e as Error).message));
  }, [bookId]);

  useEffect(() => {
    setQuery(bookId, selId);
    if (selId === null) { setDetail(null); return; }
    setDetail(null);
    setPageIdx(0);
    getAttempt(selId).then(setDetail).catch((e) => setError((e as Error).message));
  }, [bookId, selId]);

  const chooseBook = useCallback((id: number) => {
    setBookId(id);
    setSelId(null);
  }, []);

  const book = books?.find((b) => b.job_id === bookId) ?? null;
  const pageNo = detail?.page_list[pageIdx] ?? null;
  const pageBlocks = detail && pageNo !== null ? detail.blocks.filter((b) => b.page === pageNo) : [];

  return (
    <main className="wide">
      <div className="page-head">
        <div>
          <h1>Historial del playground</h1>
          <p>Cada evaluación y cada prueba de página, con su configuración, los tokens que gastó y lo que produjo.</p>
        </div>
        <Link className="btn secondary" href="/admin/playground">Volver al playground</Link>
      </div>

      {error && (
        <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>
      )}

      {books && books.length === 0 ? (
        <section className="card"><p className="muted">Todavía no hay pruebas. Ejecuta una evaluación en el playground y aparecerá aquí.</p></section>
      ) : (
        <div className="hist">
          <aside className="hist-side" aria-label="Libros">
            <div className="hist-side-head"><strong>Libros</strong><span className="muted">{books?.length ?? ""}</span></div>
            <ul className="pg-books" role="listbox" aria-label="Libros con pruebas">
              {!books && <li className="muted">Cargando…</li>}
              {books?.map((b) => (
                <li key={b.job_id}>
                  <button type="button" className="pg-book hist-book" role="option" aria-selected={b.job_id === bookId}
                    title={b.book ?? ""} onClick={() => chooseBook(b.job_id)}>
                    <span className="pg-ellipsis">{b.book ?? `Libro ${b.job_id}`}</span>
                    <span className="muted">{fmtN.format(b.attempts)} {b.attempts === 1 ? "prueba" : "pruebas"} · {fmtUsd(b.cost_usd)}</span>
                  </button>
                </li>
              ))}
            </ul>
            {book && (
              <div className="pg-book-summary">
                <strong className="pg-ellipsis" title={book.book ?? ""}>{book.book}</strong>
                <dl>
                  <dt>Pruebas</dt><dd>{fmtN.format(book.attempts)}</dd>
                  <dt>Tokens de entrada</dt><dd>{fmtN.format(book.tokens_in)}</dd>
                  <dt>Tokens de salida</dt><dd>{fmtN.format(book.tokens_out)}</dd>
                  <dt>Costo estimado</dt><dd>{fmtUsd(book.cost_usd)}</dd>
                  <dt>Última</dt><dd>{when(book.last)}</dd>
                </dl>
              </div>
            )}
          </aside>

          <section className="hist-main" aria-label="Pruebas del libro">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Qué</th><th>Configuración</th>
                    <th className="num">Tokens (entrada / salida)</th>
                    <th className="num">Costo</th><th className="num">Tiempo</th>
                  </tr>
                </thead>
                <tbody>
                  {!attempts && <tr><td colSpan={5} className="muted">Cargando…</td></tr>}
                  {attempts?.map((a) => (
                    <tr key={a.id} className="hist-row" aria-selected={a.id === selId} tabIndex={0}
                      onClick={() => setSelId(a.id === selId ? null : a.id)}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelId(a.id === selId ? null : a.id); } }}>
                      <td className="nowrap">
                        {kindLabel(a)}
                        {a.error && <span className="badge review" title={a.error}>Error</span>}
                        {!!a.won_pages?.length && <span className="badge info" title={`Mejor en págs. ${a.won_pages.join(", ")}`}>Mejor</span>}
                        <div className="muted">{when(a.created_at)} · N.º {a.run_id} · variante {a.label}</div>
                      </td>
                      <td className="wrap">{variantName(a.config)} · <span className="muted">{a.config.prompt_name}</span></td>
                      <td className="num nowrap">
                        {fmtN.format(a.tokens_in)} / {fmtN.format(a.tokens_out)}
                        {a.tokens_cache_hit > 0 && <div className="muted">{fmtN.format(a.tokens_cache_hit)} en caché</div>}
                      </td>
                      <td className="num">{fmtUsd(a.cost_usd)}</td>
                      <td className="num">{secs(a.seconds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {selId !== null && (
              <section className="card hist-detail" aria-labelledby="hist-detail-title">
                {!detail ? <p className="muted">Cargando la prueba…</p> : (
                  <>
                    <div className="card-head">
                      <div>
                        <h2 id="hist-detail-title">Evaluación N.º {detail.run_id} · variante {detail.label} · {detail.kind === "try" ? `prueba de la pág. ${detail.pages}` : `págs. ${detail.pages}`}</h2>
                        <p className="muted">{when(detail.created_at)} · {fmtN.format(detail.calls)} llamadas · {secs(detail.seconds)}</p>
                      </div>
                      <div className="row">
                        <Link className="btn secondary" href={`/admin/playground?run=${detail.run_id}`}>Abrir en el playground</Link>
                        <Link className="btn" href={reuseHref(detail)}>Reusar configuración</Link>
                      </div>
                    </div>

                    <dl className="hist-config">
                      <dt>Método</dt><dd>{detail.config.provider === "deepseek" ? "API de DeepSeek" : "Prueba sin API"}</dd>
                      {detail.config.provider === "deepseek" && <><dt>Modelo</dt><dd>{detail.config.model}</dd></>}
                      {detail.config.provider === "deepseek" && <><dt>Razonamiento</dt><dd>{THINKING[detail.config.thinking || "disabled"] ?? detail.config.thinking}</dd></>}
                      <dt>Prompt</dt><dd>{detail.config.prompt_name}</dd>
                      <dt>Tokens</dt>
                      <dd>
                        {fmtN.format(detail.tokens_in)} de entrada{detail.tokens_cache_hit ? ` (${fmtN.format(detail.tokens_cache_hit)} en caché)` : ""} · {fmtN.format(detail.tokens_out)} de salida
                      </dd>
                      <dt>Costo estimado</dt><dd>{fmtUsd(detail.cost_usd)} <span className="muted">con la tarifa en hora punta</span></dd>
                    </dl>
                    {detail.error && <div className="alert error" role="alert"><IconWarn /><span>{detail.error}</span></div>}

                    {detail.config.prompt_text && (
                      <details className="hist-prompt">
                        <summary>Ver el prompt que se usó</summary>
                        <pre className="code">{detail.config.prompt_text}</pre>
                      </details>
                    )}

                    <div className="hist-pages">
                      <div className="row">
                        <button className="btn secondary pg-icon" type="button" aria-label="Página anterior" disabled={pageIdx <= 0}
                          onClick={() => setPageIdx((i) => i - 1)}><IconArrowLeft /></button>
                        <span className="muted">Pág. {pageNo ?? "—"} · {pageIdx + 1} de {detail.page_list.length}</span>
                        <button className="btn secondary pg-icon" type="button" aria-label="Página siguiente"
                          disabled={pageIdx >= detail.page_list.length - 1} onClick={() => setPageIdx((i) => i + 1)}><IconArrowRight /></button>
                        {!detail.snapshot && detail.task === "translate" && (
                          <span className="muted">Prueba anterior al historial: se muestra el PDF actual de la variante.</span>
                        )}
                      </div>
                      <div className="hist-page">
                        {detail.task === "translate" && pageNo !== null && (
                          <div className="pg-sheet hist-sheet">
                            {/* eslint-disable-next-line @next/next/no-img-element -- PNG que genera la API al vuelo */}
                            <img src={attemptImageUrl(detail.id, pageNo)} alt={`Página ${pageNo} de esta prueba`} />
                          </div>
                        )}
                        <div className="pg-cards">
                          {pageBlocks.length === 0 && <p className="muted">Esta página no tiene bloques evaluados.</p>}
                          {pageBlocks.map((b) => (
                            <article key={b.key} className="pg-card">
                              <div className="pg-card-k">
                                <span>{blockId(b.key)}</span>
                                {b.warnings.length > 0 && <span className="badge review" title={b.warnings.join(" · ")}>⚠ {b.warnings.length}</span>}
                              </div>
                              <p className="pg-card-t muted">{plain(b.source)}</p>
                              <p className={`pg-card-t${b.output ? "" : " missing"}`}>{b.output ? plain(b.output) : "Sin resultado"}</p>
                            </article>
                          ))}
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </section>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
