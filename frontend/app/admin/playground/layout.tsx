import type { Metadata } from "next";

// la página es de cliente y no puede exportar metadata: el título del segmento vive aquí. Repite la plantilla
// para que los segmentos hijos (Historial) también terminen en «· AstroBooks».
export const metadata: Metadata = { title: { default: "Playground", template: "%s · AstroBooks" } };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
