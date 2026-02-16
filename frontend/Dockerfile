# Frontend Dockerfile for KPI Operations Platform
# node:20.18-alpine3.20 — pin to digest for reproducible builds:
# docker pull node:20.18-alpine3.20 && docker inspect --format='{{index .RepoDigests 0}}' node:20.18-alpine3.20
LABEL maintainer="KPI Operations Team"
LABEL version="1.0.4"
LABEL description="KPI Operations Platform - Vue.js Frontend"

FROM node:20.18-alpine3.20 AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# Copy source files
COPY . .

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
# nginx:1.27-alpine — pin to digest for reproducible builds:
# docker pull nginx:1.27-alpine && docker inspect --format='{{index .RepoDigests 0}}' nginx:1.27-alpine
FROM nginx:1.27-alpine AS production

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:80 || exit 1

# Run as non-root nginx user
USER nginx

CMD ["nginx", "-g", "daemon off;"]
