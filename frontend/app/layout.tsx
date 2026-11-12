import type { Metadata } from "next";
import Link from "next/link";
import { Inter } from "next/font/google";
import { IconBook } from "./components/art";
import { SideNav } from "./components/nav";
import "./tokens.css";
import "./globals.css";

// Inter es la primera familia de --font-family-body; next/font la sirve desde el propio sitio
const font = Inter({ subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "AstroBooks · Traductor de libros",
  description: "Traduce libros PDF del inglés al español conservando su diseño",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className={font.className}>
        <div className="app">
          <header className="topbar">
            <Link href="/" className="brand" aria-label="AstroBooks, inicio">
              <IconBook width={22} height={22} />
              <span>AstroBooks</span>
            </Link>
            <span className="topbar-note">Traductor de libros PDF</span>
          </header>
          <SideNav />
          <div className="content">{children}</div>
        </div>
      </body>
    </html>
  );
}
