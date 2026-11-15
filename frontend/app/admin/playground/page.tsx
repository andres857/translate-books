"use client";

/* Playground: mesa para evaluar el rendimiento de la traducción. Compara página a página el PDF original con el
   PDF que produce cada variante (método, modelo, razonamiento y prompt), más la traducción de producción.
   Controles fijos arriba; columnas con scroll lateral; panel derecho según la columna seleccionada. */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  cancelRun, composeRun, createRun, estimateRun, getJob, getPrompts, getRun, getRunPage, getSegments, jobPageImageUrl,
  listChapters, listDrafts, listPlaygroundBooks, listRuns, resumeRun, runPageImageUrl, tryVariantPage, uploadBook,
  voteRunPage, type Chapter, type JobStatus, type Estimate, type PlaygroundBook, type PlaygroundRun, type PlaygroundScope, type PlaygroundTask,
  type PromptDraft, type RunPage, type VariantInput,
} from "@/lib/api";
import type { UploadProgress } from "@/lib/api";
import { UploadProgressBar } from "@/app/components/upload-progress";
import { IconCheck, IconHourglass, IconUpload, IconWarn, IconX } from "../../components/art";
import { Panel, type PanelColumn } from "./panel";
import { ScopeDialog, type ScopeValue } from "./scope-dialog";
import {
  DEFAULTS, duration, fmtN, LABELS, MAX_VARIANTS, pageFromSegments, parsePages, sameConfig, toInput, variantName,
  type ColId, type LocalVariant,
} from "./shared";
import { Stage, type Column } from "./stage";

const STATUS_TEXT: Record<PlaygroundRun["status"], string> = {
  queued: "en cola", running: "en curso", paused: "en pausa", done: "terminada", failed: "con error", cancelled: "cancelada",
};
const SCOPE_TEXT: Record<PlaygroundScope, string> = { page: "Página", pages: "Páginas", chapter: "Capítulo", book: "Libro completo" };

type Notice = { kind: "ok" | "error"; text: string } | null;

export default function PlaygroundPage() {
  const [books, setBooks] = useState<PlaygroundBook[]>([]);
  const [bookId, setBookId] = useState<number | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chapter, setChapter] = useState("");
  const [scope, setScope] = useState<PlaygroundScope>("page");
  const [onePage, setOnePage] = useState("1");
  const [pagesSpec, setPagesSpec] = useState("");
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [estimateError, setEstimateError] = useState<string | null>(null);
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
  // subir un libro solo para evaluar: se analiza y se separa por capítulos, sin traducir nada
  const [uploadOpen, setUploadOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [rights, setRights] = useState(false);
  const [uploading, setUploading] = useState<UploadProgress | null | false>(false); // false = sin subida en curso
  const [prep, setPrep] = useState<JobStatus | null>(null);
  // resumen de la última preparación, mostrado en la vista de subida
  const [prepDone, setPrepDone] = useState<{ name: string; pages: number; blocks: number; chapters: number; detected: boolean } | null>(null);
  // primer paso: elegir libro y alcance en el modal; luego se entra en la mesa
  const [scopeOpen, setScopeOpen] = useState(true);

  const book = books.find((b) => b.id === bookId) ?? null;
  const task: PlaygroundTask = run?.task ?? book?.task ?? "translate";
  const chapterInfo = chapter === "" ? null : chapters[Number(chapter)] ?? null;
  const spec = scope === "page" ? onePage : scope === "pages" ? pagesSpec : scope === "chapter" ? chapterInfo?.pages ?? "" : "";
  const ready = !!bookId && (scope === "book" || spec.trim() !== "");
  const active = !!run && (run.status === "queued" || run.status === "running");

  const pageList = useMemo(
    () => (run ? run.page_list ?? parsePages(run.pages) : parsePages(estimate?.page_spec)),
    [run, estimate?.page_spec],
  );
  const idx = Math.min(pageIdx, Math.max(0, pageList.length - 1));
  const pageNo = pageList[idx] ?? null;
  const prodAvailable = run ? !!run.production : task === "translate" && !!book?.production;
  const prodShown = showProd && prodAvailable;
  const resultFor = (label: string) => run?.results?.find((r) => r.label === label) ?? null;
  const runVariantFor = (label: string) => run?.variants.find((v) => v.label === label) ?? null;
  const draftName = (prompt: VariantInput["prompt"]) =>
    prompt === "production" ? "Producción" : drafts.find((d) => d.id === prompt)?.name ?? `Borrador ${prompt}`;

  // ------------------------------------------------------------------ carga
  const refreshRuns = useCallback(() => listRuns().then(setRuns).catch(() => undefined), []);

  const show = useCallback((r: PlaygroundRun) => {
    setRun(r);
    setScopeOpen(false);
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
          getRun(runParam).then(show).catch(() => setScopeOpen(true));
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
    const choosing = scopeOpen && !run; // eligiendo en el modal: alcance por defecto según haya capítulos
    listChapters(bookId)
      .catch(() => [] as Chapter[])
      .then((chs) => {
        setChapters(chs);
        if (!choosing) return;
        if (chs.length) setScope("chapter");
        else {
          setScope("pages");
          setPagesSpec(`1-${Math.min(10, count)}`);
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId]);

  // estimación del alcance elegido (para la siguiente ejecución)
  const variantsKey = JSON.stringify(variants.map(toInput));
  useEffect(() => {
    setConfirming(false);
    if (!ready || !bookId) {
      setEstimate(null);
      setEstimateError(null);
      return;
    }
    let alive = true;
    const timer = setTimeout(() => {
      estimateRun({ job_id: bookId, scope, pages: spec, variants: JSON.parse(variantsKey) as VariantInput[] })
        .then((e) => { if (alive) { setEstimate(e); setEstimateError(null); } })
        .catch((e) => { if (alive) { setEstimate(null); setEstimateError((e as Error).message); } });
    }, 400);
    return () => { alive = false; clearTimeout(timer); };
  }, [bookId, scope, spec, variantsKey, ready]);

  // los borradores son de una tarea: si el borrador ya no existe, la variante vuelve a producción
  useEffect(() => {
    setVariants((vs) => vs.map((v) => (typeof v.prompt === "number" && !drafts.some((d) => d.id === v.prompt && d.task === task)
      ? { ...v, prompt: "production" } : v)));
  }, [task, drafts]);

  // seguimiento de la evaluación abierta
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
  }, [run, refreshRuns]);

  // preparación de un libro recién subido: al terminar se selecciona y se informa de lo extraído
  useEffect(() => {
    if (!prep || prep.status === "done" || prep.status === "failed" || prep.status === "cancelled") return;
    const id = prep.id;
    const timer = setTimeout(async () => {
      try {
        const next = await getJob(id);
        setPrep(next);
        if (next.status === "done") {
          const list = await listPlaygroundBooks();
          setBooks(list);
          const b = list.find((x) => x.id === id);
          setScopeOpen(true);
          changeBook(id);
          const chs = await listChapters(id).catch(() => [] as Chapter[]);
          setPrepDone({
            name: b?.name ?? next.original_name, pages: b?.page_count ?? next.page_count, blocks: b?.blocks ?? 0,
            chapters: chs.length, detected: chs[0]?.source === "detected",
          });
          setUploadOpen(true); // el resumen se ve en la misma vista de subida
          setPrep(null);
        }
      } catch {
        /* se reintenta */
      }
    }, 1500);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prep]);

  async function prepareUpload() {
    if (!file || !rights) return;
    setNotice(null);
    setUploading(null);
    try {
      const job = await uploadBook(file, rights, { mode: "prepare", ocrLang: "en", correct: false }, setUploading);
      setUploading(false);
      setPrep(job);
      setPrepDone(null);
      setFile(null);
      setRights(false);
    } catch (e) {
      setUploading(false);
      fail(e);
    }
  }

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageKey]);

  // ------------------------------------------------------------------ acciones
  const fail = (e: unknown) => setNotice({ kind: "error", text: (e as Error).message });

  function changeBook(id: number) {
    setBookId(id);
    setRun(null);
    setPageIdx(0);
    setSel(null);
  }

  function setVariant(label: string, changes: Partial<VariantInput>) {
    setVariants((vs) => vs.map((v) => (v.label === label ? { ...v, ...changes } : v)));
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
  function tryPage() {
    if (!run || !selVariant || pageNo === null) return;
    setNotice(null);
    act(() => tryVariantPage(run.id, selVariant.label, pageNo, toInput(selVariant)));
  }

  // ------------------------------------------------------------------ columnas
  const warnBadge = (n: number | undefined) => n === undefined ? null : n > 0
    ? <span className="badge review">⚠ {n} {n === 1 ? "aviso" : "avisos"}</span>
    : <span className="badge ok">Sin avisos</span>;

  const columns: Column[] = [];
  if (pageNo !== null && bookId) {
    columns.push({
      id: "orig", tag: "EN", name: "Original",
      sub: <><span className="muted pg-ellipsis">{book?.original_name ?? run?.book}</span><span className="pg-meta">{page ? `${page.blocks.length} bloques` : ""}</span></>,
      image: run ? runPageImageUrl(run.id, pageNo, "orig") : jobPageImageUrl(bookId, pageNo, "original"),
    });
    if (prodShown) {
      columns.push({
        id: "prod", tag: "ES", name: "Producción",
        sub: <>{page?.vote === "prod" && <span className="badge info">Mejor</span>}{warnBadge(page?.metrics.prod?.warn_blocks)}<span className="pg-meta">Libro traducido</span></>,
        image: run ? runPageImageUrl(run.id, pageNo, "prod") : jobPageImageUrl(bookId, pageNo, "translated"),
      });
    }
    for (const v of variants) {
      const rv = runVariantFor(v.label);
      const res = rv ? resultFor(v.label) : null;
      const m = page?.metrics[v.label];
      const modified = !!rv && !sameConfig(v, rv);
      let placeholder: Column["placeholder"];
      if (!run || !rv) placeholder = { text: "Sin ejecutar: pulsa «Ejecutar» para evaluar esta variante." };
      else if (!res) {
        const i = run.variants.findIndex((x) => x.label === v.label);
        placeholder = {
          text: run.status === "running" && run.current_variant === i
            ? `Traduciendo… ${fmtN.format(run.blocks_done ?? 0)} / ${fmtN.format(run.blocks_total ?? 0)} bloques`
            : run.status === "queued" || run.status === "running" ? "En cola"
              : run.status === "paused" ? "En pausa: reanuda la evaluación para continuar." : "Esta variante no llegó a ejecutarse.",
        };
      } else if (task === "correct") placeholder = { text: "Los libros digitalizados se comparan por bloques: cambia la vista a «Bloques»." };
      else if (run.composing === v.label || (active && !res.composed && !res.compose_error)) placeholder = { text: "Maquetando el PDF de esta variante…" };
      else if (res.compose_error) placeholder = { text: res.compose_error, action: { label: "Volver a maquetar", onClick: () => act(() => composeRun(run.id)) } };
      else if (!res.composed) placeholder = {
        text: "Esta evaluación es anterior a la mesa de PDF: su texto está evaluado pero no tiene PDF maquetado.",
        action: { label: "Maquetar PDF", onClick: () => act(() => composeRun(run.id)) },
      };
      columns.push({
        id: v.label, tag: v.label, name: variantName(v),
        sub: (
          <>
            {page?.vote === v.label && <span className="badge info">Mejor</span>}
            {res?.error && <span className="badge review" title={res.error}>Error</span>}
            {m?.stale && <span className="badge" title="Esta página se evaluó con la configuración anterior">config. anterior</span>}
            {modified && <span className="badge">modificada</span>}
            {warnBadge(m?.warn_blocks)}
            <span className="pg-meta">{res ? `${duration(res.seconds)} · ` : ""}{draftName(v.prompt)}</span>
          </>
        ),
        image: res?.composed && task === "translate" && run ? runPageImageUrl(run.id, pageNo, v.label, res.composed_at) : null,
        placeholder,
      });
    }
  }

  const panelColumns: PanelColumn[] = [
    ...(prodShown ? [{ id: "prod", tag: "ES", name: "Producción", result: null }] : []),
    ...variants.map((v) => ({ id: v.label, tag: v.label, name: variantName(v), result: runVariantFor(v.label) ? resultFor(v.label) : null })),
  ];

  const voteOptions = run ? [...variants.filter((v) => resultFor(v.label) && runVariantFor(v.label)).map((v) => v.label)] : [];
  const warnPages = useMemo(() => {
    const out = new Set<number>();
    for (const id of [...(prodShown ? ["prod"] : []), ...variants.map((v) => v.label)]) {
      for (const n of run?.summary?.[id]?.warn_pages ?? []) out.add(n);
    }
    return [...out].sort((a, b) => a - b);
  }, [run, prodShown, variants]);
  const nextWarn = pageNo === null ? undefined : warnPages.find((n) => n > pageNo) ?? warnPages[0];

  const selRv = selVariant ? runVariantFor(selVariant.label) : null;
  const tryState = {
    busy: active && run?.trying?.label === selVariant?.label,
    enabled: !!run && run.status === "done" && !!selRv && !!resultFor(selVariant?.label ?? "") && pageNo !== null,
    hint: !run ? "Ejecuta la evaluación primero: después podrás probar cambios página a página."
      : !selRv ? "Esta variante es nueva: pulsa «Ejecutar» para evaluarla con todo el alcance."
        : active ? "Espera a que termine la evaluación en curso."
          : run.status !== "done" ? "La evaluación tiene que estar terminada para probar una página."
            : "Solo vuelve a traducir esta página; el resto queda marcado como «configuración anterior» si cambias algo.",
  };

  const usesApi = variants.some((v) => v.provider === "deepseek");

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
  const closeUpload = () => { setUploadOpen(false); setFile(null); setRights(false); setDrag(false); setPrepDone(null); };
  const prepFailed = prep?.status === "failed" || prep?.status === "cancelled";
  const prepStage = prep?.stages.find((st) => st.state === "in_progress")?.label ?? (prep?.status === "queued" ? "En cola" : "…");
  // vista de subida: ocupa todo el modal (cabecera, cuerpo y pie propios); «Cancelar» vuelve al alcance
  const uploadView = uploadOpen ? (
    <>
      <div className="pg-dialog-head">
        <div className="stack">
          <strong id="pg-dialog-title">{prepDone ? "Libro listo para evaluar" : prep ? "Preparando el libro" : "Subir un libro para evaluar"}</strong>
          <span className="muted">
            Solo se prepara: se analiza el PDF, se separa por capítulos y se protegen números, glifos y términos.
            No se traduce nada ni se gasta saldo hasta que pulses «Ejecutar».
          </span>
        </div>
      </div>
      <div className="pg-upload-view">
        {prepDone ? (
          <section className="pg-upload-box pg-upload-result" aria-live="polite" aria-labelledby="pg-prep-done">
            <span className="pg-upload-icon ok"><IconCheck /></span>
            <div className="stack pg-upload-text">
              <strong id="pg-prep-done">Libro preparado sin traducir</strong>
              <span className="muted pg-ellipsis" title={prepDone.name}>{prepDone.name}</span>
            </div>
            <dl className="pg-upload-stats">
              <div><dt>Páginas</dt><dd>{fmtN.format(prepDone.pages)}</dd></div>
              <div><dt>Bloques</dt><dd>{fmtN.format(prepDone.blocks)}</dd></div>
              <div><dt>Capítulos</dt><dd>{prepDone.chapters ? fmtN.format(prepDone.chapters) : "—"}</dd></div>
            </dl>
            <span className="muted pg-upload-text">
              {prepDone.chapters
                ? `${prepDone.detected ? "Capítulos detectados por los títulos. " : ""}Elige un capítulo o un intervalo de páginas.`
                : "No se detectaron capítulos: define un intervalo de páginas para evaluar."}
            </span>
          </section>
        ) : prep ? (
          <section className="pg-upload-box" aria-live="polite" aria-labelledby="pg-prep-title">
            <div className="stack">
              <strong id="pg-prep-title" className="pg-ellipsis" title={prep.original_name}>Preparando «{prep.original_name}»</strong>
              <div className="pct">{prepFailed ? "—" : `${Math.round(prep.progress)} %`}
                <small>{prepFailed ? "detenido" : `${prepStage}${prep.current_page ? ` · pág. ${prep.current_page} de ${prep.page_count}` : ""}`}</small>
              </div>
              <div className="progress" aria-label="Preparación"><div style={{ width: `${prep.progress}%` }} /></div>
            </div>
            <ul className="stages">
              {prep.stages.map((st) => (
                <li key={st.key} className={st.state}>
                  <span className="name">{st.label}</span>
                  {st.state !== "pending" && (
                    <span className={`badge ${st.state}`}>
                      {st.state === "completed" ? <IconCheck /> : st.state === "in_progress" ? <IconHourglass /> : <IconX />}
                      {st.state === "completed" ? "Completado" : st.state === "in_progress" ? "En progreso" : st.state === "paused" ? "En pausa" : "Error"}
                    </span>
                  )}
                </li>
              ))}
            </ul>
            {prepFailed && (
              <div className="alert error" role="alert">
                <IconWarn />
                <span>{prep.error ?? "No se pudo preparar el libro."}</span>
              </div>
            )}
          </section>
        ) : uploading !== false && file ? (
          <section className="pg-upload-box">
            <UploadProgressBar name={file.name} progress={uploading} />
          </section>
        ) : (
        <div className="pg-upload-box">
          <div
            className={`dropzone ${drag ? "active" : ""}`}
            role="button"
            tabIndex={0}
            aria-label="Zona para arrastrar y soltar el PDF o seleccionarlo"
            onClick={() => fileRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileRef.current?.click(); }
            }}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); setFile(e.dataTransfer.files?.[0] ?? null); }}
          >
            <IconUpload />
            {file ? (
              <p><span className="file-chip">{file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB</span></p>
            ) : (
              <p><strong>Arrastra el PDF aquí</strong> o <strong>haz clic para seleccionarlo</strong></p>
            )}
            <p className="muted">{file ? "Haz clic para elegir otro archivo" : "Solo archivos PDF"}</p>
            <input ref={fileRef} id="pg-file" type="file" accept="application/pdf,.pdf" hidden
              onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </div>
          <label className="check">
            <input type="checkbox" checked={rights} onChange={(e) => setRights(e.target.checked)} />
            <span>Tengo derechos de uso sobre este libro</span>
          </label>
          {notice?.kind === "error" && (
            <div className="alert error" role="alert">
              <IconWarn />
              <span>{notice.text}</span>
            </div>
          )}
        </div>
        )}
      </div>
      <div className="pg-dialog-foot">
        {prepDone ? (
          <>
            <span className="muted">Sin traducir · no se ha gastado saldo</span>
            <span className="pg-spacer" />
            <button type="button" className="btn secondary" onClick={() => setPrepDone(null)}>Subir otro libro</button>
            <button type="button" className="btn" onClick={closeUpload}>Elegir qué evaluar</button>
          </>
        ) : prep ? (
          <>
            <span className="muted">{prepFailed ? "La preparación se ha detenido" : "Puedes volver: la preparación sigue en segundo plano"}</span>
            <span className="pg-spacer" />
            {prepFailed ? (
              <>
                <button type="button" className="btn secondary" onClick={() => { setPrep(null); closeUpload(); }}>Cancelar</button>
                <button type="button" className="btn" onClick={() => setPrep(null)}>Probar de nuevo</button>
              </>
            ) : (
              <button type="button" className="btn secondary" onClick={closeUpload}>Volver al alcance</button>
            )}
          </>
        ) : (
          <>
            <span className="muted">{uploading !== false ? "No cierres esta ventana hasta que termine la subida"
              : file ? (rights ? "Listo para preparar" : "Confirma que tienes derechos de uso") : "Elige un PDF"}</span>
            <span className="pg-spacer" />
            <button type="button" className="btn secondary" disabled={uploading !== false} onClick={closeUpload}>Cancelar</button>
            <button type="button" className="btn" disabled={!file || !rights || uploading !== false} onClick={prepareUpload}>
              {uploading !== false ? "Subiendo…" : "Preparar libro"}
            </button>
          </>
        )}
      </div>
    </>
  ) : null;
  // progreso de la preparación y avisos (barra lateral del modal o encima de la mesa)
  const uploadArea = (
    <>
        {prep && (
          <div className="pg-status" aria-live="polite">
            <div className="progress" aria-label="Preparación"><div style={{ width: `${prep.progress}%` }} /></div>
            <span className="muted">
              Preparando «{prep.original_name}»: {prep.stages.find((s) => s.state === "in_progress")?.label ?? (prep.status === "queued" ? "en cola" : "…")}
              {prep.current_page ? ` · pág. ${prep.current_page} de ${prep.page_count}` : ""} · sin traducir
            </span>
            {(prep.status === "failed" || prep.status === "cancelled") && (
              <button type="button" className="btn ghost" onClick={() => setPrep(null)}>Cerrar</button>
            )}
          </div>
        )}
        {notice && (
          <div className={`alert ${notice.kind === "ok" ? "ok" : "error"}`} role={notice.kind === "ok" ? "status" : "alert"}>
            {notice.kind === "ok" ? <IconCheck /> : <IconWarn />}
            <span>{notice.text}</span>
            <button type="button" className="btn ghost" onClick={() => setNotice(null)}>Cerrar</button>
          </div>
        )}
    </>
  );

  // ------------------------------------------------------------------ vista
  return (
    <main className="pg">
      <ScopeDialog open={scopeOpen} books={books} bookId={bookId} onBook={changeBook} chapters={chapters}
        value={scopeValue} onChange={setScopeValue} estimate={estimate} estimateError={estimateError}
        onClose={() => { setScopeOpen(false); closeUpload(); }}
        upload={uploadArea}
        uploadView={uploadView}
        onCancelUpload={closeUpload}
        headAction={(
          <button type="button" className="btn secondary" onClick={() => { setNotice(null); setUploadOpen(true); }}>
            <IconUpload /> {prep ? "Ver la preparación" : "Subir un libro nuevo"}
          </button>
        )} />
      <header className="pg-controls" aria-label="Controles de evaluación">
        <div className="pg-bar">
          <div className="pg-title">
            <strong>Playground</strong>
            <span>{run ? `Evaluación n.º ${run.id} · ${STATUS_TEXT[run.status]}` : "Nueva evaluación"}</span>
          </div>
          <button type="button" className="pg-scope-btn" aria-haspopup="dialog" title="Cambiar el libro o la parte que se evalúa"
            onClick={() => setScopeOpen(true)}>
            <span className="pg-ellipsis"><strong>{book?.name ?? "Sin libro"}</strong> · {scopeLabel}</span>
            <span className="pg-scope-change">Cambiar</span>
          </button>
          <label className="sr-only" htmlFor="pg-run">Evaluación</label>
          <select id="pg-run" className="pg-history" value={run?.id ?? ""} onChange={(e) => openRun(e.target.value)}>
            <option value="">Nueva evaluación</option>
            {runs.filter((r) => !bookId || r.job_id === bookId).map((r) => (
              <option key={r.id} value={r.id}>
                N.º {r.id} · {SCOPE_TEXT[r.scope ?? "pages"]} {r.scope === "book" ? "" : r.pages} · {r.variants.length} var. · {STATUS_TEXT[r.status]}
              </option>
            ))}
          </select>
          <span className="pg-spacer" />
          <div className="pg-pager" aria-label="Página actual">
            <button className="btn secondary pg-icon" type="button" aria-label="Página anterior" disabled={idx <= 0}
              onClick={() => { setPageIdx(idx - 1); setSel(null); }}>‹</button>
            <output>{pageNo === null ? "Sin páginas" : `Pág. ${pageNo} · ${idx + 1}/${pageList.length}`}</output>
            <button className="btn secondary pg-icon" type="button" aria-label="Página siguiente" disabled={idx >= pageList.length - 1}
              onClick={() => { setPageIdx(idx + 1); setSel(null); }}>›</button>
            {warnPages.length > 0 && nextWarn !== undefined && (
              <button className="btn ghost" type="button" title="Ir a la siguiente página con avisos"
                onClick={() => { setPageIdx(pageList.indexOf(nextWarn)); setSel(null); }}>
                ⚠ {warnPages.length}
              </button>
            )}
          </div>
          {voteOptions.length + (prodShown ? 1 : 0) >= 2 && pageNo !== null && (
            <>
              <span className="pg-eyebrow">Mejor</span>
              <div className="seg-control" role="radiogroup" aria-label="Mejor columna en esta página">
                {[...(prodShown ? ["prod"] : []), ...voteOptions, "tie"].map((o) => (
                  <button key={o} type="button" role="radio" aria-checked={page?.vote === o} onClick={() => vote(o)}>
                    {o === "tie" ? "Empate" : o === "prod" ? "Prod." : o}
                  </button>
                ))}
              </div>
            </>
          )}
          <button className="btn" type="button" disabled={busy || !ready || !!estimateError || active} onClick={() => start()}>
            {busy ? "Enviando…" : active ? "En curso…" : "Ejecutar"}
          </button>
        </div>

        <div className="pg-bar">
          <span className="pg-eyebrow">Variantes</span>
          <div className="pg-chips">
            {prodAvailable && (
              <button type="button" className={`pg-chip pg-chip-toggle${prodShown ? " shown" : ""}`} aria-pressed={prodShown}
                title={prodShown ? "Ocultar la columna de producción" : "Mostrar la traducción de producción como referencia"}
                onClick={() => { setShowProd(!showProd); if (col === "prod") setCol("orig"); }}>
                <span className="variant-tag plain">ES</span>Producción
              </button>
            )}
            {variants.map((v) => (
              <div key={v.label} className={`pg-chip${col === v.label ? " on" : ""}`}>
                <button type="button" className="pg-chip-open" aria-pressed={col === v.label}
                  title={`Configurar la variante ${v.label} en el panel`}
                  onClick={() => { setCol(v.label); setPanelOpen(true); }}>
                  <span className="variant-tag">{v.label}</span>
                  <span>{variantName(v)}</span>
                  <small>{draftName(v.prompt)}</small>
                </button>
                {variants.length > 1 && (
                  <button type="button" className="pg-chip-x" aria-label={`Quitar variante ${v.label}`} onClick={() => removeVariant(v.label)}>×</button>
                )}
              </div>
            ))}
            {variants.length < MAX_VARIANTS && (
              <button type="button" className="pg-chip pg-chip-add" onClick={addVariant}>+ Variante</button>
            )}
          </div>
          <span className="muted">
            {variants.length === 1 ? "Añade una variante para comparar dos configuraciones" : `${columns.length} PDF en la mesa · máx. ${MAX_VARIANTS} variantes`}
          </span>
          <span className="pg-spacer" />
          <span className="muted pg-estimate" aria-live="polite">
            {estimateError ? <span className="error-text">{estimateError}</span>
              : estimate ? (
                <>
                  {estimate.pages} {estimate.pages === 1 ? "página" : "páginas"} · {fmtN.format(estimate.blocks)} bloques
                  · ~{fmtN.format(estimate.calls_per_variant)} {estimate.calls_per_variant === 1 ? "llamada" : "llamadas"} por variante
                  {estimate.seconds !== null ? ` · ~${duration(estimate.seconds)}` : ""}
                  {estimate.needs_confirm ? " · pide confirmación" : ""}
                </>
              ) : ready ? "Calculando…" : "Elige qué evaluar"}
          </span>
        </div>

        {!scopeOpen && uploadArea}
        {confirming && estimate && (
          <div className="alert" role="alertdialog" aria-labelledby="pg-confirm">
            <IconWarn />
            <div className="stack">
              <strong id="pg-confirm">¿Evaluar {scope === "book" ? "el libro completo" : `${estimate.pages} páginas`}?</strong>
              <span>
                Son {fmtN.format(estimate.blocks)} bloques y unas {fmtN.format(estimate.calls)} llamadas en total
                {estimate.seconds !== null ? `, alrededor de ${duration(estimate.seconds)}` : ""}.
                {usesApi && " Consume saldo de DeepSeek: si se agota, la evaluación se pausa y podrás reanudarla tras recargar."}
              </span>
              <div className="row">
                <button type="button" className="btn" onClick={() => start(true)}>Confirmar y ejecutar</button>
                <button type="button" className="btn ghost" onClick={() => setConfirming(false)}>Volver</button>
              </div>
            </div>
          </div>
        )}
        {run && (active || run.status === "paused") && (
          <div className="pg-status" aria-live="polite">
            <div className="progress" aria-label="Progreso"><div style={{ width: `${run.progress}%` }} /></div>
            <span className="muted">
              {run.trying ? `Probando la variante ${run.trying.label} en la pág. ${run.trying.page}` : ""}
              {run.status === "queued" ? (run.trying ? " · en cola" : "En cola: el worker la ejecuta cuando no hay libros pendientes.")
                : run.stage === "compose" ? `${run.trying ? " · " : ""}Maquetando el PDF de la variante ${run.composing ?? ""}…`
                  : run.blocks_total ? `${run.trying ? " · " : ""}${run.current_variant !== null && !run.trying ? `Variante ${run.variants[run.current_variant]?.label}: ` : ""}${fmtN.format(run.blocks_done ?? 0)} / ${fmtN.format(run.blocks_total)} bloques` : ""}
              {run.variants.length > 1 && !run.trying ? ` · ${run.results?.length ?? 0} de ${run.variants.length} variantes terminadas` : ""}
            </span>
            {run.status === "paused" && <button type="button" className="btn" onClick={() => act(() => resumeRun(run.id))}>Reanudar</button>}
            <button type="button" className="btn secondary" onClick={() => act(() => cancelRun(run.id))}>Cancelar</button>
          </div>
        )}
        {run?.error && (
          <div className="alert error" role="alert"><IconWarn /><span>{run.error}</span></div>
        )}
      </header>

      <div className={`pg-body${panelOpen ? "" : " no-panel"}`}>
        <div className="pg-stage">
          <div className="pg-stage-bar">
            <div className="seg-control" role="radiogroup" aria-label="Vista">
              <button type="button" role="radio" aria-checked={view === "page"} onClick={() => setView("page")}>Página PDF</button>
              <button type="button" role="radio" aria-checked={view === "blocks"} onClick={() => setView("blocks")}>Bloques</button>
            </div>
            <label className="toggle"><input type="checkbox" checked={hiWarn} onChange={(e) => setHiWarn(e.target.checked)} /> Resaltar avisos</label>
            <span className="pg-spacer" />
            <span className="muted">{columns.length} columnas</span>
            <button className="btn ghost" type="button" aria-pressed={panelOpen} onClick={() => setPanelOpen(!panelOpen)}>
              {panelOpen ? "Ocultar panel" : "Mostrar panel"}
            </button>
          </div>
          {books.length === 0 ? (
            <div className="pg-empty-state">
              <div className="stack">
                <p className="muted">Sube un libro para evaluar: solo se analiza y se separa por capítulos, sin traducir nada.</p>
                <button type="button" className="btn" onClick={() => { setScopeOpen(true); setUploadOpen(true); }}>Subir libro</button>
              </div>
            </div>
          ) : pageNo === null ? (
            <div className="pg-empty-state">
              <p className="muted">{estimateError ?? "Elige qué páginas evaluar con el alcance de la derecha."}</p>
            </div>
          ) : (
            <Stage columns={columns} page={page} view={view} hiWarn={hiWarn} selCol={col} selBlock={sel} loading={pageLoading}
              onSelect={(c, b) => { setCol(c); setSel(b); if (b !== null || c !== col) setPanelOpen(true); }} />
          )}
        </div>
        {panelOpen && (
          <Panel col={col} columns={panelColumns} page={page} sel={sel} onClearSel={() => setSel(null)}
            variant={selVariant} modified={!!selVariant && !!runVariantFor(selVariant.label) && !sameConfig(selVariant, runVariantFor(selVariant.label)!)}
            onChange={(changes) => selVariant && setVariant(selVariant.label, changes)}
            task={task} drafts={drafts} productionPrompt={prompts[task]}
            onDraftSaved={(d) => setDrafts((ds) => [...ds.filter((x) => x.id !== d.id), d].sort((a, b) => a.id - b.id))}
            onError={(text) => setNotice({ kind: "error", text })}
            tryState={tryState} onTry={tryPage} run={run} pageCount={pageList.length} />
        )}
      </div>
    </main>
  );
}
