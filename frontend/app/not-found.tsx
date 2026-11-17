import type { Metadata } from "next";
import Link from "next/link";
import { IconArrowLeft } from "./components/art";

export const metadata: Metadata = { title: "Página no encontrada" };

// Ruta inexistente (o notFound()): se muestra dentro del marco de la app, con salida a Libros. Responde 404.
export default function NotFound() {
  return (
    <main>
      <section className="card" aria-labelledby="nf-title">
        <h1 id="nf-title">No encontramos esta página</h1>
        <p className="muted">La dirección no existe o ya no está disponible.</p>
        <p><Link className="btn secondary" href="/"><IconArrowLeft width={16} height={16} /> Ir a Libros</Link></p>
      </section>
    </main>
  );
}
