"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getSettings, saveSettings, SETTINGS_EVENT, testSettings, type SettingsChanges, type TranslationSettings,
} from "@/lib/api";
import { IconCheck, IconInfo, IconWarn } from "../../components/art";

type Notice = { kind: "ok" | "error"; text: string } | null;

export default function AdminSettingsPage() {
  const [current, setCurrent] = useState<TranslationSettings | null>(null);
  const [form, setForm] = useState<SettingsChanges>({});
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState<"save" | "test" | null>(null);
  const [notice, setNotice] = useState<Notice>(null);

  useEffect(() => {
    getSettings()
      .then((s) => {
        setCurrent(s);
        setForm({
          provider: s.provider, deepseek_model: s.deepseek_model, deepseek_thinking: s.deepseek_thinking,
        });
      })
      .catch((e) => setNotice({ kind: "error", text: (e as Error).message }));
  }, []);

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

  return (
    <main>
      <div className="page-head">
        <div>
          <h1>Configuración</h1>
          <p>Llave y modelo de DeepSeek para traducir y corregir. Se aplica al siguiente libro, sin reiniciar.</p>
        </div>
        <Link className="btn secondary" href="/admin">Ver libros</Link>
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
                <input value={form.deepseek_model ?? ""} onChange={(e) => set({ deepseek_model: e.target.value })} />
              </label>
              <label className="control">
                Razonamiento
                <select
                  value={form.deepseek_thinking}
                  onChange={(e) => set({ deepseek_thinking: e.target.value as TranslationSettings["deepseek_thinking"] })}
                >
                  <option value="disabled">Desactivado (más rápido)</option>
                  <option value="low">Bajo</option>
                  <option value="high">Alto (más cuidadoso)</option>
                  <option value="max">Máximo</option>
                </select>
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
