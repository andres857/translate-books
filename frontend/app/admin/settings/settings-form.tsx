"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  DEEPSEEK_MODELS, getSettings, saveSettings, SETTINGS_EVENT, testSettings, THINKING_LEVELS,
  type SettingsChanges, type TranslationSettings,
} from "@/lib/api";
import { IconCheck, IconInfo, IconWarn } from "../../components/art";

type Notice = { kind: "ok" | "error"; text: string } | null;

const formOf = (s: TranslationSettings): SettingsChanges => ({
  provider: s.provider, deepseek_model: s.deepseek_model, deepseek_thinking: s.deepseek_thinking,
  deepseek_concurrency: s.deepseek_concurrency,
});

/** Formulario de Configuración. `initial` llega del servidor (page.tsx); si no se pudo leer, se pide aquí. */
export function SettingsForm({ initial }: { initial: TranslationSettings | null }) {
  const [current, setCurrent] = useState<TranslationSettings | null>(initial);
  const [form, setForm] = useState<SettingsChanges>(initial ? formOf(initial) : {});
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState<"save" | "test" | null>(null);
  const [notice, setNotice] = useState<Notice>(null);

  useEffect(() => {
    if (initial) return; // ya vino del servidor
    getSettings()
      .then((s) => {
        setCurrent(s);
        setForm(formOf(s));
      })
      .catch((e) => setNotice({ kind: "error", text: (e as Error).message }));
  }, [initial]);

  const set = (changes: SettingsChanges) => {
    setForm((f) => ({ ...f, ...changes }));
    setNotice(null);
  };

  async function save(): Promise<boolean> {
    setBusy("save");
    setNotice(null);
    try {
      const saved = await saveSettings({
        ...form,
        ...(key.trim() ? { deepseek_api_key: key.trim() } : {}),
      });
      setCurrent(saved);
      setKey("");
      window.dispatchEvent(new Event(SETTINGS_EVENT));
      setNotice({ kind: "ok", text: "Configuración guardada. Se aplica al próximo libro que traduzcas." });
      return true;
    } catch (e) {
      setNotice({ kind: "error", text: (e as Error).message });
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function test() {
    if (!(await save())) return;
    setBusy("test");
    try {
      const r = await testSettings();
      setNotice({ kind: r.ok ? "ok" : "error", text: r.message });
    } catch (e) {
      setNotice({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  }

  if (!current) {
    return (
      <main>
        <section className="card"><p className="muted">{notice?.text ?? "Cargando configuración…"}</p></section>
      </main>
    );
  }

  const provider = form.provider ?? current.provider;
  const models = current.deepseek_models?.length ? current.deepseek_models : Object.keys(DEEPSEEK_MODELS);
  const model = form.deepseek_model ?? current.deepseek_model;

  return (
    <main>
      <div className="page-head">
        <div>
          <h1>Configuración</h1>
          <p>Llave y modelo de DeepSeek para traducir y corregir. Se aplica al siguiente libro, sin reiniciar.</p>
        </div>
        <Link className="btn secondary" href="/">Ver libros</Link>
      </div>

      <section className="card" aria-labelledby="method-title">
        <h2 id="method-title">API de DeepSeek</h2>
        <p className="muted">Se paga por uso, sin límite de sesión. Si la cuenta se queda sin saldo, el trabajo se detiene y puedes reanudarlo sin repetir lo ya traducido.</p>

        <div className="form-grid">
          {provider === "deepseek" && (
            <>
              <label className="control">
                Llave de DeepSeek
                <input
                  type="password"
                  autoComplete="off"
                  placeholder={current.deepseek_key_set ? `Guardada (••••${current.deepseek_key_hint}). Escribe otra para cambiarla` : "sk-…"}
                  value={key}
                  onChange={(e) => {
                    setKey(e.target.value);
                    setNotice(null);
                  }}
                />
              </label>
              <label className="control">
                Modelo
                <select value={model} onChange={(e) => set({ deepseek_model: e.target.value })}>
                  {models.map((m) => <option key={m} value={m}>{DEEPSEEK_MODELS[m] ?? m}</option>)}
                  {!models.includes(model) && <option value={model}>{model} (no válido)</option>}
                </select>
              </label>
              <label className="control">
                Razonamiento
                <select
                  value={form.deepseek_thinking}
                  onChange={(e) => set({ deepseek_thinking: e.target.value as TranslationSettings["deepseek_thinking"] })}
                >
                  {Object.entries(THINKING_LEVELS).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
                </select>
              </label>
              <label className="control">
                Llamadas simultáneas
                <input
                  type="number" min={1} max={32} step={1}
                  value={form.deepseek_concurrency ?? ""}
                  onChange={(e) => set({ deepseek_concurrency: e.target.value === "" ? undefined : Number(e.target.value) })}
                />
              </label>
            </>
          )}

          {provider === "fake" && (
            <div className="alert full">
              <IconInfo />
              <span>Modo de prueba: inserta texto falso para revisar la maquetación sin llamar a ningún modelo.</span>
            </div>
          )}
        </div>

        {notice && (
          <div className={`alert ${notice.kind === "ok" ? "ok" : "error"}`} role={notice.kind === "ok" ? "status" : "alert"}>
            {notice.kind === "error" ? <IconWarn /> : <IconCheck />}
            <span>{notice.text}</span>
          </div>
        )}

        <div className="row">
          <button className="btn" disabled={busy !== null} onClick={save}>
            {busy === "save" ? "Guardando…" : "Guardar"}
          </button>
          <button className="btn secondary" disabled={busy !== null} onClick={test}>
            {busy === "test" ? "Probando…" : "Probar conexión"}
          </button>
          <button
            type="button"
            className="btn ghost"
            aria-pressed={provider === "fake"}
            disabled={busy !== null}
            onClick={() => set({ provider: provider === "fake" ? "deepseek" : "fake" })}
          >
            {provider === "fake" ? "Salir del modo de prueba" : "Modo de prueba sin API"}
          </button>
        </div>
      </section>
    </main>
  );
}
