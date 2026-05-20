@echo off
REM BeExpand CRM Email — Parar Docker

set COMPOSE_FILE=-f infrastructure/docker/docker-compose.yml

if "%1"=="--vtiger" set COMPOSE_FILE=%COMPOSE_FILE% -f infrastructure/docker/docker-compose.vtiger.yml
if "%2"=="--vtiger" set COMPOSE_FILE=%COMPOSE_FILE% -f infrastructure/docker/docker-compose.vtiger.yml

echo [INFO] Parando contenedores...
docker compose %COMPOSE_FILE% down
echo [INFO] Contenedores detenidos.
