# Propuesta ejecutiva
## BeConnect AI Layer sobre OTRS/Znuny para Aiuken

### 1. Resumen ejecutivo
Aiuken ya dispone de una operativa SOC madura basada en OTRS/Znuny, con colas, roles, SLA, auditoría y flujos consolidados. La oportunidad no es sustituir ese núcleo, sino evolucionarlo hacia una **plataforma SOC inteligente** mediante una capa BeConnect AI que aporte copiloto de analista, explotación semántica del histórico, predicción de SLA, agentes especializados y gobierno trazable.

La propuesta mantiene **OTRS/Znuny como system of record** y sitúa a BeConnect como capa de inteligencia, experiencia y automatización gobernada.

### 2. Objetivo
Reducir fricción operativa y mejorar la capacidad de respuesta del SOC mediante:
- triaje asistido,
- resumen automático de tickets,
- sugerencia de cola y prioridad,
- búsqueda semántica sobre histórico,
- predicción de riesgo SLA,
- borradores de respuesta,
- reporting inteligente,
- auditoría completa de acciones humanas e IA.

### 3. Principios de la solución
1. **OTRS/Znuny sigue siendo la fuente de verdad**.
2. **Integración API-first**, sin acceso directo a base de datos.
3. **Read-only primero**, writeback después.
4. **Human-in-the-loop** para acciones críticas.
5. **Trazabilidad total** de datos, prompts, respuestas y decisiones.
6. **Aislamiento por cliente/tenant** y control de permisos.

### 4. Arquitectura objetivo
```text
Canales / Ingesta
      ↓
OTRS / Znuny (tickets, colas, SLA, auditoría)
      ↓  API / eventos / lecturas controladas
BeConnect Core (IA + orquestación + RAG + SLA)
      ↓
BeConnect UI (copiloto, war room, reporting)
```

#### Componentes
- **OTRS/Znuny**: gestión operativa de tickets, colas, estados, roles y SLA.
- **Conector BeConnect**: lectura/escritura controlada vía API.
- **Modelo canónico**: Ticket, Article, Queue, SLA, ExternalRef.
- **Capa de IA**: triaje, resumen, RAG, predicción SLA, recomendación de acciones.
- **Capa de gobierno**: RBAC, aprobación humana, auditoría, límites por cliente.
- **UI BeConnect**: Smart Queue, Ticket Copilot, SLA War Room, reporting.

### 5. Casos de uso prioritarios
#### 5.1 Ticket Copilot
Asistente lateral dentro del ticket con:
- resumen técnico,
- casos similares,
- sugerencia de cola/prioridad,
- borrador de primera respuesta,
- recomendación de escalado,
- fuentes utilizadas.

#### 5.2 Smart Queue
Bandeja inteligente con:
- prioridad sugerida,
- riesgo SLA,
- cola sugerida,
- siguiente acción recomendada,
- visibilidad del owner.

#### 5.3 SLA War Room
Vista de coordinación para:
- tickets en riesgo,
- tiempo restante efectivo,
- alertas tempranas,
- recomendaciones de actuación,
- seguimiento por turno, cliente y cola.

#### 5.4 Knowledge Vault / RAG
Motor semántico sobre:
- tickets cerrados,
- ticket_history,
- notas internas,
- runbooks,
- plantillas,
- documentación de cliente/fabricante.

### 6. Fases de implementación
| Fase | Objetivo | Entregables |
|---|---|---|
| 0 | Base técnica | Conector OTRS/Znuny, modelo canónico, normalizador, audit log, RBAC |
| 1 | Ingesta y ticket creation | Email/SIEM/ITSM → ticket, prioridad normalizada, deduplicación |
| 2 | Colas y escalado | Árbol de colas, sugerencia N1/N2/N3, owner/lock, motivo de escalado |
| 3 | Ciclo de vida + SLA | Estados, Stop-SLA, tiempo restante, riesgo de incumplimiento, alertas |
| 4 | Smart Queue + Copilot | Bandeja inteligente, resumen técnico, casos similares, borradores, aprobación |
| 5 | Knowledge Vault / RAG | Histórico consultable, embeddings, búsqueda semántica, fuentes citadas |
| 6 | Agentes + gobierno | Triage/SLA/Knowledge/Response/Escalation/Compliance Agents |
| 7 | Reporting + mejora continua | KPIs, informes, observabilidad, feedback, ajuste de reglas/prompts |

### 7. Roadmap 30/60/90 días
| Horizonte | Enfoque | Resultado |
|---|---|---|
| 0–30 días | Integración | BeConnect lee tickets, normaliza datos y audita acciones |
| 31–60 días | Operación mejorada | Tickets mejor creados, colas sugeridas, SLA básico visible |
| 61–90 días | Copiloto | Smart Queue, resúmenes, casos similares, borradores con aprobación |

### 8. Beneficios esperados
- Menor tiempo de triaje.
- Menor riesgo de incumplimiento de SLA.
- Mejor consistencia operativa.
- Reutilización del conocimiento histórico.
- Menor carga manual en N1/N2.
- Mayor trazabilidad y control.
- Mejor experiencia para analistas y coordinación.

### 9. Riesgos y mitigaciones
| Riesgo | Mitigación |
|---|---|
| Acoplamiento excesivo | API-first, modelo canónico y capas separadas |
| Automatización no gobernada | Human-in-the-loop y aprobación de acciones críticas |
| Contaminación entre clientes | Tenant isolation y permisos por rol |
| Respuestas IA sin fuente | RAG con citas obligatorias y guardrails |
| Ruido operativo | Sprint inicial read-only antes de writeback |

### 10. Métricas de éxito
- MTTA / MTTR.
- Cumplimiento SLA.
- Tiempo medio de triaje.
- Porcentaje de borradores aceptados.
- Tickets resueltos con ayuda de Copilot.
- Reutilización de conocimiento histórico.
- Reducción de escalados innecesarios.

### 11. Mensaje ejecutivo
> No venimos a cambiar el SOC de Aiuken. Venimos a potenciarlo con una capa de IA gobernada que reduce fricción, mejora la respuesta, anticipa riesgos y convierte el histórico en ventaja operativa.

### 12. Próximos pasos
1. Validar alcance funcional con Aiuken.
2. Confirmar acceso a OTRS/Znuny y modalidad de integración.
3. Aprobar Sprint 0 (base técnica).
4. Definir piloto con tickets reales y métricas de éxito.
5. Iniciar implementación incremental.
