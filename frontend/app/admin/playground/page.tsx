"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  cancelRun, createDraft, createRun, deleteDraft, getPrompts, getRun, listChapters, listDrafts, listPlaygroundBooks,
  listRuns, updateDraft, type Chapter, type PlaygroundBook, type PlaygroundRun, type PlaygroundTask, type PromptDraft,
  type Provider, type VariantInput,
} from "@/lib/api";
import { IconCheck, IconInfo, IconPlus, IconTrash, IconWarn } from "../../components/art";
import { Columns, Summary, variantLabel } from "./results";

const MAX_VARIANTS = 4;
const LABELS = "ABCD";
const TASK_TEXT: Record<PlaygroundTask, string> = {
  translate: "Traducción (libro traducido)",
  correct: "Corrección OCR (libro digitalizado)",
};
const STATUS_TEXT: Record<PlaygroundRun["status"], string> = {
  queued: "En cola", running: "En curso", done: "Terminada", failed: "Con error", cancelled: "Cancelada",
};
const DEFAULTS: Record<Provider, VariantInput> = {
  claude: { provider: "claude", model: "sonnet", effort: "", prompt: "production" },
  deepseek: { provider: "deepseek", model: "deepseek-flash", thinking: "disabled", prompt: "production" },
  fake: { provider: "fake", prompt: "production" },
};

type Editor = { index: number; draftId: number | null; name: string; text: string };
type Notice = { kind: "ok" | "error"; text: string } | null;

export default function PlaygroundPage() {
  const [books, setBooks] = useState<PlaygroundBook[]>([]);
  const [bookId, setBookId] = useState<number | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chapter, setChapter] = useState<string>("");
  const [pages, setPages] = useState("");
  const [drafts, setDrafts] = useState<PromptDraft[]>([]);
  const [production, setProduction] = useState<Record<PlaygroundTask, string> | null>(null);
  const [variants, setVariants] = useState<VariantInput[]>([DEFAULTS.claude, DEFAULTS.deepseek]);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [runs, setRuns] = useState<PlaygroundRun[]>([]);
  const [run, setRun] = useState<PlaygroundRun | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);

  const book = books.find((b) => b.id === bookId) ?? null;
  const task: PlaygroundTask = book?.task ?? "translate";
  const taskDrafts = drafts.filter((d) => d.task === task);

  // al abrir una ejecución, el formulario toma su libro, páginas y variantes (para repetirla o ajustarla)
  const show = useCallback((r: PlaygroundRun) => {
    setRun(r);
    setBookId(r.job_id);
    setPages(r.pages);
    setVariants(r.variants.map((v) => ({
      provider: v.provider, model: v.model, thinking: v.thinking, effort: v.effort, prompt: v.prompt,
    })));
  }, []);

  const refreshRuns = useCallback(() => listRuns().then(setRuns).catch(() => undefined), []);

  // carga inicial y parámetros ?draft= / ?task= que llegan desde Administración › Prompts
  useEffect(() => {
    Promise.all([listPlaygroundBooks(), listDrafts(), getPrompts()])
      .then(([b, d, p]) => {
        setBooks(b);
        setDrafts(d);
        setProduction({ translate: p.translate.text, correct: p.correct.text });
        const params = new URLSearchParams(window.location.search);
        const runParam = Number(params.get("run"));
        if (runParam) getRun(runParam).then(show).catch(() => undefined);
        const draft = d.find((x) => x.id === Number(params.get("draft")));
        const wanted: PlaygroundTask | null = draft?.task ?? (params.get("task") as PlaygroundTask | null);
        const first = b.find((x) => !wanted || x.task === wanted) ?? b[0];
        if (first && !runParam) setBookId(first.id);
        if (draft) setVariants([{ ...DEFAULTS.claude, prompt: draft.id }, DEFAULTS.claude]);
        if (!draft && wanted && first?.task === wanted) {
          setEditor({ index: 0, draftId: null, name: "", text: wanted === "correct" ? p.correct.text : p.translate.text });
        }
      })
      .catch((e) => setNotice({ kind: "error", text: (e as Error).message }));
    refreshRuns();
  }, [refreshRuns, show]);

  useEffect(() => {
    if (bookId === null) return;
    setChapters([]);
    setChapter("");
    listChapters(bookId).then(setChapters).catch(() => setChapters([]));
  }, [bookId]);

  // los borradores son de una tarea: al cambiar de libro (y de tarea) las variantes vuelven a producción
  useEffect(() => {
    setVariants((vs) => vs.map((v) => (typeof v.prompt === "number" && !taskDrafts.some((d) => d.id === v.prompt)
      ? { ...v, prompt: "production" } : v)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task, drafts]);

  // seguimiento de la ejecución abierta
  const runId = run?.id;
  const runStatus = run?.status;
  useEffect(() => {
    if (!runId || (runStatus !== "queued" && runStatus !== "running")) return;
    const timer = setTimeout(async () => {
      try {
        const next = await getRun(runId);
        setRun(next);
        if (next.status !== "queued" && next.status !== "running") refreshRuns();
      } catch {
        /* se reintenta en el siguiente ciclo */
      }
    }, 2000);
    return () => clearTimeout(timer);
  }, [run, runId, runStatus, refreshRuns]);

  const setVariant = (i: number, changes: Partial<VariantInput>) =>
    setVariants((vs) => vs.map((v, j) => (j === i ? { ...v, ...changes } : v)));

  function openEditor(i: number) {
    const v = variants[i];
    const draft = typeof v.prompt === "number" ? drafts.find((d) => d.id === v.prompt) : undefined;
    setEditor(draft
      ? { index: i, draftId: draft.id, name: draft.name, text: draft.text }
      : { index: i, draftId: null, name: "", text: production?.[task] ?? "" });
    setNotice(null);
  }

  async function saveEditor() {
    if (!editor) return;
    if (!editor.name.trim() || !editor.text.trim()) {
      setNotice({ kind: "error", text: "El borrador necesita nombre y texto." });
      return;
    }
    try {
      const saved = editor.draftId
        ? await updateDraft(editor.draftId, { name: editor.name, text: editor.text })
        : await createDraft({ task, name: editor.name, text: editor.text });
      setDrafts((ds) => [...ds.filter((d) => d.id !== saved.id), saved].sort((a, b) => a.id - b.id));
      if (editor.index < variants.length) setVariant(editor.index, { prompt: saved.id });
      setEditor(null);
      setNotice({ kind: "ok", text: `Borrador «${saved.name}» guardado. Producción no cambia.` });
    } catch (e) {
      setNotice({ kind: "error", text: (e as Error).message });
    }
  }

  async function removeDraft(id: number) {
    try {
      await deleteDraft(id);
      setDrafts((ds) => ds.filter((d) => d.id !== id));
      setEditor(null);
    } catch (e) {
      setNotice({ kind: "error", text: (e as Error).message });
    }
  }

  async function start() {
    if (!bookId) return;
    setBusy(true);
    setNotice(null);
    try {
      const created = await createRun({
        job_id: bookId, pages, chapter: chapter === "" ? null : chapters[Number(chapter)]?.title ?? null, variants,
      });
      setRun(await getRun(created.id));
      refreshRuns();
    } catch (e) {
      setNotice({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }

  async function open(id: number) {
    try {
      show(await getRun(id));
      document.getElementById("results")?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      setNotice({ kind: "error", text: (e as Error).message });
    }
  }

  const usesSubscription = variants.some((v) => v.provider === "claude");
  const usesApi = variants.some((v) => v.provider === "deepseek");
  const active = run && (run.status === "queued" || run.status === "running");

  return (
    <main className="wide">
      <div className="page-head">
        <div>
          <h1>Playground</h1>
          <p>Compara método, modelo, razonamiento y prompt sobre un capítulo real. No cambia el libro ni la producción.</p>
        </div>
        <Link className="btn secondary" href="/admin/prompts">Ver prompts</Link>
      </div>

      {notice && (
        <div className={`alert ${notice.kind === "ok" ? "ok" : "error"}`} role={notice.kind === "ok" ? "status" : "alert"}>
          {notice.kind === "ok" ? <IconCheck /> : <IconWarn />}
          <span>{notice.text}</span>
        </div>
      )}

      <section className="card" aria-labelledby="cfg-title">
        <h2 id="cfg-title">Qué evaluar</h2>
        {books.length === 0 ? (
          <p className="muted">Necesitas al menos un libro terminado. <Link href="/">Sube uno</Link>.</p>
        ) : (
          <div className="form-grid">
            <label className="control">
              Libro
              <select value={bookId ?? ""} onChange={(e) => setBookId(Number(e.target.value))}>
                {books.map((b) => <option key={b.id} value={b.id}>{b.name} · {b.page_count} págs.</option>)}
              </select>
            </label>
            <label className="control">
              Tarea
              <input value={TASK_TEXT[task]} readOnly aria-readonly="true" />
            </label>
            <label className="control">
              Capítulo
              <select
                value={chapter}
                disabled={chapters.length === 0}
                onChange={(e) => {
                  const c = chapters[Number(e.target.value)];
                  setChapter(e.target.value);
                  if (c) setPages(c.pages);
                }}
              >
                <option value="">{chapters.length ? "Elige un capítulo…" : "El PDF no tiene índice"}</option>
                {chapters.map((c, i) => (
                  <option key={c.title + c.pages} value={String(i)}>
                    {c.level > 1 ? "— " : ""}{c.title} (págs. {c.pages})
                  </option>
                ))}
              </select>
            </label>
            <label className="control">
              Páginas
              <input value={pages} placeholder="12-18" onChange={(e) => { setPages(e.target.value); setChapter(""); }} />
            </label>
          </div>
        )}
      </section>

      <section className="card" aria-labelledby="var-title">
        <div className="card-head">
          <h2 id="var-title">Variantes</h2>
          <span className="muted">Hasta {MAX_VARIANTS} · máx. 40 páginas y 600 bloques por ejecución</span>
        </div>
        <div className="variants">
          {variants.map((v, i) => (
            <div className="variant" key={i}>
              <div className="variant-head">
                <span className="variant-tag" aria-label={`Variante ${LABELS[i]}`}>{LABELS[i]}</span>
                {variants.length > 1 && (
                  <button type="button" className="btn ghost" aria-label={`Quitar variante ${LABELS[i]}`}
                    onClick={() => setVariants((vs) => vs.filter((_, j) => j !== i))}>
                    <IconTrash width={16} height={16} />
                  </button>
                )}
              </div>
              <label className="control">
                Método
                <select value={v.provider} onChange={(e) => setVariant(i, { ...DEFAULTS[e.target.value as Provider], prompt: v.prompt })}>
                  <option value="claude">Suscripción de Claude</option>
                  <option value="deepseek">API de DeepSeek</option>
                  <option value="fake">Prueba sin API</option>
                </select>
              </label>
              {v.provider === "claude" && (
                <>
                  <label className="control">
                    Modelo
                    <select value={v.model} onChange={(e) => setVariant(i, { model: e.target.value })}>
                      <option value="sonnet">Sonnet</option>
                      <option value="opus">Opus</option>
                    </select>
                  </label>
                  <label className="control">
                    Esfuerzo
                    <select value={v.effort} onChange={(e) => setVariant(i, { effort: e.target.value })}>
                      <option value="">Por defecto</option>
                      <option value="low">Bajo</option>
                      <option value="medium">Medio</option>
                      <option value="high">Alto</option>
                    </select>
                  </label>
                </>
              )}
              {v.provider === "deepseek" && (
                <>
                  <label className="control">
                    Modelo
                    <input value={v.model} onChange={(e) => setVariant(i, { model: e.target.value })} />
                  </label>
                  <label className="control">
                    Razonamiento
                    <select value={v.thinking} onChange={(e) => setVariant(i, { thinking: e.target.value })}>
                      <option value="disabled">Desactivado</option>
                      <option value="low">Bajo</option>
                      <option value="high">Alto</option>
                      <option value="max">Máximo</option>
                    </select>
                  </label>
                </>
              )}
              <label className="control">
                Prompt
                <select
                  value={String(v.prompt)}
                  onChange={(e) => setVariant(i, { prompt: e.target.value === "production" ? "production" : Number(e.target.value) })}
                >
                  <option value="production">Producción</option>
                  {taskDrafts.map((d) => <option key={d.id} value={d.id}>Borrador: {d.name}</option>)}
                </select>
              </label>
              <button type="button" className="btn secondary" onClick={() => openEditor(i)}>
                {typeof v.prompt === "number" ? "Editar borrador" : "Crear borrador desde producción"}
              </button>
            </div>
          ))}
          {variants.length < MAX_VARIANTS && (
            <button type="button" className="variant add"
              onClick={() => setVariants((vs) => [...vs, { ...vs[vs.length - 1] }])}>
              <IconPlus width={20} height={20} />
              Añadir variante
            </button>
          )}
        </div>

        {editor && (
          <div className="variant" role="group" aria-labelledby="editor-title">
            <div className="variant-head">
              <h3 id="editor-title">
                {editor.draftId ? "Editar borrador" : "Nuevo borrador"} · variante {LABELS[editor.index]} · {TASK_TEXT[task]}
              </h3>
              <button type="button" className="btn ghost" onClick={() => setEditor(null)}>Cerrar</button>
            </div>
            <label className="control">
              Nombre
              <input value={editor.name} placeholder="p. ej. Más literal" onChange={(e) => setEditor({ ...editor, name: e.target.value })} />
            </label>
            <label className="control">
              Prompt del sistema
              <textarea className="mono" value={editor.text} onChange={(e) => setEditor({ ...editor, text: e.target.value })} />
            </label>
            <div className="alert">
              <IconInfo />
              <span>
                Conserva la forma de respuesta JSON que pide el prompt de producción: si el modelo no la devuelve, esa
                variante saldrá con error. {task === "correct" && <>Puedes usar <code>{"{lang}"}</code> para el idioma del libro.</>}
              </span>
            </div>
            <div className="row">
              <button type="button" className="btn" onClick={saveEditor}>Guardar borrador</button>
              <button type="button" className="btn ghost" onClick={() => setEditor({ ...editor, text: production?.[task] ?? "" })}>
                Restaurar texto de producción
              </button>
              {editor.draftId && (
                <button type="button" className="btn ghost" onClick={() => removeDraft(editor.draftId!)}>Eliminar borrador</button>
              )}
            </div>
          </div>
        )}

        <div className="run-bar">
          <span className="muted">
            {variants.map((v, i) => `${LABELS[i]}: ${variantLabel({ thinking: "", effort: "", model: "", ...v })}`).join(" · ")}
            {usesSubscription && " · consume uso de tu suscripción"}
            {usesApi && " · consume saldo de DeepSeek"}
          </span>
          <button type="button" className="btn lg" disabled={busy || !bookId || !pages.trim() || !!active} onClick={start}>
            {busy ? "Enviando…" : active ? "Evaluación en curso…" : "Ejecutar"}
          </button>
        </div>
      </section>

      {run && (
        <div id="results" className="stack">
          <section className="card" aria-labelledby="sum-title">
            <div className="card-head">
              <div>
                <h2 id="sum-title">Evaluación n.º {run.id}</h2>
                <p className="muted">
                  {run.book} · págs. {run.pages}{run.chapter ? ` · ${run.chapter}` : ""} · {TASK_TEXT[run.task]}
                </p>
              </div>
              <div className="row">
                <span className={`badge ${run.status === "done" ? "ok" : run.status === "running" ? "info" : run.status === "failed" ? "review" : ""}`}>
                  {STATUS_TEXT[run.status]}{run.status === "running" ? ` · ${Math.round(run.progress)}%` : ""}
                </span>
                {active && (
                  <button type="button" className="btn secondary" onClick={async () => setRun({ ...run, ...(await cancelRun(run.id)) })}>
                    Cancelar
                  </button>
                )}
              </div>
            </div>
            {active && <div className="progress" aria-label="Progreso"><div style={{ width: `${run.progress}%` }} /></div>}
            {run.status === "queued" && (
              <p className="muted">En cola: el worker la ejecuta cuando no hay libros pendientes.</p>
            )}
            {run.error && <div className="alert error" role="alert"><IconWarn /><span>{run.error}</span></div>}
            <Summary run={run} />
          </section>
          <Columns run={run} />
        </div>
      )}

      <section className="card" aria-labelledby="hist-title">
        <h2 id="hist-title">Historial</h2>
        {runs.length === 0 ? (
          <p className="muted">Todavía no hay evaluaciones.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th className="num">N.º</th><th>Libro</th><th>Páginas</th><th>Variantes</th><th>Estado</th><th /></tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id}>
                    <td className="num">{r.id}</td>
                    <td className="wrap">{r.book}</td>
                    <td>{r.pages}</td>
                    <td className="wrap">{r.variants.map((v) => `${v.label}: ${variantLabel(v)} (${v.prompt_name})`).join(" · ")}</td>
                    <td>{STATUS_TEXT[r.status]}</td>
                    <td><button type="button" className="btn ghost" onClick={() => open(r.id)}>Abrir</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
