"""
Punto de entrada de la API REST.

Arranque: uvicorn src.api.main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import auth
from src.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida: se ejecuta al arrancar y al cerrar la app."""
    # Al arrancar: crear tablas si no existen
    await init_db()
    yield
    # Al cerrar: limpiar si es necesario


app = FastAPI(
    title="BeExpand CRM Email API",
    description="API de clasificación y gestión de correos con integración VTiger",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1/auth")

# CORS: permitir que el frontend (React en otro puerto) llame al API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Puerto de Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Endpoint de bienvenida (health check)."""
    return {
        "app": "BeExpand CRM Email",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/api/v1/health")
async def health():
    """Health check detallado."""
    return {
        "status": "healthy",
        "database": "sqlite (dev)",
    }
