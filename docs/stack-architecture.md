# Stack Tecnológico y Arquitectura del Sistema

> Documento definitivo — Actualizado tras reunión con Aiuken (11/05/2026)
> Reemplaza las especulaciones iniciales con decisiones confirmadas.

---

## 1. Decisiones Confirmadas con el Cliente

| Aspecto | Decisión | Impacto técnico |
|---------|----------|-----------------|
| **CRM** | VTiger | Integración vía REST API. Autenticación con token. |
| **Email** | Ionos e Imax | Conexión IMAP estándar en ambos. Sin dependencia de Graph API. |
| **Clasificación** | Contextual (Cliente/Lead/Proveedor) | Enfoque híbrido: Keywords primero, NLP en el futuro. |
| **Stack** | Validado por Aiuken | Sin restricciones técnicas que cambien la propuesta. |

---

## 2. Stack Tecnológico Definitivo

### 2.1 Backend — Python + FastAPI

| Componente | Tecnología | Versión | Justificación |
|------------|-----------|---------|---------------|
| Lenguaje | Python | 3.12+ | Ecosistema NLP (spaCy, NLTK), tipado moderno, madurez. |
| Framework API | FastAPI | 0.115+ | Async nativo, validación Pydantic, OpenAPI automático. |
| ASGI Server | Uvicorn | — | Servidor ASGI estándar para FastAPI. |
| ORM | SQLAlchemy 2.0 + Alembic | — | ORM maduro, async support, migrations. |
| DB Driver | asyncpg | — | Driver PostgreSQL async nativo. |
| Email (IMAP) | `imaplib` + `email` (stdlib) | — | Sin dependencias externas. Ionos e Imax usan IMAP estándar. |
| HTTP Client | httpx | — | Cliente HTTP async para VTiger API. |
| Task Queue | Celery + Redis | — | Polling periódico de buzones sin bloquear API. |
| Clasificación (hoy) | RuleEngine propio | — | Keywords + patrones + cruce con datos VTiger. |
| Clasificación (futuro) | spaCy | 3.x | Modelo de clasificación entrenado con datos reales. |
| Auth | python-jose + passlib | — | JWT simple. Sistema interno — no necesita OAuth2 complejo. |

### 2.2 Base de Datos — PostgreSQL

| Aspecto | Decisión | Motivo |
|---------|----------|--------|
| Motor | PostgreSQL 16 | Datos relacionales (contactos, correos, oportunidades). |
| Full-Text Search | tsvector + tsquery | Búsqueda sobre contenido de emails sin Elasticsearch. |
| Datos flexibles | JSONB | Metadatos de email y VTiger sin esquema rígido. |
| Migraciones | Alembic | Control de versiones del esquema. |

### 2.3 Frontend — React + TypeScript

| Componente | Tecnología | Justificación |
|------------|-----------|---------------|
| Framework | React 19 + TypeScript | Tipado fuerte, ecosistema maduro. |
| Build tool | Vite | Dev server rápido, builds optimizados. |
| Routing | React Router v7 | Estándar de facto. |
| Charts | Recharts | Dashboard con gráficos simples y declarativos. |
| UI | CSS Modules + variables CSS | Sin dependencia de librerías UI pesadas. |

### 2.4 Infraestructura

| Componente | Tecnología | Uso |
|------------|-----------|-----|
| Contenedores | Docker + docker-compose | Entorno reproducible local y producción. |
| Proxy | Nginx (en contenedor) | Reverse proxy para FastAPI + frontend estático. |
| Cache/Queue | Redis | Backend de Celery + caché de consultas frecuentes. |
| Entorno dev | Docker Compose | Postgres + Redis + API + Worker en un comando. |

---

## 3. Arquitectura del Sistema

### 3.1 Diagrama de Componentes (C4 - Nivel 1)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PERIODIC TASK                                 │
│                 (Celery Beat → cada N minutos)                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      EMAIL PROCESSOR                                  │
│                                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────────────┐      │
│  │ IMAPConnector │───▶│   Parser     │───▶│    EmailFilter    │      │
│  │ (Ionos/Imax)  │    │ (subject,    │    │ (spam, auto-reply,│      │
│  │   imaplib     │    │  body, from,  │    │  mailing lists)   │      │
│  └──────────────┘    │  attachments) │    └────────────────────┘      │
│                      └──────────────┘                                │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       CLASSIFIER (Core)                                │
│                                                                       │
│  Email → FeatureExtractor → ClassifierStrategy (Strategy Pattern)     │
│                                      │                                │
│                         ┌────────────┴────────────┐                   │
│                         ▼                         ▼                   │
│              ┌────────────────────┐   ┌────────────────────┐          │
│              │   RuleEngine       │   │   MLClassifier     │          │
│              │   (keywords+hoy)   │   │   (spaCy, futuro)  │          │
│              │                    │   │                    │          │
│              │   ✅ Confianza≥90% │   │   ⏳ En desarrollo  │          │
│              │   → clasifica      │   │                    │          │
│              │   → envía a CRM    │   │                    │          │
│              │                    │   │                    │          │
│              │   ❌ Confianza<90% │   │   → marca para     │          │
│              │   → pendiente      │   │     revisión       │          │
│              └────────────────────┘   └────────────────────┘          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       CRM INTEGRATION                                  │
│                                                                       │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐      │
│  │  ContactSync   │  │ InteractionLog │  │ OpportunityTracker │      │
│  │  (VTiger REST) │  │  (vtiger_client)│  │  (vtiger_client)  │      │
│  └────────────────┘  └────────────────┘  └────────────────────┘      │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DATABASE (PostgreSQL)                          │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │   contacts   │  │    emails    │  │opportunities  │                 │
│  │  +crm_id     │  │  +fts_index  │  │  +pipeline    │                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        REST API (FastAPI)                              │
│                                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Contacts │  │  Emails  │  │Pipeline  │  │   Auth   │              │
│  │ /api/v1/ │  │ /api/v1/ │  │ /api/v1/ │  │ /api/v1/ │              │
│  │ contacts │  │  emails  │  │pipeline  │  │   auth   │              │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FRONTEND (React + TypeScript)                       │
│                                                                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
│  │    Dashboard     │  │    Contacts      │  │    Pipeline      │    │
│  │  (resumen diario │  │  (lista+filtros) │  │  (oportunidades  │    │
│  │   semanal)       │  │  búsqueda)       │  │   seguimiento)   │    │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Flujo de Clasificación Híbrido (detalle)

```
Email procesado y filtrado
         │
         ▼
┌─────────────────────────────┐
│ 1. FeatureExtractor          │
│                              │
│    a) ¿Remitente existe en   │
│       VTiger como contacto?   │──Sí──▶ Hereda categoría del CRM
│       └─ No, seguir          │
│                              │
│    b) Extraer features:      │
│       - Asunto (tokens)      │
│       - Cuerpo (primeras     │
│         200 palabras)        │
│       - Adjuntos (nombres,   │
│         extensiones)         │
│       - Dirección from/domain│
│       - Frecuencia del       │
│         remitente            │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 2. RuleEngine                │
│                              │
│    Keywords por categoría:   │
│                              │
│    CLIENTE:                  │
│    - "pedido" "factura"      │
│    - "soporte" "incidencia"  │
│    - "renovación" "contrato" │
│    - "baja" "cancelación"    │
│    - URLs de tracking        │
│                              │
│    LEAD:                     │
│    - "presupuesto"           │
│    - "información"           │
│    - "cotización"            │
│    - "quiero contratar"      │
│    - "me interesa"           │
│    - "demo" "prueba"         │
│                              │
│    PROVEEDOR:                │
│    - "albarán"               │
│    - "proveedor"             │
│    - "suministro"            │
│    - "factura proveedor"     │
│    - "nuestros servicios"    │
│    - "condiciones pago"      │
│                              │
│    Reglas adicionales:       │
│    - Si remitente repetido   │
│      (>5 emails) → pesa a    │
│      cliente                 │
│    - Si dominio =            │
│      proveedor conocido      │
│      → pesa a proveedor      │
│    - Si "presupuesto" +      │
│      "gracias" → pesa a lead │
│                              │
│    Cálculo de confianza:     │
│    Score = Σ(keywords p/peso)│
│    Si score ≥ threshold:     │
│       ✅ Clasificación directa│
│    Si score < threshold:     │
│       ❌ Marcar pendiente     │
└─────────────────────────────┘
```

### 3.3 Estrategia de Clasificación (Strategy Pattern)

```python
from abc import ABC, abstractmethod

class ClassifierStrategy(ABC):
    """Interfaz para estrategias de clasificación."""
    
    @abstractmethod
    def classify(self, email: ProcessedEmail) -> ClassificationResult:
        ...

class RuleEngine(ClassifierStrategy):
    """Clasificación basada en keywords y reglas."""
    ...

class MLClassifier(ClassifierStrategy):
    """Clasificación basada en modelo NLP (futuro)."""
    ...

class HybridClassifier(ClassifierStrategy):
    """Orquestador: RuleEngine + fallback a MLClassifier."""
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.ml_classifier = MLClassifier()
    
    def classify(self, email):
        result = self.rule_engine.classify(email)
        if result.confidence >= 0.9:
            return result
        # Si no, delegar a ML o marcar pendiente
        ...
```

---

## 4. Decisiones Arquitectónicas Clave (ADR)

### ADR-001: Clasificación Híbrida

**Contexto:** Aiuken clasifica correos manualmente leyendo el contexto. No hay datos etiquetados para entrenar un modelo.

**Decisión:** Implementar RuleEngine por keywords como capa primaria. Cuando se acumulen suficientes correos clasificados (>500), añadir MLClassifier con spaCy como capa secundaria.

**Consecuencias:**
- Rápida de implementar (días vs semanas)
- El cliente entiende y puede ajustar las reglas
- Los correos dudosos se marcan para revisión y alimentan el dataset futuro

### ADR-002: IMAP nativo vs Graph API

**Contexto:** Las plataformas confirmadas son Ionos e Imax, ambas con soporte IMAP.

**Decisión:** Usar `imaplib` de la stdlib de Python. Sin dependencias externas.

**Consecuencias:** Migrar a Graph API solo si el cliente añade Microsoft 365 en el futuro.

### ADR-003: PostgreSQL como única BD

**Contexto:** Datos mixtos: relacionales (contactos, oportunidades) y semiestructurados (metadatos de email, payload de VTiger).

**Decisión:** PostgreSQL con JSONB para metadatos y tsvector para búsqueda de texto completo. Evita tener dos motores de BD.

**Consecuencias:** Una sola tecnología de datos que gestionar. Las consultas FTS cubren el caso de uso sin Elasticsearch.

### ADR-004: Celery + Redis para tareas periódicas

**Contexto:** El sistema debe revisar buzones periódicamente sin bloquear el API.

**Decisión:** Celery Beat programa tareas. Redis como broker y backend de resultados.

**Consecuencias:** Escalable horizontalmente (múltiples workers). Redis también sirve para caché de API.

---

## 5. Estructura del Proyecto (Refinada)

```
backend/
├── src/
│   ├── email_processor/
│   │   ├── __init__.py
│   │   ├── imap_connector.py      # Conexión IMAP Ionos/Imax
│   │   ├── parser.py               # Parseo de email
│   │   └── filter.py               # Filtrado de irrelevantes
│   ├── classifier/
│   │   ├── __init__.py
│   │   ├── strategy.py             # Interfaz abstracta ClassifierStrategy
│   │   ├── feature_extractor.py    # Extracción de features del email
│   │   ├── rule_engine.py          # RuleEngine con keywords
│   │   ├── ml_classifier.py        # MLClassifier con spaCy (futuro)
│   │   └── models.py               # Category enum + ClassificationResult
│   ├── crm_integration/
│   │   ├── __init__.py
│   │   ├── vtiger_client.py        # Cliente API REST VTiger
│   │   ├── contact_sync.py         # Sincronización contactos
│   │   └── opportunity_logger.py   # Registro oportunidades
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI entrypoint
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── contacts.py
│   │   │   ├── emails.py
│   │   │   ├── pipeline.py
│   │   │   └── auth.py
│   │   └── schemas.py              # Pydantic models
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py               # SQLAlchemy models
│   │   └── session.py              # DB session management
│   └── tasks/
│       ├── __init__.py
│       └── email_poller.py         # Celery tarea periódica
├── tests/
│   ├── __init__.py
│   ├── test_email_processor/
│   ├── test_classifier/
│   └── test_crm_integration/
├── alembic/
│   └── versions/
├── alembic.ini
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
└── docker-compose.yml

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Contacts.tsx
│   │   └── Pipeline.tsx
│   ├── services/
│   │   └── api.ts
│   └── utils/
├── public/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── Dockerfile
└── .dockerignore

infrastructure/
├── docker/
│   ├── nginx/
│   │   └── default.conf
│   └── postgres/
│       └── init.sql
└── database/
    └── seeds/
        └── sample_data.sql
```

---

## 6. Issues Relacionadas

| Issue | Estado |
|-------|--------|
| #1 — Stack tecnológico definitivo | ✅ **COMPLETED** |
| #2 — Arquitectura del sistema | ✅ **COMPLETED** |
| #3 — Modelo de datos (ERD) | 🔄 **IN PROGRESS** |
| #4 — Wireframes del dashboard | ⏳ PENDING |
| #5 — Setup entorno de desarrollo | ⏳ PENDING |

---

*Documento generado el 12/05/2026. Próxima revisión: al completar M1.*
