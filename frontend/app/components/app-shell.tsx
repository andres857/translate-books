"use client";

/* Marco de la aplicación: con sesión normal, barra lateral + contenido; en el login y en el cambio
   obligatorio de contraseña, solo la tarjeta centrada. No muestra nada protegido hasta conocer la sesión. */
import type { ReactNode } from "react";
import type { AuthState } from "@/lib/api";
import { usePathname } from "next/navigation";
import { AuthProvider, PUBLIC_PATHS, useAuth, useAuthRedirect } from "@/lib/auth";
import { SideNav } from "./nav";

function Shell({ children }: { children: ReactNode }) {
  const { state } = useAuth();
  const { allowed } = useAuthRedirect();
  const pathname = usePathname() ?? "/";
  const bare = PUBLIC_PATHS.includes(pathname) || state?.session.kind !== "normal";

  if (!allowed) {
    return <div className="auth-screen"><p className="muted" role="status">Cargando…</p></div>;
  }
  if (bare) return <div className="auth-screen">{children}</div>;
  return (
    <div className="app">
      <SideNav />
      <div className="content">{children}</div>
    </div>
  );
}

export function AppShell({ children, initial }: { children: ReactNode; initial?: AuthState | null }) {
  return (
    <AuthProvider initial={initial}>
      <Shell>{children}</Shell>
    </AuthProvider>
  );
}
