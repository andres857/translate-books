"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getPrompts, listDrafts, type PromptDraft, type PromptInfo, type PromptTask } from "@/lib/api";
import { IconCheck, IconCopy, IconWarn } from "../../components/art";

const ORDER: PromptTask[] = ["translate", "correct", "shorten", "names"];
const MODE: Record<PromptInfo["mode"], string> = { translate: "Traducir libro", digitize: "Solo digitalizar" };

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="btn ghost"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {
          setDone(false);
        }
      }}
    >
      {done ? <IconCheck width={16} height={16} /> : <IconCopy width={16} height={16} />}
      {done ? "Copiado" : "Copiar"}
    </button>
  );
}

export default function PromptsPage() {
  const [prompts, setPrompts] = useState<Record<PromptTask, PromptInfo> | null>(null);
  const [drafts, setDrafts] = useState<PromptDraft[]>([]);
  const [tab, setTab] = useState<PromptTask>("translate");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPrompts().then(setPrompts).catch((e) => setError((e as Error).message));
    listDrafts().then(setDrafts).catch(() => setDrafts([]));
  }, []);

  function tabKey(e: React.KeyboardEvent) {
    const i = ORDER.indexOf(tab);
    const next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : -1;
    if (next < 0 || next >= ORDER.length) return;
    e.preventDefault();
    setTab(ORDER[next]);
    document.getElementById(`ptab-${ORDER[next]}`)?.focus();
  }

  const p = prompts?.[tab];
  const own = drafts.filter((d) => d.task === tab);
  const testable = tab === "translate" || tab === "correct";

  return (
    <main className="wide">
      <div className="page-head">
        <div>
          <h1>Prompts</h1>
          <p>Instrucciones que recibe el modelo en cada tarea. Son las de producción y no se editan aquí.</p>
        </div>
        <Link className="btn" href="/admin/playground">Probar en el playground</Link>
      </div>

      {error && <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>}

      <div className="tabs" role="tablist" aria-label="Tareas" onKeyDown={tabKey}>
        {ORDER.map((t) => (
          <button key={t} id={`ptab-${t}`} role="tab" type="button" aria-selected={tab === t}
            aria-controls="prompt-panel" tabIndex={tab === t ? 0 : -1} onClick={() => setTab(t)}>
            {prompts?.[t].title ?? t}
          </button>
        ))}
      </div>

      <div id="prompt-panel" role="tabpanel" aria-labelledby={`ptab-${tab}`} className="stack">
        {!p && !error && <section className="card"><p className="muted">Cargando prompts…</p></section>}
        {p && (
          <>
            <section className="card">
              <div className="card-head">
                <div>
                  <h2>{p.title}</h2>
                  <p className="muted">{p.description}</p>
                </div>
                <div className="row">
                  <span className="badge info">{MODE[p.mode]}</span>
                  <span className="badge">Versión {p.version}</span>
                </div>
              </div>
              <div className="code-head">
                <h3>Prompt del sistema</h3>
                <CopyButton text={p.text} />
              </div>
              <pre className="code">{p.text}</pre>
              <h3>Mensaje de usuario</h3>
              <pre className="code small">{p.user_template}</pre>
            </section>

            <section className="card">
              <h2>Por método</h2>
              <p className="muted">El prompt es el mismo; cambia cómo se pide y se valida la salida.</p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Método</th><th>Formato de salida y llamada</th></tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>API de DeepSeek</td>
                      <td className="wrap"><pre className="code small flat">{p.output.deepseek}</pre></td>
                    </tr>
                    <tr>
                      <td>Suscripción de Claude</td>
                      <td className="wrap"><pre className="code small flat">{p.output.claude}</pre></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            {testable && (
              <section className="card">
                <div className="card-head">
                  <h2>Borradores de esta tarea</h2>
                  <Link className="btn secondary" href={`/admin/playground?task=${tab}`}>Nuevo borrador</Link>
                </div>
                {own.length === 0 && <p className="muted">Aún no hay borradores. Créalos desde el playground.</p>}
                {own.length > 0 && (
                  <ul className="draft-list">
                    {own.map((d) => (
                      <li key={d.id}>
                        <span>{d.name}</span>
                        <Link href={`/admin/playground?draft=${d.id}`}>Probar en el playground</Link>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </main>
  );
}
