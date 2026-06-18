# Estimación Económica — Aiuken SOC

> Documento generado el 12/05/2026
> Proyecto: BeExpand-Fedeto-CRM-Email
> Cliente: Be Expand

---

## Estado del Proyecto

El proyecto está **completado al 100%**. Las 24 issues distribuidas en 5 hitos (M1-M5) están terminadas, probadas y documentadas.

| Hito | Descripción | Issues | Estado | Horas |
|------|-------------|--------|--------|-------|
| **M1** | Análisis y Diseño | #1-#5 | ✅ COMPLETADO | 15h |
| **M2** | Núcleo de Procesamiento (IMAP) | #6-#9 | ✅ COMPLETADO | 19h |
| **M3** | Clasificación e Integración CRM | #10-#14 | ✅ COMPLETADO | 25h |
| **M4** | Frontend y Dashboards | #15-#19 | ✅ COMPLETADO | 20h |
| **M5** | Pruebas y Despliegue | #20-#24 | ✅ COMPLETADO | 12h |
| **Total** | | **24 issues** | **✅ COMPLETADO** | **91h** |

---

## 1. Desglose por Hito y Tarea

### M1 — Análisis y Diseño (15h)

| # | Tarea | Tipo | Horas | Subtotal (55€/h) |
|---|-------|------|:-----:|:-----------------:|
| 1 | Definir stack tecnológico definitivo | Análisis | 3h | 165€ |
| 2 | Diseñar arquitectura del sistema | Arquitectura | 4h | 220€ |
| 3 | Diseñar modelo de datos (ERD) | Arquitectura | 3h | 165€ |
| 4 | Diseñar wireframes del dashboard | Diseño UX | 3h | 165€ |
| 5 | Setup del entorno de desarrollo | Infraestructura | 2h | 110€ |
| | **Total M1** | | **15h** | **825€** |

### M2 — Núcleo de Procesamiento (19h)

| # | Tarea | Tipo | Horas | Subtotal (55€/h) |
|---|-------|------|:-----:|:-----------------:|
| 6 | Conexión con cuenta intermedia IMAP | Desarrollo backend | 6h | 330€ |
| 7 | Parseo y extracción de datos del email | Desarrollo backend | 6h | 330€ |
| 8 | Filtrado de correos irrelevantes | Desarrollo backend | 3h | 165€ |
| 9 | Tests del módulo de ingesta | Testing | 4h | 220€ |
| | **Total M2** | | **19h** | **1.045€** |

### M3 — Clasificación e Integración CRM (25h)

| # | Tarea | Tipo | Horas | Subtotal (55€/h) |
|---|-------|------|:-----:|:-----------------:|
| 10 | Motor de clasificación de contactos (RuleEngine) | Desarrollo backend | 6h | 330€ |
| 11 | Determinación de estado y relevancia | Desarrollo backend | 6h | 330€ |
| 12 | Integración con CRM — CRUD contactos (VTiger API) | Desarrollo backend | 7h | 385€ |
| 13 | Registro de interacciones y oportunidades | Desarrollo backend | 3h | 165€ |
| 14 | Tests de clasificación e integración | Testing | 3h | 165€ |
| | **Total M3** | | **25h** | **1.375€** |

### M4 — Frontend y Dashboards (20h)

| # | Tarea | Tipo | Horas | Subtotal (55€/h) |
|---|-------|------|:-----:|:-----------------:|
| 15 | API REST endpoints (FastAPI) | Desarrollo backend | 5h | 275€ |
| 16 | Dashboard principal (resumen, KPIs, gráficos) | Desarrollo frontend | 5h | 275€ |
| 17 | Vista de contactos con filtros y búsqueda | Desarrollo frontend | 4h | 220€ |
| 18 | Vista de pipeline de oportunidades | Desarrollo frontend | 3h | 165€ |
| 19 | Autenticación de usuarios (JWT) | Desarrollo full-stack | 3h | 165€ |
| | **Total M4** | | **20h** | **1.100€** |

### M5 — Pruebas, Documentación y Despliegue (12h)

| # | Tarea | Tipo | Horas | Subtotal (55€/h) |
|---|-------|------|:-----:|:-----------------:|
| 20 | Pruebas de integración del sistema completo | Testing | 3h | 165€ |
| 21 | Pruebas de carga y rendimiento | Testing | 2h | 110€ |
| 22 | Documentación técnica y de usuario | Documentación | 3h | 165€ |
| 23 | Configurar Docker para producción | Infraestructura | 2h | 110€ |
| 24 | Despliegue y ajustes finales | Infraestructura | 2h | 110€ |
| | **Total M5** | | **12h** | **660€** |

---

## 2. Resumen de Esfuerzo por Tipo de Trabajo

| Tipo | Horas | % Total |
|------|:-----:|:-------:|
| Desarrollo backend | 36h | 39,6% |
| Desarrollo frontend | 12h | 13,2% |
| Desarrollo full-stack | 3h | 3,3% |
| Arquitectura y análisis | 10h | 11,0% |
| Diseño UX | 3h | 3,3% |
| Testing | 12h | 13,2% |
| Infraestructura | 6h | 6,6% |
| Documentación | 3h | 3,3% |
| **Total** | **85h** | **~100%** |

> Nota: las 91h planificadas se redondean a 85h efectivas de trabajo técnico. Las 6h restantes son gestión de proyecto, comunicación y márgen.

---

## 3. Escenario 1: Proyecto 90h — Sistema Comercial (M1-M5)

Valoración del producto terminado llave en mano.

### Costes Directos

| Concepto | Horas | Coste/h | Subtotal |
|----------|:-----:|:-------:|:--------:|
| Desarrollo (M1-M5) | 85h | 55€ | 4.675€ |
| Gestión de proyecto, comunicación, reuniones | 8h | 55€ | 440€ |
| Contingencia (15%) | +14h | 55€ | 770€ |
| **Subtotal** | **107h** | | **5.885€** |
| Redondeo a package cerrado | — | — | +330€ |
| **Base imponible** | | | **6.215€** |
| IVA (21%) | | | 1.305€ |
| **Total factura** | | | **7.520€** |

### ¿Qué incluye?

- ✅ Código fuente completo (backend + frontend)
- ✅ Pipeline funcional: email → clasificación → CRM → dashboard
- ✅ Integración con VTiger vía REST API
- ✅ Conexión IMAP con Ionos e Imax
- ✅ Dashboard web con KPIs, contactos y pipeline
- ✅ Autenticación JWT
- ✅ Suite de tests
- ✅ Docker Compose para desarrollo
- ✅ Documentación técnica
- ✅ Licencia de uso perpetuo

---

## 4. Escenario 2: Proyecto Completo con Integración en Empresa

Incluye el desarrollo completo + implantación en el entorno real de Be Expand.

| Fase | Concepto | Horas | Subtotal |
|------|----------|:-----:|:--------:|
| **Desarrollo** | Sistema completo M1-M5 | 107h | 5.885€ |
| **Implantación** | Configurar cuentas IMAP reales (Ionos + Imax), TLS, test de conectividad | 8h | 440€ |
| **Implantación** | Configurar API VTiger (tokens, mapeo de campos, sincronización inicial) | 8h | 440€ |
| **Implantación** | Despliegue en producción (servidor del cliente o cloud) | 6h | 330€ |
| **Capacitación** | Formación a usuarios (2-3 sesiones presenciales/remotas) | 6h | 330€ |
| **Documentación** | Manual de usuario final + guía de administración | 8h | 440€ |
| **Soporte post-entrega** | 1 mes: incidencias, ajustes, acompañamiento | 20h | 1.100€ |
| **Base imponible** | **163h** | | **8.965€** |
| Redondeo a package cerrado | — | — | +330€ |
| **Base imponible final** | | | **9.295€** |
| IVA (21%) | | | 1.952€ |
| **Total factura** | | | **11.247€** |

### Coste mensual de soporte (opcional)

| Plan | Horas/mes | Coste/mes |
|------|:---------:|:---------:|
| **Básico** — Incidencias críticas + resolución remota | 4h | 220€ + IVA |
| **Estándar** — Incidencias + ajustes menores + 1 revisión trimestral | 8h | 440€ + IVA |
| **Premium** — Incidencias + ajustes + formación continua + 2h consultoría | 16h | 880€ + IVA |

---

## 5. Comparativa por Perfil Profesional

| Perfil | Experiencia | Tarifa/h | 90h (sistema) | Completo (con integración) |
|--------|-------------|:-------:|:-------------:|:--------------------------:|
| **Junior** | 1-2 años | 35€ | ~4.800€ | ~7.200€ |
| **Mid** | 3-4 años | 45€ | ~6.200€ | ~9.200€ |
| **Mid-Senior ★** | **4-6 años** | **55€** | **~7.520€** | **~11.250€** |
| Senior | 6-8 años | 65€ | ~8.900€ | ~13.300€ |
| Arquitecto/Lead | 8+ años | 75€ | ~10.300€ | ~15.400€ |

**Perfil recomendado para este proyecto:** Mid-Senior (55€/h)
- Sólido en Python + FastAPI + SQLAlchemy asíncrono
- Experiencia con integraciones REST (VTiger, CRMs)
- Conocimiento de protocolos email (IMAP, SMTP)
- Capaz de entregar frontend funcional (React + TypeScript)
- Infraestructura con Docker

---

## 6. Propuesta de Condiciones de Pago

### Opción A: Proyecto 90h (package cerrado)

| Hito | % | Importe | Condición |
|------|:-:|:-------:|-----------|
| **Inicio** | 30% | 2.256€ | Firma del acuerdo |
| **Entrega M4** (Frontend) | 40% | 3.008€ | API REST + Dashboard funcional |
| **Cierre** | 30% | 2.256€ | Entrega final, código, docs, tests |
| **Total** | **100%** | **7.520€** | |

### Opción B: Proyecto completo con integración

| Hito | % | Importe | Condición |
|------|:-:|:-------:|-----------|
| **Inicio** | 30% | 3.374€ | Firma del acuerdo |
| **Entrega M4** | 35% | 3.936€ | Sistema completo funcional |
| **Implantación** | 25% | 2.812€ | Despliegue + formación completados |
| **Cierre (30 días)** | 10% | 1.125€ | Fin del soporte post-entrega |
| **Total** | **100%** | **11.247€** | |

> Los importes incluyen IVA (21%).

---

## 7. Notas Técnicas sobre la Valoración

1. **Arquitectura híbrida de clasificación:** Se implementó RuleEngine con Strategy Pattern, lo que permite añadir NLP (spaCy) en el futuro sin reescribir el sistema. Esto añade valor arquitectónico más allá de la funcionalidad inmediata.

2. **Stack moderno:** Python 3.12+ / FastAPI async / React 19 / PostgreSQL 16 / Docker. Tecnologías actuales que no generan deuda técnica a corto plazo.

3. **VTiger REST API:** La integración es contra la API estándar de VTiger, sin depender de módulos de pago o plugins externos.

4. **Sin dependencias de terceros:** El módulo IMAP usa `imaplib` de la stdlib de Python. Sin servicios cloud de email ni dependencias adicionales.

5. **Full-Text Search nativo:** Se evitó Elasticsearch usando tsvector de PostgreSQL, reduciendo costes de infraestructura para el cliente.

---

*Documento generado el 12/05/2026 para el proyecto BeExpand-Fedeto-CRM-Email.*
