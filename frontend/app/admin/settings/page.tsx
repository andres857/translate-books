"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getSettings, saveSettings, SETTINGS_EVENT, testSettings, type Provider, type SettingsChanges, type TranslationSettings,
} from "@/lib/api";
import { IconCheck, IconInfo, IconWarn } from "../../components/art";

const METHODS: { id: Provider; title: string; text: string }[] = [
  {
    id: "claude",
    title: "Suscripción de Claude",
    text: "Usa tu plan Pro/Max con Claude Code. Sin costo por llamada; limitado por el uso de la suscripción.",
  },
  { id: "deepseek", title: "API de DeepSeek", text: "Usa tu llave de DeepSeek. Se paga por uso, sin límite de sesión." },
];

const AUTH_TEXT: Record<TranslationSettings["claude_auth"], string> = {
  token: "Autenticado con token de suscripción (funciona dentro de Docker).",
  session: "Usa la sesión de Claude Code iniciada en este equipo (solo desarrollo local).",
  none: "Sin autenticar: pega un token de suscripción para usar este método.",
};

type Notice = { kind: "ok" | "error"; text: string } | null;

export default function AdminSettingsPage() {
  const [current, setCurrent] = useState<TranslationSettings | null>(null);
  const [form, setForm] = useState<SettingsChanges>({});
  const [key, setKey] = useState("");
  const [token, setToken] = useState("");
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
      const saved = await saveSettings({
        ...form,
        ...(key.trim() ? { deepseek_api_key: key.trim() } : {}),
        ...(token.trim() ? { claude_oauth_token: token.trim() } : {}),
      });
      setCurrent(saved);
      setKey("");
      setToken("");
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
          <p>Método de inferencia para traducir y corregir. Se aplica al siguiente libro, sin reiniciar.</p>
        </div>
        <Link className="btn secondary" href="/admin">Ver libros</Link>
      </div>

      <section className="card" aria-labelledby="method-title">
        <h2 id="method-title">Método de traducción</h2>
        <div className="modes" role="radiogroup" aria-labelledby="method-title">
          {METHODS.map((m) => (
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
              <label className="control">
                Token de suscripción
                <input
                  type="password"
                  autoComplete="off"
                  placeholder={current.claude_token_set ? `Guardado (••••${current.claude_token_hint}). Escribe otro para cambiarlo` : "sk-ant-oat…"}
                  value={token}
                  onChange={(e) => {
                    setToken(e.target.value);
                    setNotice(null);
                  }}
                />
              </label>
              <label className="control">
                Modelo de Claude
                <select value={form.claude_model} onChange={(e) => set({ claude_model: e.target.value as "sonnet" | "opus" })}>
                  <option value="sonnet">Sonnet (recomendado)</option>
                  <option value="opus">Opus (más lento, consume más cuota)</option>
                </select>
              </label>
              <div className={`alert full ${current.claude_auth === "none" ? "" : "ok"}`} role="status">
                {current.claude_auth === "none" ? <IconWarn /> : <IconCheck />}
                <span>{AUTH_TEXT[current.claude_auth]}</span>
              </div>
              {!current.claude_available && (
                <div className="alert full" role="status">
                  <IconWarn />
                  <span>No se encontró el programa <code>claude</code> en el servidor. La imagen de Docker ya lo incluye.</span>
                </div>
              )}
              <div className="alert full">
                <IconInfo />
                <span>
                  Para obtener el token ejecuta <code>claude setup-token</code> en tu equipo (con tu cuenta Pro/Max) y
                  pégalo aquí. Límites: el uso cuenta contra las ventanas de 5 horas y semanal de tu plan; si se agota,
                  el trabajo se detiene con un aviso y puedes reanudarlo después sin repetir lo ya traducido.
                </span>
              </div>
            </>
          )}

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
            onClick={() => set({ provider: provider === "fake" ? current.provider === "fake" ? "deepseek" : current.provider : "fake" })}
          >
            {provider === "fake" ? "Salir del modo de prueba" : "Modo de prueba sin API"}
          </button>
        </div>
      </section>
    </main>
  );
}
