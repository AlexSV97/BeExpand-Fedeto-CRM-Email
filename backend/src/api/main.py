"""
Punto de entrada de la API REST.

Arranque: uvicorn src.api.main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import (
    accounts,
    auth,
    classification,
    contacts,
    dashboard,
    emails,
    opportunities,
)
from passlib.hash import bcrypt
from sqlalchemy import select

from src.config import get_settings
from src.db.models import User
from src.db.session import async_session_factory, init_db


async def seed_admin():
    """Crea el usuario admin por defecto si no existe."""
    settings = get_settings()
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.username == settings.admin_username)
        )
        if result.scalar_one_or_none() is None:
            user = User(
                username=settings.admin_username,
                hashed_password=bcrypt.hash(settings.admin_password),
                role="admin",
                active=True,
                full_name="Administrador",
            )
            session.add(user)
            await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida: se ejecuta al arrancar y al cerrar la app."""
    # Al arrancar: crear tablas si no existen + seed admin
    await init_db()
    await seed_admin()
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
app.include_router(accounts.router, prefix="/api/v1/accounts")
app.include_router(emails.router, prefix="/api/v1/emails")
app.include_router(contacts.router, prefix="/api/v1/contacts")
app.include_router(opportunities.router, prefix="/api/v1/opportunities")
app.include_router(classification.router, prefix="/api/v1/classification-history")
app.include_router(dashboard.router, prefix="/api/v1/dashboard")

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
