"use client";

/* Estado de la sesión en memoria (usuario + CSRF), consultado a /api/auth/me al cargar.
   Redirige a /login o /change-password según el estado y avisa a las demás pestañas con BroadcastChannel
   (solo el tipo de evento: nunca credenciales). La defensa real está en el servidor. */
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AUTH_EVENT, getMe, logout as apiLogout, setCsrfToken, type AuthState } from "./api";
import { safeNext } from "./redirect";

type AuthContext = {
  state: AuthState | null;
  ready: boolean;
  isAdmin: boolean;
  /** Guarda la sesión que devolvió login/cambio de contraseña/reautenticación y avisa a las otras pestañas. */
  accept: (s: AuthState) => void;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
};

const Ctx = createContext<AuthContext | null>(null);
const CHANNEL = "astrobooks-auth";
export const PUBLIC_PATHS = ["/login"];

export function useAuth(): AuthContext {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth fuera de AuthProvider");
  return c;
}

export { safeNext } from "./redirect";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState | null>(null);
  const [ready, setReady] = useState(false);
  const channel = useRef<BroadcastChannel | null>(null);

  const store = useCallback((s: AuthState | null) => {
    setCsrfToken(s?.csrf_token ?? null);
    setState(s);
  }, []);

  const refresh = useCallback(async () => {
    try {
      store(await getMe());
    } catch {
      store(null);
    } finally {
      setReady(true);
    }
  }, [store]);

  const accept = useCallback((s: AuthState) => {
    store(s);
    setReady(true);
    channel.current?.postMessage({ type: "changed" });
  }, [store]);

  const signOut = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      /* la sesión ya no valía: igual se limpia */
    }
    store(null);
    channel.current?.postMessage({ type: "logout" });
  }, [store]);

  useEffect(() => {
    void refresh();
    const onAuth = () => void refresh();
    const onVisible = () => { if (document.visibilityState === "visible") void refresh(); };
    window.addEventListener(AUTH_EVENT, onAuth);
    document.addEventListener("visibilitychange", onVisible);
    if ("BroadcastChannel" in window) {
      channel.current = new BroadcastChannel(CHANNEL);
      channel.current.onmessage = () => void refresh();
    }
    return () => {
      window.removeEventListener(AUTH_EVENT, onAuth);
      document.removeEventListener("visibilitychange", onVisible);
      channel.current?.close();
      channel.current = null;
    };
  }, [refresh]);

  return (
    <Ctx.Provider value={{ state, ready, isAdmin: state?.user.role === "admin", accept, refresh, signOut }}>
      {children}
    </Ctx.Provider>
  );
}

/** Adónde debe ir esta ruta según la sesión; null = puede mostrarse. */
export function routeFor(pathname: string, state: AuthState | null): string | null {
  const isPublic = PUBLIC_PATHS.includes(pathname);
  if (!state) return isPublic ? null : `/login${pathname === "/" ? "" : `?next=${encodeURIComponent(pathname)}`}`;
  if (state.session.kind === "restricted") return pathname === "/change-password" ? null : "/change-password";
  if (isPublic) return "/";
  if (pathname.startsWith("/admin") && state.user.role !== "admin") return "/";
  return null;
}

export function useAuthRedirect(): { allowed: boolean } {
  const { state, ready } = useAuth();
  const pathname = usePathname() ?? "/";
  const router = useRouter();
  const target = ready ? routeFor(pathname, state) : null;
  useEffect(() => {
    if (!target) return;
    // tras el login se respeta ?next= (solo rutas internas)
    if (pathname === "/login" && target === "/") {
      router.replace(safeNext(new URLSearchParams(window.location.search).get("next")));
    } else {
      router.replace(target);
    }
  }, [target, pathname, router]);
  return { allowed: ready && !target };
}
