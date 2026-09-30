# syntax=docker/dockerfile:1

# ---- Build the React app -------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY public ./public
COPY src ./src

# Empty means same origin: nginx proxies /api/ and /admin/ and serves /media/.
# Set it to an absolute URL to point the bundle at an external API instead.
ARG REACT_APP_API_BASE_URL=
ENV REACT_APP_API_BASE_URL=${REACT_APP_API_BASE_URL}
RUN npm run build

# ---- Serve the bundle and proxy the API ----------------------------------
FROM nginx:1.27-alpine

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/build /usr/share/nginx/html

# Rendered into the template by the nginx image's envsubst entrypoint.
ENV API_UPSTREAM=karaoke-gen-service:8000 \
    NGINX_CLIENT_MAX_BODY_SIZE=200m \
    NGINX_ENVSUBST_FILTER="^(API_UPSTREAM|NGINX_CLIENT_MAX_BODY_SIZE)$"

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
