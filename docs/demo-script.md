# Demo PoC — Aiuken SOC

> **Fecha**: Viernes 22 de mayo de 2026
> **Duración estimada**: 20-25 minutos
> **Objetivo**: Mostrar el sistema funcionando en vivo desde 0

---

## ⚙️ Setup (antes de la demo)

```bash
# 1. Arrancar backend
cd backend
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload

# 2. Arrancar frontend (otra terminal)
cd frontend
npx vite --port 5173

# 3. Verificar que responde
curl http://localhost:8001/health
# → {"status":"ok"}
```

>

**Si hay datos simulados**: `cd backend && python scripts/simulate_data.py`
**Si se quiere ver correos entrando en vivo**: lanzar el botón "Sincronizar" durante la demo.

---

## 🎬 Demo (guion paso a paso)

### 0. Pantalla de Login (30s)

> **Lo que ve el cliente**: Fondo slate-900, tarjeta blanca centrada con logo "Aiuken SOC", campos Usuario y Contraseña.

```
Usuario:    admin
Contraseña: <ADMIN_PASSWORD_DEMO>
```

**🎙️ Discurso:**
> "Este es el acceso al sistema. Cada usuario del equipo tendrá su propio login. Entramos con las credenciales de administrador de demo."

[clic en "Iniciar sesión"]

---

### 1. Dashboard — Vista General (5 min)

> **Lo que ve el cliente**: 4 tarjetas KPI arriba:
> - ✉️ **Total correos** procesados
> - 📅 **Correos hoy**
> - 🏷️ **Categorías** activas
> - 📊 **Etapas** en pipeline

**🎙️ Discurso:**
> "Esta es la pantalla principal. En un golpe de vista sabemos cuántos correos hemos procesado, cuántos han entrado hoy, y cómo se distribuyen."

#### KPIs destacados
> Señalar con el cursor: "Aquí vemos el volumen total de correos clasificados, los que han llegado hoy —esto se actualiza solo cada 5 minutos—, las categorías de contacto que tenemos activas y las etapas del pipeline comercial."

#### Feed de últimos correos

> **Lo que ve el cliente**: Lista vertical con tarjetas de correos. Cada tarjeta muestra:
> - Remitente y asunto
> - Categoría con badge de color (🔵 Cliente / 🟡 Lead / 🟢 Proveedor)
> - Método de clasificación (badge: Reglas / BERT / Ollama)
> - Resumen automático del correo
> - Urgencia (🔥 Alta / Media / Baja)
> - Badge "Revisado" si procede

**🎙️ Discurso:**
> "Cada correo que entra se clasifica automáticamente. El sistema usa tres métodos en paralelo —reglas de negocio, un modelo BERT entrenado con nuestros datos, y un modelo de lenguaje local— y los combina para decidir la categoría. Como veis, no solo dice si es cliente o lead: también extrae un resumen, detecta la urgencia, y sabe qué acción requiere."

> ✅ **Clic en un correo** → abre el detalle (si el cliente pregunta).

#### Botones de acción (cabecera)

> **Lo que ve el cliente**: Barra con botones:
> - 🔄 **Sincronizar** — forzar clasificación de correos pendientes
> - 📋 **Reentrenar** — mejorar el modelo BERT con datos reales

**🎙️ Discurso:**
> "El sistema sincroniza los correos automáticamente cada 5 minutos con Celery. Pero si queremos forzar una clasificación ahora mismo, tenemos este botón. Y el botón de reentrenar permite mejorar el modelo BERT con los datos que ya hemos clasificado —aprende de nuestras correcciones."

---

### 2. Gráficos de Series Temporales + Predicciones (4 min)

> Scroll down

> **Lo que ve el cliente**: 4 gráficos con Recharts:
> 1. **Volumen de correos** — barras por día + línea discontinua de predicción (30/60/90 días)
> 2. **Correos por categoría** — barras apiladas (cliente/lead/proveedor) + total proyectado
> 3. **Precisión media del modelo** — evolución de la confianza del clasificador
> 4. **Contactos capturados** — acumulado de contactos nuevos

**🎙️ Discurso:**
> "Esto es el corazón analítico del sistema. Arriba tenéis selector para cambiar el horizonte de predicción entre 30, 60 y 90 días."
>
> "Cada gráfico combina datos reales (barras azules) con la predicción (línea discontinua naranja). El forecast usa regresión lineal con estacionalidad semanal y ruido histórico —no es una línea recta plana, es realista."
>
> "El de categorías apiladas permite ver si están entrando más leads que clientes, por ejemplo. El de precisión nos dice cómo de fiable es el clasificador cada día. Y el de contactos muestra la tracción comercial."

---

### 3. Contactos (3 min)

> Clic en "Contactos" en el menú lateral

> **Lo que ve el cliente**: Tabla de contactos clasificados con:
> - Nombre, email, empresa
> - Categoría (badge de color)
> - Número de correos intercambiados
> - Búsqueda por texto + filtro por categoría
> - Paginación

**🎙️ Discurso:**
> "Aquí tenéis todos los contactos que el sistema ha identificado automáticamente a partir de los correos. No hay que darlos de alta manualmente: al recibir un correo de una persona nueva, el sistema crea el contacto y lo clasifica."
>
> "Podemos buscar por nombre o email, filtrar solo leads, solo clientes... y si una clasificación no es correcta, podemos cambiarla desde aquí."

> ✅ **Clic en un lead** → "Este contacto entró como lead pero si ya es cliente, podemos recategorizarlo al vuelo."

---

### 4. Oportunidades — Pipeline Comercial (3 min)

> Clic en "Oportunidades" en el menú lateral

> **Lo que ve el cliente**: Tablero kanban con columnas:
> - 🟦 **Nueva**
> - 🟩 **Calificada**
> - 🟧 **Propuesta**
> - 🟪 **Negociación**
> - ✅ **Ganada**
> - ❌ **Perdida**

**🎙️ Discurso:**
> "Cada oportunidad se genera automáticamente cuando un correo de un lead o cliente indica intención de compra, consulta comercial, o renovación. El sistema detecta frases como 'presupuesto', 'queremos contratar', 'renovación' y crea la oportunidad con el contacto vinculado."

> ✅ Señalar una tarjeta de oportunidad:
> "Aquí vemos el título, el contacto asociado, el valor estimado y la probabilidad. Podemos arrastrar entre etapas, editar, o crear una nueva manualmente."

---

### 5. Detalle de Email (3 min)

> Clic en cualquier correo del dashboard o contactos

> **Lo que ve el cliente**: Página completa con:
> - **Asunto, remitente, fecha**
> - **Cuerpo del email** formateado
> - **Clasificación**: categoría + confianza + método
> - **Voto del orquestador**: qué método ganó y por qué
> - **Historial de clasificaciones**: cada método (Reglas, BERT, Ollama) con su voto individual
> - **Resumen automático** extraído por IA
> - **Acciones ejecutadas**: qué se hizo (guardar en BD, sincronizar CRM, etc.)
> - **Enrutamiento**: departamentos y personas destino

**🎙️ Discurso:**
> "Esto es el detalle completo de un correo. Aquí veis la transparencia total del sistema: no solo os decimos la categoría final, sino cómo ha votado cada clasificador."
>
> "Fijaos: las Reglas votaron 'Proveedor', BERT votó 'Cliente', y Ollama votó 'Cliente'. Como dos de tres coincidieron, ganó por mayoría. Si los tres votan distinto, el LLM actúa como juez."
>
> "El resumen permite entender el correo sin leerlo entero —ideal para correos largos de proveedores."

---

### 6. Sincronización CRM (2 min)

> Desde el Dashboard, clic en "Sincronizar CRM"

> **Lo que ve el cliente**: Tabla modal con resultados de sincronización: contactos creados/actualizados/saltados en VTiger

**🎙️ Discurso:**
> "El sistema se integra con VTiger, vuestro CRM. Con este botón sincronizamos todos los contactos clasificados. Los que ya existen se actualizan, los nuevos se crean automáticamente."
>
> "Esto significa que el equipo comercial tiene los contactos siempre actualizados en el CRM sin tener que introducir nada manualmente."

---

### 7. Cierre Técnico (preguntas + Q&A, 3 min)

**Puntos a destacar si preguntan:**

| Área | Resumen |
|------|---------|
| **Seguridad** | JWT con expiración, contraseñas hasheadas con bcrypt |
| **IA local** | Ollama (llama3.2:3b) — 100% local, sin enviar datos a terceros |
| **Precisión** | ~92% con consenso de 3 clasificadores |
| **Escalabilidad** | PostgreSQL + Celery + Redis, Docker |
| **Trazabilidad** | Cada decisión de clasificación queda registrada con su voto individual |
| **Personalizable** | Se pueden ajustar reglas de negocio, reentrenar BERT, modificar prompt del LLM |

---

## 🚨 Posibles problemas y soluciones

| Problema | Solución |
|----------|----------|
| Backend no arranca | `cd backend && pip install -r requirements.txt && uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload` |
| Frontend no arranca | `cd frontend && npm install && npx vite --port 5173` |
| Login falla | Verificar que el seed de admin se ejecutó: en backend, revisar `aiuken.db` |
| Gráficos vacíos | Ejecutar `python scripts/simulate_data.py` para generar 30 días de datos demo |
| Sincronización no responde | Verificar Ollama: `ollama serve` y `ollama pull llama3.2:3b` |
| Error de CORS | Backend en puerto 8001, frontend proxy configurado en vite.config.ts |

---

## 📊 Escenarios alternativos

### Si hay poco tiempo (10 min)
1. Login → Dashboard (KPIs + feed)
2. Series temporales + predicciones
3. Contactos (un lead)
4. Pipeline oportunidades
5. Cierre: "y esto se sincroniza con VTiger automáticamente"

### Si el cliente quiere ver más técnica
1. Login
2. Dashboard completo
3. Detalle de email con el desglose de clasificadores
4. "Reentrenar" modelo — mostrar que aprende
5. Ejecutar simulación de 30 días para ver forecast a 90 días
6. Sincronización CRM + mostrar en VTiger

### Demo en Docker (sin entorno local)
```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
# Abrir http://localhost:5173
```
