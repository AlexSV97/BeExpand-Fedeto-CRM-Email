@echo off
title Sincronizar Correos - BeExpand CRM
chcp 65001 >nul
cls

echo ╔══════════════════════════════════════════════════╗
echo ║                                                  ║
echo ║     📧 Sincronizar Correos IMAP                 ║
echo ║                                                  ║
╚══════════════════════════════════════════════════╝
echo.
echo Conectando con el backend...

:: Login y sync en un solo comando Python
py -c "
import httpx, json
try:
    r = httpx.post('http://localhost:8000/api/v1/auth/login',
        json={'username':'admin','password':'admin123'}, timeout=5)
    token = r.json()['access_token']
    r2 = httpx.post('http://localhost:8000/api/v1/emails/sync',
        headers={'Authorization': f'Bearer {token}'}, timeout=30)
    result = r2.json()
    if result.get('connected'):
        print(f'\n✅ Conectado a Gmail correctamente')
        print(f'📨 Correos encontrados: {result[\"fetched\"]}')
        print(f'💾 Correos guardados:   {result[\"saved\"]}')
        if result.get('duplicates'):
            print(f'🔁 Duplicados omitidos: {result[\"duplicates\"]}')
        if result.get('errors'):
            print(f'❌ Errores:             {result[\"errors\"]}')
        print(f'\n🎉 Sincronizacion completada!')
    else:
        print(f'\n❌ Error: {result.get(\"error\", \"Error desconocido\")}')
except httpx.ConnectError:
    print('\n❌ No se puede conectar al backend.')
    print('   Asegurate de que el backend esta corriendo en localhost:8000')
except Exception as e:
    print(f'\n❌ Error: {e}')
" 2>&1

echo.
echo Pulsa cualquier tecla para salir
pause >nul
