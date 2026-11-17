"use client";

/* Cambio de contraseña: obligatorio tras recibir una temporal (sesión restringida) y voluntario desde la barra
   lateral. Al cambiarla se cierran las demás sesiones abiertas. */
import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { changePassword } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { IconBook, IconCheck, IconWarn } from "../components/art";

const MIN = 12;

export default function ChangePasswordPage() {
  const { state, accept, signOut } = useAuth();
  const router = useRouter();
  const forced = state?.session.kind === "restricted";
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const mismatch = repeat.length > 0 && next !== repeat;
  const short = next.length > 0 && next.length < MIN;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (mismatch || short) return;
    setBusy(true);
    setError(null);
    try {
      const s = await changePassword(current, next);
      setCurrent(""); setNext(""); setRepeat("");
      setDone(true);
      accept(s);
      // cambio obligatorio (venía de una temporal): ya puede usar la app. /change-password también es el
      // cambio voluntario, así que routeFor no redirige solo: se va a Libros aquí
      if (forced) router.replace("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={forced ? "auth-card card" : "auth-page"} aria-labelledby="pw-title">
      {forced && <span className="brand"><IconBook width={22} height={22} /> AstroBooks</span>}
      <div className={forced ? "" : "page-head"}>
        <div>
          <h1 id="pw-title">{forced ? "Elige tu contraseña" : "Cambiar contraseña"}</h1>
          <p className="muted">
            {forced
              ? "Entraste con una contraseña temporal. Crea una propia para continuar."
              : "Se cerrarán tus sesiones abiertas en otros navegadores."}
          </p>
        </div>
      </div>
      <form className={forced ? "stack" : "card stack"} onSubmit={submit} noValidate>
        <label className="control">
          {forced ? "Contraseña temporal" : "Contraseña actual"}
          <input type="password" autoComplete="current-password" required autoFocus value={current}
            onChange={(e) => { setCurrent(e.target.value); setDone(false); }} />
        </label>
        <label className="control">
          Contraseña nueva
          <input type="password" autoComplete="new-password" required minLength={MIN} value={next}
            aria-describedby="pw-hint" aria-invalid={short || undefined}
            onChange={(e) => { setNext(e.target.value); setDone(false); }} />
          <span id="pw-hint" className={short ? "error-text" : "muted"}>Al menos {MIN} caracteres; no uses tu correo.</span>
        </label>
        <label className="control">
          Repite la contraseña nueva
          <input type="password" autoComplete="new-password" required value={repeat} aria-invalid={mismatch || undefined}
            aria-describedby={mismatch ? "pw-mismatch" : undefined}
            onChange={(e) => { setRepeat(e.target.value); setDone(false); }} />
          {mismatch && <span id="pw-mismatch" className="error-text">Las contraseñas no coinciden.</span>}
        </label>
        {error && <div className="alert error" role="alert"><IconWarn /><span>{error}</span></div>}
        {done && !forced && (
          <div className="alert ok" role="status"><IconCheck /><span>Contraseña cambiada.</span></div>
        )}
        <div className="row">
          <button className="btn" disabled={busy || !current || !next || mismatch || short || next !== repeat}>
            {busy ? "Guardando…" : "Guardar contraseña"}
          </button>
          {forced
            ? <button type="button" className="btn ghost" onClick={() => void signOut()}>Salir</button>
            : <Link className="btn ghost" href="/">Cancelar</Link>}
        </div>
      </form>
    </main>
  );
}
