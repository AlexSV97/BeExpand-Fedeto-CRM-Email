# Proyecto Be Expand FEDETO

Sistema de centralización y estructuración de información clave proveniente del correo electrónico, con integración CRM para la gestión de contactos, oportunidades y seguimiento comercial.

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

**Be Expand FEDETO** es una solución híbrida diseñada para centralizar, estructurar y procesar automáticamente la información proveniente del correo electrónico empresarial. El sistema clasifica contactos (clientes, leads, proveedores, etc.), determina el estado de las interacciones y se integra con el CRM para proporcionar una visión operativa clara de la actividad comercial.

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

*Tecnologías propuestas — sujetas a validación durante el desarrollo.*

| Capa | Tecnología |
|------|-----------|
| Backend | Python / Node.js |
| Base de Datos | PostgreSQL / MongoDB |
| Frontend | React / Vue.js |
| Email Processing | IMAP / Microsoft Graph API |
| CRM | HubSpot / Salesforce API |
| Contenedores | Docker |

## Estructura del Proyecto

```
Proyecto_Be_Expand_Fedeto/
├── backend/
│   ├── src/
│   │   ├── email_processor/    # Procesamiento y parsing de correos
│   │   ├── classifier/         # Clasificación de contactos y estados
│   │   ├── crm_integration/    # Integración con el CRM
│   │   ├── api/                # API REST endpoints
│   │   └── utils/              # Utilidades compartidas
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/         # Componentes reutilizables
│   │   ├── pages/              # Páginas/dashboards
│   │   ├── services/           # Conexión con API
│   │   └── utils/              # Utilidades frontend
│   └── package.json
├── infrastructure/
│   ├── docker/                 # Dockerfiles y docker-compose
│   └── database/               # Migraciones y seeds
├── docs/                       # Documentación adicional
├── .gitignore
└── README.md
```

## Instalación y Configuración

*Próximamente — una vez definido el stack tecnológico final.*

```bash
# Clonar el repositorio
git clone https://github.com/AlexSV97/Proyecto_Be_Expand_Fedeto.git
cd Proyecto_Be_Expand_Fedeto

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

Este proyecto está desarrollado en el marco de **Be Expand FEDETO**.
