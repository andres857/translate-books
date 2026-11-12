"use client";

import { useCallback, useEffect, useState } from "react";
import {
  addGlossary, addTerm, deleteGlossary, deleteTerm, listGlossary, listTerms, type GlossaryEntry, type ProtectedTerm,
} from "@/lib/api";
import { IconPlus, IconTrash, IconWarn } from "../../../components/art";

const CATEGORY: Record<string, string> = { NAME: "Nombre propio", BRAND: "Marca", CODE: "Código", TERM: "Término" };

export function Terms({ documentId }: { documentId: number }) {
  const [glossary, setGlossary] = useState<GlossaryEntry[]>([]);
  const [terms, setTerms] = useState<ProtectedTerm[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [g, setG] = useState({ source: "", target: "", scope: "book" });
  const [t, setT] = useState({ term: "", category: "NAME", scope: "book" });

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
        <p className="muted">Cómo debe traducirse siempre un término.</p>
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
          <button className="btn lg" type="submit" disabled={!g.source.trim() || !g.target.trim()}><IconPlus /> Añadir</button>
        </form>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Inglés</th><th>Español</th><th>Se aplica a</th><th><span className="muted">Acciones</span></th></tr></thead>
            <tbody>
              {glossary.map((x) => (
                <tr key={x.id}>
                  <td className="wrap">{x.source}</td>
                  <td className="wrap">{x.target}</td>
                  <td>{scopeOf(x.document_id)}</td>
                  <td>
                    <button type="button" className="btn ghost" aria-label={`Quitar ${x.source} del glosario`}
                      onClick={() => run(() => deleteGlossary(x.id))}><IconTrash /> Quitar</button>
                  </td>
                </tr>
              ))}
              {glossary.length === 0 && <tr><td colSpan={4}>El glosario está vacío.</td></tr>}
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
          <button className="btn lg" type="submit" disabled={t.term.trim().length < 2}><IconPlus /> Añadir</button>
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
