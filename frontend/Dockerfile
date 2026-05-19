# ── Stage 1: Builder ──
FROM node:22-alpine AS builder

WORKDIR /app

# Dependencias (caché optimizado: package*.json primero)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Código fuente (paths relativos al build context = raíz del proyecto)
COPY frontend/tsconfig.json frontend/vite.config.ts frontend/index.html ./
COPY frontend/src/ src/

# Build de producción
RUN npm run build

# ── Stage 2: Runtime (nginx) ──
FROM nginx:alpine

# Copiar configuración nginx (path relativo al build context = raíz del proyecto)
COPY infrastructure/docker/nginx/frontend.conf /etc/nginx/conf.d/default.conf

# Copiar build stage 1
COPY --from=builder /app/dist /usr/share/nginx/html

# Puerto (coincide con docker-compose: 5173:80)
EXPOSE 80

# Salud: verificar que nginx responde
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
