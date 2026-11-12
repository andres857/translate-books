"""AZW3 para Kindle: se convierte el EPUB que ya generamos con `ebook-convert` de Calibre.

Así se conserva todo lo del EPUB (índice navegable, figuras, texto fluido). Calibre es un programa
externo: si no está instalado, el resto de descargas sigue funcionando.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class Azw3Unavailable(RuntimeError):
    pass


def ebook_convert_binary() -> str | None:
    return shutil.which(os.environ.get("EBOOK_CONVERT_BIN") or "ebook-convert")


def ebook_convert_available() -> bool:
    return ebook_convert_binary() is not None


def azw3_path_for(output_pdf: str | Path) -> Path:
    return Path(output_pdf).with_suffix(".azw3")


def build_azw3(epub_path: Path, out_path: Path, timeout: int = 900) -> Path:
    binary = ebook_convert_binary()
    if binary is None:
        raise Azw3Unavailable("Calibre (ebook-convert) no está instalado")
    epub_path, out_path = Path(epub_path), Path(out_path)
    tmp = out_path.with_name(out_path.stem + ".tmp.azw3")  # la extensión decide el formato de salida
    try:
        proc = subprocess.run([binary, str(epub_path), str(tmp), "--no-inline-toc"], capture_output=True,
                              text=True, timeout=timeout)
        if proc.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
            raise RuntimeError(f"ebook-convert falló ({proc.returncode}): {(proc.stderr or proc.stdout)[-500:]}")
        os.replace(tmp, out_path)
    finally:
        tmp.unlink(missing_ok=True)
    return out_path
