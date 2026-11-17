"use client"; // los límites de error deben ser componentes de cliente

/* Error inesperado al renderizar una vista: mensaje claro, reintentar y salida a Libros. El detalle técnico
   va a la consola, no a la pantalla. En Next 16 la función para reintentar se llama `retry`. */
import { useEffect } from "react";
import Link from "next/link";
import { IconRefresh, IconWarn } from "./components/art";

export default function ErrorView({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main>
      <section className="card" aria-labelledby="err-title">
        <div className="alert error" role="alert">
          <IconWarn />
          <div>
            <h1 id="err-title">Algo salió mal en esta vista</h1>
            <p className="muted">Puedes reintentarlo; si sigue fallando, vuelve a Libros y ábrela de nuevo.</p>
          </div>
        </div>
        <div className="row">
          <button type="button" className="btn" onClick={() => retry()}><IconRefresh /> Reintentar</button>
          <Link className="btn secondary" href="/">Ir a Libros</Link>
        </div>
      </section>
    </main>
  );
}
