"use client";

/* Subir un libro solo para evaluar: se analiza y se separa por capítulos, sin traducir nada. Estado del
   formulario, subida con progreso y seguimiento de la preparación hasta que termina. */
import { useEffect, useRef, useState } from "react";
import { getJob, uploadBook, type JobStatus, type UploadProgress } from "@/lib/api";

/** Resumen de la última preparación, mostrado en la vista de subida. */
export type PrepSummary = { name: string; pages: number; blocks: number; chapters: number; detected: boolean };

export function usePreparation(opts: {
  /** el libro `id` terminó de prepararse: la página lo selecciona y devuelve el resumen que se muestra */
  onPrepared: (id: number, job: JobStatus) => Promise<PrepSummary>;
  onStart: () => void;
  onError: (e: unknown) => void;
}) {
  const [uploadOpen, setUploadOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [rights, setRights] = useState(false);
  const [uploading, setUploading] = useState<UploadProgress | null | false>(false); // false = sin subida en curso
  const [prep, setPrep] = useState<JobStatus | null>(null);
  const [prepDone, setPrepDone] = useState<PrepSummary | null>(null);

  // los callbacks de la página cambian en cada render; el seguimiento solo debe reaccionar a `prep`
  const cb = useRef(opts);
  useEffect(() => { cb.current = opts; });

  // preparación de un libro recién subido: al terminar se selecciona y se informa de lo extraído
  useEffect(() => {
    if (!prep || prep.status === "done" || prep.status === "failed" || prep.status === "cancelled") return;
    const id = prep.id;
    const timer = setTimeout(async () => {
      try {
        const next = await getJob(id);
        setPrep(next);
        if (next.status === "done") {
          setPrepDone(await cb.current.onPrepared(id, next));
          setUploadOpen(true); // el resumen se ve en la misma vista de subida
          setPrep(null);
        }
      } catch {
        /* se reintenta */
      }
    }, 1500);
    return () => clearTimeout(timer);
  }, [prep]);

  async function prepareUpload() {
    if (!file || !rights) return;
    cb.current.onStart();
    setUploading(null);
    try {
      const job = await uploadBook(file, rights, { mode: "prepare", ocrLang: "en", correct: false }, setUploading);
      setUploading(false);
      setPrep(job);
      setPrepDone(null);
      setFile(null);
      setRights(false);
    } catch (e) {
      setUploading(false);
      cb.current.onError(e);
    }
  }

  const closeUpload = () => { setUploadOpen(false); setFile(null); setRights(false); setDrag(false); setPrepDone(null); };

  return {
    uploadOpen, setUploadOpen, file, setFile, drag, setDrag, rights, setRights, uploading, prep, setPrep,
    prepDone, setPrepDone, prepareUpload, closeUpload,
  };
}

export type Preparation = ReturnType<typeof usePreparation>;
