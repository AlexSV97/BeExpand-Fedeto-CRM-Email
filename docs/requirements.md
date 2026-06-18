# Toma de Requisitos — Aiuken

## Requisitos Funcionales

### RF1 - Ingesta de Correos
- Conexión a cuenta intermedia vía IMAP / Microsoft Graph API
- Descarga y parseo de correos (asunto, cuerpo, remitente, destinatarios, adjuntos)
- Filtrado de correos irrelevantes (spam, automáticos, etc.)

### RF2 - Clasificación de Contactos
- Identificar remitente como: Cliente, Lead, Proveedor, Otro
- Extraer datos de contacto (nombre, email, empresa, cargo)
- Detectar si es nuevo contacto o existente

### RF3 - Determinación de Estado y Relevancia
- Estado: Pendiente, En seguimiento, Cerrado, Escalado
- Relevancia: Alta, Media, Baja (según keywords, remitente, frecuencia)
- Detectar oportunidades de negocio en el contenido

### RF4 - Integración con CRM
- Crear/actualizar contactos en el CRM automáticamente
- Registrar interacciones y oportunidades
- Comunicación bidireccional: leer datos del CRM para enriquecer información

### RF5 - Dashboard y Reporting
- Resumen diario/semanal de actividad comercial
- Vista de contactos y su estado actual
- Seguimiento de oportunidades y pipeline comercial
- Búsqueda y filtros por tipo, estado, fecha, relevancia

## Requisitos No Funcionales

### RNF1 - Seguridad
- Autenticación de usuarios
- Cifrado de credenciales de buzones y CRM
- Cumplimiento GDPR en almacenamiento de datos personales

### RNF2 - Rendimiento
- Procesamiento eficiente de alto volumen de correos
- Respuesta en interfaz < 2s en consultas comunes

### RNF3 - Escalabilidad
- Capacidad de añadir nuevos buzones sin reconfigurar el sistema
- Arquitectura modular que permita crecimiento horizontal

### RNF4 - Disponibilidad
- Tolerancia a fallos en el módulo de ingesta
- Sistema de reintentos ante caídas del CRM o servidor de correo
