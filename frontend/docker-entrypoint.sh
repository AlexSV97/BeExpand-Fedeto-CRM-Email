#!/bin/sh
set -e

# Expand environment variables in nginx.conf template
if [ -f /etc/nginx/templates/default.conf.template ]; then
  envsubst '${API_UPSTREAM}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf
fi

# Execute the nginx command
exec "$@"
