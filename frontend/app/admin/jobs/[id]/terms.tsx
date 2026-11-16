"use client";

import { useCallback, useEffect, useState } from "react";
import {
  addGlossary, addTerm, deleteGlossary, deleteTerm, discoverGlossary, editGlossary, glossaryDiscovery, listGlossary,
  listTerms, type GlossaryDiscovery, type GlossaryEntry, type ProtectedTerm,
} from "@/lib/api";
import { IconCheck, IconPlus, IconTrash, IconWand, IconWarn, IconX } from "../../../components/art";

const CATEGORY: Record<string, string> = { NAME: "Nombre propio", BRAND: "Marca", CODE: "Código", TERM: "Término" };

export function Terms({ documentId }: { documentId: number }) {
  const [glossary, setGlossary] = useState<GlossaryEntry[]>([]);
  const [terms, setTerms] = useState<ProtectedTerm[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [g, setG] = useState({ source: "", target: "", scope: "book" });
  const [t, setT] = useState({ term: "", category: "NAME", scope: "book" });
  const [disc, setDisc] = useState<GlossaryDiscovery | null>(null);
  const [editing, setEditing] = useState<{ id: number; target: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const [gl, tr] = await Promise.all([listGlossary(documentId), listTerms(documentId)]);
      setGlossary(gl);
      setTerms(tr);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [documentId]);

  useEffect(() => {
    load();
  }, [load]);

  // estado del descubrimiento (va en segundo plano): se consulta mientras esté en marcha
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const d = await glossaryDiscovery(documentId);
        if (!alive) return;
        setDisc((prev) => {
          if (prev?.status === "running" && d.status !== "running") load();
          return d;
        });
        if (d.status === "running") timer = setTimeout(poll, 2000);
      } catch {
        /* sin estado: el botón sigue disponible */
      }
    };
    if (!disc || disc.status === "running") poll();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [documentId, disc?.status, load]); // eslint-disable-line react-hooks/exhaustive-deps

  async function discover() {
    try {
      setDisc(await discoverGlossary(documentId));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function saveEdit() {
    if (!editing || !editing.target.trim()) return;
    await run(() => editGlossary(editing.id, { target: editing.target }));
    setEditing(null);
  }

  const autoCount = glossary.filter((x) => x.origin === "auto").length;
  const running = disc?.status === "running";

  async function run(action: () => Promise<unknown>) {
    try {
      await action();
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const scopeOf = (id: number | null) => (id === null ? "Todos los libros" : "Este libro");
  const docFor = (scope: string) => (scope === "book" ? documentId : null);

  return (
    <div className="viewer">
      {error && <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>}
      <p className="muted">
        Los cambios se aplican la próxima vez que se traduzca el libro (o una página que se recomponga y no esté en
        la caché). No cambian por sí solos el PDF ya generado.
      </p>

      <section className="card" aria-labelledby="glossary-title">
        <h2 id="glossary-title">Glosario</h2>
        <p className="muted">
          Cómo debe traducirse siempre un término. Al traducir un libro por primera vez se genera su glosario con el
          modelo (entradas «auto»); corrige aquí lo que no te convenza: lo corregido pasa a «manual» y no se sustituye.
        </p>
        <div className="glossary-discover">
          <span className="muted">
            Especialidad: <strong>{disc?.domain || "sin detectar"}</strong> · {autoCount} entradas auto
          </span>
          <button type="button" className="btn ghost" disabled={running} onClick={discover}>
            <IconWand /> {running ? "Generando glosario…" : autoCount ? "Volver a generar" : "Generar glosario"}
          </button>
        </div>
        {running && (
          <p className="muted" role="status">
            Analizando términos del libro{disc?.total ? ` (lote ${disc.done ?? 0} de ${disc.total})` : ""}. Tarda uno o
            dos minutos y cuesta unos céntimos.
          </p>
        )}
        {disc?.status === "done" && (
          <div className="alert ok" role="status"><IconCheck />
            <span>
              Glosario generado: {disc.count ?? 0} términos
              {typeof disc.cost_usd === "number" ? ` (costo aprox. ${disc.cost_usd.toFixed(3)} USD)` : ""}. Se sustituyen
              solo las entradas auto.
            </span>
          </div>
        )}
        {disc?.status === "failed" && <div className="alert error" role="alert"><IconWarn /><span>{disc.error}</span></div>}
        <form className="form-grid" onSubmit={(e) => {
          e.preventDefault();
          if (!g.source.trim() || !g.target.trim()) return;
          run(() => addGlossary(g.source, g.target, docFor(g.scope))).then(() => setG({ ...g, source: "", target: "" }));
        }}>
          <label className="control">Término en inglés
            <input value={g.source} onChange={(e) => setG({ ...g, source: e.target.value })} />
          </label>
          <label className="control">Traducción
            <input value={g.target} onChange={(e) => setG({ ...g, target: e.target.value })} />
          </label>
          <label className="control">Se aplica a
            <select value={g.scope} onChange={(e) => setG({ ...g, scope: e.target.value })}>
              <option value="book">Este libro</option>
              <option value="all">Todos los libros</option>
            </select>
          </label>
          <button className="btn" type="submit" disabled={!g.source.trim() || !g.target.trim()}><IconPlus /> Añadir</button>
        </form>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Inglés</th><th>Español</th><th>Origen</th><th>Se aplica a</th><th><span className="muted">Acciones</span></th></tr>
            </thead>
            <tbody>
              {glossary.map((x) => (
                <tr key={x.id}>
                  <td className="wrap">
                    {x.source}
                    {x.category && <div className="muted">{x.category}</div>}
                  </td>
                  <td className="wrap">
                    {editing?.id === x.id ? (
                      <form className="glossary-edit" onSubmit={(e) => { e.preventDefault(); saveEdit(); }}>
                        <input aria-label={`Traducción de ${x.source}`} value={editing.target} autoFocus
                          onChange={(e) => setEditing({ id: x.id, target: e.target.value })}
                          onKeyDown={(e) => { if (e.key === "Escape") setEditing(null); }} />
                        <button className="btn ghost" type="submit" aria-label="Guardar" disabled={!editing.target.trim()}>
                          <IconCheck />
                        </button>
                        <button className="btn ghost" type="button" aria-label="Cancelar" onClick={() => setEditing(null)}>
                          <IconX />
                        </button>
                      </form>
                    ) : (
                      <button type="button" className="glossary-target" title="Editar traducción"
                        onClick={() => setEditing({ id: x.id, target: x.target })}>{x.target}</button>
                    )}
                    {x.note && <div className="muted">{x.note}</div>}
                  </td>
                  <td><span className={`badge ${x.origin === "auto" ? "info" : "ok"}`}>{x.origin === "auto" ? "auto" : "manual"}</span></td>
                  <td>{scopeOf(x.document_id)}</td>
                  <td>
                    <button type="button" className="btn ghost" aria-label={`Quitar ${x.source} del glosario`}
                      onClick={() => run(() => deleteGlossary(x.id))}><IconTrash /> Quitar</button>
                  </td>
                </tr>
              ))}
              {glossary.length === 0 && <tr><td colSpan={5}>El glosario está vacío.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card" aria-labelledby="terms-title">
        <h2 id="terms-title">Términos protegidos</h2>
        <p className="muted">Nombres, marcas y códigos que no deben traducirse.</p>
        <form className="form-grid" onSubmit={(e) => {
          e.preventDefault();
          if (t.term.trim().length < 2) return;
          run(() => addTerm(t.term, t.category, docFor(t.scope))).then(() => setT({ ...t, term: "" }));
        }}>
          <label className="control">Término
            <input value={t.term} onChange={(e) => setT({ ...t, term: e.target.value })} />
          </label>
          <label className="control">Tipo
            <select value={t.category} onChange={(e) => setT({ ...t, category: e.target.value })}>
              {Object.entries(CATEGORY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className="control">Se aplica a
            <select value={t.scope} onChange={(e) => setT({ ...t, scope: e.target.value })}>
              <option value="book">Este libro</option>
              <option value="all">Todos los libros</option>
            </select>
          </label>
          <button className="btn" type="submit" disabled={t.term.trim().length < 2}><IconPlus /> Añadir</button>
        </form>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Término</th><th>Tipo</th><th>Se aplica a</th><th><span className="muted">Acciones</span></th></tr></thead>
            <tbody>
              {terms.map((x) => (
                <tr key={x.id}>
                  <td className="wrap">{x.term}</td>
                  <td>{CATEGORY[x.category] ?? x.category}</td>
                  <td>{scopeOf(x.document_id)}</td>
                  <td>
                    <button type="button" className="btn ghost" aria-label={`Quitar ${x.term} de los términos protegidos`}
                      onClick={() => run(() => deleteTerm(x.id))}><IconTrash /> Quitar</button>
                  </td>
                </tr>
              ))}
              {terms.length === 0 && <tr><td colSpan={4}>No hay términos protegidos manuales.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
