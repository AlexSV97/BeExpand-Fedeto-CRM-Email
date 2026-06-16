"""
Router de autenticación.

Endpoints:
    POST /login  — validar credenciales, emitir JWT (exp=480min)
    GET  /me     — retorna usuario autenticado vía get_current_user
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from src.utils.passwords import verify_password
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import User
from src.db.session import get_db
from src.utils.jwt import encode

from src.api.deps import get_current_user
from src.api.schemas import LoginRequest, TokenResponse, UserResponse

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Autentica usuario y retorna token JWT (expira en 480 minutos)."""
    settings = get_settings()

    # Buscar usuario por username
    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    user = result.scalar_one_or_none()

    # Validar existencia y contraseña
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Verificar que el usuario esté activo
    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )

    # Generar JWT
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role,
        "iat": now,
        "exp": expire,
    }
    token = encode(payload, settings.secret_key, algorithm=settings.algorithm)

    # Actualizar last_login
    user.last_login = now
    await db.flush()

    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    """Retorna la información del usuario autenticado."""
    return current_user
