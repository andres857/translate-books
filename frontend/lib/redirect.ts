/* Destino seguro tras el login (`?next=`). Función pura: no depende del navegador y se prueba sola. */

// origen ficticio: solo sirve para que URL resuelva rutas relativas y detectar si el destino cambia de origen
const BASE = "http://app.invalid";

/** Devuelve una ruta interna (`/ruta?consulta#ancla`) o `/` si el destino podría salir de la app.
 *  El navegador trata `\` como `/` y descarta tabuladores y saltos de línea, así que `/\evil.com` o
 *  `/\t/evil.com` acabarían en `//evil.com`: se rechazan antes de resolver y se comprueba el origen. */
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || /[\\\u0000-\u001f\u007f]/.test(next)) return "/";
  let url: URL;
  try {
    url = new URL(next, BASE);
  } catch {
    return "/";
  }
  if (url.origin !== BASE) return "/";
  if (url.pathname === "/login" || url.pathname.startsWith("/login/")) return "/"; // sin bucle de redirección
  return url.pathname + url.search + url.hash;
}
