"use client";

/* Entrada con correo y contraseña. Los fallos muestran siempre el mismo mensaje (no se revela si existe la cuenta). */
import { useState, type FormEvent } from "react";
import { login } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { IconBook, IconWarn } from "../components/art";

export default function LoginPage() {
  const { accept } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      accept(await login(email.trim(), password)); // AppShell redirige según la sesión
    } catch (err) {
      setError((err as Error).message);
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-card card" aria-labelledby="login-title">
      <span className="brand"><IconBook width={22} height={22} /> AstroBooks</span>
      <div>
        <h1 id="login-title">Iniciar sesión</h1>
        <p className="muted">Usa la cuenta que te dio el administrador.</p>
      </div>
      <form className="stack" onSubmit={submit} noValidate>
        <label className="control">
          Correo
          <input type="email" autoComplete="username" required autoFocus value={email}
            onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="control">
          Contraseña
          <input type="password" autoComplete="current-password" required value={password}
            onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>}
        <button className="btn auth-submit" disabled={busy || !email.trim() || !password}>
          {busy ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </main>
  );
}
