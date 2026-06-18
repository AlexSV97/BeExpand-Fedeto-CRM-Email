# Backlog técnico implementable
## Aiuken SOC como capa de inteligencia sobre OTRS/Znuny

### Objetivo
Convertir la propuesta en un plan de ejecución técnico, priorizado y entregable por fases, manteniendo OTRS/Znuny como sistema de registro y Aiuken SOC como capa de inteligencia gobernada.

---

## Criterios transversales
- **OTRS/Znuny es la fuente de verdad**.
- **Integración API-first**: no escribir directamente en BD.
- **Read-only primero**: la primera versión solo lee y observa.
- **Human-in-the-loop** para acciones críticas.
- **Auditoría obligatoria** de lecturas, escrituras y decisiones IA.
- **Aislamiento por cliente/tenant**.

---

## Épica 0 — Base técnica
### Objetivo
Preparar el núcleo de integración, normalización y gobierno.

### Historias
| ID | Historia | Prioridad | Dependencias | Criterio de aceptación |
|---|---|---:|---|---|
| BT-01 | Crear conector REST OTRS/Znuny | P0 | — | Aiuken SOC puede autenticar, leer tickets e historial y registrar comentarios/estado vía API |
| BT-02 | Definir modelo canónico interno | P0 | — | Existe esquema común para `Ticket`, `Article`, `Queue`, `SLA`, `ExternalRef` |
| BT-03 | Implementar normalizador OTRS → modelo interno | P0 | BT-01, BT-02 | El payload de OTRS/Znuny se convierte sin pérdida crítica |
| BT-04 | Añadir audit log técnico | P0 | BT-02 | Toda acción queda registrada con actor, timestamp, fuente y resultado |
| BT-05 | Configurar RBAC + tenant context | P0 | — | Los accesos y datos quedan segmentados por rol y cliente |
| BT-06 | Healthcheck y observabilidad básica | P1 | BT-01 | Hay métricas de conectividad, latencia y errores por integración |

### Salida esperada
Aiuken SOC puede **leer tickets** de OTRS/Znuny, normalizarlos y auditar toda interacción.

---

## Épica 1 — Ingesta y creación de ticket
### Objetivo
Convertir eventos entrantes en tickets trazables.

### Historias
| ID | Historia | Prioridad | Dependencias | Criterio de aceptación |
|---|---|---:|---|---|
| IN-01 | Ingestar email como ticket | P0 | BT-01, BT-03 | Un email se convierte en ticket con estado/cola/prioridad correctos |
| IN-02 | Ingestar alerta SIEM como ticket | P1 | BT-01, BT-03 | Una alerta se registra con severidad y metadatos correctos |
| IN-03 | Ingestar ITSM externo como ticket | P1 | BT-01, BT-03 | Incidencias externas se crean o enlazan sin duplicados |
| IN-04 | Normalizar prioridad desde severidad | P0 | BT-02, BT-03 | Severidad alta/media/baja mapea a prioridad operativa |
| IN-05 | Evitar tickets duplicados | P0 | BT-01, BT-03 | Eventos repetidos no generan tickets nuevos |
| IN-06 | Generar auto-respuesta/ack | P1 | IN-01 | Se confirma recepción con ticket ID y trazabilidad |

### Salida esperada
Cualquier evento soportado termina como ticket correcto y deduplicado.

---

## Épica 2 — Colas y escalado
### Objetivo
Respetar la topología operativa de Aiuken (N1/N2/N3/fabricante/external ITSM).

### Historias
| ID | Historia | Prioridad | Dependencias | Criterio de aceptación |
|---|---|---:|---|---|
| CE-01 | Modelar árbol de colas | P0 | BT-02 | Existe representación de colas raíz, subcolas y especiales |
| CE-02 | Sugerir cola según cliente/servicio | P1 | CE-01, IN-01 | El sistema propone cola inicial con confianza y explicación |
| CE-03 | Sugerir nivel N1/N2/N3 | P1 | CE-01 | El sistema recomienda nivel operativo según complejidad |
| CE-04 | Registrar escalado con motivo | P1 | BT-04 | Cada escalado deja causa, actor y timestamp |
| CE-05 | Gestión de owner/lock por ticket | P1 | BT-05 | El ticket tiene propietario y bloqueo rastreables |
| CE-06 | Escalado a fabricante / ITSM externo | P2 | CE-04 | Se puede enviar el caso a un destino externo con tracking |

### Salida esperada
La IA propone, pero la estructura operativa manda y queda registrada.

---

## Épica 3 — Ciclo de vida + SLA
### Objetivo
Pasar de SLA reactivo a SLA predictivo.

### Historias
| ID | Historia | Prioridad | Dependencias | Criterio de aceptación |
|---|---|---:|---|---|
| SLA-01 | Mapear estados del ticket | P0 | BT-02 | El ciclo de vida queda representado de forma consistente |
| SLA-02 | Detectar Stop-SLA | P0 | SLA-01 | Estados de pausa congelan/reanudan SLA correctamente |
| SLA-03 | Calcular tiempo restante SLA | P1 | SLA-01, SLA-02 | El sistema muestra tiempo restante por ticket |
| SLA-04 | Calcular riesgo de incumplimiento | P1 | SLA-03 | Se estima probabilidad de breach antes de ocurrir |
| SLA-05 | Generar alertas tempranas | P1 | SLA-04 | Se notifica antes de vencimiento a analista/coordinación |
| SLA-06 | SLA War Room básico | P2 | SLA-05 | Existe vista operativa con tickets críticos y vencimientos |

### Salida esperada
El sistema puede anticipar problemas de SLA y priorizar acciones.

---

## Épica 4 — Smart Queue + Copilot
### Objetivo
Mejorar la experiencia del analista con una bandeja inteligente y asistencia contextual.

### Historias
| ID | Historia | Prioridad | Dependencias | Criterio de aceptación |
|---|---|---:|---|---|
| CP-01 | Bandeja inteligente | P1 | CE-02, SLA-04 | La lista muestra prioridad, riesgo SLA, cola sugerida y owner |
| CP-02 | Vista detalle enriquecida | P1 | BT-02, SLA-01 | El ticket muestra timeline, historial, SLA y contexto |
| CP-03 | Resumen técnico automático | P1 | IN-01 | El sistema resume el caso con contexto útil |
| CP-04 | Casos similares | P1 | KV-01 | El copilot recupera tickets parecidos con fuentes |
| CP-05 | Borrador de primera respuesta | P1 | KV-02 | Se genera respuesta utilizable como borrador |
| CP-06 | Borrador de actualización interna | P1 | KV-02 | Se genera una nota interna accionable |
| CP-07 | Aprobación humana previa a envío | P0 | GOV-01 | Ninguna respuesta crítica sale sin validación |

### Salida esperada
El analista gana velocidad y consistencia, sin perder control.

---

## Épica 5 — Knowledge Vault / RAG
### Objetivo
Convertir el histórico del SOC en conocimiento reutilizable.

### Historias
| ID | Historia | Prioridad | Dependencias | Criterio de aceptación |
|---|---|---:|---|---|
| KV-01 | Ingestar tickets cerrados | P1 | BT-01, BT-02 | Tickets históricos quedan indexados |
| KV-02 | Ingestar notas internas y runbooks | P1 | BT-02 | Documentos operativos quedan disponibles para consulta |
| KV-03 | Generar embeddings | P1 | KV-01, KV-02 | El corpus queda vectorizado y consultable |
| KV-04 | Búsqueda semántica por ticket | P1 | KV-03 | Se recupera contexto relevante por ticket/consulta |
| KV-05 | Reranking de resultados | P2 | KV-04 | Los resultados se ordenan por relevancia real |
| KV-06 | Citar fuentes en respuestas | P1 | KV-04 | Toda respuesta IA referencia el origen del conocimiento |

### Salida esperada
Aiuken SOC puede responder usando histórico y runbooks con fuentes trazables.

---

## Épica 6 — Agentes + gobierno
### Objetivo
Evolucionar a un sistema agentic gobernado, sin autonomía peligrosa.

### Historias
| ID | Historia | Prioridad | Dependencias | Criterio de aceptación |
|---|---|---:|---|---|
| AG-01 | Definir Triage Agent | P2 | CP-03 | Existe agente para triaje y priorización con límites claros |
| AG-02 | Definir SLA Agent | P2 | SLA-04 | Existe agente para riesgo y alertas SLA |
| AG-03 | Definir Knowledge Agent | P2 | KV-04 | Existe agente para recuperación de conocimiento |
| AG-04 | Definir Response Agent | P2 | CP-05, KV-06 | Existe agente para borradores con guardrails |
| AG-05 | Definir Escalation Agent | P2 | CE-03, CE-04 | Existe agente de recomendación de escalado |
| AG-06 | Definir Compliance Agent | P2 | BT-04, BT-05 | Existe agente que valida permisos, privacidad y auditoría |
| AG-07 | Aprobar acciones críticas | P0 | GOV-01 | Cambios sensibles requieren aprobación humana |

### Salida esperada
Los agentes colaboran, pero no actúan libres ni opacos.

---

## Épica 7 — Reporting + mejora continua
### Objetivo
Cerrar el ciclo de medición, aprendizaje y mejora.

### Historias
| ID | Historia | Prioridad | Dependencias | Criterio de aceptación |
|---|---|---:|---|---|
| RP-01 | KPIs operativos | P1 | BT-04 | Existen métricas MTTA/MTTR/SLA/backlog/reabiertos |
| RP-02 | Informe diario de turno | P1 | RP-01 | Se genera un reporte diario automático |
| RP-03 | Informe semanal por cliente | P1 | RP-01 | Se genera un reporte segmentado por tenant/cliente |
| RP-04 | Dashboard de observabilidad | P1 | BT-06 | Hay vista de logs, latencia, coste y fallos |
| RP-05 | Feedback de analistas sobre IA | P2 | CP-01 | Los analistas pueden corregir sugerencias |
| RP-06 | Ajuste de reglas/prompts/runbooks | P2 | RP-05 | El sistema mejora a partir del feedback operativo |

### Salida esperada
El SOC ve su rendimiento y el sistema aprende de la operación real.

---

## Orden de implementación recomendado
### MVP 1
1. Base técnica
2. Ingesta email → ticket
3. SLA básico
4. Auditoría y RBAC

### MVP 2
5. Colas y escalado
6. Smart Queue
7. Ticket Copilot
8. Aprobación humana

### MVP 3
9. Knowledge Vault / RAG
10. SLA predictivo avanzado
11. Reporting

### MVP 4
12. Agentes especializados
13. Gobierno completo
14. Mejora continua

---

## Riesgos principales
| Riesgo | Mitigación |
|---|---|
| Acoplamiento excesivo | API-first y modelo canónico |
| Automatización no gobernada | Human-in-the-loop y aprobaciones |
| Contaminación entre clientes | Tenant isolation y RBAC |
| Respuestas IA sin fuente | RAG con citas obligatorias |
| Ruido operativo | Sprint inicial read-only antes de writeback |

---

## Definición de done por fase
Una fase se considera completa cuando:
- los datos quedan normalizados,
- las acciones quedan auditadas,
- el usuario puede validar el resultado,
- y no se rompe el flujo operativo de Aiuken.
