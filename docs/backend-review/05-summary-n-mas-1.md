# 05 · El resumen del admin hace una consulta por página

- **Severidad:** Alto
- **Categoría:** Rendimiento
- **Estado:** resuelto · commit(s) `2ccecb7`
- **Ubicación:** `backend/app/api/routes_admin.py:62-86` (`summary`, líneas 67-73)
- **Aceptación:** [05-summary-n-mas-1.aceptacion.md](05-summary-n-mas-1.aceptacion.md)

## Problema

Por cada página se accede a `p.segments` (carga perezosa) para contar bloques, traducidos, editados y la escala
mínima:

```python
for p in db.scalars(select(Page).where(Page.job_id == job_id).order_by(Page.number)):
    scales = [s.fit_scale for s in p.segments if s.fit_scale]
```

## Cómo reproducirlo

Medido sobre una copia de la BD real: `GET /api/admin/jobs/1/summary` → **198 queries** (192 páginas + 6).

## Impacto

La pantalla «Resumen» del admin tarda proporcionalmente al número de páginas; un libro de 600 páginas son ~600 consultas y miles de objetos en memoria.

## Corrección propuesta

Una consulta agregada: `select(Segment.page_id, func.count(), func.sum(case(...)), func.min(Segment.fit_scale)).group_by(Segment.page_id)` unida a las páginas. La forma del JSON no cambia.

## Notas

Decisión al resolver: la subconsulta reproduce en SQL la «verdad» de Python del código anterior: traducido =
`action = 'translate'` con `translation` no NULL ni vacía; editado = `edited` verdadero; `min_scale` = mínimo de
`fit_scale` ignorando NULL y 0 (`if s.fit_scale`). Se usa outer join para que las páginas sin bloques sigan saliendo
con `segments: 0` y `min_scale: null`; el redondeo a 2 decimales sigue en Python. El frontend no necesita cambios
porque el JSON es idéntico (mismo sha256 sobre la copia de la BD real).
