# Planificación 30h / 60h / 90h

## Leyenda

| Prioridad | Color | Significado |
|-----------|-------|-------------|
| Alta | Rojo | Tareas críticas, bloquean el avance del proyecto |
| Media | Amarillo | Tareas importantes, valor para el negocio |
| Baja | Verde | Mejora continua, refinamiento y cierre |

---

## Primeras 30h — Fundamentos (Prioridad: ALTA)

| # | Tarea | Prioridad | Hito | Horas | Acumulado |
|---|-------|-----------|------|-------|-----------|
| 1 | Definir stack tecnológico definitivo | Alta | M1 | 3h | 3h |
| 2 | Diseñar arquitectura del sistema | Alta | M1 | 4h | 7h |
| 3 | Diseñar modelo de datos (ERD) | Alta | M1 | 3h | 10h |
| 4 | Diseñar wireframes del dashboard | Alta | M1 | 3h | 13h |
| 5 | Setup del entorno de desarrollo | Alta | M1 | 2h | 15h |
| 6 | Conexión con cuenta intermedia | Alta | M2 | 6h | 21h |
| 7 | Parseo y extracción de datos | Alta | M2 | 6h | 27h |
| 8 | Filtrado de correos irrelevantes | Alta | M2 | 3h | 30h |

**30h → ¿Qué ve la empresa?** Arquitectura definida, motor de ingesta de correos operativo.

---

## 30h → 60h — Núcleo e Integración (Prioridad: ALTA + MEDIA)

| # | Tarea | Prioridad | Hito | Horas | Acumulado |
|---|-------|-----------|------|-------|-----------|
| 9 | Tests del módulo de ingesta | Alta | M2 | 4h | 34h |
| 10 | Motor de clasificación de contactos | Alta | M3 | 6h | 40h |
| 11 | Determinación de estado y relevancia | Alta | M3 | 6h | 46h |
| 12 | Integración con CRM (CRUD contactos) | Alta | M3 | 7h | 53h |
| 13 | Registro de interacciones y oportunidades | Media | M3 | 3h | 56h |
| 14 | Tests de clasificación e integración | Media | M3 | 3h | 59h |

**60h → ¿Qué ve la empresa?** Los correos se clasifican automáticamente y los contactos se registran en el CRM.

---

## 60h → 90h — Frontend y Cierre (Prioridad: ALTA + MEDIA + BAJA)

| # | Tarea | Prioridad | Hito | Horas | Acumulado |
|---|-------|-----------|------|-------|-----------|
| 15 | API REST endpoints | Alta | M4 | 5h | 64h |
| 16 | Dashboard principal (resumen actividad) | Media | M4 | 5h | 69h |
| 17 | Vista de contactos con filtros | Media | M4 | 4h | 73h |
| 18 | Vista de pipeline de oportunidades | Media | M4 | 3h | 76h |
| 19 | Autenticación de usuarios | Media | M4 | 3h | 79h |
| 20 | Pruebas de integración del sistema | Media | M5 | 3h | 82h |
| 21 | Pruebas de carga y rendimiento | Baja | M5 | 2h | 84h |
| 22 | Documentación técnica y de usuario | Media | M5 | 3h | 87h |
| 23 | Configurar Docker para producción | Baja | M5 | 2h | 89h |
| 24 | Despliegue y ajustes finales | Media | M5 | 2h | 91h |

**90h → ¿Qué ve la empresa?** Sistema completo con dashboard web, pipeline de oportunidades y documentación.

---

## Resumen por Prioridad

| Prioridad | Tareas | Horas |
|-----------|--------|-------|
| Alta | #1-#12, #15 | 59h |
| Media | #13, #14, #16-#20, #22, #24 | 28h |
| Baja | #21, #23 | 4h |
| **Total** | **24 tareas** | **91h** |
