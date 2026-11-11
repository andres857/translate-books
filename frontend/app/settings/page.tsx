"use client";

import { useEffect, useState } from "react";
import {
  getSettings, saveSettings, testSettings, type Provider, type SettingsChanges, type TranslationSettings,
} from "@/lib/api";
import { IconInfo, IconWarn } from "../components/art";

const MODES: { id: Provider; title: string; text: string }[] = [
  { id: "claude", title: "Claude · tu suscripción", text: "Usa el login de Claude Code de este equipo. Sin costo por llamada." },
  { id: "deepseek", title: "DeepSeek (API)", text: "Usa tu llave de DeepSeek. Se paga por uso." },
  { id: "fake", title: "Prueba sin API", text: "Texto falso para revisar la maquetación sin gastar nada." },
];

type Notice = { kind: "ok" | "error"; text: string } | null;

export default function SettingsPage() {
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
          claude_model: s.claude_model,
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
      const saved = await saveSettings({ ...form, ...(key.trim() ? { deepseek_api_key: key.trim() } : {}) });
      setCurrent(saved);
      setKey("");
      setNotice({ kind: "ok", text: "Ajustes guardados. Se aplican al próximo libro que traduzcas." });
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
        <section className="card"><p className="muted">{notice?.text ?? "Cargando ajustes…"}</p></section>
      </main>
    );
  }

  const provider = form.provider ?? current.provider;

  return (
    <main>
      <section className="card" aria-labelledby="mode-title">
        <div className="card-head">
          <h2 id="mode-title">Modo de traducción</h2>
        </div>
        <div className="modes" role="radiogroup" aria-labelledby="mode-title">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              role="radio"
              aria-checked={provider === m.id}
              className={`mode ${provider === m.id ? "on" : ""}`}
              onClick={() => set({ provider: m.id })}
            >
              <strong>{m.title}</strong>
              <span>{m.text}</span>
            </button>
          ))}
        </div>

        <div className="form-grid">
          {provider === "claude" && (
            <>
              <label>
                Modelo de Claude
                <select value={form.claude_model} onChange={(e) => set({ claude_model: e.target.value as "sonnet" | "opus" })}>
                  <option value="sonnet">Sonnet (recomendado)</option>
                  <option value="opus">Opus (más lento, consume más cuota)</option>
                </select>
              </label>
              {!current.claude_available && (
                <div className="alert warn" role="status">
                  <IconWarn />
                  <span>No se encontró el programa <code>claude</code> en el equipo donde corre el servidor.</span>
                </div>
              )}
              <div className="note" style={{ marginTop: 0 }}>
                <IconInfo width={24} height={24} />
                <span>
                  Usa la sesión de Claude Code iniciada en este equipo; no hace falta llave. Si se agota el uso de tu
                  suscripción, el trabajo se detiene con un aviso y puedes reanudarlo después.
                </span>
              </div>
            </>
          )}

          {provider === "deepseek" && (
            <>
              <label>
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
              <label>
                Modelo
                <input value={form.deepseek_model ?? ""} onChange={(e) => set({ deepseek_model: e.target.value })} />
              </label>
              <label>
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
        </div>

        {notice && (
          <div className={`alert ${notice.kind === "ok" ? "ok" : "error"}`} role={notice.kind === "ok" ? "status" : "alert"}>
            {notice.kind === "error" && <IconWarn />}
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
        </div>
      </section>
    </main>
  );
}
