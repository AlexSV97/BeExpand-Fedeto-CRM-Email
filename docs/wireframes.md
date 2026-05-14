# Wireframes del Dashboard

> Diseño de interfaz de usuario — Sistema BeExpand CRM Email
> Última actualización: 12/05/2026

---

## Índice de Pantallas

1. [Login](#1-pantalla-de-login)
2. [Dashboard Principal](#2-dashboard-principal)
3. [Contactos](#3-vista-de-contactos)
4. [Pipeline de Oportunidades](#4-pipeline-de-oportunidades)
5. [Flujo de Navegación](#5-flujo-de-navegacion)
6. [Especificaciones de Componentes](#6-especificaciones-de-componentes)

---

## 1. Pantalla de Login

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                          ┌───────────────────┐                      │
│                          │                   │                      │
│                          │   [LOGO]          │                      │
│                          │   Be Expand       │                      │
│                          │   CRM Email       │                      │
│                          │                   │                      │
│                          │   ┌───────────┐   │                      │
│                          │   │ Usuario    │   │                      │
│                          │   └───────────┘   │                      │
│                          │                   │                      │
│                          │   ┌───────────┐   │                      │
│                          │   │ Contraseña │   │                      │
│                          │   └───────────┘   │                      │
│                          │                   │                      │
│                          │   ┌───────────┐   │                      │
│                          │   │  Iniciar   │   │                      │
│                          │   │  Sesión    │   │                      │
│                          │   └───────────┘   │                      │
│                          │                   │                      │
│                          └───────────────────┘                      │
│                                                                     │
│                    © Be Expand — Sistema Interno                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Especificaciones:**
- Diseño centrado, tarjeta blanca sobre fondo gris claro
- Autenticación por usuario/contraseña (JWT)
- Sin registro público — solo administrador crea usuarios
- Modo offline no aplica (sistema interno)

---

## 2. Dashboard Principal

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🔔 BeExpand CRM                         👤 Admin ▼   🔴 ⚙️        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [📊 Dashboard]  [👥 Contactos]  [📈 Pipeline]                     │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  📅 Resumen Semanal — Semana del 11/05 al 17/05                   │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ 📨       │  │ 👤       │  │ 📈       │  │ ⏳       │           │
│  │ 47       │  │ 12       │  │ 3        │  │ 8        │           │
│  │ Correos  │  │ Contactos│  │ Oportunid│  │ Pendientes│           │
│  │ nuevos   │  │ nuevos   │  │ nuevas   │  │ revisión │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
│                                                                     │
│  ─────────────────────────────────────────────────────────────      │
│                                                                     │
│  📊 Clasificación de Correos (últimos 7 días)                      │
│                                                                     │
│  Cliente  ████████████████░░░░░░░░░░░░░░░░  45%                   │
│  Lead     ██████████░░░░░░░░░░░░░░░░░░░░░░  30%                   │
│  Proveed. ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░  18%                  │
│  Otro     ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   7%                 │
│                                                                     │
│  ─────────────────────────────────────────────────────────────      │
│                                                                     │
│  📨 Últimos Correos Clasificados                                   │
│                                                                     │
│  ┌────┬──────────────────┬──────────────┬────────┬────────┐       │
│  │    │ Asunto           │ Remitente    │ Tipo   │ Estado │       │
│  ├────┼──────────────────┼──────────────┼────────┼────────┤       │
│  │ 🔴 │ Pedido #3842     │ Ana García   │ Cliente│ Cerrado│       │
│  │ 🟡 │ Presupuesto obras│ Construcciones│ Lead   │ Pending│       │
│  │ 🟢 │ Factura mensual  │ Suministros  │ Proved.│ Cerrado│       │
│  │ 🔴 │ Soporte urgente  │ María López  │ Cliente│ Seguim.│       │
│  │ 🟡 │ Info productos   │ TechCorp     │ Lead   │ Pending│       │
│  └────┴──────────────────┴──────────────┴────────┴────────┘       │
│                                                                     │
│  [Ver todos los correos →]                                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Especificaciones:**
- **Header**: Logo + notificaciones + perfil usuario + settings
- **Navegación**: Pestañas horizontales para las 3 vistas principales
- **KPI Cards**: 4 métricas clave en tarjetas con icono + número + etiqueta
- **Gráfico de clasificación**: Barras de progreso horizontales con porcentajes
- **Tabla de últimos correos**: Con indicador de prioridad (🔴 alta / 🟡 media / 🟢 baja)
- **Enlace "Ver todos"**: Navega a vista de contactos filtrada

---

## 3. Vista de Contactos

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🔔 BeExpand CRM                         👤 Admin ▼   🔴 ⚙️        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [📊 Dashboard]  [👥 Contactos]  [📈 Pipeline]                     │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  👥 Contactos                                                      │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 🔍 Buscar por nombre, email, empresa...     [Filtros ▼]   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Filtros activos: [Todos ▼]  [Cliente]  [Lead]  [Proveedor]       │
│                                                                     │
│  ┌────┬────────────────┬──────────────┬──────────┬────────┬──────┐ │
│  │    │ Nombre         │ Empresa      │ Email    │ Tipo   │ Correos│
│  ├────┼────────────────┼──────────────┼──────────┼────────┼──────┤ │
│  │ 👤 │ Ana García     │ García SL    │ ana@...  │ Cliente│ 23   │ │
│  │ 👤 │ Construcciones │ Const. Pérez │ obras@.. │ Lead   │ 5    │ │
│  │ 👤 │ Suministros    │ Sumi. SA     │ factu... │ Proved.│ 12   │ │
│  │ 👤 │ María López    │ Tech Corp    │ maria..  │ Cliente│ 8    │ │
│  │ 👤 │ TechCorp       │ TechCorp SL  │ info@... │ Lead   │ 3    │ │
│  │ 👤 │ Juan Ruiz      │ —            │ juan@... │ Cliente│ 15   │ │
│  │ 👤 │ BCN Soluciones │ BCN Sol.     │ contra.. │ Proved.│ 7    │ │
│  │ 👤 │ Laura Gómez    │ Inmob. Gómez │ laura..  │ Lead   │ 2    │ │
│  └────┴────────────────┴──────────────┴──────────┴────────┴──────┘ │
│                                                                     │
│  Mostrando 8 de 12 contactos                    [< 1 2 3 >]       │
│                                                                     │
│  ─────────────────────────────────────────────────────────────      │
│                                                                     │
│  📋 Detalle rápido — Ana García                                    │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │ Ana García                        [Editar] [Ver en VTiger]│      │
│  │ ana@garcia-sl.com                                        │      │
│  │ García SL · Directora Comercial                          │      │
│  │                                                          │      │
│  │ 🏷️ Cliente   📊 Relevancia: Alta   📧 23 correos       │      │
│  │                                                          │      │
│  │ Último email: "Pedido #3842 — 12/05/2026"               │      │
│  │ Estado: ✅ Cerrado                                       │      │
│  │ Oportunidad: 📈 Renovación contrato — 15.000€           │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Especificaciones:**
- **Buscador**: Campo de texto con debounce + botón de filtros avanzados
- **Chips de filtro rápido**: Botones tipo pill para filtrar por categoría
- **Tabla de contactos**: Con foto/avatar, nombre, empresa, email, tipo, nº correos
- **Panel lateral de detalle**: Al hacer clic en un contacto, se abre panel a la derecha
- **Acciones**: Botones "Editar" y "Ver en VTiger" (abre CRM en otra pestaña)
- **Paginación**: Navegación inferior con número de página

---

## 4. Pipeline de Oportunidades

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🔔 BeExpand CRM                         👤 Admin ▼   🔴 ⚙️        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [📊 Dashboard]  [👥 Contactos]  [📈 Pipeline]                     │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  📈 Pipeline de Oportunidades                    Período: [📅 ▼]  │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ 💰 45.000€   │  │ 📊 32.000€   │  │ ✅ 12.000€   │             │
│  │ Pipeline     │  │ En negoc.    │  │ Cerradas     │             │
│  │ total        │  │ activo       │  │ este mes     │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
│                                                                     │
│  ─────────────────────────────────────────────────────────────      │
│                                                                     │
│  Kanban de Oportunidades                                            │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────┐ │
│  │  🆕 NUEVA    │  │  🔍 CALIFIC. │  │  💬 PROPUE. │  │  🤝    │ │
│  │              │  │              │  │              │  │ NEGOC. │ │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │  │┌──────┐│ │
│  │ │TechCorp  │ │  │ │BCN Sol.  │ │  │ │García SL │ │  ││Ruiz  ││ │
│  │ │Info pro- │ │  │ │Sist.      │ │  │ │Renovación│ │  ││Contr.││ │
│  │ │ductos    │ │  │ │seguridad  │ │  │ │contrato  │ │  ││final ││ │
│  │ │          │ │  │ │          │ │  │ │15.000€   │ │  ││8.000€││ │
│  │ │3.000€    │ │  │ │8.000€    │ │  │ │50%       │ │  ││70%   ││ │
│  │ │20%       │ │  │ │40%       │ │  │ │          │ │  ││      ││ │
│  │ │📅 30/06  │ │  │ │📅 15/06  │ │  │ │📅 01/06  │ │  ││📅 20/││ │
│  │ │          │ │  │ │          │ │  │ │          │ │  ││ 05   ││ │
│  │ │ ┌──────┐ │ │  │ │ ┌──────┐ │ │  │ └──────────┘ │  │└──────┘│ │
│  │ │ │Gómez │ │ │  │ │ │---   │ │ │  │              │  │        │ │
│  │ │ │Inmo. │ │ │  │ │ │      │ │ │  │              │  │ ┌────┐ │ │
│  │ │ │2.000€│ │ │  │ │ │      │ │ │  │              │  │ │--- │ │ │
│  │ │ │15%   │ │ │  │ │ │      │ │ │  │              │  │ └────┘ │ │
│  │ │ └──────┘ │ │  │ │ └──────┘ │ │  │              │  │        │ │
│  │ │ ┌──────┐ │ │  │ └──────────┘ │  │              │  │ [+Add] │ │
│  │ │ │Pérez │ │ │  │  [+ Añadir]  │  │  [+ Añadir]  │  └────────┘ │
│  │ │ │Const.│ │ │  └──────────────┘  └──────────────┘             │
│  │ │ │5.000€│ │ │                                                 │
│  │ │ └──────┘ │ │                                                 │
│  │ │ [+Add]   │ │                                                 │
│  │ └──────────┘ │                                                 │
│  └──────────────┘                                                 │
│                                                                     │
│  ─────────────────────────────────────────────────────────────      │
│                                                                     │
│  📊 Proyección Mensual                                             │
│                                                                     │
│  Objetivo: 50.000€            ████████████████░░░░░░░░  65%       │
│  Actual:   32.000€            ████████████████░░░░░░░░            │
│                                                                     │
│  Meta ▲                                                           │
│  50K ┤ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░              │
│  40K ┤ ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░              │
│  30K ┤ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░              │
│  20K ┤ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░              │
│  10K ┤ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░              │
│      └──────────────────────────────────────────────►             │
│      S1    S2    S3    S4    S5    S6    S7    S8    Semana      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Especificaciones:**
- **KPIs superiores**: Pipeline total, negociación activo, cerradas este mes
- **Kanban**: 4 columnas (Nueva → Calificada → Propuesta → Negociación)
- **Cada tarjeta**: Nombre empresa, descripción breve, valor, probabilidad, fecha cierre
- **Colores**: Indicación visual de probabilidad (rojo <30%, amarillo 30-60%, verde >60%)
- **Gráfico de proyección**: Barra de progreso hacia objetivo + minigráfico de tendencia semanal
- **Drag & drop**: Las tarjetas se arrastran entre columnas (actualiza stage en BD + VTiger)

---

## 5. Flujo de Navegación

```
                    ┌─────────┐
                    │  LOGIN  │
                    └────┬────┘
                         │
                         ▼
              ┌─────────────────────┐
              │                     │
         ┌────┤   DASHBOARD         ├────┐
         │    │   (Resumen)         │    │
         │    └─────────────────────┘    │
         │                               │
         ▼                               ▼
  ┌──────────────┐              ┌──────────────────┐
  │  CONTACTOS   │              │    PIPELINE      │
  │              │              │                  │
  │  - Lista     │              │  - Kanban        │
  │  - Filtros   │              │  - Proyección    │
  │  - Detalle   │              │  - KPIs          │
  └──────────────┘              └──────────────────┘
         │                               │
         ▼                               ▼
  ┌──────────────┐              ┌──────────────────┐
  │  Ver en      │              │  Crear/Editar    │
  │  VTiger      │              │  Oportunidad     │
  │  (nueva pesta)│              │  (modal)         │
  └──────────────┘              └──────────────────┘
```

---

## 6. Especificaciones de Componentes

### 6.1 Sistema de Navegación

| Elemento | Tipo | Comportamiento |
|----------|------|----------------|
| Menú principal | Pestañas horizontales | 3 ítems: Dashboard, Contactos, Pipeline |
| Indicador activo | Línea inferior coloreada | Muestra qué pestaña está seleccionada |
| Header | Fijo superior | Logo izquierda, notificaciones + perfil derecha |
| Breadcrumb | No aplica | Solo 3 pantallas, navegación plana |

### 6.2 Sistema de Diseño (Design Tokens)

| Token | Valor | Uso |
|-------|-------|-----|
| `--color-primary` | `#2563EB` (blue-600) | Botones, enlaces, indicadores |
| `--color-success` | `#16A34A` (green-600) | Cerrado, completado |
| `--color-warning` | `#D97706` (amber-600) | Pendiente, en seguimiento |
| `--color-danger` | `#DC2626` (red-600) | Escalado, urgente |
| `--color-bg` | `#F9FAFB` (gray-50) | Fondo de página |
| `--color-surface` | `#FFFFFF` | Tarjetas, paneles |
| `--color-border` | `#E5E7EB` (gray-200) | Bordes de tabla, tarjetas |
| `--radius-sm` | `4px` | Inputs, botones pequeños |
| `--radius-md` | `8px` | Tarjetas, paneles |
| `--radius-lg` | `12px` | Modales, componentes grandes |
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Tarjetas |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Modales, dropdowns |
| `--font` | `Inter, system-ui, sans-serif` | Tipografía del sistema |

### 6.3 Responsive Breakpoints

| Breakpoint | Ancho | Comportamiento |
|------------|-------|----------------|
| Desktop | >1024px | Diseño completo, kanban 4 columnas |
| Tablet | 768-1024px | Kanban 2 columnas, tabla simplificada |
| Mobile | <768px | Navegación hamburguesa, cards en lugar de tabla |

### 6.4 Estados de Carga y Vacío

| Estado | Comportamiento |
|--------|----------------|
| **Carga** | Skeleton screens en tarjetas y tabla |
| **Vacío** | Ilustración + mensaje "No hay datos aún. Configura un buzón para empezar." + CTA |
| **Error** | Banner de error con mensaje descriptivo + botón "Reintentar" |
| **Sin conexión** | Indicador "Modo offline — los datos se actualizarán al reconectar" |

---

## 7. Mapa de Issues Relacionadas

| Issue | Tarea | Estado |
|-------|-------|--------|
| #1 | Stack tecnológico | ✅ COMPLETED |
| #2 | Arquitectura del sistema | ✅ COMPLETED |
| #3 | Modelo de datos (ERD) | ✅ COMPLETED |
| **#4** | **Wireframes del dashboard** | **✅ COMPLETED** |
| #5 | Setup del entorno de desarrollo | ⏳ PENDING |

---

*Documento generado el 12/05/2026 — wireframes funcionales listos para implementación frontend.*
