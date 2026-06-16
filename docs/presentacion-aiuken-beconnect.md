# Presentación ejecutiva
## BeConnect AI Layer sobre OTRS/Znuny para Aiuken

---

## Slide 1 — Título
**BeConnect AI Layer para Aiuken**

Evolución inteligente del SOC sobre OTRS/Znuny

---

## Slide 2 — Punto de partida
- Aiuken ya opera sobre una base SOC madura en OTRS/Znuny.
- El sistema actual resuelve tickets, colas, roles, SLA y auditoría.
- La oportunidad es añadir una capa de inteligencia sin romper la operación.

**Mensaje clave:** no sustituir, sino potenciar.

---

## Slide 3 — La propuesta
BeConnect se integra como una **capa AI gobernada** sobre OTRS/Znuny para aportar:
- copiloto de analista,
- búsqueda semántica del histórico,
- predicción de SLA,
- resumen automático de tickets,
- sugerencia de cola y prioridad,
- borradores de respuesta,
- observabilidad y trazabilidad.

---

## Slide 4 — Arquitectura objetivo
![Arquitectura general](../images/ChatGPT%20Image%2016%20jun%202026,%2015_33_29.png)

```text
Canales / Ingesta
      ↓
OTRS / Znuny (system of record)
      ↓  API / eventos / lecturas controladas
BeConnect Core (IA + orquestación + RAG + SLA)
      ↓
BeConnect UI (copiloto, war room, reporting)
```

Principios:
- API-first
- read-only primero
- human-in-the-loop
- auditoría completa
- aislamiento por cliente

---

## Slide 5 — Casos de uso prioritarios
![Flujo 1: Ingesta y creación de ticket](../images/ChatGPT%20Image%2016%20jun%202026,%2015_48_14%20(1).png)

### 1. Smart Queue
- prioridad sugerida
- cola sugerida
- riesgo SLA
- siguiente acción recomendada

### 2. Ticket Copilot
- resumen técnico
- casos similares
- borrador de respuesta
- recomendación de escalado

### 3. SLA War Room
- tickets críticos
- tiempo restante
- alertas tempranas
- vista por turno y cliente

---

## Slide 6 — Knowledge Vault / RAG
![Flujo 5: Knowledge Vault / RAG](../images/ChatGPT%20Image%2016%20jun%202026,%2015_48_15%20(5).png)

BeConnect aprende del histórico del SOC:
- tickets cerrados
- ticket_history
- notas internas
- runbooks
- documentación de clientes y fabricantes

Resultado:
- casos similares
- respuestas con fuente
- mejor reutilización del conocimiento
- menos tiempo de investigación

---

## Slide 7 — Gobierno y seguridad
![Flujo 6: Agentes y gobierno](../images/ChatGPT%20Image%2016%20jun%202026,%2015_48_15%20(6).png)

- OTRS/Znuny sigue siendo la fuente de verdad.
- Las acciones críticas requieren aprobación humana.
- Todo queda auditado.
- Los agentes IA operan con límites claros.
- Se respetan roles, colas y separación por cliente.

---

## Slide 8 — Roadmap 30/60/90
![Flujo 7: Reporting y mejora continua](../images/ChatGPT%20Image%2016%20jun%202026,%2015_48_15%20(7).png)

### 0–30 días
Integración y base técnica.

### 31–60 días
Operación mejorada: tickets mejor creados, colas sugeridas, SLA visible.

### 61–90 días
Copiloto operativo: Smart Queue, resúmenes, casos similares, borradores.

---

## Slide 9 — Beneficios esperados
![Cierre / visión global](../images/ChatGPT%20Image%2016%20jun%202026,%2015_48_15%20(8).png)

- menos tiempo de triaje,
- menor riesgo SLA,
- mejor consistencia operativa,
- reutilización del conocimiento,
- menor carga manual,
- mayor trazabilidad,
- mejor experiencia para analistas y coordinación.

---

## Slide 10 — Cierre
> No venimos a cambiar el SOC de Aiuken. Venimos a potenciarlo con una capa de IA gobernada que reduce fricción, mejora la respuesta, anticipa riesgos y convierte el histórico en ventaja operativa.

**Próximo paso:** piloto incremental sobre tickets reales.
