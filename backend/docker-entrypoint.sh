#!/bin/sh
# docker-entrypoint.sh — Espera a PostgreSQL y luego arranca la app
set -e

# Si DATABASE_URL contiene postgresql, esperar a que esté disponible
if echo "$DATABASE_URL" | grep -q "postgresql"; then
    echo "Esperando a PostgreSQL..."

    python3 -c "
import os, socket, time, sys
from urllib.parse import urlparse

url = os.environ.get('DATABASE_URL', '')
if not url:
    print('  DATABASE_URL no está configurada, saltando wait')
    sys.exit(0)

try:
    parsed = urlparse(url)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 5432
    print(f'  Host: {host}, Puerto: {port}')

    for i in range(30):
        try:
            s = socket.create_connection((host, port), timeout=3)
            s.close()
            print('PostgreSQL disponible ✓')
            sys.exit(0)
        except (OSError, socket.timeout):
            if i > 0:
                print(f'  Esperando... (intento {i+1}/30)')
            time.sleep(2)
    print('⚠️  PostgreSQL no disponible tras 30 intentos, arrancando de todas formas')
except Exception as e:
    print(f'⚠️  Error parseando DATABASE_URL o conectando: {e}')
    print('  Arrancando app de todas formas...')
"
fi

# Ejecutar el comando que se pase como argumento
exec "$@"
