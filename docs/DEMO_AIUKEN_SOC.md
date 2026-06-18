# Guion de Demo — Aiuken SOC (plataforma de inteligencia sobre OTRS/Znuny)

> Demo de la **capa de inteligencia gobernada** que amplía la operación SOC de
> Aiuken sobre OTRS/Znuny sin reemplazar el sistema de registro: copiloto de
> analista, RAG con citas, SLA predictivo, escalado, agentes y observabilidad.

## 0. Antes de empezar (pre-flight)

Ejecuta el chequeo en vivo — si sale **ALL GREEN**, todo está listo:

```bash
python backend/scripts/demo_preflight.py
# o contra otro entorno:
DEMO_BASE_URL=https://beexpand-fedeto-crm-email.onrender.com python backend/scripts/demo_preflight.py
```

- **Frontend (demo):** https://beconnect-frontend.onrender.com
- **API backend:** https://beexpand-fedeto-crm-email.onrender.com
- **Login:** `admin` / `admin123`
- Recarga con **Ctrl+Shift+R** si vienes de una versión anterior cacheada.

**Encadre clave (decirlo al inicio):** "Esto es OTRS/Znuny como *system of
record* + Aiuken SOC como *capa de inteligencia*. Ahora mismo corre en **modo
demo** con tickets sintéticos; el mismo flujo apunta a **OTRS real** en cuanto se
configuran credenciales (`OTRS_ZNUNY_BASE_URL`/`API_TOKEN`) — el badge cambia a
**Live** y lee/escribe tickets reales. Está probado E2E con un cliente OTRS
simulado y hay un smoke parametrizable para validar el OTRS real."

---

## Arco de la demo (≈12–15 min)

| # | Escena | Superficie / acción | Épica |
|---|--------|---------------------|-------|
| 1 | Login + modo | Login → badge Live/Demo/Degraded | — |
| 2 | Command Center | KPIs, alertas, presión de cola | RP-01 |
| 3 | Smart Inbox | Cada ticket con **riesgo SLA + cola sugerida + owner** | CP-01 / CE-02 / SLA-04 |
| 4 | Ticket Copilot | Contexto + resumen + **casos similares (RAG)** | CP-02/03/04 |
| 5 | Borrador IA | Respuesta a cliente / nota interna **con aprobación humana** | CP-05/06/07 |
| 6 | RAG con citas | Respuesta fundamentada que **cita sus fuentes** | KV-06 |
| 7 | SLA War Room + alertas | Timers de incumplimiento + **alertas tempranas** | SLA-03/04/05/06 |
| 8 | Escalado | N-niveles (N1→N3) y **a fabricante/ITSM externo con tracking** | CE-03/06 |
| 9 | Gobierno | Recomendaciones de agentes + **cola de aprobaciones** | AG-01..07 |
| 10 | Observabilidad | Integraciones, actividad, fallos | RP-04 |

---

## Escena 1 — Login y modo de operación (1 min)
- Entra con `admin`/`admin123`.
- Señala el **badge de modo** (Demo). Explica el encadre OTRS real vs demo.

## Escena 2 — Command Center (2 min)
- Superficie inicial: KPIs (tickets activos, breaches SLA, backlog), alertas
  recientes, presión de cola.
- **Mensaje:** "Visión de turno en un vistazo; los KPIs salen de la operación real."
- API: `GET /api/v1/soc/command-center`.

## Escena 3 — Smart Inbox (2 min)
- Abre la cola de tickets. Cada fila lleva **prioridad, riesgo SLA, tiempo
  restante, cola sugerida y owner**.
- **Mensaje:** "La IA propone (cola sugerida por reglas + riesgo SLA), pero la
  estructura operativa manda."
- API: `GET /api/v1/soc/tickets` (campos `slaRisk`, `suggestedQueue`, `owner`).

## Escena 4 — Ticket Copilot (3 min)
- Abre `TICKET-1000`. Muestra timeline/contexto, resumen del caso y **casos
  similares recuperados del Knowledge Vault** (con su fuente).
- **Mensaje:** "El analista gana velocidad sin perder contexto; el conocimiento
  del SOC se reutiliza."
- API: `GET /api/v1/soc/tickets/TICKET-1000/copilot`.

## Escena 5 — Borrador IA + aprobación humana (2 min)
- Genera un **borrador de respuesta** (cliente) y una **nota interna**.
- **Mensaje clave de gobierno:** "El borrador **nunca se envía solo**: siempre
  requiere aprobación humana (`requires_approval`). Si no hay LLM, cae a plantilla."
- API: `POST /api/v1/soc/tickets/TICKET-1000/draft?kind=customer_reply`.

## Escena 6 — RAG con citas obligatorias (2 min)
- Pregunta libre (p.ej. "password reset"). La respuesta **cita sus fuentes** `[n]`.
- **Mensaje:** "Toda respuesta IA referencia el origen del conocimiento; sin
  fuentes, no inventa." (fallback extractivo si no hay LLM).
- API: `POST /api/v1/search/knowledge/answer`.

## Escena 7 — SLA War Room + alertas tempranas (2 min)
- Muestra timers de incumplimiento y colas activas.
- Lanza un **scan de alertas tempranas** → se notifica *antes* del vencimiento.
- **Mensaje:** "De SLA reactivo a SLA predictivo."
- API: `GET /api/v1/soc/sla`, `POST /api/v1/soc/sla/alerts/scan`.

## Escena 8 — Escalado N-niveles y externo (2 min)
- Escala un ticket N1→N2/N3 (recomendación + registro con motivo/actor/timestamp).
- Escala **a fabricante/ITSM externo**: genera una **referencia de tracking** y
  registra el handoff.
- API: `POST /api/v1/soc/tickets/TICKET-1000/escalate`,
  `POST /api/v1/soc/tickets/TICKET-1000/escalate-external`.

## Escena 9 — Agentes + gobierno (2 min)
- Muestra las recomendaciones por agente (triage, SLA, knowledge, response,
  escalation, compliance) y la **cola de aprobaciones pendientes**.
- **Mensaje:** "Los agentes proponen, pero no actúan libres: acciones críticas →
  aprobación humana."
- API: `POST /api/v1/agents/recommendation`, `GET /api/v1/agents/approvals/pending`.

## Escena 10 — Observabilidad y cierre (1 min)
- Snapshot de observabilidad: estado de integraciones (DB/OTRS/IA), modo,
  actividad y fallos.
- **Cierre:** "Plataforma SOC con memoria operativa y gobierno, lista para
  conectar a OTRS real de Aiuken: solo faltan credenciales."
- API: `GET /api/v1/reporting/observability`.

---

## Preguntas frecuentes (Aiuken)
- **¿Escribe en OTRS?** Sí, en modo Live: notas como artículos reales
  (`add_article`), reclasificar/escalar propagan (`update_ticket`). Best-effort:
  nunca rompe el flujo si OTRS falla.
- **¿Y los datos sensibles / multi-cliente?** OTRS sigue siendo el system of
  record; auditoría obligatoria; aislamiento por rol/cliente (RBAC).
- **¿La IA puede actuar sola?** No. Human-in-the-loop en acciones críticas
  (borradores, escalados, cambios sensibles) vía cola de aprobaciones.
- **¿Cómo pasamos a producción real?** Configurar `OTRS_ZNUNY_*`, validar con el
  smoke (`pytest tests/smoke -m smoke` o el workflow manual "OTRS Live Smoke"),
  y el badge pasa a Live. Ver README → "Modos de operación".

## Plan B (si algo va lento en vivo)
- Las llamadas IA (RAG, borradores) pueden tardar unos segundos (LLM real). Si el
  entorno está frío, abre primero el frontend para "despertar" el backend.
- Si una superficie no carga: **Ctrl+Shift+R** (caché). El pre-flight (Escena 0)
  detecta cualquier fallo antes de empezar.
