"use client";

/* Playground: mesa para evaluar el rendimiento de la traducción. Compara página a página el PDF original con el
   PDF que produce cada variante (método, modelo, razonamiento y prompt), más la traducción de producción.
   Controles fijos arriba; columnas con scroll lateral; panel derecho según la columna seleccionada. */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createRun, deletePlaygroundBook, getPrompts, getRun, getRunPage, getSegments, listChapters, listDrafts, listPlaygroundBooks,
  listRuns, tryVariantPage, voteRunPage, type Chapter, type PlaygroundBook, type PlaygroundRun, type PlaygroundScope,
  type PlaygroundTask, type PromptDraft, type RunPage, type VariantInput,
} from "@/lib/api";
import { IconUpload } from "../../components/art";
import { buildColumns } from "./columns";
import { Controls } from "./controls";
import { Panel } from "./panel";
import { ScopeView, type ScopeValue } from "./scope-view";
import { DEFAULTS, fmtN, LABELS, modelId, pageFromSegments, parsePages, toInput, type ColId, type LocalVariant } from "./shared";
import { Mesa } from "./mesa";
import { PrepArea, UploadView, type Notice } from "./upload-view";
import { usePreparation } from "./use-preparation";
import { useEstimate, useRunTracking } from "./use-run";

export default function PlaygroundPage() {
  const [books, setBooks] = useState<PlaygroundBook[]>([]);
  const [bookId, setBookId] = useState<number | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chapter, setChapter] = useState("");
  const [scope, setScope] = useState<PlaygroundScope>("page");
  const [onePage, setOnePage] = useState("1");
  const [pagesSpec, setPagesSpec] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [drafts, setDrafts] = useState<PromptDraft[]>([]);
  const [prompts, setPrompts] = useState<Record<PlaygroundTask, string>>({ translate: "", correct: "" });
  const [variants, setVariants] = useState<LocalVariant[]>([{ ...DEFAULTS.deepseek, label: "A" }]);
  const [runs, setRuns] = useState<PlaygroundRun[]>([]);
  const [run, setRun] = useState<PlaygroundRun | null>(null);
  const [pageIdx, setPageIdx] = useState(0);
  const [page, setPage] = useState<RunPage | null>(null);
  const [pageLoading, setPageLoading] = useState(false);
  const [view, setView] = useState<"page" | "blocks">("page");
  const [hiWarn, setHiWarn] = useState(false);
  const [panelOpen, setPanelOpen] = useState(true);
  const [col, setCol] = useState<ColId>("A");
  const [sel, setSel] = useState<string | null>(null);
  const [showProd, setShowProd] = useState(true);
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);
  // vista inicial: elegir libro y alcance; luego se entra en la mesa («Cambiar» vuelve a esta vista)
  const [scopeOpen, setScopeOpen] = useState(true);
  const [entered, setEntered] = useState(false); // ya hay una mesa a la que volver

  const book = books.find((b) => b.id === bookId) ?? null;
  const task: PlaygroundTask = run?.task ?? book?.task ?? "translate";
  const chapterInfo = chapter === "" ? null : chapters[Number(chapter)] ?? null;
  const spec = scope === "page" ? onePage : scope === "pages" ? pagesSpec : scope === "chapter" ? chapterInfo?.pages ?? "" : "";
  const ready = !!bookId && (scope === "book" || spec.trim() !== "");
  const active = !!run && (run.status === "queued" || run.status === "running");
  // estimación del alcance elegido (para la siguiente ejecución); al cambiar, se cierra la confirmación
  const { estimate, estimateError } = useEstimate({ ready, bookId, scope, spec, variants, onInputsChange: () => setConfirming(false) });

  const pageList = useMemo(
    () => (run ? run.page_list ?? parsePages(run.pages) : parsePages(estimate?.page_spec)),
    [run, estimate?.page_spec],
  );
  const idx = Math.min(pageIdx, Math.max(0, pageList.length - 1));
  const pageNo = pageList[idx] ?? null;
  const prodAvailable = run ? !!run.production : task === "translate" && !!book?.production;
  const prodShown = showProd && prodAvailable;
  const draftName = (prompt: VariantInput["prompt"]) =>
    prompt === "production" ? "Producción" : drafts.find((d) => d.id === prompt)?.name ?? `Borrador ${prompt}`;

  // ------------------------------------------------------------------ carga
  const refreshRuns = useCallback(() => listRuns().then(setRuns).catch(() => undefined), []);

  const show = useCallback((r: PlaygroundRun) => {
    setRun(r);
    setScopeOpen(false);
    setEntered(true);
    setBookId(r.job_id);
    const s = r.scope ?? "pages";
    setScope(s === "chapter" ? "pages" : s); // el capítulo se elige de nuevo de la lista
    if (s === "page") setOnePage(r.pages);
    else setPagesSpec(r.pages);
    setVariants(r.variants.map((v) => ({
      ...(v.provider === "deepseek" || v.provider === "fake" ? toInput(v) : { ...DEFAULTS.deepseek, prompt: v.prompt }),
      label: v.label,
    })));
    setPageIdx(0);
    setSel(null);
    setCol(r.variants[0]?.label ?? "orig");
  }, []);

  useEffect(() => {
    Promise.all([listPlaygroundBooks(), listDrafts(), getPrompts()])
      .then(([b, d, p]) => {
        setBooks(b);
        setDrafts(d);
        setPrompts({ translate: p.translate.text, correct: p.correct.text });
        const params = new URLSearchParams(window.location.search);
        const runParam = Number(params.get("run"));
        if (runParam) {
          setScopeOpen(false);
          // «Reusar configuración» desde el historial: se aplica a esa variante y queda como modificada
          let use: (Partial<VariantInput> & { label?: string }) | null = null;
          try { use = JSON.parse(params.get("use") ?? "null"); } catch { use = null; }
          getRun(runParam).then((r) => {
            show(r);
            if (use?.label) {
              const { label, ...cfg } = use;
              setVariants((vs) => vs.map((v) => (v.label === label ? { ...v, ...cfg } : v)));
              setCol(label);
              setPanelOpen(true);
            }
          }).catch(() => setScopeOpen(true));
        }
        const draft = d.find((x) => x.id === Number(params.get("draft")));
        const wanted = draft?.task ?? (params.get("task") as PlaygroundTask | null);
        const first = b.find((x) => !wanted || x.task === wanted) ?? b[0];
        if (first && !runParam) setBookId(first.id);
        if (draft) setVariants([{ ...DEFAULTS.deepseek, prompt: draft.id, label: "A" }, { ...DEFAULTS.deepseek, label: "B" }]);
      })
      .catch((e) => setNotice({ kind: "error", text: (e as Error).message }));
    refreshRuns();
  }, [refreshRuns, show]);

  useEffect(() => {
    if (bookId === null) return;
    setChapters([]);
    setChapter("");
    const count = books.find((b) => b.id === bookId)?.page_count ?? 1;
    const choosing = scopeOpen && !run; // eligiendo en la vista inicial: alcance por defecto según haya capítulos
    let alive = true; // si se cambia de libro antes de que respondan, los capítulos del anterior se descartan
    listChapters(bookId)
      .catch(() => [] as Chapter[])
      .then((chs) => {
        if (!alive) return;
        setChapters(chs);
        if (!choosing) return;
        if (chs.length) {
          setScope("chapter");
          setChapter("0");
        }
        else {
          setScope("pages");
          setPagesSpec(`1-${Math.min(10, count)}`);
        }
      });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al cambiar de libro; books, scopeOpen y run se leen como estén entonces
  }, [bookId]);


  // los borradores son de una tarea: si el borrador ya no existe, la variante vuelve a producción
  useEffect(() => {
    setVariants((vs) => vs.map((v) => (typeof v.prompt === "number" && !drafts.some((d) => d.id === v.prompt && d.task === task)
      ? { ...v, prompt: "production" } : v)));
  }, [task, drafts]);

  // seguimiento de la evaluación abierta
  useRunTracking(run, setRun, refreshRuns);

  // subir un libro solo para evaluar: al terminar la preparación se selecciona y se informa de lo extraído
  const prepare = usePreparation({
    onStart: () => setNotice(null),
    onError: (e) => fail(e),
    onPrepared: async (id, next) => {
      const list = await listPlaygroundBooks();
      setBooks(list);
      const b = list.find((x) => x.id === id);
      setScopeOpen(true);
      changeBook(id);
      const chs = await listChapters(id).catch(() => [] as Chapter[]);
      return {
        name: b?.name ?? next.original_name, pages: b?.page_count ?? next.page_count, blocks: b?.blocks ?? 0,
        chapters: chs.length, detected: chs[0]?.source === "detected",
      };
    },
  });

  // datos de la página visible: bloques con su posición, salidas, avisos y métricas por columna
  const pageKey = run
    ? [run.id, pageNo, run.status, ...(run.results ?? []).map((r) => `${r.label}${r.composed_at ?? ""}${(r.stale_pages ?? []).join(".")}`)].join("|")
    : `${bookId}|${pageNo}|${prodAvailable}`;
  useEffect(() => {
    if (pageNo === null || (!run && !bookId)) {
      setPage(null);
      return;
    }
    let alive = true;
    setPageLoading(true);
    const load = run ? getRunPage(run.id, pageNo) : getSegments(bookId!, pageNo).then((d) => pageFromSegments(d, prodAvailable));
    load
      .then((p) => { if (alive) setPage(p); })
      .catch(() => { if (alive) setPage(null); })
      .finally(() => { if (alive) setPageLoading(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- pageKey resume run, pageNo, bookId y prodAvailable
  }, [pageKey]);

  // ------------------------------------------------------------------ acciones
  const fail = (e: unknown) => setNotice({ kind: "error", text: (e as Error).message });

  function changeBook(id: number | null) {
    setBookId(id);
    setRun(null);
    setPageIdx(0);
    setSel(null);
  }

  // borra el libro y su análisis en cascada; si era el activo, pasa al primero que quede
  async function deleteBook(b: PlaygroundBook) {
    await deletePlaygroundBook(b.id);
    const list = await listPlaygroundBooks();
    setBooks(list);
    if (bookId === b.id) {
      changeBook(list[0]?.id ?? null);
      setEntered(false);
    }
    refreshRuns();
    setNotice({ kind: "ok", text: `Se eliminó «${b.name}» con todo su análisis.` });
  }

  function setVariant(label: string, changes: Partial<VariantInput>) {
    setVariants((vs) => vs.map((v) => (v.label === label ? { ...v, ...changes } : v)));
  }

  // método de la primera variante, elegido en la barra de la vista inicial
  function setMethod(m: string) {
    setVariants((vs) => vs.map((v, i) => (i > 0 ? v : m === "fake"
      ? { ...DEFAULTS.fake, prompt: v.prompt, label: v.label }
      : { ...DEFAULTS.deepseek, thinking: v.provider === "deepseek" ? v.thinking : "disabled", model: m, prompt: v.prompt, label: v.label })));
  }

  function addVariant() {
    const free = LABELS.find((l) => !variants.some((v) => v.label === l));
    if (!free) return;
    const last = variants[variants.length - 1];
    const copy: LocalVariant = last
      ? { ...toInput(last), ...(last.provider === "deepseek" ? { thinking: last.thinking === "high" ? "disabled" : "high" } : {}), label: free }
      : { ...DEFAULTS.deepseek, label: free };
    setVariants((vs) => [...vs, copy]);
    setCol(free);
    setPanelOpen(true);
  }

  function removeVariant(label: string) {
    setVariants((vs) => vs.filter((v) => v.label !== label));
    if (col === label) setCol("orig");
  }

  async function start(confirmed = false) {
    if (!bookId) return;
    if (estimate?.needs_confirm && !confirmed) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    setBusy(true);
    setNotice(null);
    try {
      const created = await createRun({
        job_id: bookId, scope, pages: spec, chapter: scope === "chapter" ? chapterInfo?.title ?? null : null,
        variants: variants.map(toInput), confirm: confirmed,
      });
      const full = await getRun(created.id);
      setRun(full);
      setVariants(full.variants.map((v) => ({ ...toInput(v), label: v.label })));
      setCol(full.variants.find((v) => v.label === col) ? col : full.variants[0]?.label ?? "orig");
      setPageIdx(0);
      setSel(null);
      refreshRuns();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function openRun(value: string) {
    if (!value) {
      setRun(null);
      setPageIdx(0);
      return;
    }
    try {
      show(await getRun(Number(value)));
    } catch (e) {
      fail(e);
    }
  }

  async function act(fn: () => Promise<PlaygroundRun>) {
    if (!run) return;
    try {
      const next = await fn();
      setRun({ ...run, ...next });
    } catch (e) {
      fail(e);
    }
  }

  async function vote(value: string) {
    if (!run || pageNo === null) return;
    const next = page?.vote === value ? null : value;
    try {
      const { votes } = await voteRunPage(run.id, pageNo, next);
      setRun({ ...run, votes });
      setPage((p) => (p ? { ...p, vote: next } : p));
      getRun(run.id).then((r) => setRun((cur) => (cur?.id === r.id ? r : cur))).catch(() => undefined); // resumen
    } catch (e) {
      fail(e);
    }
  }

  const selVariant = variants.find((v) => v.label === col) ?? null;
  function tryPage(target: LocalVariant | null = selVariant) {
    if (!run || !target || pageNo === null) return;
    setNotice(null);
    act(() => tryVariantPage(run.id, target.label, pageNo, toInput(target)));
  }


  // ------------------------------------------------------------------ columnas
  const { columns, panelColumns, voteOptions, warnPages, nextWarn, tryState, selModified } = buildColumns({
    run, page, pageNo, bookId, book, variants, prodShown, task, active, selVariant, draftName, act, tryPage,
  });

  const scopeLabel = scope === "book" ? `Libro completo (${fmtN.format(book?.page_count ?? 0)} págs.)`
    : scope === "chapter" ? (chapterInfo ? `${chapterInfo.title} · págs. ${chapterInfo.pages}` : "Elige un capítulo")
      : scope === "page" ? `Pág. ${onePage}` : pagesSpec.trim() ? `Págs. ${pagesSpec}` : "Elige las páginas";
  const scopeValue: ScopeValue = { scope, onePage, pagesSpec, chapter };
  const setScopeValue = (v: Partial<ScopeValue>) => {
    if (v.scope !== undefined) setScope(v.scope);
    if (v.onePage !== undefined) setOnePage(v.onePage);
    if (v.pagesSpec !== undefined) setPagesSpec(v.pagesSpec);
    if (v.chapter !== undefined) setChapter(v.chapter);
  };
  const uploadArea = <PrepArea p={prepare} notice={notice} onCloseNotice={() => setNotice(null)} />;

  // ------------------------------------------------------------------ vista
  if (scopeOpen && prepare.uploadOpen) return (
    <main onKeyDown={(e) => { if (e.key === "Escape" && prepare.uploading === false) prepare.closeUpload(); }}>
      <UploadView p={prepare} notice={notice} />
    </main>
  );
  if (scopeOpen) return (
    <main className="wide">
      <ScopeView books={books} bookId={bookId} onBook={changeBook} onDeleteBook={deleteBook} chapters={chapters}
        value={scopeValue} onChange={setScopeValue} estimate={estimate} estimateError={estimateError}
        method={variants[0]?.provider === "fake" ? "fake" : modelId(variants[0]?.model)} onMethod={setMethod}
        variantCount={variants.length} busy={busy}
        onContinue={() => { setScopeOpen(false); setEntered(true); void start(); }}
        onBack={entered ? () => setScopeOpen(false) : undefined}
        upload={uploadArea}
        uploadAction={(
          <button type="button" className="btn" onClick={() => { setNotice(null); prepare.setUploadOpen(true); }}>
            <IconUpload /> {prepare.prep ? "Ver la preparación" : "Subir un libro nuevo"}
          </button>
        )} />
    </main>
  );

  return (
    <main className="pg">
      <Controls run={run} runs={runs} bookId={bookId} bookName={book?.name ?? null} scopeLabel={scopeLabel}
        onScope={() => setScopeOpen(true)} onOpenRun={openRun}
        idx={idx} pageNo={pageNo} pageList={pageList} onGoTo={(i) => { setPageIdx(i); setSel(null); }}
        warnPages={warnPages} nextWarn={nextWarn}
        voteOptions={voteOptions} prodShown={prodShown} prodAvailable={prodAvailable} page={page} onVote={vote}
        busy={busy} ready={ready} active={active} onStart={start}
        variants={variants} col={col} draftName={draftName}
        onToggleProd={() => { setShowProd(!showProd); if (col === "prod") setCol("orig"); }}
        onOpenVariant={(label) => { setCol(label); setPanelOpen(true); }}
        onRemoveVariant={removeVariant} onAddVariant={addVariant}
        columnsCount={columns.length} estimate={estimate} estimateError={estimateError}
        statusArea={!scopeOpen && uploadArea} confirming={confirming} onCancelConfirm={() => setConfirming(false)}
        scope={scope} act={act} />

      <Mesa panelOpen={panelOpen} onTogglePanel={() => setPanelOpen(!panelOpen)} view={view} onView={setView}
        hiWarn={hiWarn} onHiWarn={setHiWarn} columns={columns} noBooks={books.length === 0}
        emptyText={pageNo === null ? estimateError ?? "Elige qué páginas evaluar con el alcance de la derecha." : null}
        onUpload={() => { setScopeOpen(true); prepare.setUploadOpen(true); }}
        page={page} col={col} sel={sel} loading={pageLoading}
        onSelect={(c, b) => { setCol(c); setSel(b); if (b !== null || c !== col) setPanelOpen(true); }}
        panel={(
          <Panel col={col} columns={panelColumns} page={page} sel={sel} onClearSel={() => setSel(null)}
            variant={selVariant} modified={selModified}
            onChange={(changes) => selVariant && setVariant(selVariant.label, changes)}
            task={task} drafts={drafts} productionPrompt={prompts[task]}
            onDraftSaved={(d) => setDrafts((ds) => [...ds.filter((x) => x.id !== d.id), d].sort((a, b) => a.id - b.id))}
            onError={(text) => setNotice({ kind: "error", text })}
            tryState={tryState} onTry={() => tryPage()} run={run} pageCount={pageList.length} />
        )} />
    </main>
  );
}
