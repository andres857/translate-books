# Traductor de libros PDF (EN → ES)

Traduce libros PDF del inglés al español conservando número de páginas, tamaño, imágenes, gráficos,
cajas de color, nombres propios, ISBN, URLs y números.

```
frontend (Next.js :3000) → api (FastAPI :8000) → SQLite (data/app.db) ← worker (pipeline)
pipeline: análisis → protección → traducción (DeepSeek) → reconstrucción → validación
```

## Instalación con Docker (recomendado)

```bash
git clone https://github.com/lore2203/traductor_libros.git
cd traductor_libros
cp .env.example .env        # en Windows: copy .env.example .env
mkdir data                  # créala tú: si la crea Docker queda a nombre de root
docker compose up --build -d
```

En `.env` pon la llave de DeepSeek, `DEEPSEEK_API_KEY=sk-…`, o pégala después en la web, en
**Administración › Configuración**.

Si el puerto 3000 u 8000 está ocupado, cambia `WEB_PORT` / `API_PORT` en `.env`. `APP_UID`/`APP_GID` deben ser los
de tu usuario (`id -u`, `id -g`) para que los archivos de `data/` queden a tu nombre.

Requisitos: Git y Docker Desktop. El repositorio es privado: al clonar, inicia sesión con tu cuenta de
GitHub. El archivo `.env` (con la llave) no se sube a GitHub, así que hay que crearlo en cada equipo.

Abre http://localhost:3000. Los PDF originales y traducidos quedan en `data/` (nunca dentro de la BD).

> Sin llave de DeepSeek puedes probar la maquetación con `FAKE_TRANSLATOR=true` en `.env`
> (inserta el texto original alargado un 25 % para simular la expansión del español).

## Desarrollo local (sin Docker)

```bash
python -m venv .venv && .venv/Scripts/pip install -e "backend[dev]"   # Linux/Mac: .venv/bin/pip
cd backend
python -m pytest                                   # pruebas
python -m app.cli analyze libro.pdf --pages 1-5    # ver segmentos detectados
python -m app.cli translate libro.pdf --pages 1-12 --out ../data/outputs/cli   # traducir (usa caché)
python -m app.cli translate libro.pdf --fake       # sin API, solo maquetación
alembic upgrade head                               # esquema de la base de datos (repetir tras actualizar el código)
uvicorn app.main:app --reload                      # API
python -m app.worker                               # worker
cd ../frontend && npm install && npm run dev       # interfaz
```

## Traducción con DeepSeek (Administración › Configuración)

En la web, **Administración › Configuración** (`/admin/settings`; `/settings` redirige allí) configura la traducción y
se aplica al siguiente libro, sin reiniciar:

- **DeepSeek (API)**: llave, modelo y razonamiento editables. Las llaves de DeepSeek empiezan por `sk-`. Si la cuenta
  se queda sin saldo, el trabajo se detiene con un aviso y se puede reanudar (la caché evita repetir lo ya traducido).
- **Prueba sin API** (botón secundario): traductor falso para revisar la maquetación.

"Probar conexión" hace una traducción real mínima con el modo elegido. Los ajustes se guardan en
`data/settings.json` (fuera de git, permisos 0600) y sobrescriben a `.env`; la llave nunca se devuelve.
En la CLI: `python -m app.cli translate libro.pdf --provider deepseek|fake`.

## Solo digitalizar (PDF escaneado → PDF digital, sin traducir)

Al subir un libro, **"Solo digitalizar"** convierte un PDF escaneado en un PDF con texto seleccionable y
buscable, más su EPUB para Kindle, sin traducir:

1. Análisis: detecta las páginas sin texto (las que ya tienen texto no se tocan).
2. OCR con **OCRmyPDF/Tesseract** (`--skip-text --rotate-pages --deskew --clean --optimize 1`): capa de texto
   invisible sobre la imagen original, que no cambia. Idioma: inglés, español o ambos.
3. Corrección opcional con DeepSeek (Administración › Configuración): solo errores de reconocimiento
   ("youre" → "you’re", "anastrology" → "an astrology"), sin traducir ni reescribir. Se rechaza si cambia
   números, formato o longitud. Se usa en el EPUB; el PDF conserva la capa de OCR con sus posiciones exactas.
4. EPUB fluido: las páginas escaneadas salen como texto; las figuras se recortan por zonas con tinta que no
   son texto; las láminas sin texto, como imagen de página completa.

Requisitos en el equipo del worker: `sudo apt install tesseract-ocr tesseract-ocr-spa ocrmypdf` (la imagen de
Docker ya los incluye). Reporte: `reporte-digitalizacion.json`.

## Descarga para Kindle (EPUB y AZW3)

Cada trabajo terminado ofrece, además del PDF, **"Para Kindle (EPUB)"**: un EPUB 3 fluido (texto ajustable)
generado desde los segmentos traducidos, no desde el PDF. Títulos → índice navegable; párrafos partidos entre
columnas o páginas se unen; se quitan encabezados, pies y números de página; figuras recortadas del PDF
traducido; páginas muy visuales (infografías, escaneadas) como imagen de página completa seguida de su texto.
Envíalo con Send to Kindle (web hasta 200 MB, correo hasta 50 MB): Amazon lo convierte; no hace falta MOBI/AZW.
Para trabajos antiguos se genera al descargarlo, o con `python -m app.cli epub <job_id>`.

**AZW3**: "Kindle (AZW3)" convierte ese mismo EPUB con `ebook-convert` de Calibre, así que conserva índice,
figuras y texto fluido; sirve para copiarlo al Kindle por USB. Requiere Calibre en el equipo del worker/API
(`sudo apt install calibre`; la imagen de Docker ya lo incluye, unos 400 MB más). Sin Calibre el botón se
desactiva y el resto de descargas sigue igual. CLI: `python -m app.cli epub <job_id> --azw3`.

## Acceso: login, roles y recuperación

La aplicación pide correo y contraseña. No hay autorregistro: las cuentas las crea un administrador.

- **Primer arranque**: define `ADMIN_BOOTSTRAP_EMAIL` y `ADMIN_BOOTSTRAP_PASSWORD` (≥ 12 caracteres) en `.env`.
  El api crea ese admin una sola vez (si el correo ya existe no toca nada) y pide cambiar la contraseña en el
  primer login.
- **Roles**: `user` ve y sube **sus** libros, sigue el progreso, descarga, cancela y reanuda. `admin` ve todos
  los libros y además borra, revisa (`/admin/jobs/…`), usa el Playground y Prompts, cambia la Configuración y
  gestiona cuentas en **Administración › Usuarios**. Los libros subidos antes del login solo los ve el admin.
- **Cuentas**: el alta y el reset generan una contraseña temporal que se muestra una sola vez, vence a las 24 h
  y obliga a cambiarla. Cambiar rol, desactivar o resetear cierra las sesiones de esa cuenta. Las escrituras
  en Usuarios piden confirmar la contraseña del admin (10 min). Siempre queda al menos un admin activo.
- **Sesión**: cookie `HttpOnly`/`SameSite=Strict` (`Secure` y prefijo `__Host-` fuera de `http://localhost`),
  8 h como máximo y 30 min de inactividad. Toda escritura exige `Origin` exacto (`CORS_ORIGINS`), el encabezado
  `X-Requested-With: traductor` y el token CSRF de la sesión. Hay límite de intentos de login (429 +
  `Retry-After`).
- **Recuperación** (sin acceso de admin):
  `docker compose exec api python -m app.cli auth-recover --email tu@correo` crea o reactiva la cuenta como
  admin y muestra una contraseña temporal nueva.

## Administración (`/admin`)

Solo para administradores. Lista los libros y, por libro:

- **Resumen**: páginas correctas y para revisar, validaciones del libro y tabla de páginas con sus motivos.
- **Comparar**: original y resultado lado a lado, con zoom y desplazamiento conjunto, y el texto por bloque
  (original | traducción). El original nunca se sobrescribe: vive en `data/uploads/<sha>/original.pdf`.
- **Editar y recomponer**: se corrige la traducción de un bloque (admite `<b>` e `<i>`), se guarda y
  "Recomponer página" vuelve a maquetar solo esa página en el PDF; las demás no cambian. Lo corregido a mano
  no se reescribe ni se acorta con el modelo: si no cabe, la página queda para revisión. EPUB y AZW3 se
  regeneran en la siguiente descarga. Mientras se recompone (segundos) el libro no se puede descargar.
- **Glosario y términos**: traducciones fijas y términos protegidos, globales o solo del libro; se aplican en
  la siguiente traducción.

Los estilos de toda la interfaz salen de `handoff/tokens.css` (copiado a `frontend/app/tokens.css`);
`node handoff/check.mjs frontend/app` comprueba que no haya valores escritos a mano.

## Configuración (`.env`)

| Variable | Descripción |
|---|---|
| `DEEPSEEK_API_KEY` | Llave de DeepSeek. Nunca se guarda en BD ni se envía al frontend. |
| `DEEPSEEK_MODEL` | Modelo de traducción (`deepseek-flash`). |
| `MAX_UPLOAD_MB` | Tamaño máximo del PDF. |
| `DEEPSEEK_THINKING` | Razonamiento del modelo al traducir: `high` (por defecto, máxima calidad), `low`, `disabled` (unas 2-3 veces más rápido, calidad algo menos pulida). |
| `TRANSLATION_CONCURRENCY` | Solicitudes simultáneas a la API (por defecto 10). |
| `MIN_FONT_SCALE` / `MIN_FONT_SIZE_PT` | Límite de reducción del texto. Solo se pide revisión si el texto queda por debajo del tamaño mínimo legible o se superpone con otro bloque. |
| `FAKE_TRANSLATOR` | `true` para probar sin API. |
| `WEB_PORT` / `API_PORT` | Puertos publicados por `docker compose` (3000 / 8000). |
| `APP_UID` / `APP_GID` | Usuario con el que corren los contenedores (dueño de `data/`). |
| `CORS_ORIGINS` | Origen exacto del navegador (`http://localhost:WEB_PORT`): CORS y comprobación de `Origin` en escrituras. |
| `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD` / `ADMIN_BOOTSTRAP_NAME` | Admin inicial (ver «Acceso»). |
| `TRUSTED_PROXIES` | Redes del proxy propio (el frontend). Desde ellas la IP del usuario es desconocida y el límite de intentos usa solo el correo y el total. El compose usa las redes internas de Docker. |
| `SESSION_MAX_HOURS` / `SESSION_IDLE_MINUTES` / `COOKIE_SECURE` | Duración de la sesión y cookie `Secure` (`auto`, `true`, `false`). |
| `EBOOK_CONVERT_BIN` | Ruta de `ebook-convert` (Calibre) si no está en el `PATH`. |

## Almacenamiento de archivos (S3 + CDN)

`docker compose up -d` levanta también:

| Servicio | Puerto | Qué hace |
|---|---|---|
| `seaweedfs` | `S3_PORT` (8333) | API compatible con S3 (`weed mini`), datos en el volumen `seaweedfs-data`. Credenciales en `infra/seaweedfs/s3.json` (identidad `backend` con todo sobre `uploads`; `anonymous` solo lectura). |
| `storage-init` | — | Crea el bucket si falta y aplica su CORS (`S3_CORS_ORIGINS`) para las subidas prefirmadas desde el navegador; luego termina. |
| `cdn` | `CDN_PORT` (8080) | Nginx con caché delante de SeaweedFS: solo GET/HEAD, `Cache-Control: public, max-age=604800`, cabecera `X-Cache-Status`. |

La base de datos guarda solo la **key** (`files/<yyyy>/<mm>/<uuid>.<ext>`); la URL pública se construye con
`PUBLIC_BASE_URL + "/" + key`, así que cambiar de proveedor o de CDN no exige migrar datos. El código usa
el puerto `app/storage/port.py` (`Depends(get_storage)`); `boto3` solo aparece en `app/storage/adapters/`.

Endpoints de ejemplo (`/api/files`, máximo `UPLOAD_MAX_SIZE_MB`, tipos `UPLOAD_ALLOWED_MIME`, el tipo real se
comprueba por los *magic bytes*):

```bash
curl -F file=@foto.png localhost:8000/api/files                 # → {id, key, url} (url al CDN)
curl -I <url>; curl -I <url>                                      # X-Cache-Status: MISS y luego HIT
curl -X POST localhost:8000/api/files/presign -H 'Content-Type: application/json' \
     -d '{"filename":"foto.png","contentType":"image/png","size":12345}'   # → {url, key, expires_at} (5 min)
curl -X PUT -H 'Content-Type: image/png' --data-binary @foto.png '<url prefirmada>'
curl -X POST localhost:8000/api/files/confirm -H 'Content-Type: application/json' \
     -d '{"key":"<key>","filename":"foto.png","contentType":"image/png","size":12345}'
curl localhost:8000/api/files/1        # URL pública, o prefirmada si se subió con private=true
curl -X DELETE localhost:8000/api/files/1
```

Probar el bucket con la CLI de AWS:

```bash
AWS_ACCESS_KEY_ID=dev-access-key AWS_SECRET_ACCESS_KEY=dev-secret-key-change-me \
  aws s3 ls s3://uploads --recursive --endpoint-url http://localhost:8333
```

Si hiciera falta reaplicar el CORS a mano: `docker compose run --rm storage-init`
(o `aws s3api put-bucket-cors --endpoint-url http://localhost:8333 ...`).

Pruebas: `pytest tests/test_files.py` (storage falso) y `pytest -m s3` (contra el SeaweedFS y el CDN del compose;
se saltan si no responden).

### Subida de libros con progreso real

Las subidas de libros (página principal y Playground) van directas del navegador al S3 con una URL prefirmada
(`POST /api/jobs/presign` → `PUT` → `POST /api/jobs/from-upload`), así la barra muestra los bytes realmente
enviados. El backend copia el PDF a `DATA_DIR` (el pipeline no cambia) y borra el temporal
`books/incoming/…`. Si el S3 no responde, la subida pasa por `POST /api/jobs` como antes, también con progreso.
En S3/R2 conviene una regla de ciclo de vida que borre `books/incoming/` a 1 día (subidas abandonadas).

### Cambiar a AWS S3, DigitalOcean Spaces o Cloudflare R2

Solo `.env`: copia el bloque de `infra/env/aws-s3.env`, `do-spaces.env` o `cloudflare-r2.env`
(endpoint, región — `auto` en R2 —, path-style, credenciales y `PUBLIC_BASE_URL` del CDN/dominio público).
Dentro de Docker define también `S3_INTERNAL_ENDPOINT` y `S3_PUBLIC_ENDPOINT` (el compose usa por defecto los
de SeaweedFS) y quita los servicios `seaweedfs`/`cdn` si no los necesitas. No se usan ACL por objeto (R2 no
las soporta): el acceso público se da a nivel de bucket (política, dominio propio, r2.dev o CDN de Spaces).

## Prueba con el libro de referencia

Copia el PDF a `backend/tests/fixtures/` (está excluido de git) y ejecuta:

```bash
cd backend
python -m app.cli translate tests/fixtures/<libro>.pdf --out ../data/outputs/ref
```

La salida incluye el PDF `<Título en español> (ES).pdf` y `reporte-traduccion.json` con validaciones,
páginas correctas y páginas para revisión.

## Cómo conserva el diseño

- **Texto digital** (PyMuPDF): se analiza carácter a carácter; se detectan párrafos, columnas, filas de índice,
  saltos de línea intencionales (créditos, listas) y fragmentos en otro peso/color/tamaño.
- **Motor de maquetación propio** (`pipeline/layout.py`): coloca cada línea sobre la línea base original, con el
  interlineado, alineación y justificación originales, y aplica **escala horizontal calibrada** para que la fuente
  sustituta ocupe el mismo ancho que la original. Si el español no cabe: amplía la caja hacia espacio libre,
  condensa levemente y reduce el tamaño hasta un mínimo legible; nunca corta texto. Respeta la sangría de cada
  línea original (texto que rodea íconos o imágenes).
- **Fuentes**: se reutiliza la fuente embebida solo si todos los glifos del español tienen contorno real (los
  subconjuntos de InDesign conservan el mapa de caracteres pero vacían los glifos no usados); si no, la misma
  fuente libre cuando existe (Lilita One, Roboto Slab) o una equivalente con el mismo peso y altura de x
  (Rokkitt, Roboto Condensed, Noto) — ver `backend/fonts/`.
- **Texto curvo o inclinado** (rótulos de ruedas, cintas onduladas): se encadenan las letras del texto vectorial
  que siguen una misma trayectoria, se traduce la frase y se dibuja letra a letra sobre la misma curva
  (`pipeline/curved.py`). No necesita OCR.
- **Símbolos** de fuentes Pi/astrológicas, números de página e índice, ISBN, URLs y nombres se conservan intactos.
- **Texto dentro de imágenes** (portadas): OCR con Tesseract (también texto vertical, girando la imagen 90°/270°),
  borrado con inpainting (OpenCV) y texto traducido encima. Se informa como advertencia y solo pide revisión si
  la confianza del reconocimiento es baja. Requiere Docker (Tesseract).
- **Reporte**: no se marcan como problema los textos conservados a propósito (citas «Autor, Título», títulos de
  obras, entradas del índice) ni los números escritos con palabras («1960s» → «años sesenta»). Incluye
  `tiempos_por_etapa_s`.

## Estado

- [x] Fase 1: estructura, BD (SQLite + SQLAlchemy + Alembic), Docker
- [x] Fase 2: pipeline de texto digital (análisis, protección, traducción, reconstrucción, validación) + CLI
- [x] Fase 3: API + worker con cola en SQLite, cancelar/reanudar
- [x] Fase 4: frontend mínimo (carga, progreso, resultado)
- [x] Fase 5 (parcial): OCR con Tesseract + inpainting para texto en imágenes
- [ ] Fase 5 (pendiente): PaddleOCR opcional y DeepSeek Vision para regiones dudosas
- [ ] Fase 6: revisión lado a lado y edición de segmentos
- [ ] Fase 7: pulido
