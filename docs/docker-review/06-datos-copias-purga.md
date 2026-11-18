# 06 · Sin copias de seguridad de SQLite ni purga programada

- **Severidad:** Alto
- **Categoría:** Datos
- **Estado:** resuelto · commit(s) `8cffa4b`
- **Ubicación:** `docker-compose.yml` (`./data:/data` bind mount), `README.md` (paso `mkdir data`, purga «prográmala si quieres»), `backend/app/cli.py` (`purge`)
- **Aceptación:** [06-datos-copias-purga.aceptacion.md](06-datos-copias-purga.aceptacion.md)

## Problema

La BD (`data/app.db`, WAL) y los PDFs viven en un bind mount que hay que crear a mano con el UID correcto. No existe
ninguna copia automática: las únicas copias son las que hicieron a mano las fichas de migración
(`data/app.db.bak-review09/10`). La purga de sesiones y bitácora (#16 del backend) depende de un cron en el host.

## Cómo reproducirlo

`ls data/` muestra solo copias manuales; no hay servicio ni comando de copia; la purga no corre sola.

## Impacto

Una migración fallida, un disco lleno o un borrado accidental pierden todos los libros y correcciones sin forma de recuperarlos.

## Corrección propuesta

Servicio(s) en el compose que reutilicen la imagen del backend: copia diaria consistente con WAL (API de backup de sqlite3 o `VACUUM INTO`) a `data/backups/` con retención (p. ej. 7 diarias), y la purga diaria (`app.cli purge`). Comando para copia y **restauración** documentados (restaurar exige parar api y worker). Mantener el bind mount `./data` (los PDFs deben seguir accesibles en el host); documentar el `mkdir data` o crearlo con el UID correcto de forma segura.

## Notas

Probar la restauración SOLO sobre una copia (p. ej. levantar un stack temporal con otra carpeta de datos o restaurar a un archivo aparte y comprobarlo), nunca sobrescribiendo `data/app.db`. Si hay que reiniciar api/worker, comprobar antes que no hay trabajos activos.

Decisiones (opción recomendada):

- Un solo servicio `backup` (imagen `traductor-backend`, mismo usuario `APP_UID`) con `python -m app.cli backup loop`:
  copia + retención + purga a `BACKUP_HOUR` UTC (3) y, al arrancar, si falta la copia del día (equipo apagado de
  noche). `backup once` fuerza una ejecución. La purga llama en proceso a `app.auth.purge.purge` (el mismo código que
  `app.cli purge`), después de la copia.
- Copia con la API de backup de sqlite3 a un `.tmp`, `journal_mode=DELETE` (un archivo), `integrity_check` y
  renombrado atómico a `app-AAAA-MM-DD.db` (fecha UTC; la del día se reemplaza). Retención `BACKUP_KEEP` = 7, solo
  sobre ese patrón.
- `data/backups/` la crea el servicio (UID 1000); el `mkdir data` del README se mantiene. No cubre `uploads`/`outputs`
  ni SeaweedFS (documentado). La skill `deploy` añade `backup` al reinicio del backend.
- Copia previa: `data/app.db.bak-docker06` (API de backup, integrity `ok`).

