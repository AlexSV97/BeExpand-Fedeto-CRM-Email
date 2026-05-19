-- BeExpand CRM Email — Inicialización de la base de datos PostgreSQL
--
-- Este script se ejecuta UNA sola vez al crear el contenedor por primera vez.
-- Las migraciones del esquema se gestionan con Alembic (backend/alembic/).
--
-- Aquí se pueden añadir extensiones o configuraciones globales.

-- Extensión para búsqueda de texto completo (FTS)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Extensión para UUIDs (por si se necesitan en el futuro)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
