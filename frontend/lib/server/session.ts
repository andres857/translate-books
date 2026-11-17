/* Lecturas del API desde el servidor de Next (Server Components), con la cookie de sesión de la petición.
   Solo se importa desde componentes de servidor: usa next/headers. */
import { cookies } from "next/headers";
import type { AuthState } from "@/lib/api";

// dentro de Docker, el api se llama «api» (BACKEND_URL también hace falta en tiempo de ejecución)
const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";
const SESSION_COOKIES = ["__Host-tl_session", "tl_session"];

/** null = no hay sesión o el API la rechaza (401/403/404); undefined = no se pudo saber (red, 5xx). */
export async function serverFetch<T>(path: string): Promise<T | null | undefined> {
  const jar = await cookies();
  const session = SESSION_COOKIES.map((n) => jar.get(n)).find(Boolean);
  if (!session) return null;
  try {
    const res = await fetch(`${BACKEND}${path}`, {
      headers: { Cookie: `${session.name}=${session.value}`, "X-Requested-With": "traductor" },
      cache: "no-store",
    });
    if (res.status >= 500) return undefined;
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return undefined;
  }
}

/** Sesión de la petición actual, para que la primera respuesta ya traiga la app (sin «Cargando…»). */
export function getServerSession() {
  return serverFetch<AuthState>("/api/auth/me");
}
