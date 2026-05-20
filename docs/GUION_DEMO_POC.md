# Guión de Demo — PoC BeExpand CRM Email

> **Duración estimada**: 15-20 minutos
> **Prep**: Backend + Frontend arrancados, navegador en http://localhost:5173

---

## 🎬 Escena 1 — Login (1 min)

**Acción**: Abres http://localhost:5173, ves pantalla de login.

**Guión**:
> "Este es el dashboard de gestión de correos. Usamos autenticación JWT — cada usuario tiene su sesión. Ahora entramos con admin."

**Click**: `admin` / `admin123` → **Login**

---

## 📊 Escena 2 — Dashboard General (3 min)

**Acción**: Te aparece el dashboard con tarjetas KPI, gráficos y feed.

**Qué señalar**:
1. **4 tarjetas KPI** arriba: total correos, correos hoy, contactos, oportunidades
2. **Gráfico de forecast** (predicción a 30/60/90 días)
3. **Feed de últimos correos** con badges de color

**Click**: Pasa el ratón por los badges de los correos en el feed:
- 🔵 Reglas (rule_engine)
- 🟣 BERT
- 🟢 Ollama

**Guión**:
> "Cada correo que entra se clasifica automáticamente con 3 motores EN PARALELO: un sistema de reglas con keywords que tarda 1ms, un modelo BERT de inteligencia artificial que tarda 50ms, y un LLM local con Ollama que hace análisis semántico profundo en 1-3 segundos."
>
> "Los 3 votan simultáneamente, y un resolvedor decide la categoría final. Si los 3 coinciden es consenso, si 2 de 3 es mayoría, y si ninguno coincide un juez LLM desempata."

**Click**: Señala el donut "Método de clasificación" — muestra consenso/mayoría/juez.

---

## 📈 Escena 3 — Forecasting y Tendencias (2 min)

**Acción**: Baja al área de TimeSeriesCharts (gráficos de proyección).

**Qué señalar**:
1. Línea de predicción a 30 días con tendencia creciente
2. Desglose por categoría (cliente/lead/proveedor)
3. Selector 30d/60d/90d

**Click**: Cambia entre 30d, 60d, 90d para mostrar que el forecast se adapta.

**Guión**:
> "El sistema aprende de los patrones semanales: los lunes recibimos más correos, los fines de semana mucho menos. El forecast incorpora estacionalidad semanal, tendencia lineal y ruido histórico para hacer predicciones realistas."
>
> "Esto permite a dirección anticipar volumen de trabajo y planificar recursos."

---

## 👥 Escena 4 — Contactos (2 min)

**Acción**: Click en "Contactos" en la barra lateral.

**Qué señalar**:
1. 25 contactos con nombre, empresa, email, categoría
2. Buscador en vivo
3. Filtro por categoría (cliente/lead/proveedor)

**Click**: Escribe "Innovatech" en el buscador.
**Click**: Filtra por "cliente" para mostrar solo clientes.

**Guión**:
> "Cada persona que escribe un correo se registra automáticamente como contacto y se clasifica. Podéis buscar por nombre, email o filtrar por tipo."
>
> "Cuando tengamos la integración con VTiger, estos contactos se crearán automáticamente en vuestro CRM sin intervención manual."

---

## 💰 Escena 5 — Pipeline de Oportunidades (2 min)

**Acción**: Click en "Oportunidades" en la barra lateral.

**Qué señalar**:
1. Tarjetas tipo kanban organizadas por etapa
2. Valor económico estimado
3. Probabilidad y fecha de cierre

**Click**: Pulsa "Nueva oportunidad" para mostrar el modal.
**Click**: Arrastra visualmente entre etapas (o edita).

**Guión**:
> "Cuando un lead muestra interés comercial, se crea una oportunidad y sigue un pipeline: nueva → calificada → propuesta → negociación → cerrada."
>
> "Cada oportunidad tiene un valor estimado y una probabilidad, lo que permite hacer proyecciones de ingresos y seguir el embudo comercial."
>
> "Hoy tenemos 20 oportunidades simuladas para la demo. Con VTiger, cada una se sincronizaría bidireccionalmente con vuestro CRM."

---

## 📨 Escena 6 — Detalle de Email + Votación (3 min)

**Acción**: Click en la barra lateral "Dashboard", luego click en cualquier email del feed reciente.

**Qué señalar**:
1. Cuerpo del email completo con datos realistas
2. **3 badges de votación**: Reglas, BERT, Ollama — cada uno con su voto y confianza
3. Badge de resolución: "Consenso" / "Mayoría" / "Juez LLM"
4. Metadatos: urgencia, departamento destino, acción requerida

**Guión**:
> "Este es el corazón del sistema. Cada email se procesa con 3 clasificadores independientes, y aquí veis el resultado de cada uno:"
>
> - 🔵 **Reglas**: busca keywords como 'factura', 'presupuesto', 'incidencia' y asigna pesos
> - 🟣 **BERT**: modelo de lenguaje entrenado que entiende el significado semántico
> - 🟢 **Ollama**: LLM local que hace análisis de contexto profundo
>
> "Si alguno se equivoca, los otros lo corrigen. El sistema es mucho más robusto que cualquier clasificador individual."

**Qué más señalar en el detalle**:
- "Vía: Consenso" (o Mayoría) — cómo se tomó la decisión
- Urgencia: alta/media/baja
- Departamento: soporte / comercial / compras / dirección

---

## 🔄 Escena 7 — Sincronización en Vivo (2 min)

**Acción**: Vuelve al Dashboard, busca el botón "🔄 Sincronizar" (arriba).

**Click**: "🔄 Sincronizar"

**Guión**:
> "Este botón conecta con la bandeja de entrada vía IMAP, descarga los correos nuevos y los procesa con el pipeline completo."
>
> "En producción, esto ocurre automáticamente cada 5 minutos con Celery Beat. El sistema polléa la bandeja, clasifica, enruta y persiste sin intervención humana."

**Espera 3-5 segundos**, muestra que los correos aparecen en el feed.

---

## 🧠 Escena 8 — Arquitectura y Cierre (2 min)

**Sin clicks**. Pantalla final del dashboard.

**Guión de cierre**:

> "¿Qué hemos visto hoy?"
>
> 1. **Ingesta automática** de correos desde cualquier cuenta IMAP
> 2. **Clasificación multi-agente** con 3 motores en paralelo para máxima precisión
> 3. **Dashboard en tiempo real** con KPIs, forecast y pipeline comercial
> 4. **Detalle de email** con trazabilidad completa de cada clasificación
> 5. **Pipeline de oportunidades** para seguimiento comercial
>
> "¿Qué viene después cuando decidáis implementarlo?"
>
> - 🔗 **Integración con VTiger**: los contactos y oportunidades que veis aquí se crearán automáticamente en vuestro CRM
> - 📬 **Vuestras cuentas reales**: IMAP contra Ionos/Imax con vuestros buzones reales
> - 🎯 **Fine-tuning BERT**: entrenamos el modelo con vuestros propios correos para >90% de precisión
> - 🐳 **Despliegue Docker**: un solo comando y el sistema entero está en producción

---

## ⚡ Checklist pre-demo

- [ ] Backend arrancado (`uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload`)
- [ ] Frontend arrancado (`npm run dev`)
- [ ] Login funciona (admin/admin123)
- [ ] Dashboard carga con 390+ emails
- [ ] Contactos muestra 25+ registros
- [ ] Oportunidades muestra 20+ registros
- [ ] Forecast muestra gráficos (Ollama funcionando)
- [ ] Navegador en pantalla completa, sin pestañas de debug
- [ ] Copia de seguridad BD hecha (`copy backend\beexpand.db backend\beexpand_demo_backup.db`)
