/* Cliente HTTP de /api/*: sesión en memoria (CSRF), encabezados de la aplicación y errores con código. */


// ---------------------------------------------------------------- sesión
// El token de sesión vive en una cookie HttpOnly que JavaScript no ve. Aquí solo se guarda, en memoria,
// el token CSRF que devuelve /api/auth/me (nunca en localStorage ni en la URL).

let csrfToken: string | null = null;
export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

/** Lo emite parse() cuando el servidor dice que la sesión ya no vale o que falta cambiar la contraseña. */
export const AUTH_EVENT = "astrobooks:auth";

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** Encabezados que el backend exige: el de la aplicación siempre y el CSRF en escrituras. */
export function apiHeaders(method: string): Record<string, string> {
  const h: Record<string, string> = { "X-Requested-With": "traductor" };
  if (UNSAFE.has(method.toUpperCase()) && csrfToken) h["X-CSRF-Token"] = csrfToken;
  return h;
}

/** Mensaje cuando el navegador no llega al servidor (fetch rechaza con un TypeError cuyo mensaje está en inglés). */
export const OFFLINE = "No hay conexión con el servidor. Comprueba que el servicio esté en marcha e inténtalo de nuevo.";

/** fetch hacia /api/* con la cookie de sesión, el encabezado de la aplicación y el CSRF. Un fallo de red se
 *  convierte en ApiError (estado 0, código NETWORK) con un mensaje en español; una cancelación se respeta. */
export async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  for (const [k, v] of Object.entries(apiHeaders(init.method ?? "GET"))) headers.set(k, v);
  try {
    return await fetch(url, { ...init, headers, credentials: "same-origin" });
  } catch (e) {
    if ((e as Error)?.name === "AbortError") throw e;
    throw new ApiError(OFFLINE, 0, "NETWORK");
  }
}

/** Error de la API con su código (`REAUTH_REQUIRED`, `LAST_ADMIN`…) además del mensaje. */
export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code: string | null) {
    super(message);
  }
}

export async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg =
      res.status === 413
        ? "El archivo es demasiado grande para el límite configurado."
        : res.status >= 500
          ? "El servidor no pudo procesar la solicitud. Verifica que el servicio esté en funcionamiento e inténtalo de nuevo."
          : res.status === 429
            ? "Demasiados intentos. Espera unos minutos e inténtalo de nuevo."
            : "No pudimos completar la acción. Intenta de nuevo.";
    let code: string | null = null;
    try {
      const body = await res.json();
      if (typeof body.message === "string") msg = body.message;
      else if (typeof body.detail === "string") msg = body.detail;
      if (typeof body.code === "string") code = body.code;
    } catch {
      /* respuesta sin JSON */
    }
    if ((res.status === 401 && code === "UNAUTHENTICATED") || code === "PASSWORD_CHANGE_REQUIRED") {
      if (typeof window !== "undefined") window.dispatchEvent(new Event(AUTH_EVENT));
    }
    throw new ApiError(msg, res.status, code);
  }
  return res.json() as Promise<T>;
}

/** RequestInit con método y, si hay cuerpo, JSON. */
export const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: body === undefined ? undefined : { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

/** RequestInit con método y cuerpo JSON obligatorio. */
export const jsonBody = (method: string, body: unknown): RequestInit => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});
