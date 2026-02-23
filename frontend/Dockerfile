# Frontend Dockerfile for KPI Operations Platform
# Production: pin to @sha256: digest from docker.io for reproducible builds
# docker pull node:20.18-alpine3.20 && docker inspect --format='{{index .RepoDigests 0}}' node:20.18-alpine3.20
FROM node:20.18-alpine3.20 AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# Copy source files
COPY . .

# Build arg for API URL — must be declared here so Vite bakes it at build time
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL

# Build for production
RUN npm run build

# Development stage
FROM node:20.18-alpine3.20 AS development

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# Copy source files
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Production stage (final — default target for `docker build`)
# Production: pin to @sha256: digest from docker.io for reproducible builds
# docker pull nginx:1.27-alpine && docker inspect --format='{{index .RepoDigests 0}}' nginx:1.27-alpine
FROM nginx:1.27-alpine AS production

LABEL maintainer="KPI Operations Team"
LABEL version="1.0.4"
LABEL description="KPI Operations Platform - Vue.js Frontend"

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:80 || exit 1

# CSP connect-src customization (e.g. "https://api.example.com" on Render)
ENV CSP_CONNECT_EXTRA=""

# Use envsubst to replace env vars in nginx.conf, then start nginx
# Runs as root so envsubst can write to /etc/nginx/conf.d/; nginx workers drop to 'nginx' user
CMD ["/bin/sh", "-c", "envsubst '${CSP_CONNECT_EXTRA}' < /etc/nginx/conf.d/default.conf > /tmp/default.conf && mv /tmp/default.conf /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
