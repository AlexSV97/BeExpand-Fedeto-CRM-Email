@echo off
title BeExpand CRM Email - Demo
chcp 65001 >nul
cls

echo ╔══════════════════════════════════════════════════╗
echo ║                                                  ║
echo ║     🚀 BeExpand CRM Email - MODO DEMO            ║
echo ║                                                  ║
╚══════════════════════════════════════════════════╝
echo.

:: ─── 1. Limpiar puertos ──────────────────────────────
echo [1/5] Limpiando puertos anteriores...
for /f "tokens=5" %%a in ('netstat -ano ^| find ":8000" ^| find "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| find ":5173" ^| find "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo     ✅ Puertos libres

:: ─── 2. Crear .env si no existe ──────────────────────
if not exist "%~dp0backend\.env" (
    echo [2/5] Creando archivo .env con credenciales IMAP...
    (
        echo IMAP_EMAIL=beexpandcrmpoc@gmail.com
        echo IMAP_PASSWORD=rkvm qaiu elow tokc
    ) > "%~dp0backend\.env"
    echo     ✅ .env creado
) else (
    echo [2/5] .env ya existe, lo usamos tal cual
)

:: ─── 3. Arrancar Backend ─────────────────────────────
echo [3/5] Arrancando backend (FastAPI)...
start "Backend - BeExpand CRM" cmd /k "cd /d "%~dp0backend" && title Backend - BeExpand CRM && py -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000"
timeout /t 5 /nobreak >nul
echo     ✅ Backend corriendo en http://localhost:8000

:: ─── 4. Arrancar Frontend ────────────────────────────
echo [4/5] Arrancando frontend (React + Vite)...
start "Frontend - BeExpand CRM" cmd /k "cd /d "%~dp0frontend" && title Frontend - BeExpand CRM && npx vite"
timeout /t 4 /nobreak >nul
echo     ✅ Frontend corriendo en http://localhost:5173

:: ─── 5. Abrir navegador ──────────────────────────────
echo [5/5] Abriendo navegador...
start http://localhost:5173

echo.
echo ╔══════════════════════════════════════════════════╗
echo ║                                                  ║
echo ║   🎯 DEMO LISTA                                  ║
echo ║                                                  ║
echo ║   Abre el navegador en:                          ║
echo ║   http://localhost:5173                          ║
echo ║                                                  ║
echo ║   Usuario:  admin                                ║
║   Contraseña:  admin123                            ║
echo ║                                                  ║
echo ║   Para sincronizar correos, abre otra            ║
║   terminal y pega:                                 ║
echo ║   sync.bat                                       ║
║                                                  ║
╚══════════════════════════════════════════════════╝
echo.
echo Pulsa cualquier tecla para cerrar esta ventana (los servicios siguen abiertos)
pause >nul
