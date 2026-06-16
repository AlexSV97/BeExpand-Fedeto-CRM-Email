# Aiuken SOC

> **Plataforma de inteligencia y operaciones SOC — clasificación inteligente de correos, gestión de tickets y centro de comando**

---

## ¿Qué es?

**Aiuken SOC** es un sistema que **lee, clasifica y organiza automáticamente los correos electrónicos** que llegan a la empresa, y provee un **Centro de Operaciones de Seguridad (SOC)** completo para la gestión de tickets, SLA, agentes, auditoría y reportes.

Cada correo se analiza, se categoriza (cliente, proveedor, lead, etc.), se determina su urgencia y relevancia, y se registra en el CRM — todo sin intervención humana.

Sobre esa base, la plataforma ofrece un **SOC shell** con 9 superficies especializadas: Command Center, Smart Ticket Queue, Ticket Copilot, SLA War Room, Knowledge Vault, Agent Governance, Reporting, Audit y Configuration.

El resultado: un equipo que **deja de perder tiempo organizando correos y tickets** y se centra en lo que realmente importa: **resolver incidentes, dar servicio y vender**.

---

## El Problema

Las empresas reciben decenas o cientos de correos al día en múltiples direcciones. Alguien tiene que:

- Leer cada correo y entender de qué trata
- Decidir si es importante o no
- Identificar si es un cliente nuevo, un proveedor, una oportunidad
- Decidir a qué departamento enviarlo
- Apuntar la información en el CRM
- Hacer seguimiento para que no se pierda
- Gestionar tickets, SLA, colas y escalados manualmente

**Esto es lento, caro y propenso a errores.** Los correos importantes se pierden entre el ruido, las oportunidades se enfrían, y el CRM se acaba quedando desactualizado porque nadie tiene tiempo de rellenarlo manualmente.

---

## La Solución

**Un sistema automatizado que hace todo ese trabajo en segundos.**

Cada correo que llega a la empresa pasa por un pipeline inteligente que:

1. **Lee y analiza** el contenido del correo
2. **Clasifica** el tipo de contacto y la categoría del mensaje
3. **Evalúa la urgencia** y la relevancia comercial
4. **Determina el departamento** al que debe dirigirse
5. **Actualiza el CRM** automáticamente
6. **Muestra todo** en un dashboard SOC con 9 superficies especializadas

Y todo esto ocurre **en menos de 5 segundos por correo**, 24/7, sin que nadie tenga que hacer nada.

---

## ¿Cómo Funciona? El Viaje de un Correo

Para que se entienda bien, sigamos el camino de un correo desde que llega hasta que se muestra en el dashboard:

### 1. 📥 Llega un correo
Un cliente escribe a una dirección vigilada. El sistema lo detecta automáticamente (revisa la bandeja de entrada cada 60 segundos).

### 2. 📄 Se analiza el contenido
El sistema extrae todo lo importante del correo: quién lo envía, de qué empresa es, qué pide, si adjunta documentos, el nivel de urgencia.

### 3. 🤖 Tres clasificadores votan
Aquí está la clave del sistema. **Tres sistemas de inteligencia artificial diferentes analizan el correo de forma simultánea**, cada uno con su enfoque:

| Clasificador | ¿Cómo funciona? | Lo bueno |
|:---|:---|---|
| **Reglas** | Busca palabras clave (presupuesto, factura, urgencia, reclamación) | Instantáneo (~1 ms), muy fiable con patrones conocidos |
| **BERT** | Red neuronal entrenada con miles de ejemplos reales | Detecta patrones aunque no estén las palabras exactas, mejora con el tiempo |
| **LLM** | Modelo de lenguaje avanzado (IA generativa) que comprende el contexto | Detecta matices, sarcasmo, intención — como un humano |

Al ser tres sistemas independientes votando, si dos de los tres coinciden, la clasificación es fiable. Si los tres discrepan, un sistema de desempate revisa los votos y decide.

### 4. ✅ Se asigna una categoría
El correo se etiqueta automáticamente: *consulta, presupuesto, pedido, reclamación, seguimiento, proveedor, interno, spam...*

### 5. 🧭 Se enruta al departamento correspondiente
El sistema decide a qué área debe llegar (comercial, administración, soporte, dirección) y lo registra.

### 6. 💾 Se guarda en el CRM
Toda la información relevante se vuelca automáticamente en VTiger: contacto, empresa, oportunidad, historial de interacciones.

### 7. 📊 Se muestra en el SOC
En tiempo real, el equipo ve en el Command Center los KPIs, alertas, presión de cola y riesgo SLA.

**Todo esto ocurre en menos de 5 segundos.** Mientras un humano estaría aún leyendo el asunto, el sistema ya ha clasificado, registrado y mostrado el correo.

---

## Humano vs Sistema

| Aspecto | Trabajo manual | Con Aiuken SOC |
|:---|:---|:---|
| **Tiempo por correo** | 2-5 minutos leyendo, entendiendo y clasificando | 2-5 segundos automático |
| **Jornada de 8h** | ~100-150 correos procesados | Todos los que lleguen, sin límite |
| **Errores** | Cansancio, despistes, criterio inconsistente | Siempre el mismo criterio, trazable |
| **Cobertura** | Se priorizan los correos "que suenan importantes" | El 100% de los correos se clasifican |
| **CRM actualizado** | Depende de la voluntad de cada uno | Se actualiza siempre, sin depender de nadie |
| **Disponibilidad** | Solo en horario laboral | 24/7, fines de semana y festivos |
| **Coste por correo** | Salario + tiempo + errores | Coste tecnológico mínimo |
| **Escalabilidad** | Para procesar más, necesitas contratar más personas | Duplicas o triplicas el volumen sin cambiar nada |

---

## Beneficios para la Empresa

### Para el equipo de operaciones/SOC
- **Dejan de perder tiempo** leyendo y clasificando correos y tickets manualmente
- **Ven todas las incidencias** en un Command Center unificado
- **Pueden priorizar** por urgencia, SLA, valor — no por orden de llegada

### Para la dirección
- **Visibilidad total** de la actividad: KPIs, cumplimiento SLA, rendimiento de agentes
- **Detección temprana** de incidentes y riesgos de incumplimiento
- **Auditoría completa** de todas las acciones — IA y humanas

### Para la empresa en general
- **Ningún correo importante se pierde** — el 100% se clasifica y almacena
- **El CRM está siempre actualizado**, sin depender de que alguien lo rellene
- **Escalable**: funciona igual con 10 correos al día que con 500
- **Auditable**: todo lo que ocurre queda registrado

---

## Aiuken SOC Shell — Centro de Comando

El frontend incluye un **SOC Shell** completo con 9 superficies especializadas, accesible mediante feature flag:

### Cómo activarlo
```js
localStorage.setItem('soc_shell_enabled', 'true')
// Recargar la página
```

### Superficies del SOC

| # | Superficie | Descripción |
|---|-----------|-------------|
| 1 | **Command Center** | KPIs en tiempo real, alertas recientes, presión de cola, resumen de riesgo SLA |
| 2 | **Smart Ticket Queue** | Bandeja inteligente con filtros, búsqueda, paginación — navega al Copilot por fila |
| 3 | **Ticket Copilot** | Vista partida: detalle del ticket + panel de IA con sugerencias, borradores y acciones |
| 4 | **SLA War Room** | Temporizadores de SLA, alertas de breach, matriz prioridad×cola |
| 5 | **Knowledge Vault** | Buscador de artículos, categorías (SOPs, Playbooks, Known Issues), relevance score |
| 6 | **Agent Governance** | Roster de agentes, estado online, menú de override, compliance score |
| 7 | **Reporting** | Reportes por tipo (SLA, agentes, tickets, colas), date range, gráficos Recharts |
| 8 | **Audit** | Timeline de eventos inmutable, filtros por actor/tipo/fecha, detalles expandibles |
| 9 | **Configuration** | Thresholds de SLA, definiciones de niveles, visibilidad de superficies, integraciones |

### Arquitectura del SOC Shell

```
src/
├── services/soc/
│   ├── contracts.ts          # Tipos: SurfaceId, SurfaceStatus, SurfaceDescriptor
│   ├── surfaceRegistry.tsx   # Registro singleton con lazy loading de las 9 surfaces
│   ├── socShellStore.ts      # Store Zustand + history.pushState/popstate sync
│   ├── SocShellProvider.tsx  # Context provider con useSocShell() hook
│   ├── client.ts             # socFetch() con auth JWT, timeout 30s, 2 retries con backoff
│   ├── endpoints.ts          # Mapeo SurfaceId → rutas API (/api/v1/soc/*)
│   ├── normalize/            # 9 normalizadores API → view-model
│   └── index.ts              # Barrel
├── components/soc/
│   ├── SocShell.tsx          # Shell principal con tab strip y surface outlet
│   ├── SocLoadingState.tsx   # Estado de carga
│   ├── SocEmptyState.tsx     # Estado vacío con CTA opcional
│   ├── SocErrorState.tsx     # Estado de error con retry
│   ├── SocStaleBanner.tsx    # Banner de datos desactualizados
│   └── index.ts              # Barrel
├── content/socCopy.ts        # Sistema de copia neutral con SOC_TERM_MAP + t()
├── config/socShell.ts        # Feature flag vía localStorage
└── pages/soc/                # 9 surfaces implementadas
```

**Principios de diseño:**
- **Sin React Router**: la navegación entre surfaces usa Zustand + History API
- **Feature flag**: `localStorage.setItem('soc_shell_enabled', 'true')` activa el SOC shell; con flag OFF la app funciona exactamente como antes
- **Mock data fallback**: todas las surfaces muestran datos de ejemplo cuando el backend no está disponible
- **Copia neutral**: `socCopy.ts` traduce términos legacy automáticamente

---

## Para los Técnicos

### Stack Tecnológico

| Capa | Tecnología |
|:---|:---|
| **Backend** | Python 3.12+, FastAPI, SQLAlchemy 2.0 asíncrono |
| **Base de datos** | PostgreSQL 16 (SQLite en desarrollo) |
| **Frontend** | React 19 + TypeScript 6, Vite 8, Tailwind CSS 4, Zustand 5, Recharts, Framer Motion |
| **Clasificación** | Pipeline multi-agente paralelo: Rule Engine + BERT (ONNX) + LLM (OpenRouter) |
| **CRM** | VTiger REST API (cliente HTTP con httpx) |
| **Correo** | IMAP nativo (conexión directa al servidor de correo) |
| **Autenticación** | JWT (python-jose + passlib + bcrypt) |
| **Despliegue** | Render (cloud), Docker para desarrollo local |

### Pipeline de Clasificación

```
Correo → IMAP Sync → Parser → Analyzer (LLM)
                                    │
           ┌────────────────────────┴────────────────────────┐
           │              ORQUESTADOR PARALELO                │
           │                                                  │
           │  ┌─────────────────┐  ┌──────────┐  ┌────────┐  │
           │  │ RuleClassifier  │  │ BERT     │  │ LLM    │  │
           │  │ (~1ms, reglas)  │  │ (~50ms)  │  │ (~2s)  │  │
           │  └────────┬────────┘  └─────┬────┘  └───┬────┘  │
           └───────────┼──────────────────┼───────────┼───────┘
                       └──────────────────┼───────────┘
                                          ▼
                              VoteResolver (consenso / mayoría / juez)
                                          │
                                 ┌────────┴────────┐
                                 ▼                  ▼
                            Router              Dashboard / SOC
                         (departamento)       (React + Recharts + SOC Shell)
                                 │
                                 ▼
                          ActionExecutor
                         (CRM + historial)
```

**Los 3 clasificadores se ejecutan en paralelo.** Cada uno vota con el mismo peso. Si 2 de 3 coinciden, gana esa categoría por mayoría. Si los 3 son distintos, un juez (IA) revisa los votos y decide.

### Estructura del Proyecto

```
BeExpand-Fedeto-CRM-Email/
├── backend/
│   ├── src/
│   │   ├── email_processor/    # IMAP, parseo y filtrado de correos
│   │   ├── classifier/         # Clasificadores (rule, bert/ONNX, llm)
│   │   ├── orchestrator/       # Orquestador paralelo + VoteResolver
│   │   ├── agents/             # Analyzer, Router, ActionExecutor
│   │   ├── api/                # API REST (FastAPI)
│   │   ├── db/                 # Modelos de base de datos
│   │   ├── crm_integration/    # Integración con VTiger
│   │   └── tasks/              # Tareas programadas
│   ├── scripts/                # Utilidades (datos de prueba, testeo)
│   └── tests/                  # Tests automatizados (156 tests)
├── frontend/
│   └── src/
│       ├── pages/              # Dashboard, Contactos, Oportunidades, Ajustes
│       │   └── soc/            # 9 surfaces del SOC Shell (CommandCenter, TicketQueue, etc.)
│       ├── components/
│       │   ├── ...             # Componentes reutilizables existentes
│       │   └── soc/            # SocShell, SocLoadingState, SocEmptyState, SocErrorState, SocStaleBanner
│       ├── services/
│       │   ├── api.ts          # Cliente API general
│       │   └── soc/            # Adaptador SOC: client, endpoints, normalize, store, registry
│       ├── content/
│       │   └── socCopy.ts      # Sistema de copia neutral con term map
│       ├── config/
│       │   └── socShell.ts     # Feature flag del SOC Shell
│       └── contexts/           # AuthContext, etc.
└── infrastructure/             # Docker, configuraciones
```

### Desarrollo Local

```bash
git clone https://github.com/AlexSV97/BeExpand-Fedeto-CRM-Email.git
cd BeExpand-Fedeto-CRM-Email

# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend (otra terminal)
cd frontend
npm install
npm run dev
```

### Tests

```bash
# Backend (156 tests automatizados)
cd backend && pytest -v

# Frontend (build check)
cd frontend && npm run build
```

---

## Estado del Proyecto

| Hito | Estado |
|:---|:---:|
| M1 — Captura de correos (IMAP) | ✅ Completo |
| M2 — Parseo y análisis de contenido | ✅ Completo |
| M3 — Clasificadores (Rule + BERT + LLM) | ✅ Completo |
| M4 — API REST + Dashboard React | ✅ Completo |
| M5 — Orquestador paralelo multi-agente | ✅ Completo |
| Backend Aiuken SOC (Sprints 0-7) | ✅ Completo (156 tests) |
| Despliegue en Render | ✅ Operativo |
| Dashboard con Settings | ✅ Completo |
| **SOC Shell Frontend** | ✅ **Completo (9 superficies)** |
| Command Center | ✅ KPIs, alertas, presión de cola, riesgo SLA |
| Smart Ticket Queue | ✅ Filtros, búsqueda, paginación, navegación a Copilot |
| Ticket Copilot | ✅ Split view, sugerencias IA, acciones |

## Aiuken SOC — Capa de Inteligencia sobre OTRS/Znuny

### Contexto estratégico
Aiuken dispone de una base SOC madura sobre OTRS/Znuny. Aiuken SOC se propone como una **capa de inteligencia gobernada** que amplía esa operación sin reemplazar el sistema de registro, incorporando copiloto de analista, RAG, SLA predictivo, agentes especializados y observabilidad.

### Principios de diseño
- **OTRS/Znuny como system of record**
- **Aiuken SOC como capa de inteligencia y experiencia**
- **Integración API-first**
- **Lectura primero, escritura asistida después**
- **Human-in-the-loop para acciones críticas**
- **Auditoría completa de IA y usuarios**

### Arquitectura objetivo
```text
Canales / Ingesta
      ↓
OTRS / Znuny (tickets, colas, SLA, auditoría)
      ↓  API / eventos / lecturas controladas
Aiuken SOC Core (IA + orquestación + RAG + SLA)
      ↓
Aiuken SOC UI (copiloto, war room, reporting, command center)
```

### Alcance por fases

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

### Roadmap 30/60/90 días

| Horizonte | Enfoque | Resultado |
|---|---|---|
| 0–30 días | Integración | Aiuken SOC lee tickets, normaliza datos y audita acciones |
| 31–60 días | Operación mejorada | Tickets mejor creados, colas sugeridas, SLA básico visible |
| 61–90 días | Copiloto | Smart Queue, resúmenes, casos similares, borradores con aprobación |

### Backlog resumido
- Conector OTRS/Znuny
- Modelo canónico `Ticket/Article/Queue/SLA/ExternalRef`
- Normalización de tickets y eventos
- Audit log y RBAC
- Ingesta email / SIEM / ITSM
- Colas y escalado N1/N2/N3
- SLA predictivo y alertas tempranas
- Smart Queue y Ticket Copilot
- Knowledge Vault / RAG
- Agentes especializados con gobierno
- Reporting y mejora continua

### Documentación asociada
- [Propuesta ejecutiva](docs/propuesta-aiuken-beconnect.md)
- [Backlog técnico implementable](docs/backlog-aiuken-beconnect.md)
- [Índice maestro](docs/indice-maestro-aiuken.md)

### Diagramas de apoyo
- [Arquitectura general](images/ChatGPT%20Image%2016%20jun%202026,%2015_33_29.png)
- [Flujo 1: Ingesta y creación de ticket](images/ChatGPT%20Image%2016%20jun%202026,%2015_48_14%20(1).png)
- [Flujo 2: Colas y escalado](images/ChatGPT%20Image%2016%20jun%202026,%2015_48_14%20(2).png)
- [Flujo 3: Ciclo de vida y SLA](images/ChatGPT%20Image%2016%20jun%202026,%2015_48_14%20(3).png)
- [Flujo 4: Smart Queue + Copilot](images/ChatGPT%20Image%2016%20jun%202026,%2015_48_15%20(4).png)
- [Flujo 5: Knowledge Vault / RAG](images/ChatGPT%20Image%2016%20jun%202026,%2015_48_15%20(5).png)
- [Flujo 6: Agentes y gobierno](images/ChatGPT%20Image%2016%20jun%202026,%2015_48_15%20(6).png)
- [Flujo 7: Reporting y mejora continua](images/ChatGPT%20Image%2016%20jun%202026,%2015_48_15%20(7).png)
- [Cierre / visión global](images/ChatGPT%20Image%2016%20jun%202026,%2015_48_15%20(8).png)

### Mensaje ejecutivo
> **No venimos a cambiar el SOC de Aiuken. Venimos a potenciarlo con una capa de IA gobernada que reduce fricción, mejora la respuesta, anticipa riesgos y convierte el histórico en ventaja operativa.**

---

## Licencia

Proyecto desarrollado para **Aiuken**.
