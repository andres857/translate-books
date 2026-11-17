import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { connection } from "next/server";
import { AppShell } from "./components/app-shell";
import "./tokens.css";
import "./globals.css";

// Inter es la primera familia de --font-family-body; next/font la sirve desde el propio sitio
const font = Inter({ subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  // cada segmento pone su título («Usuarios» → «Usuarios · AstroBooks»); la portada es la lista de libros
  title: { default: "Libros · AstroBooks", template: "%s · AstroBooks" },
  description: "Traduce libros PDF del inglés al español conservando su diseño",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // renderizado por solicitud: Next aplica a sus scripts el nonce de la CSP que pone proxy.ts
  await connection();
  return (
    <html lang="es">
      <body className={font.className}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
