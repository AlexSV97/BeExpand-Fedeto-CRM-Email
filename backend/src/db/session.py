"""
Configuración de la base de datos con SQLAlchemy asíncrono.

Soporta SQLite (desarrollo) y PostgreSQL (producción) sin cambiar código.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from src.config import get_settings

settings = get_settings()

# Motor de base de datos (SQLite o PostgreSQL según DATABASE_URL)
engine = create_async_engine(settings.database_url, echo=settings.debug)

# Fábrica de sesiones asíncronas
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clase base para todos los modelos SQLAlchemy."""
    pass


async def get_db() -> AsyncSession:
    """Dependencia de FastAPI: proporciona una sesión de BD por petición."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Crea todas las tablas (útil para desarrollo con SQLite)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
