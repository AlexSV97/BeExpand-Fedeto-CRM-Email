"""Schemas para autenticación (login + token + usuario)."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Credenciales de inicio de sesión."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Respuesta con token JWT."""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Información pública del usuario (sin password)."""
    id: str
    username: str
    email: str | None = None
    full_name: str | None = None
    role: str
    active: bool

    model_config = {"from_attributes": True}
