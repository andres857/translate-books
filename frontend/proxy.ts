import { NextResponse, type NextRequest } from "next/server";

/* Antes de cada página: CSP con nonce nuevo por respuesta y, sin cookie de sesión, al login.
   La redirección es solo comodidad: el backend comprueba la sesión en cada petición a /api. */

const SESSION_COOKIES = ["__Host-tl_session", "tl_session"];
const PUBLIC = ["/login"];

function csp(nonce: string): string {
  const dev = process.env.NODE_ENV === "development";
  // la subida directa hace PUT a la URL prefirmada del almacenamiento S3 (otro origen)
  const connect = ["'self'", ...(process.env.CSP_CONNECT_SRC ?? "").split(/[\s,]+/).filter(Boolean)];
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}`,
    // React escribe atributos style en línea (no admiten nonce)
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' blob: data:",
    "font-src 'self'",
    `connect-src ${connect.join(" ")}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession = SESSION_COOKIES.some((c) => request.cookies.has(c));
  if (!hasSession && !PUBLIC.includes(pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = pathname === "/" ? "" : `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }

  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const policy = csp(nonce);
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", policy);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", policy);
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "same-origin");
  response.headers.set("X-Frame-Options", "DENY");
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!api|_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
