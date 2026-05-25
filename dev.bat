@echo off
title BeExpand CRM Email - Dev Launcher
cd /d "%~dp0"

:: ── Colors ──
set "VERDE=[92m"
set "AMARILLO=[93m"
set "CYAN=[96m"
set "ROJO=[91m"
set "RESET=[0m"

cls
echo.
echo %CYAN%====================================================%RESET%
echo %CYAN%    BeExpand CRM Email - Entorno de Desarrollo%RESET%
echo %CYAN%====================================================%RESET%
echo.

:: ── 1. Limpiar puertos anteriores ──
echo %AMARILLO%[1/4] Limpiando puertos anteriores...%RESET%
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul
echo %VERDE%  Puertos liberados%RESET%
echo.

:: ── 2. Arrancar Backend ──
echo %AMARILLO%[2/4] Arrancando Backend (puerto 8001)...%RESET%
start "Backend" cmd /k "cd /d %~dp0backend && title Backend - BeExpand API && python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload"
echo %VERDE%  Backend iniciado%RESET%
echo.

:: ── 3. Arrancar Frontend ──
echo %AMARILLO%[3/4] Arrancando Frontend (puerto 5173)...%RESET%
start "Frontend" cmd /k "cd /d %~dp0frontend && title Frontend - BeExpand Dashboard && npx vite --port 5173"
echo %VERDE%  Frontend iniciado%RESET%
echo.

:: ── 4. Esperar y abrir navegador ──
echo %AMARILLO%[4/4] Esperando servidores...%RESET%
timeout /t 7 /nobreak >nul
echo Abriendo navegador...
start http://localhost:5173
echo.

echo %CYAN%====================================================%RESET%
echo %VERDE%  Todo listo!%RESET%
echo.
echo  %CYAN*Backend:%RESET%  http://localhost:8001
echo  %CYAN*Frontend:%RESET% http://localhost:5173
echo  %CYAN*API Docs:%RESET% http://localhost:8001/docs
echo.
echo  Las ventanas de terminal se recargan SOLAS
echo  ante cualquier cambio en el codigo.
echo.
echo  %AMARILLO%Presiona cualquier tecla para CERRAR todo%RESET%
echo %CYAN%====================================================%RESET%
echo.
pause >nul

:: ── Cleanup ──
echo.
echo %AMARILLO%Cerrando servidores...%RESET%

:: Cerrar por ventana
taskkill /f /fi "WINDOWTITLE eq Backend*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Frontend*" >nul 2>&1

:: Si no se cerraron, forzar por puerto
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo %VERDE%Servidores cerrados.%RESET%
timeout /t 2 /nobreak >nul
