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
                  ┌─────────────────┐
                  │  Buzones Entrada │
                  │  (Múltiples Dptos)│
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Cuenta Intermedia│
                  │  (Procesamiento)  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Motor de        │
                  │  Clasificación   │
                  └────────┬────────┘
                           │
               ┌───────────┴───────────┐
               ▼                       ▼
        ┌──────────────┐      ┌──────────────┐
        │     CRM      │      │  Dashboards  │
        │  (Contactos, │      │  (Resúmenes, │
        │   Oportunidades)│      │   Seguimiento)│
        └──────────────┘      └──────────────┘
```

## Tecnologías

Stack definitivo — validado con Be Expand en reunión del 11/05/2026.

| Capa | Tecnología | Detalle |
|------|-----------|---------|
| Backend | **Python 3.12+** | FastAPI, SQLAlchemy 2.0, Celery |
| Base de Datos | **PostgreSQL 16** | JSONB para metadatos, tsvector para búsqueda |
| Frontend | **React 19 + TypeScript** | Vite, Recharts, React Router |
| Email Processing | **IMAP nativo** (`imaplib`) | Ionos e Imax confirmados |
| CRM | **VTiger REST API** | Cliente HTTP con `httpx` |
| Task Queue | **Celery + Redis** | Polling periódico de buzones |
| Clasificación | **Híbrida (Keywords → NLP futuro)** | RuleEngine + spaCy (Strategy Pattern) |
| Contenedores | **Docker + docker-compose** | Entorno reproducible |
| Autenticación | **JWT** | `python-jose` + `passlib` |

> 📄 Documentación detallada del stack y la arquitectura en [`docs/stack-architecture.md`](docs/stack-architecture.md)

## Estructura del Proyecto

```
BeExpand-Fedeto-CRM-Email/
├── backend/
│   ├── src/
│   │   ├── email_processor/    # Conexión IMAP, parseo y filtrado
│   │   ├── classifier/         # Clasificación híbrida (keywords → NLP)
│   │   ├── crm_integration/    # Integración con VTiger REST API
│   │   ├── api/                # FastAPI REST endpoints
│   │   └── tasks/              # Celery tareas periódicas
│   ├── tests/
│   ├── alembic/                # Migraciones de BD
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/         # Componentes reutilizables
│   │   ├── pages/              # Dashboard, Contacts, Pipeline
│   │   ├── services/           # Conexión con API
│   │   └── utils/              # Utilidades frontend
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── infrastructure/
│   ├── docker/
│   │   ├── nginx/              # Reverse proxy config
│   │   └── postgres/           # Init scripts
│   └── database/
│       └── seeds/              # Datos de ejemplo
├── docs/
│   ├── stack-architecture.md   # Stack y arquitectura definitivos
│   ├── data-model.md           # Modelo de datos (ERD)
│   ├── requirements.md         # Requisitos funcionales y no funcionales
│   ├── planning-30-60-90.md    # Planificación temporal
│   ├── SESION_2026-05-11.md    # Sesión 1
│   ├── SESION_2026-05-12.md    # Sesión 2
│   ├── diagrama_arquitectura.png
│   ├── diagrama_flujo.png
│   ├── diagrama_modelodatos.png
│   ├── diagrama_motor.png
│   └── diagrama_completo.png
├── .gitignore
└── README.md
```

## Instalación y Configuración

*Próximamente — una vez definido el stack tecnológico final.*

```bash
# Clonar el repositorio
git clone https://github.com/AlexSV97/BeExpand-Fedeto-CRM-Email.git
cd BeExpand-Fedeto-CRM-Email

# (Instrucciones específicas según tecnología seleccionada)
```

## Uso

*Pendiente de definir según el desarrollo del proyecto.*

## Contribución

Para contribuir al proyecto:

1. Haz un fork del repositorio
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Realiza tus cambios y haz commit (`git commit -m 'Añadir nueva funcionalidad'`)
4. Sube tus cambios (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## Licencia

Este proyecto está desarrollado para **Be Expand**.
