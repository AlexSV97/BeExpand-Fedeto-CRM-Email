# ── Build stage ──
FROM node:22-alpine AS build

WORKDIR /app

# Install dependencies (cached via package*.json)
COPY package.json package-lock.json ./
RUN npm ci

# Build-time env for Vite (inlined at build time)
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=${VITE_API_URL}

# Copy source and build
COPY . .
RUN npm run build

# ── Runtime stage (nginx) ──
FROM nginx:alpine

# Copy nginx config template (nginx official image will envsubst it at startup)
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]