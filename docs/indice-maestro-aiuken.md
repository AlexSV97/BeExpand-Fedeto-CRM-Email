# Índice maestro — Aiuken SOC / AI Layer

Este documento conecta la documentación principal del programa Aiuken SOC sobre OTRS/Znuny para Aiuken.

## Documentos principales

### 1) Propuesta ejecutiva
**Archivo:** `docs/propuesta-aiuken-beconnect.md` (contenido Aiuken SOC)

Contiene la narrativa comercial y estratégica:
- resumen ejecutivo
- objetivo
- principios
- arquitectura objetivo
- casos de uso prioritarios
- fases de implementación
- roadmap 30/60/90 días
- beneficios, riesgos y métricas

### 2) Backlog técnico implementable
**Archivo:** `docs/backlog-aiuken-beconnect.md` (contenido Aiuken SOC)

Contiene el plan de ejecución técnica:
- epics
- historias
- prioridades
- dependencias
- criterios de aceptación
- MVPs
- riesgos
- definition of done

### 3) README del repositorio
**Archivo:** `README.md`

Sirve como visión general del producto Aiuken SOC, su stack de despliegue y la evolución hacia una capa de inteligencia sobre OTRS/Znuny.

---

## Orden de lectura recomendado
1. `README.md`
2. `docs/propuesta-aiuken-beconnect.md`
3. `docs/backlog-aiuken-beconnect.md`

---

## Mensaje de proyecto
**Aiuken SOC como capa de inteligencia sobre OTRS/Znuny**

La arquitectura propuesta mantiene OTRS/Znuny como system of record y añade Aiuken SOC como capa de inteligencia, copiloto, RAG, agentes gobernados, observabilidad y background jobs con Redis/Celery.
