# BeExpand-Fedeto-CRM-Email

Proyecto desarrollado para **Be Expand** — sistema de centralización y estructuración de información clave proveniente del correo electrónico, con integración CRM para la gestión de contactos, oportunidades y seguimiento comercial.

## Índice

- [Descripción del Proyecto](#descripción-del-proyecto)
- [Problema](#problema)
- [Solución Propuesta](#solución-propuesta)
- [Arquitectura del Sistema](#arquitectura-del-sistema)
- [Tecnologías](#tecnologías)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Instalación y Configuración](#instalación-y-configuración)
- [Uso](#uso)
- [Comandos útiles](#comandos-útiles)
- [Contribución](#contribución)
- [Licencia](#licencia)

## Descripción del Proyecto

Sistema diseñado para **Be Expand** que permite centralizar, estructurar y procesar automáticamente la información proveniente del correo electrónico empresarial. Clasifica contactos (clientes, leads, proveedores, etc.), determina el estado de las interacciones y se integra con el CRM para proporcionar una visión operativa clara de la actividad comercial.

## Problema

La empresa enfrenta los siguientes desafíos:

- **Alto volumen de correos electrónicos** recibidos en múltiples bandejas de entrada, especialmente en dirección.
- **Información dispersa** entre departamentos sin un sistema estructurado de gestión.
- **Pérdida de oportunidades** por falta de seguimiento eficiente de clientes potenciales.
- **Análisis manual** costoso y propenso a errores para identificar contactos, estados y relevancia de oportunidades.
- **Baja integración con el CRM** actual, dificultando la toma de decisiones comerciales.

## Solución Propuesta

Desarrollo de un sistema que:

1. **Centraliza** los correos relevantes a través de una cuenta intermedia.
2. **Clasifica automáticamente** los contactos (cliente, lead, proveedor, etc.).
3. **Determina el estado** de las interacciones y la relevancia de cada oportunidad.
4. **Se integra con el CRM** existente para actualizar registros de forma automatizada.
5. **Genera resúmenes y dashboards** para el seguimiento comercial y la gestión de proyectos.

### Objetivos

| Objetivo | Descripción |
|----------|-------------|
| Centralización | Unificar bandejas de entrada en un único punto de procesamiento |
| Automatización | Reducir al mínimo la intervención manual en la clasificación y registro |
| Trazabilidad | Mantener un historial completo de interacciones con cada contacto |
| Eficiencia | Aumentar la tasa de conversión de oportunidades en clientes |
| Visibilidad | Proporcionar dashboards operativos para la toma de decisiones |

## Arquitectura del Sistema

```
                    ┌──────────────────────┐
                    │   Buzones IMAP       │
                    │  (Ionos / Imax)      │
                    └─────────┬────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                    │  Auto-Sync Loop      │
                    │  (asyncio, cada 60s) │
                    └─────────┬────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                    │  Email Parser        │
                    │  (body, attachments, │
                    │   recipients)        │
                    └─────────┬────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                    │   Analyzer (LLM)     │
                    │  empresa, urgencia,  │
                    │  acción, entidades   │
                    └─────────┬────────────┘
                              │
                    ┌─────────┴──────────────────┐
                    │  ORQUESTADOR PARALELO       │
                    │                             │
                    │  ┌──────────────────────┐   │
                    │  │ RuleClassifierAgent  │   │
                    │  │ (keywords ponderados)│   │
                    │  └──────────┬───────────┘   │
                    │  ┌──────────────────────┐   │
                    │  │ BertClassifierAgent  │   │
                    │  │ (DistilBERT, ~50ms)  │   │  ← PARALELO
                    │  └──────────┬───────────┘   │
                    │  ┌──────────────────────┐   │
                    │  │ LLMClassifierAgent   │   │
                    │  │ (Ollama, ~1-3s)      │   │
                    │  └──────────┬───────────┘   │
                    └─────────────┼───────────────┘
                                  │
                                  ▼
                    ┌──────────────────────┐
                    │    VoteResolver      │
                    │ CONSENSUS / MAJORITY │
                    │ LLM_JUDGE / FALLBACK │
                    └─────────┬────────────┘
                              │
                    ┌─────────┴────────────┐
                    ▼                      ▼
             ┌───────────┐        ┌──────────────┐
             │  Router   │        │  Dashboard   │
             │ (Dpto    )│        │  (Recharts   │
             │  destino )│        │   + React)   │
             └─────┬─────┘        └──────────────┘
                   │
                   ▼
             ┌───────────┐
             │  Action   │
             │  Executor │
             │ (BD + CRM)│
             └───────────┘
```

## Tecnologías

Stack definitivo — validado con Be Expand en reunión del 11/05/2026.

| Capa | Tecnología | Detalle |
|------|-----------|---------|
| Backend | **Python 3.12+** | FastAPI, SQLAlchemy 2.0 (async), Alembic |
| Base de Datos | **PostgreSQL 16** | SQLite (dev), asyncpg (prod) |
| Frontend | **React 19 + TypeScript** | Vite 8 (Rolldown), Recharts, React Router 7 |
| Email Processing | **IMAP nativo** (`imaplib`) | Ionos e Imax confirmados |
| CRM | **VTiger REST API** | Cliente HTTP con `httpx` |
| Task Queue | **Celery + Redis** | Polling periódico de buzones |
| Clasificación | **Orquestador multi-agente paralelo** | 3 clasificadores simultáneos + VoteResolver |
| Rule Engine | **Keywords ponderados** | ~1ms, primer clasificador |
| BERT NLP | **DistilBERT multilingual** | ~50ms, reentrenable con datos reales |
| LLM | **Ollama (llama3.2:3b)** | ~1-3s, análisis contextual profundo |
| Contenedores | **Docker + docker-compose** | Entorno reproducible |
| Autenticación | **JWT** | `python-jose` + `passlib` + bcrypt |

> 📄 Documentación detallada del stack y la arquitectura en [`docs/stack-architecture.md`](docs/stack-architecture.md)

## Estructura del Proyecto

```
BeExpand-Fedeto-CRM-Email/
├── backend/
│   ├── src/
│   │   ├── email_processor/    # Conexión IMAP, parseo y filtrado
│   │   ├── classifier/         # Clasificadores individuales (rule, bert, llm)
│   │   ├── orchestrator/       # Orquestador multi-agente paralelo + VoteResolver
│   │   ├── agents/             # Agentes de análisis (Analyzer, Router, ActionExecutor)
│   │   ├── api/                # FastAPI REST (routers: auth, dashboard, emails, etc.)
│   │   ├── db/                 # Modelos SQLAlchemy + sesión asíncrona
│   │   ├── crm_integration/    # Integración con VTiger REST API
│   │   ├── tasks/              # Tareas Celery (sync_emails, etc.)
│   │   ├── training/           # Reentrenamiento del clasificador BERT
│   │   ├── integrations/       # Integraciones auxiliares
│   │   ├── utils/              # Utilidades compartidas
│   │   ├── config.py           # Configuración centralizada (pydantic-settings)
│   │   └── celery_app.py       # Aplicación Celery + beat schedule
│   ├── scripts/                # Scripts de utilidad
│   │   ├── simulate_data.py    # Genera 30 días de datos de prueba
│   │   ├── train_bert_hybrid.py# Reentrenar clasificador BERT
│   │   └── test_classifier.py  # Test del pipeline de clasificación
│   ├── tests/                  # ~113 tests (pytest-asyncio)
│   ├── alembic/                # Migraciones de base de datos
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/              # Dashboard, Contacts, EmailDetail, Opportunities, Login
│   │   ├── components/         # Componentes reutilizables (UI)
│   │   ├── contexts/           # AuthContext (login, token, sesión)
│   │   ├── lib/                # Utilidades (formatNumbers, etc.)
│   │   └── services/           # api.ts — cliente HTTP con JWT
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── infrastructure/
│   ├── docker/
│   │   ├── docker-compose.yml       # Postgres, Redis, Backend, Frontend, Celery
│   │   ├── docker-compose.vtiger.yml# VTiger CRM opcional (perfil vtiger)
│   │   ├── docker-start.bat         # Script arranque rápido
│   │   ├── docker-stop.bat          # Script parada
│   │   ├── nginx/frontend.conf      # Proxy inverso para SPA
│   │   └── postgres/init.sql        # Extensiones PostgreSQL
│   └── database/
│       └── seeds/                   # Datos de ejemplo
├── docs/
│   ├── stack-architecture.md
│   ├── data-model.md
│   ├── requirements.md
│   ├── planning-30-60-90.md
│   ├── SESION_2026-05-11.md
│   ├── SESION_2026-05-12.md
│   └── diagramas_*.png
├── AGENTS.md                   # Guía de contexto para asistentes AI
├── .gitignore
└── README.md
```

## Instalación y Configuración

### Requisitos

- **Docker** (Rancher Desktop o Docker Desktop)
- **Ollama** (opcional, para clasificación con IA local) — `ollama pull llama3.2:3b`
- **Git**

### Arranque rápido con Docker

```bash
# Clonar el repositorio
git clone https://github.com/AlexSV97/BeExpand-Fedeto-CRM-Email.git
cd BeExpand-Fedeto-CRM-Email

# Opción 1: Script de arranque (Windows)
.\infrastructure\docker\docker-start.bat

# Opción 2: Directo con docker compose
docker compose -f infrastructure/docker/docker-compose.yml up -d

# Reconstruir imágenes tras cambios
docker compose -f infrastructure/docker/docker-compose.yml build

# Parar
docker compose -f infrastructure/docker/docker-compose.yml down
```

Una vez arrancado, los servicios están disponibles en:

| Servicio | URL |
|----------|-----|
| Frontend (Dashboard) | http://localhost:5173 |
| Backend (API) | http://localhost:8000 |
| Documentación API (Swagger) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

**Credenciales por defecto:** `admin` / `admin123`

### Desarrollo local (sin Docker)

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend (en otra terminal)
cd frontend
npm install
npm run dev
```

## Uso

1. Abre http://localhost:5173 en el navegador
2. Inicia sesión con `admin` / `admin123`
3. El dashboard muestra el resumen de correos procesados, contactos y oportunidades
4. El sistema sincroniza correos automáticamente cada 60 segundos (auto-sync integrado en FastAPI, no requiere Celery en producción)
5. Opcional: en el Panel de Control del Dashboard, selecciona auto-refresh (10s, 30s, 60s) para ver los nuevos correos sin recargar

### Páginas del dashboard

| Página | Ruta | Descripción |
|--------|------|-------------|
| Dashboard | `/dashboard` | Resumen general, gráficos de volumen, forecast, confianza |
| Contactos | `/contacts` | Listado y filtrado de contactos clasificados |
| Oportunidades | `/opportunities` | Pipeline de oportunidades por etapa |
| Ajustes | `/settings` | Configuración IMAP, notificaciones Telegram, cambio de contraseña, estado del sistema |
| Detalle Email | `/emails/:id` | Clasificaciones individuales y resolución del voto |

## Comandos útiles

```bash
# ── Backend ──

# Arrancar API en desarrollo (puerto 8001 para no chocar con Docker)
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload

# Ejecutar tests
pytest -v

# Tests de un módulo específico
pytest tests/test_orchestrator.py -v

# Generar datos simulados (30 días de emails + contactos)
python scripts/simulate_data.py

# Reentrenar clasificador BERT con datos reales
python scripts/train_bert_hybrid.py

# Probar el pipeline de clasificación completo
python scripts/test_classifier.py --verbose

# ── Frontend ──

# Arrancar en desarrollo
npm run dev

# Build de producción
npm run build

# ── Docker ──

# Arrancar todo el stack
.\infrastructure\docker\docker-start.bat

# Arrancar incluyendo VTiger CRM
.\infrastructure\docker\docker-start.bat --vtiger

# Ver logs en tiempo real
docker compose -f infrastructure/docker/docker-compose.yml logs -f

# Reconstruir imágenes tras cambios
docker compose -f infrastructure/docker/docker-compose.yml build

# Parar servicios
docker compose -f infrastructure/docker/docker-compose.yml down

# ── Base de Datos ──

# Migraciones Alembic (cuando sea necesario)
cd backend
alembic revision --autogenerate -m "descripcion"
alembic upgrade head
```

## Contribución

Para contribuir al proyecto:

1. Haz un fork del repositorio
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Realiza tus cambios y haz commit (`git commit -m 'Añadir nueva funcionalidad'`)
4. Sube tus cambios (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## Licencia

Este proyecto está desarrollado para **Be Expand**.
