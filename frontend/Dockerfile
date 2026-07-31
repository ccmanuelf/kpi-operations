# Frontend Dockerfile for KPI Operations Platform
#
# Build context: REPOSITORY ROOT (not frontend/). The build stage needs
# docs/user-guide/ alongside frontend/ — frontend/src/help/index.ts globs
# ../../../docs/user-guide/*.md at build time to embed the in-app Help
# Center content, and that path only resolves if docs/ is reachable from
# the build context (ISSUE-018: it previously wasn't, so the Help Center
# shipped with zero sections). Build with:
#   docker build -f frontend/Dockerfile -t kpi-frontend .
#
# Production: pin to @sha256: digest from docker.io for reproducible builds
# docker pull node:22.22-alpine3.23 && docker inspect --format='{{index .RepoDigests 0}}' node:22.22-alpine3.23
FROM node:22.22-alpine3.23 AS builder

WORKDIR /workspace/frontend

# Copy package files first for layer caching
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# Copy frontend source, then the docs it globs at build time. The docs must
# land at /workspace/docs/user-guide — three levels up from
# frontend/src/help/index.ts — mirroring the repo's own directory layout.
COPY frontend/. .
COPY docs/user-guide/ /workspace/docs/user-guide/

# Build arg for API URL — must be declared here so Vite bakes it at build time
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL

# Build arg gating the Login view's self-registration button (demo-only
# backend endpoint — see backend/routes/auth.py). Set to "true" only for
# demo deployments (Render); defaults off everywhere else.
ARG VITE_DEMO_MODE=false
ENV VITE_DEMO_MODE=$VITE_DEMO_MODE

# Build for production
RUN npm run build

# Development stage
FROM node:22.22-alpine3.23 AS development

WORKDIR /workspace/frontend

# Copy package files first for layer caching
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# Copy frontend source + docs (see builder stage comment above)
COPY frontend/. .
COPY docs/user-guide/ /workspace/docs/user-guide/

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
COPY --from=builder /workspace/frontend/dist /usr/share/nginx/html

# Copy nginx config
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
# Create empty upstream.conf so the include directive doesn't fail before entrypoint runs
RUN touch /etc/nginx/conf.d/upstream.inc

# Copy entrypoint script (generates proxy config at runtime based on BACKEND_URL)
COPY frontend/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 80

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:80 || exit 1

# Entrypoint replaces backend URLs via sed, then starts nginx
ENTRYPOINT ["/docker-entrypoint.sh"]
