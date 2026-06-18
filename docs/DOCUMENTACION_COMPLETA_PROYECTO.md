# Documentación Completa del Proyecto — Aiuken SOC

> **Proyecto**: Aiuken SOC
> **Cliente**: Aiuken
> **Última actualización**: 15/05/2026
> **Estado actual**: M1-M4 ✅ Completados | M5 🟡 En progreso

---

## Índice

1. [Descripción General](#1-descripción-general)
2. [Problema y Solución](#2-problema-y-solución)
3. [Arquitectura del Sistema](#3-arquitectura-del-sistema)
4. [Stack Tecnológico](#4-stack-tecnológico)
5. [Modelo de Datos](#5-modelo-de-datos)
6. [Pipeline de Clasificación Híbrida](#6-pipeline-de-clasificación-híbrida)
7. [Estructura del Proyecto](#7-estructura-del-proyecto)
8. [Frontend](#8-frontend)
9. [Planificación 30-60-90](#9-planificación-30-60-90)
10. [Estimación Económica](#10-estimación-económica)
11. [Issues y Milestones](#11-issues-y-milestones)
12. [Sesiones de Trabajo](#12-sesiones-de-trabajo)
13. [Pendiente Actual (M5)](#13-pendiente-actual-m5)

---

## 1. Descripción General

Sistema diseñado para **Aiuken** que permite centralizar, estructurar y procesar automáticamente la información proveniente del correo electrónico empresarial. Clasifica contactos (clientes, leads, proveedores, etc.), determina el estado de las interacciones y se integra con el CRM (VTiger) para proporcionar una visión operativa clara de la actividad comercial.

---

## 2. Problema y Solución

### Problemas Identificados

| Problema | Impacto |
|----------|---------|
| Alto volumen de correos en múltiples bandejas | Información dispersa |
| Sin sistema estructurado de gestión | Pérdida de oportunidades |
| Análisis manual costoso y propenso a errores | Baja eficiencia operativa |
| Baja integración con CRM actual | Dificultad en toma de decisiones |

### Solución Propuesta

1. **Centralizar** correos a través de una cuenta intermedia
2. **Clasificar automáticamente** contactos (cliente, lead, proveedor, otro)
3. **Determinar estado** de interacciones y relevancia de oportunidades
4. **Integrar con CRM** (VTiger REST API) para actualización automatizada
5. **Generar dashboards** para seguimiento comercial

### Objetivos del Sistema

| Objetivo | Descripción |
|----------|-------------|
| Centralización | Unificar bandejas en un único punto de procesamiento |
| Automatización | Mínima intervención manual en clasificación y registro |
| Trazabilidad | Historial completo de interacciones con cada contacto |
| Eficiencia | Aumentar tasa de conversión de oportunidades |
| Visibilidad | Dashboards operativos para toma de decisiones |

---

## 3. Arquitectura del Sistema

### Diagrama de Alto Nivel

```
                  ┌─────────────────┐
                  │  Buzones Entrada │
                  │ (Ionos / Imax)   │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Cuenta Intermedia│
                  │  (Gmail POC)      │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Motor de        │
                  │  Clasificación   │
                  │  (3 niveles)     │
                  └────────┬────────┘
                           │
               ┌───────────┴───────────┐
               ▼                       ▼
        ┌──────────────┐      ┌──────────────┐
        │     CRM      │      │  Dashboards  │
        │  (VTiger)    │      │  (React)     │
        └──────────────┘      └──────────────┘
```

### Flujo de Clasificación Híbrido (3 niveles)

```
Email procesado y filtrado
         │
         ▼
┌─────────────────────────────┐
│ Nivel 1: RuleEngine          │
│ Keywords ponderadas (peso 1-4)│
│                              │
│ ✅ Confianza ≥ 0.80         │
│    → Clasificación directa   │
│                              │
│ ❌ Confianza < 0.80         │
│    → Pasa a Nivel 2          │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Nivel 2: DistilBERT          │
│ (Fine-tune, 316 muestras)    │
│                              │
│ ✅ Confianza ≥ 0.80         │
│    → Clasificación           │
│                              │
│ ❌ Confianza < 0.80         │
│    → Pasa a Nivel 3          │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Nivel 3: Ollama (llama3.2)  │
│ Prompt estructurado JSON    │
│                              │
│ → Clasificación final        │
│   para casos ambiguos        │
└─────────────────────────────┘
```

### Decisiones Arquitectónicas Clave (ADR)

| ADR | Decisión | Impacto |
|-----|----------|---------|
| ADR-001 | Clasificación híbrida (RuleEngine → BERT → Ollama) | Strategy Pattern. Sin datos etiquetados iniciales. |
| ADR-002 | IMAP nativo (`imaplib`) vs Graph API | Sin dependencias externas para Ionos/Imax |
| ADR-003 | PostgreSQL única BD (JSONB + tsvector) | Evita dos motores de BD |
| ADR-004 | Celery + Redis para tareas periódicas | Escalable horizontalmente |

---

## 4. Stack Tecnológico

### Backend

| Componente | Tecnología | Versión |
|------------|-----------|---------|
| Lenguaje | Python | 3.12+ |
| Framework API | FastAPI | 0.115+ |
| ASGI Server | Uvicorn | — |
| ORM | SQLAlchemy 2.0 + Alembic | — |
| DB (desarrollo) | SQLite (aiosqlite) | — |
| DB (producción) | PostgreSQL 16 | — |
| Email IMAP | `imaplib` + `email` (stdlib) | — |
| HTTP Client | httpx | — |
| Task Queue | Celery + Redis | — |
| Clasificación N1 | RuleEngine (keywords) | Peso 1-4 por keyword |
| Clasificación N2 | DistilBERT (multilingual cased) | Fine-tune propio |
| Clasificación N3 | Ollama + llama3.2:3b | Local, ~2GB |
| Auth | python-jose + passlib | JWT |

### Frontend

| Componente | Tecnología | Versión |
|------------|-----------|---------|
| Framework | React | 19 |
| Lenguaje | TypeScript | 6 |
| Build tool | Vite | 8 |
| Bundler | Rolldown | — |
| Routing | React Router | — |
| Charts | Recharts | — |
| Estilos | Tailwind CSS | 4 |
| Estado | useState + context | — |

### Infraestructura

| Componente | Tecnología |
|------------|-----------|
| Contenedores | Docker + docker-compose |
| Proxy | Nginx (en contenedor) |
| Cache/Queue | Redis |
| OS | Windows 11 (dev) |

---

## 5. Modelo de Datos

### Entidades

| Entidad | Descripción | FK |
|---------|-------------|-----|
| `accounts` | Configuración de buzones IMAP | — |
| `emails` | Correos procesados (núcleo del sistema) | account_id → accounts |
| `contacts` | Contactos sincronizados con VTiger | — |
| `email_contacts` | Relación N:M emails ↔ contactos | email_id, contact_id |
| `classification_history` | Traza de decisiones de clasificación | email_id → emails |
| `opportunities` | Oportunidades de negocio | email_id, contact_id |
| `users` | Usuarios del sistema | — |

### Reglas de Negocio Clave

- **Clasificación por defecto**: `pendiente`
- **Confianza mínima para automática**: ≥ 80%
- **Deduplicación de emails**: Unique constraint (message_id, account_id)
- **Ciclo de vida contacto**: Si >5 interacciones como lead → sugerir cambio a cliente
- **Creación de oportunidades**: `category=lead` AND keywords de compra AND confianza ≥ 85%
- **Full-Text Search**: tsvector con pesos (A: asunto, B: cuerpo) en español

---

## 6. Pipeline de Clasificación Híbrida

### Nivel 1 — RuleEngine Ponderado

- Keywords con peso individual (1-4)
- Desempate por prioridad de categoría: proveedor > lead > cliente
- Resuelve 9/9 casos en test sintético

**Keywords por categoría:**

| Categoría | Keywords clave |
|-----------|---------------|
| **Cliente** | pedido, factura, soporte, incidencia, renovación, contrato, baja, cancelación |
| **Lead** | presupuesto, información, cotización, quiero contratar, me interesa, demo, prueba |
| **Proveedor** | albarán, proveedor, suministro, factura proveedor, nuestros servicios, condiciones pago |

### Nivel 2 — DistilBERT

- Fine-tuneado con datos reales + aumentados + sintéticos (316 muestras)
- Calibrado: 88-95% en aciertos, 47-49% en dudosos
- Threshold de decisión: 0.80
- CPU, ~50ms/inferencia

### Nivel 3 — Ollama (llama3.2:3b)

- Tercera capa para casos ambiguos
- Prompt estructurado con JSON response
- Fiabilidad general del sistema: **92%** (12/13 escenarios sintéticos)
- IMAP sync probado: 10 correos reales clasificados sin errores

---

## 7. Estructura del Proyecto

```
Aiuken SOC/
├── backend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── main.py              # FastAPI entrypoint
│   │   │   ├── deps.py              # Dependencias (auth, DB)
│   │   │   ├── routers/             # Routes: auth, contacts, emails, dashboard...
│   │   │   └── schemas/             # Pydantic models
│   │   ├── classifier/
│   │   │   └── bert_classifier.py   # Clasificador BERT
│   │   ├── email_processor/
│   │   │   ├── fetcher.py           # Conexión IMAP + parseo + clasificación
│   │   │   └── summarizer.py        # Generación de resúmenes con Ollama
│   │   ├── db/
│   │   │   ├── models.py            # SQLAlchemy models
│   │   │   └── session.py           # DB session management
│   │   ├── crm_integration/         # VTiger (pendiente implementación)
│   │   ├── config.py                # Configuración
│   │   └── utils/                   # Utilidades
│   ├── scripts/
│   │   ├── test_classifier.py       # Test del clasificador
│   │   ├── train_bert_classifier.py # Entrenamiento BERT
│   │   └── train_bert_hybrid.py     # Entrenamiento híbrido
│   ├── tests/
│   │   ├── test_api/                # Tests de endpoints
│   │   │   ├── test_accounts.py
│   │   │   ├── test_auth.py
│   │   │   ├── test_classification.py
│   │   │   ├── test_contacts.py
│   │   │   ├── test_dashboard.py
│   │   │   ├── test_emails.py
│   │   │   └── test_opportunities.py
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_routers_pr2.py
│   │   └── test_schemas.py
│   ├── alembic/
│   │   └── versions/
│   │       └── 6cf8e53ba70a_create_initial_models.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx        # KPIs + feed + distribución
│   │   │   ├── Contacts.tsx         # Lista + filtros + detalle
│   │   │   ├── Opportunities.tsx    # Pipeline oportunidades
│   │   │   └── Login.tsx            # Autenticación
│   │   ├── components/
│   │   │   └── Layout.tsx           # Sidebar + header + breadcrumb
│   │   ├── services/                # API client
│   │   ├── contexts/                # Auth context
│   │   ├── lib/                     # Utilidades
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── infrastructure/
│   └── docker/
│       ├── nginx/                   # Reverse proxy
│       └── postgres/                # Init scripts
├── docs/
│   ├── DOCUMENTACION_COMPLETA_PROYECTO.md  ← Este documento
│   ├── SESION_2026-05-11.md               # Sesión 1
│   ├── SESION_2026-05-12.md               # Sesión 2
│   ├── sesion-2026-05-13.md               # Sesión 3
│   ├── sesion-2026-05-14.md               # Sesión 4
│   ├── stack-architecture.md              # Stack y arquitectura
│   ├── data-model.md                      # Modelo de datos
│   ├── requirements.md                    # Requisitos funcionales
│   ├── planning-30-60-90.md               # Planificación temporal
│   ├── estimacion-economica.md            # Estimación económica
│   ├── wireframes.md                      # Especificaciones UI
│   ├── wireframe-dashboard.svg
│   ├── wireframe-contacts.svg
│   ├── wireframe-pipeline.svg
│   ├── diagrama_arquitectura.png
│   ├── diagrama_flujo.png
│   ├── diagrama_modelodatos.png
│   ├── diagrama_motor.png
│   └── diagrama_completo.png
├── README.md
└── .gitignore
```

---

## 8. Frontend

### Pantallas Implementadas

| Pantalla | Ruta | Descripción |
|----------|------|-------------|
| **Login** | `/login` | Autenticación JWT |
| **Dashboard** | `/dashboard` | 4 KPI cards, feed últimos 10 emails clasificados con resumen expandible, donut de distribución, botón sync IMAP |
| **Contactos** | `/contacts` | Lista con filtros, búsqueda, detalle de contacto |
| **Pipeline** | `/opportunities` | Kanban de oportunidades, proyección mensual |

### Layout

- Sidebar con SVG icons (Dashboard, Contactos, Oportunidades, Logout)
- Header con breadcrumb y avatar de usuario
- Diseño responsive con Tailwind CSS 4

### Design Tokens

| Token | Valor | Uso |
|-------|-------|-----|
| Primary | `#2563EB` (blue-600) | Botones, enlaces |
| Success | `#16A34A` (green-600) | Cerrado, completado |
| Warning | `#D97706` (amber-600) | Pendiente |
| Danger | `#DC2626` (red-600) | Escalado, urgente |

---

## 9. Planificación 30-60-90

### Primeras 30h — M1+M2 (Fundamentos) ✅ COMPLETADO

| # | Tarea | Horas | Estado |
|---|-------|:-----:|:------:|
| 1 | Stack tecnológico definitivo | 3h | ✅ |
| 2 | Arquitectura del sistema | 4h | ✅ |
| 3 | Modelo de datos (ERD) | 3h | ✅ |
| 4 | Wireframes del dashboard | 3h | ✅ |
| 5 | Setup entorno de desarrollo | 2h | ✅ |
| 6 | Conexión IMAP | 6h | ✅ |
| 7 | Parseo y extracción | 6h | ✅ |
| 8 | Filtrado de correos | 3h | ✅ |

### 30h→60h — M3 (Núcleo e Integración) ✅ COMPLETADO

| # | Tarea | Horas | Estado |
|---|-------|:-----:|:------:|
| 9 | Tests de ingesta | 4h | ✅ |
| 10 | Motor de clasificación | 6h | ✅ |
| 11 | Estado y relevancia | 6h | ✅ |
| 12 | Integración CRM (CRUD) | 7h | ✅ |
| 13 | Registro interacciones | 3h | ✅ |
| 14 | Tests clasificación | 3h | ✅ |

### 60h→90h — M4+M5 (Frontend y Cierre) 🟡 PARCIAL

| # | Tarea | Horas | Estado |
|---|-------|:-----:|:------:|
| 15 | API REST endpoints | 5h | ✅ |
| 16 | Dashboard principal | 5h | ✅ |
| 17 | Vista contactos | 4h | ✅ |
| 18 | Pipeline oportunidades | 3h | ✅ |
| 19 | Autenticación | 3h | ✅ |
| **20** | **Pruebas integración** | **3h** | 🟡 |
| **21** | **Pruebas carga/rendimiento** | **2h** | 🟡 |
| **22** | **Documentación** | **3h** | 🟡 |
| **23** | **Docker producción** | **2h** | 🟡 |
| **24** | **Despliegue y ajustes** | **2h** | 🟡 |

---

## 10. Estimación Económica

### Proyecto 90h — Sistema Completo (Package Cerrado)

| Concepto | Importe |
|----------|:-------:|
| Desarrollo (85h efectivas + gestión) | 5.885€ |
| Contingencia (15%) | 770€ |
| **Base imponible** | **6.215€** |
| IVA (21%) | 1.305€ |
| **Total factura** | **7.520€** |

### Proyecto Completo con Integración en Empresa

| Concepto | Importe |
|----------|:-------:|
| Desarrollo sistema completo | 5.885€ |
| Implantación (config IMAP real + VTiger + deploy) | 1.210€ |
| Capacitación + documentación usuario | 770€ |
| Soporte post-entrega (1 mes) | 1.100€ |
| **Total factura** | **~11.250€** |

### Perfil Recomendado: Mid-Senior (55€/h)

---

## 11. Issues y Milestones

### Milestones

| Hito | Descripción | Issues | Estado |
|------|-------------|--------|:------:|
| **M1** | Análisis y Diseño | #1-#5 | ✅ COMPLETADO |
| **M2** | Núcleo de Procesamiento (IMAP) | #6-#9 | ✅ COMPLETADO |
| **M3** | Clasificación e Integración CRM | #10-#14 | ✅ COMPLETADO |
| **M4** | Frontend y Dashboards | #15-#19 | ✅ COMPLETADO |
| **M5** | Pruebas y Despliegue | #20-#24 | 🟡 PENDIENTE |

### Issues Abiertas (M5)

| Issue | Tarea | Prioridad |
|:-----:|-------|:---------:|
| #20 | Pruebas de integración de todo el sistema | Media |
| #21 | Pruebas de carga y rendimiento | Baja |
| #22 | Documentación técnica y de usuario | Media |
| #23 | Configurar Docker para producción | Baja |
| #24 | Despliegue y ajustes finales | Media |

---

## 12. Sesiones de Trabajo

### Sesión 1 — 11/05/2026
- Setup del repositorio y documentación inicial
- Creación de diagramas de arquitectura
- Issues y milestones creados (24 issues, 5 milestones)
- README inicial con descripción del proyecto

### Sesión 2 — 12/05/2026
- **Reunión con Aiuken completada**
- Stack definitivo validado: Python/FastAPI/React/PostgreSQL/VTiger
- Arquitectura, modelo de datos y wireframes diseñados
- M1 completado: 5 issues cerradas
- Primeros commits a GitHub

### Sesión 3 — 13/05/2026
- **Tailwind CSS 4** instalado y refactorizado el frontend (~250 líneas de `style={{}}` eliminadas)
- **Conexión IMAP con Gmail** funcional (cuenta de pruebas IMAP)
- 3 correos reales sincronizados, 0 errores
- **Ollama** instalado (pendiente descargar modelo)
- Issues de M4 cerradas (Dashboard, Contactos, Pipeline, Auth)

### Sesión 4 — 14/05/2026
- **Pipeline híbrido completo** (3 niveles): RuleEngine → DistilBERT → Ollama
- RuleEngine ponderado: 9/9 test sintéticos
- DistilBERT fine-tuneado: 316 muestras, 88-95% aciertos
- Ollama/llama3.2: capa final para casos ambiguos
- Fiabilidad general: **92%** (12/13 escenarios)
- IMAP sync: 10 correos reales clasificados sin errores
- **Dashboard rediseñado**: 4 KPI cards, feed, donut, botón sync
- **Layout**: Sidebar con SVG icons, header con breadcrumb

### Sesión 5 — 15/05/2026
- **FASE 1: Resumen de correos en Dashboard** implementada
- Nuevo módulo `summarizer.py` que genera resúmenes con Ollama (prompt estructurado JSON)
- Resumen se genera automáticamente al procesar cada correo (en `fetcher.py`)
- Campo `summary` añadido a tabla `emails` en BD + migración Alembic
- Dashboard: cada correo en el feed tiene botón "Resumen" que despliega panel con el resumen
- Animación fadeIn para el panel expandible
- Documentación completa del proyecto creada en `docs/DOCUMENTACION_COMPLETA_PROYECTO.md`

---

## 13. Pendiente Actual (M5)

### Issues Abiertas para Completar

| Prioridad | Tarea | Descripción |
|:---------:|-------|-------------|
| 🔴 Alta | #20 — Pruebas de integración | Validar flujo completo: IMAP → clasificación → BD → API → frontend |
| 🟡 Media | #22 — Documentación técnica | Manual de administración + documentación de API |
| 🟡 Media | #24 — Despliegue y ajustes | Puesta en producción del sistema |
| 🟢 Baja | #21 — Pruebas de carga | Verificar rendimiento con volumen alto de correos |
| 🟢 Baja | #23 — Docker producción | Configurar Docker Compose para producción con Postgres |

### Deuda Técnica / Mejoras Futuras

- [ ] Re-entrenar BERT con más datos reales (a medida que crezca classification_history)
- [x] Migrar de SQLite a PostgreSQL para producción (Render Postgres)
- [ ] Integración VTiger para sincronizar contactos y oportunidades
- [ ] Tests unitarios formales para el pipeline híbrido (13 escenarios)
- [ ] Dashboard: filtros por fecha, exportar reportes
- [ ] El servidor debe arrancarse con IMAP_EMAIL y IMAP_PASSWORD en environment variables

### Comandos Útiles

```bash
# Arrancar backend
cd backend
$env:IMAP_EMAIL="<IMAP_EMAIL_DE_PRUEBA>"
$env:IMAP_PASSWORD="<IMAP_PASSWORD_DE_PRUEBA>"
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload

# Arrancar frontend
cd frontend
npx vite --port 5173

# Re-entrenar BERT con datos reales
cd backend
python scripts/train_bert_hybrid.py

# Test del clasificador
cd backend
python scripts/test_classifier.py --verbose
python scripts/test_classifier.py --inject-db

# Login de prueba: admin / <ADMIN_PASSWORD_DEMO>
```

### Servicios

| Servicio | URL |
|----------|-----|
| Backend (API) | http://localhost:8001 |
| Frontend (Dashboard) | http://localhost:5173 |
| Ollama | http://127.0.0.1:11434 |

---

*Documento generado el 15/05/2026. Se actualizará conforme avance el proyecto.*
