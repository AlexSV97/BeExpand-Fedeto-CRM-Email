# Modelo de Datos — Aiuken SOC

> Diseñado para PostgreSQL 16 con soporte JSONB y Full-Text Search (tsvector).
> Última actualización: 12/05/2026

---

## 1. Diagrama Entidad-Relación

```
┌─────────────┐       ┌─────────────────┐       ┌──────────────┐
│   accounts  │       │ classification_  │       │   contacts   │
│             │       │    history       │       │              │
│ id (PK)     │       │                  │       │ id (PK)      │
│ name        │       │ id (PK)          │       │ crm_id       │
│ email_host  │──┐    │ email_id (FK)    │──┐    │ name         │
│ email_port  │  │    │ category         │  │    │ email        │
│ email_user  │  │    │ confidence       │  │    │ company      │
│ email_pass  │  │    │ method           │  │    │ position     │
│ provider    │  │    │ reviewed         │  │    │ category     │
│ active      │  │    │ reviewed_by      │  │    │ phone        │
│ created_at  │  │    │ created_at       │  │    │ source       │
└─────────────┘  │    └─────────────────┘  │    │ metadata (JB)│
                 │                         │    │ created_at   │
                 │                         │    │ updated_at   │
                 │    ┌─────────────────┐   │    └──────┬───────┘
                 │    │     emails      │   │           │
                 │    │                 │   │           │
                 └────┤ id (PK)         │   │           │
                      │ account_id (FK) │───┘           │
                      │ message_id      │               │
                      │ subject         │               │
                      │ body_plain      │               │
                      │ body_html       │               │
                      │ sender_email    │               │
                      │ sender_name     │               │
                      │ recipients (JB) │               │
                      │ has_attachments │               │
                      │ attachments (JB)│               │
                      │ received_at     │               │
                      │ processed_at    │               │
                      │ category        │               │
                      │ relevance       │               │
                      │ status          │               │
                      │ fts_vector      │               │
                      │ metadata (JB)   │               │
                      │ created_at      │               │
                      └────────┬───────-┘               │
                               │                        │
                               │  ┌────────────────┐    │
                               │  │ email_contacts  │    │
                               │  │ (N:M join)      │    │
                               │  │ email_id (FK)   │────┤
                               │  │ contact_id (FK) │────┘
                               │  │ role (from/to)  │
                               │  └────────────────┘
                               │
                      ┌────────┴────────┐
                      │  opportunities   │
                      │                  │
                      │ id (PK)          │
                      │ email_id (FK)    │
                      │ contact_id (FK)  │
                      │ title            │
                      │ description      │
                      │ stage            │
                      │ value            │
                      │ probability      │
                      │ expected_close   │
                      │ source           │
                      │ notes            │
                      │ metadata (JB)    │
                      │ created_at       │
                      │ updated_at       │
                      └──────────────────┘
```

---

## 2. Entidades Detalladas

### 2.1 `accounts` — Configuración de Buzones IMAP

Cada buzón que el sistema monitoriza. Be Expand confirmó Ionos e Imax.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | `UUID` PK | Identificador único |
| `name` | `VARCHAR(100)` | Nombre descriptivo (ej. "Ionos Comercial") |
| `email_host` | `VARCHAR(255)` | Servidor IMAP (ej. `imap.ionos.es`) |
| `email_port` | `INTEGER` | Puerto IMAP (993 para SSL) |
| `email_user` | `VARCHAR(255)` | Cuenta de correo |
| `email_pass` | `VARCHAR(500)` | Cifrado (AES-256-GCM en reposo) |
| `provider` | `VARCHAR(50)` | `ionos`, `imax` — para particularidades de cada uno |
| `active` | `BOOLEAN` | `true` → el poller procesa este buzón |
| `last_polled_at` | `TIMESTAMP` | Última vez que se revisó |
| `created_at` | `TIMESTAMP` | |
| `updated_at` | `TIMESTAMP` | |

```sql
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    email_host VARCHAR(255) NOT NULL,
    email_port INTEGER NOT NULL DEFAULT 993,
    email_user VARCHAR(255) NOT NULL,
    email_pass VARCHAR(500) NOT NULL,  -- cifrado
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('ionos', 'imax', 'other')),
    active BOOLEAN NOT NULL DEFAULT true,
    last_polled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### 2.2 `emails` — Correos Procesados

El núcleo del sistema. Cada correo procesado, parseado y clasificado.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | `UUID` PK | |
| `account_id` | `UUID` FK → `accounts.id` | Buzón de origen |
| `message_id` | `VARCHAR(255)` | `Message-ID` header del email (para dedup) |
| `subject` | `TEXT` | Asunto del correo |
| `body_plain` | `TEXT` | Cuerpo en texto plano |
| `body_html` | `TEXT` | Cuerpo en HTML (nullable) |
| `sender_email` | `VARCHAR(255)` | Email del remitente |
| `sender_name` | `VARCHAR(255)` | Nombre del remitente |
| `recipients` | `JSONB` | Array de destinatarios: `[{email, name, type}]` |
| `has_attachments` | `BOOLEAN` | Si contiene adjuntos |
| `attachments` | `JSONB` | Array: `[{filename, size, content_type}]` |
| `received_at` | `TIMESTAMP` | Fecha del header `Date` |
| `processed_at` | `TIMESTAMP` | Cuándo lo procesó el sistema |
| `category` | `VARCHAR(20)` | `cliente`, `lead`, `proveedor`, `otro`, `pendiente` |
| `relevance` | `VARCHAR(10)` | `alta`, `media`, `baja` |
| `status` | `VARCHAR(20)` | `pendiente`, `en_seguimiento`, `cerrado`, `escalado` |
| `fts_vector` | `TSVECTOR` | Índice de búsqueda de texto completo |
| `metadata` | `JSONB` | Metadatos adicionales (cabeceras, etc.) |
| `created_at` | `TIMESTAMP` | |

```sql
CREATE TABLE emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    message_id VARCHAR(255),
    subject TEXT,
    body_plain TEXT,
    body_html TEXT,
    sender_email VARCHAR(255) NOT NULL,
    sender_name VARCHAR(255),
    recipients JSONB DEFAULT '[]',
    has_attachments BOOLEAN DEFAULT false,
    attachments JSONB DEFAULT '[]',
    received_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE,
    category VARCHAR(20) DEFAULT 'pendiente',
    relevance VARCHAR(10) DEFAULT 'media',
    status VARCHAR(20) DEFAULT 'pendiente',
    fts_vector TSVECTOR,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Dedup: no procesar el mismo email dos veces
    CONSTRAINT uq_message_id_account UNIQUE (message_id, account_id)
);

-- Índices
CREATE INDEX idx_emails_sender_email ON emails(sender_email);
CREATE INDEX idx_emails_category ON emails(category);
CREATE INDEX idx_emails_status ON emails(status);
CREATE INDEX idx_emails_received_at ON emails(received_at DESC);
CREATE INDEX idx_emails_fts ON emails USING GIN(fts_vector);
```

### 2.3 `contacts` — Contactos (Sincronizados con VTiger)

Representan personas/empresas que se cruzan con el sistema.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | `UUID` PK | |
| `crm_id` | `VARCHAR(100)` | ID del contacto en VTiger (nullable si no existe aún) |
| `name` | `VARCHAR(255)` | Nombre completo |
| `email` | `VARCHAR(255)` | Email principal (único) |
| `company` | `VARCHAR(255)` | Empresa |
| `position` | `VARCHAR(255)` | Cargo |
| `category` | `VARCHAR(20)` | `cliente`, `lead`, `proveedor`, `otro` |
| `phone` | `VARCHAR(50)` | Teléfono |
| `source` | `VARCHAR(50)` | `email`, `crm`, `manual` |
| `metadata` | `JSONB` | Datos adicionales de VTiger |
| `first_email_at` | `TIMESTAMP` | Primer email recibido de este contacto |
| `last_email_at` | `TIMESTAMP` | Último email recibido |
| `email_count` | `INTEGER` | Total de emails de este contacto |
| `created_at` | `TIMESTAMP` | |
| `updated_at` | `TIMESTAMP` | |

```sql
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crm_id VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    company VARCHAR(255),
    position VARCHAR(255),
    category VARCHAR(20) DEFAULT 'otro',
    phone VARCHAR(50),
    source VARCHAR(50) DEFAULT 'email',
    metadata JSONB DEFAULT '{}',
    first_email_at TIMESTAMP WITH TIME ZONE,
    last_email_at TIMESTAMP WITH TIME ZONE,
    email_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_contacts_email UNIQUE (email),
    CONSTRAINT uq_contacts_crm_id UNIQUE (crm_id)
);

CREATE INDEX idx_contacts_category ON contacts(category);
CREATE INDEX idx_contacts_name ON contacts(name);
```

### 2.4 `email_contacts` — Relación N:M entre Emails y Contactos

Un email puede tener múltiples destinatarios. Un contacto puede aparecer en múltiples emails.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `email_id` | `UUID` FK → `emails.id` | |
| `contact_id` | `UUID` FK → `contacts.id` | |
| `role` | `VARCHAR(10)` | `from` (remitente), `to` (destinatario) |

```sql
CREATE TABLE email_contacts (
    email_id UUID NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL CHECK (role IN ('from', 'to')),
    
    PRIMARY KEY (email_id, contact_id, role)
);

CREATE INDEX idx_email_contacts_contact ON email_contacts(contact_id);
```

### 2.5 `classification_history` — Historial de Clasificaciones

Traza de cada decisión de clasificación. Esencial para auditar y para entrenar el ML en el futuro.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | `UUID` PK | |
| `email_id` | `UUID` FK → `emails.id` | |
| `category` | `VARCHAR(20)` | Categoría asignada |
| `confidence` | `FLOAT` | 0.0 — 1.0 |
| `method` | `VARCHAR(20)` | `rule_engine`, `ml_classifier`, `manual` |
| `details` | `JSONB` | Keywords encontradas, scores, features usadas |
| `reviewed` | `BOOLEAN` | Si fue revisado manualmente |
| `reviewed_by` | `VARCHAR(100)` | Quién lo revisó |
| `reviewed_at` | `TIMESTAMP` | |
| `created_at` | `TIMESTAMP` | |

```sql
CREATE TABLE classification_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id UUID NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    category VARCHAR(20) NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    method VARCHAR(20) NOT NULL CHECK (method IN ('rule_engine', 'ml_classifier', 'manual')),
    details JSONB DEFAULT '{}',
    reviewed BOOLEAN DEFAULT false,
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_classification_email ON classification_history(email_id);
CREATE INDEX idx_classification_method ON classification_history(method);
CREATE INDEX idx_classification_reviewed ON classification_history(reviewed)
    WHERE reviewed = false;
```

### 2.6 `opportunities` — Oportunidades de Negocio

Oportunidades detectadas a partir de correos.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | `UUID` PK | |
| `email_id` | `UUID` FK → `emails.id` | Email origen |
| `contact_id` | `UUID` FK → `contacts.id` | Contacto asociado |
| `title` | `VARCHAR(255)` | Título de la oportunidad |
| `description` | `TEXT` | Descripción |
| `stage` | `VARCHAR(30)` | `nueva`, `calificada`, `propuesta`, `negociacion`, `cerrada_ganada`, `cerrada_perdida` |
| `value` | `DECIMAL(12,2)` | Valor estimado |
| `probability` | `INTEGER` | Probabilidad 0-100 |
| `expected_close` | `DATE` | Fecha estimada de cierre |
| `source` | `VARCHAR(50)` | `email_automatic`, `manual` |
| `crm_id` | `VARCHAR(100)` | ID en VTiger (si se sincroniza) |
| `notes` | `TEXT` | Notas internas |
| `metadata` | `JSONB` | |
| `created_at` | `TIMESTAMP` | |
| `updated_at` | `TIMESTAMP` | |

```sql
CREATE TABLE opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id UUID REFERENCES emails(id),
    contact_id UUID NOT NULL REFERENCES contacts(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    stage VARCHAR(30) NOT NULL DEFAULT 'nueva',
    value DECIMAL(12,2),
    probability INTEGER CHECK (probability >= 0 AND probability <= 100),
    expected_close DATE,
    source VARCHAR(50) DEFAULT 'email_automatic',
    crm_id VARCHAR(100),
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_opportunities_stage ON opportunities(stage);
CREATE INDEX idx_opportunities_contact ON opportunities(contact_id);
CREATE INDEX idx_opportunities_expected_close ON opportunities(expected_close);
```

### 2.7 `users` — Usuarios del Sistema

Usuarios internos que acceden al dashboard.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | `UUID` PK | |
| `username` | `VARCHAR(100)` | Único |
| `email` | `VARCHAR(255)` | |
| `hashed_password` | `VARCHAR(255)` | bcrypt hash |
| `full_name` | `VARCHAR(255)` | |
| `role` | `VARCHAR(20)` | `admin`, `viewer` |
| `active` | `BOOLEAN` | |
| `created_at` | `TIMESTAMP` | |
| `last_login` | `TIMESTAMP` | |

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255),
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(20) NOT NULL DEFAULT 'viewer',
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);
```

---

## 3. Reglas de Negocio en el Modelo

### 3.1 Clasificación por Defecto

- `emails.category` por defecto: `pendiente`
- La clasificación se asigna tras pasar por el RuleEngine
- Si la confianza es < 90%, se queda como `pendiente` hasta revisión manual

### 3.2 Ciclo de Vida de un Contacto

```
1. Llega un email → FeatureExtractor detecta remitente
2. ¿Existe en contacts.email?
   │
   ├── Sí → Se asocia el email al contacto existente
   │        Si era lead y hay >5 interacciones → sugerir cambio a cliente
   │
   └── No → Se crea contacto nuevo con category = pendiente
             Se clasifica por RuleEngine
             Si confianza ≥ 90% → se asigna categoría
             Si confianza < 90% → pendiente de revisión manual
```

### 3.3 Creación de Oportunidades

- Una oportunidad se crea automáticamente cuando un email clasificado como `lead` contiene keywords de compra
- Regla: si `category = lead` AND (contiene "presupuesto" OR "contratar" OR "me interesa") AND confianza ≥ 85% → crear oportunidad en stage `nueva`

### 3.4 Full-Text Search

```sql
-- Trigger para mantener fts_vector actualizado
CREATE OR REPLACE FUNCTION emails_fts_update() RETURNS trigger AS $$
BEGIN
    NEW.fts_vector := 
        setweight(to_tsvector('spanish', COALESCE(NEW.subject, '')), 'A') ||
        setweight(to_tsvector('spanish', COALESCE(NEW.body_plain, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_emails_fts
    BEFORE INSERT OR UPDATE ON emails
    FOR EACH ROW EXECUTE FUNCTION emails_fts_update();
```

```sql
-- Ejemplo de consulta FTS
SELECT e.subject, e.sender_name, e.category
FROM emails e
WHERE e.fts_vector @@ to_tsquery('spanish', 'presupuesto & obras');
```

---

## 4. Migraciones con Alembic

El modelo se implementará vía SQLAlchemy 2.0 + Alembic:

```bash
cd backend
alembic init alembic
alembic revision --autogenerate -m "create initial models"
alembic upgrade head
```

Cada entidad tendrá su modelo en `backend/src/db/models.py` con la sintaxis SQLAlchemy 2.0 MappedAsDataclass.

---

## 5. Issues Relacionadas

| Issue | Estado |
|-------|--------|
| #1 — Stack tecnológico | ✅ COMPLETED |
| #2 — Arquitectura del sistema | ✅ COMPLETED |
| #3 — Modelo de datos (ERD) | 🔄 IN PROGRESS (este documento) |
| #4 — Wireframes del dashboard | ⏳ PENDING |
| #5 — Setup entorno de desarrollo | ⏳ PENDING |

---

*Documento generado el 12/05/2026. Pendiente de revisión antes de implementar migraciones.*
