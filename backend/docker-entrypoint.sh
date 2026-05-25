#!/bin/sh
# docker-entrypoint.sh — Espera a PostgreSQL y luego arranca la app
set -e

# Si DATABASE_URL contiene postgresql, esperar a que esté disponible
if echo "$DATABASE_URL" | grep -q "postgresql"; then
    echo "Esperando a PostgreSQL..."
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_PORT="${DB_PORT:-5432}"
    echo "  Host: $DB_HOST, Puerto: $DB_PORT"

    # Usar Python para socket check (netcat no está en slim)
    python3 -c "
import socket, time, sys
for i in range(30):
    try:
        s = socket.create_connection(('$DB_HOST', $DB_PORT), timeout=3)
        s.close()
        print('PostgreSQL disponible ✓')
        sys.exit(0)
    except (OSError, socket.timeout):
        if i > 0:
            print(f'  Esperando... (intento {i+1}/30)')
        time.sleep(2)
print('ERROR: PostgreSQL no disponible tras 30 intentos')
sys.exit(1)
"
fi

# Ejecutar el comando que se pase como argumento
exec "$@"
