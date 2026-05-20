@echo off
REM BeExpand CRM Email — Arranque rápido con Docker
REM Uso: .\infrastructure\docker\docker-start.bat [--build] [--vtiger]

echo ========================================
echo  BeExpand CRM Email — Docker
echo ========================================

set COMPOSE_FILE=-f infrastructure/docker/docker-compose.yml

if "%1"=="--build" (
    echo [INFO] Reconstruyendo imagenes...
    docker compose %COMPOSE_FILE% build
)
if "%2"=="--build" (
    echo [INFO] Reconstruyendo imagenes...
    docker compose %COMPOSE_FILE% build
)

if "%1"=="--vtiger" (
    echo [INFO] Incluyendo VTiger CRM...
    set COMPOSE_FILE=%COMPOSE_FILE% -f infrastructure/docker/docker-compose.vtiger.yml
)
if "%2"=="--vtiger" (
    echo [INFO] Incluyendo VTiger CRM...
    set COMPOSE_FILE=%COMPOSE_FILE% -f infrastructure/docker/docker-compose.vtiger.yml
)

echo [INFO] Arrancando contenedores...
docker compose %COMPOSE_FILE% up -d

echo.
echo [INFO] Comprobando estado...
docker compose %COMPOSE_FILE% ps

echo.
echo ========================================
echo  Servicios disponibles:
echo  Frontend:  http://localhost:5173
echo  Backend:   http://localhost:8000
echo  API Docs:  http://localhost:8000/docs
echo  Postgres:  localhost:5432
echo  Redis:     localhost:6379
echo ========================================
echo.
echo Credenciales: admin / admin123
echo.
echo Para ver logs: docker compose %COMPOSE_FILE% logs -f
echo Para parar:    docker compose %COMPOSE_FILE% down
