import type { Metadata } from "next";

// la página es de cliente y no puede exportar metadata: el título del segmento vive aquí
export const metadata: Metadata = { title: "Revisión del libro" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
