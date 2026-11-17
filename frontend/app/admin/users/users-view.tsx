"use client";

/* Administración › Usuarios: alta (rol user por defecto), cambio de rol, activar/desactivar y contraseña temporal.
   Las escrituras piden confirmar la contraseña del admin si no lo hizo hace poco (REAUTH_REQUIRED). La contraseña
   temporal se muestra una sola vez y solo vive en el estado de esta vista. */
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type FormEvent } from "react";
import {
  ApiError, createUser, listUsers, reauthenticate, resetUserPassword, updateUser,
  type AuthUser, type Role, type TempPassword,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { IconCheck, IconCopy, IconKey, IconPlus, IconWarn, IconX } from "../../components/art";

const ROLE_LABEL: Record<Role, string> = { admin: "Administrador", user: "Usuario" };
const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString("es", { dateStyle: "medium", timeStyle: "short" }) : "—");
const noop = () => () => {};

/** Fecha en la zona horaria del navegador. En el servidor (y al hidratar) no se pinta: la zona del servidor
 *  no es la del usuario y el HTML no coincidiría. */
function LocalDate({ iso }: { iso: string | null }) {
  const text = useSyncExternalStore(noop, () => fmt(iso), () => "");
  return <time dateTime={iso ?? undefined}>{text}</time>;
}

type Notice = { kind: "ok" | "error"; text: string } | null;

/** Vista de Usuarios. `initial` llega del servidor (page.tsx); si no se pudo leer, se pide aquí. */
export function UsersView({ initial }: { initial: AuthUser[] | null }) {
  const { state, accept } = useAuth();
  const [users, setUsers] = useState<AuthUser[] | null>(initial);
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState<number | "new" | null>(null);
  const [form, setForm] = useState<{ email: string; name: string; role: Role }>({ email: "", name: "", role: "user" });
  const [temp, setTemp] = useState<TempPassword | null>(null);
  const [copied, setCopied] = useState(false);
  // acción en espera de que el admin confirme su contraseña
  const pending = useRef<(() => Promise<void>) | null>(null);
  const [reauth, setReauth] = useState(false);
  const [reauthPw, setReauthPw] = useState("");
  const [reauthError, setReauthError] = useState<string | null>(null);

  const load = useCallback(() => {
    listUsers(1, 200).then((p) => setUsers(p.items)).catch((e) => setNotice({ kind: "error", text: (e as Error).message }));
  }, []);
  useEffect(() => {
    if (!initial) load(); // si vino del servidor no se repite; tras cada cambio se recarga con load()
  }, [initial, load]);

  /** Ejecuta una escritura; si el servidor pide reautenticación, la guarda y muestra el formulario. */
  async function run(key: number | "new", action: () => Promise<void>) {
    setBusy(key);
    setNotice(null);
    try {
      await action();
    } catch (e) {
      if (e instanceof ApiError && e.code === "REAUTH_REQUIRED") {
        pending.current = action;
        setReauth(true);
      } else {
        setNotice({ kind: "error", text: (e as Error).message });
      }
    } finally {
      setBusy(null);
    }
  }

  async function confirmReauth(e: FormEvent) {
    e.preventDefault();
    setReauthError(null);
    try {
      accept(await reauthenticate(reauthPw));
    } catch (err) {
      setReauthError((err as Error).message);
      return;
    } finally {
      setReauthPw("");
    }
    setReauth(false);
    const action = pending.current;
    pending.current = null;
    if (action) await run("new", action);
  }

  function cancelReauth() {
    pending.current = null;
    setReauth(false);
    setReauthPw("");
    setReauthError(null);
  }

  const showTemp = (t: TempPassword) => {
    setTemp(t);
    setCopied(false);
  };

  function create(e: FormEvent) {
    e.preventDefault();
    const body = { email: form.email.trim(), name: form.name.trim(), role: form.role };
    void run("new", async () => {
      showTemp(await createUser(body));
      setForm({ email: "", name: "", role: "user" });
      load();
    });
  }

  const patch = (u: AuthUser, changes: { role?: Role; active?: boolean }, done: string) =>
    run(u.id, async () => {
      await updateUser(u.id, changes);
      setNotice({ kind: "ok", text: done });
      load();
    });

  const reset = (u: AuthUser) =>
    run(u.id, async () => {
      showTemp(await resetUserPassword(u.id));
      load();
    });

  async function copy() {
    if (!temp) return;
    try {
      await navigator.clipboard.writeText(temp.temporary_password);
      setCopied(true);
    } catch {
      setCopied(false); // sin permiso de portapapeles: se puede seleccionar a mano
    }
  }

  const me = state?.user.id;

  return (
    <main>
      <div className="page-head">
        <div>
          <h1>Usuarios</h1>
          <p>Cuentas con acceso. Los usuarios ven y suben sus propios libros; los administradores gestionan todo.</p>
        </div>
      </div>

      {reauth && (
        <section className="card" aria-labelledby="reauth-title">
          <h2 id="reauth-title">Confirma tu contraseña</h2>
          <p className="muted">Por seguridad, los cambios en cuentas piden tu contraseña si no la escribiste hace poco.</p>
          <form className="row" onSubmit={confirmReauth}>
            <label className="control users-reauth">
              <span className="sr-only">Tu contraseña</span>
              <input type="password" autoComplete="current-password" autoFocus value={reauthPw}
                onChange={(e) => setReauthPw(e.target.value)} placeholder="Tu contraseña" />
            </label>
            <button className="btn" disabled={!reauthPw}>Confirmar</button>
            <button type="button" className="btn ghost" onClick={cancelReauth}>Cancelar</button>
          </form>
          {reauthError && <div className="alert error" role="alert"><IconWarn /><span>{reauthError}</span></div>}
        </section>
      )}

      {temp && (
        <div className="alert ok" role="status">
          <IconKey />
          <div className="stack temp-pass">
            <span>
              Contraseña temporal de <strong>{temp.user.email}</strong>. Se muestra solo esta vez: cópiala y
              entrégasela por un canal seguro. Vence el {fmt(temp.user.temp_password_expires_at)} y pedirá cambiarla al entrar.
            </span>
            <code className="temp-pass-value">{temp.temporary_password}</code>
            <div className="row">
              <button type="button" className="btn secondary" onClick={copy}>
                {copied ? <IconCheck /> : <IconCopy />} {copied ? "Copiada" : "Copiar"}
              </button>
              <button type="button" className="btn ghost" onClick={() => setTemp(null)}><IconX /> Ya la guardé</button>
            </div>
          </div>
        </div>
      )}

      {notice && (
        <div className={`alert ${notice.kind}`} role={notice.kind === "ok" ? "status" : "alert"}>
          {notice.kind === "ok" ? <IconCheck /> : <IconWarn />}<span>{notice.text}</span>
        </div>
      )}

      <section className="card" aria-labelledby="new-user-title">
        <h2 id="new-user-title">Nueva cuenta</h2>
        <form className="form-grid" onSubmit={create}>
          <label className="control">
            Correo
            <input type="email" required autoComplete="off" value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </label>
          <label className="control">
            Nombre
            <input type="text" autoComplete="off" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label className="control">
            Rol
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
              <option value="user">{ROLE_LABEL.user}</option>
              <option value="admin">{ROLE_LABEL.admin}</option>
            </select>
          </label>
          <div>
            <button className="btn" disabled={busy !== null || !form.email.trim()}>
              <IconPlus /> {busy === "new" ? "Creando…" : "Crear cuenta"}
            </button>
          </div>
        </form>
      </section>

      {users === null && !notice && <section className="card"><p>Cargando…</p></section>}
      {users && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Cuenta</th>
                <th>Rol</th>
                <th>Estado</th>
                <th>Alta</th>
                <th><span className="muted">Acciones</span></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const self = u.id === me;
                return (
                  <tr key={u.id}>
                    <td className="wrap">
                      <strong>{u.name}</strong>{self && <span className="muted"> (tú)</span>}
                      <div className="muted">{u.email}</div>
                    </td>
                    <td>
                      <label className="control">
                        <span className="sr-only">Rol de {u.email}</span>
                        <select value={u.role} disabled={self || busy !== null}
                          title={self ? "No puedes cambiar tu propio rol" : undefined}
                          onChange={(e) => void patch(u, { role: e.target.value as Role },
                            `${u.email} ahora es ${ROLE_LABEL[e.target.value as Role].toLowerCase()}. Sus sesiones se cerraron.`)}>
                          <option value="user">{ROLE_LABEL.user}</option>
                          <option value="admin">{ROLE_LABEL.admin}</option>
                        </select>
                      </label>
                    </td>
                    <td>
                      <span className={`badge ${u.active ? "ok" : "review"}`}>{u.active ? "Activa" : "Desactivada"}</span>
                      {u.active && u.must_change_password && <div className="muted">Pendiente de cambiar la contraseña</div>}
                    </td>
                    <td><LocalDate iso={u.created_at} /></td>
                    <td>
                      <div className="row">
                        <button type="button" className="btn secondary" disabled={self || busy !== null}
                          onClick={() => void reset(u)}>
                          <IconKey /> Contraseña temporal
                        </button>
                        <button type="button" className="btn ghost" disabled={self || busy !== null}
                          onClick={() => void patch(u, { active: !u.active },
                            u.active ? `${u.email} quedó desactivada y sus sesiones se cerraron.` : `${u.email} vuelve a estar activa.`)}>
                          {u.active ? "Desactivar" : "Activar"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
