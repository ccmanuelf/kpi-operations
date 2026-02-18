# Production Readiness Hardening — Client Go-Live Checklist

## Context

This prompt activates when a client has completed the demo/validation phase on SQLite and is ready to go live on their MariaDB instance. The application platform has proven its value replacing scattered XLSX files, and the client has confirmed the transition.

The goal is to ensure production-grade quality across the full stack: code + data + infrastructure + observability + recovery.

## Current State (as of demo phase completion)

- SQLite demo: fully functional, 39 tables, 5 demo clients, all features seeded
- Migration wizard: tested, TABLE_ORDER validated (45 tables in 11 tiers)
- CI/CD: branch protection enforced, build-before-test gating, 75% backend coverage threshold
- Frontend: 1,476 tests, 0 failures, composable architecture, full i18n
- Backend: 4,281 tests, 0 failures, 75.99% coverage, no bare exceptions
- Security: auth on all routes, CORS validated, rate limiting, security headers, pre-commit hooks

---

## PHASE 0: Credential Bootstrap (Immediately After Migration)

This phase runs right after the MariaDB migration completes and before the client's team starts using the system. Demo users are preserved as inactive references — useful for the new admin to study roles, permissions, and test workflows before onboarding real staff.

### 0.1 Rotate SECRET_KEY

- [ ] Generate a new production `SECRET_KEY` (minimum 64 characters, cryptographically random):
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(64))"
  ```
- [ ] Set the new key in the production `.env` or secret manager
- [ ] Restart the application — all existing demo JWTs are now invalid (forced re-login)
- [ ] Verify `validate_production_config()` accepts the new key (not in `DEFAULT_INSECURE_VALUES`)

### 0.2 Deactivate Demo Users

All seeded demo users have known passwords (visible in `init_demo_database.py` and `demo_seeder.py`). Mark them inactive so they cannot authenticate, but preserve them for reference:

- [ ] Mark all demo users as `is_active = False` via admin API or direct SQL:
  ```sql
  UPDATE USER SET is_active = 0
  WHERE username IN ('admin', 'supervisor1', 'supervisor2', 'supervisor3',
    'supervisor4', 'supervisor5', 'operator1', 'operator2', 'operator3',
    'operator4', 'operator5', 'operator6', 'leader1', 'poweruser',
    'e2e_admin', 'e2e_supervisor', 'e2e_operator');
  ```
- [ ] Verify no demo user can log in after deactivation
- [ ] Demo users remain visible in Admin > Users for the new admin to review role structures

### 0.3 Create Production Admin Account

- [ ] Create a new admin user with a strong generated password:
  - Username: client-specific (e.g., `acme_admin`, not generic `admin`)
  - Password: minimum 16 characters, generated (not chosen)
  - Role: `admin`
  - Associated to the client's `client_id`
- [ ] Deliver credentials securely to the client admin (not via email — use a secure channel)
- [ ] Client admin logs in, verifies access, changes password on first use

### 0.4 Client Onboards Real Users

The production admin creates the client's actual team through the Admin UI:

- [ ] Create supervisor accounts for each shift lead (real names, role-appropriate permissions)
- [ ] Create operator accounts for floor staff
- [ ] Assign users to correct `client_id` and shifts
- [ ] Each user logs in and changes their initial password
- [ ] Verify role-based access: operators see My Shift, supervisors see dashboards, admin sees settings

### 0.5 Deactivate Demo Clients

- [ ] Mark demo clients as `is_active = False`:
  ```sql
  UPDATE CLIENT SET is_active = 0
  WHERE client_id IN ('ACME-MFG', 'TEXTILE-PRO', 'FASHION-WORKS',
    'QUALITY-STITCH', 'GLOBAL-APPAREL', 'DEMO-001', 'TEST-001', 'SAMPLE-001');
  ```
- [ ] Create the client's production `client_id` and `client_name` via Admin UI
- [ ] Verify demo client data is invisible in all views (filtered by `is_active` and `client_id`)
- [ ] Demo clients remain in the database for reference but don't appear in dropdowns or queries

### 0.6 Verification

- [ ] No demo user can authenticate (all inactive)
- [ ] No demo client appears in client selectors (all inactive)
- [ ] Production admin can log in and manage users
- [ ] At least one real operator can log in and submit a production entry
- [ ] Audit log shows the new admin's user_id (not demo user IDs)
- [ ] `SECRET_KEY` is rotated (no demo JWT can be reused)

---

## PHASE 1: MariaDB Migration Hardening

### 1.1 Pre-Migration Validation

Execute the SQLite-to-MariaDB migration against a staging MariaDB instance and verify:

- [ ] All 45 tables created with correct InnoDB engine, utf8mb4 charset
- [ ] All foreign key constraints intact after migration
- [ ] Row counts match between SQLite source and MariaDB target (use `DataMigrator.verify_migration()`)
- [ ] Boolean conversion correct (SQLite 0/1 to MariaDB TINYINT)
- [ ] DateTime conversion correct (SQLite string to MariaDB DATETIME, timezone-aware)
- [ ] JSON columns preserved (capacity scenarios, event payloads)
- [ ] Decimal precision preserved (KPI percentages, SAM times)
- [ ] NULL handling consistent across all columns
- [ ] Migration wizard UI shows accurate progress (poll endpoint returns correct table counts)
- [ ] Provider state file (`database/provider_state.json`) correctly records the switch

### 1.2 Connection Pool Tuning

Review and adjust QueuePool settings for the client's expected concurrent users:

- [ ] `DATABASE_POOL_SIZE` — base pool size (default 20, adjust per expected concurrent sessions)
- [ ] `DATABASE_MAX_OVERFLOW` — overflow connections (default 10)
- [ ] `DATABASE_POOL_TIMEOUT` — wait timeout (default 30s)
- [ ] `DATABASE_POOL_RECYCLE` — connection recycle interval (default 3600s, MariaDB `wait_timeout` alignment)
- [ ] `pool_pre_ping=True` confirmed (validates connections before checkout)
- [ ] Test under concurrent load: 10-50 simultaneous API requests, verify no connection exhaustion

### 1.3 Schema Migration Tooling (Alembic)

For schema changes after go-live, data cannot be regenerated — it's real production data:

- [ ] Install Alembic (`pip install alembic`)
- [ ] Initialize with `alembic init` pointing to existing SQLAlchemy Base
- [ ] Generate initial migration from current schema (`alembic revision --autogenerate -m "initial"`)
- [ ] Test upgrade/downgrade cycle on staging MariaDB
- [ ] Add `alembic upgrade head` to deployment scripts
- [ ] Document migration workflow: create revision → test on staging → deploy to production

---

## PHASE 2: Redis Integration

### 2.1 Token Blacklist (Persistent)

Replace in-memory token blacklist with Redis-backed storage:

- [ ] Add `redis` to `requirements.txt`
- [ ] Create `backend/cache/redis_client.py` with connection pool
- [ ] Modify `backend/auth/jwt.py`:
  - `blacklist_token(jti)` → `redis.setex(f"blacklist:{jti}", ttl=ACCESS_TOKEN_EXPIRE_MINUTES*60, value=1)`
  - `is_token_blacklisted(jti)` → `redis.exists(f"blacklist:{jti}")`
- [ ] Graceful fallback: if Redis unavailable, log warning and deny (fail-closed)
- [ ] Add Redis health check to `/health/` endpoint
- [ ] Add `REDIS_URL` environment variable (default `redis://localhost:6379/0`)

### 2.2 Rate Limiting (Persistent)

Replace in-memory slowapi storage with Redis-backed:

- [ ] Modify `backend/middleware/rate_limit.py`:
  - Replace `MemoryStorage` with `RedisStorage(REDIS_URL)`
- [ ] Rate limits survive server restarts
- [ ] Rate limits shared across multiple backend instances (if load-balanced)
- [ ] Test: hit rate limit, restart server, verify limit still enforced

### 2.3 Session Cache (Optional)

For frequently accessed data that doesn't change often:

- [ ] Cache client configuration lookups (TTL: 5 minutes)
- [ ] Cache KPI threshold lookups (TTL: 10 minutes)
- [ ] Cache user permissions (TTL: 2 minutes, invalidate on role change)
- [ ] Add cache invalidation on write operations

---

## PHASE 3: Observability

### 3.1 Error Tracking

- [ ] Integrate Sentry (or equivalent):
  - `pip install sentry-sdk[fastapi]`
  - Initialize in `backend/main.py` with DSN from environment
  - Frontend: `npm install @sentry/vue` and initialize in `main.js`
- [ ] Configure error grouping and alerting rules
- [ ] Set up Slack/email notifications for unhandled exceptions
- [ ] Verify PII scrubbing (no passwords, tokens, or client data in error reports)

### 3.2 Structured Logging

- [ ] Replace `logging.getLogger()` with structured JSON logging:
  - Add `python-json-logger` to requirements
  - Configure in `backend/config.py` with JSON formatter
  - Include: timestamp, level, module, request_id, client_id, user_id
- [ ] Log rotation: configure max file size and retention
- [ ] Centralized collection: forward to client's log aggregation system (ELK, CloudWatch, etc.)
- [ ] Add request_id middleware for request tracing across logs

### 3.3 Health Checks (Production-Grade)

Enhance existing health endpoints:

- [ ] `/health/live` — liveness probe (already exists, keep lightweight)
- [ ] `/health/ready` — readiness probe: check DB connection + Redis connection + pool utilization
- [ ] `/health/deep` — deep health: run a test query, verify table existence, check disk space
- [ ] Add response time to health check responses
- [ ] Configure alerting: page if `/health/ready` fails for 3 consecutive checks

### 3.4 Metrics (Optional)

If the client needs performance dashboards:

- [ ] Add Prometheus metrics endpoint (`/metrics`)
- [ ] Track: request latency (p50/p95/p99), active connections, error rate, cache hit ratio
- [ ] Frontend: track page load times, API response times via Performance API

---

## PHASE 4: Backup & Recovery

### 4.1 Database Backup

- [ ] Automated daily backup: `mysqldump` or MariaDB `mariabackup`
- [ ] Backup retention: 30 days rolling
- [ ] Backup verification: weekly restore to staging, run health check
- [ ] Point-in-time recovery: enable MariaDB binary logging
- [ ] Document RTO (Recovery Time Objective) and RPO (Recovery Point Objective)

### 4.2 Application State Backup

- [ ] Back up `database/provider_state.json` (migration history)
- [ ] Back up `.env` and deployment configuration
- [ ] Back up Redis data (if using AOF persistence)
- [ ] Document rollback procedure: how to revert to previous application version

### 4.3 Disaster Recovery Plan

- [ ] Document step-by-step recovery from:
  - Database corruption
  - Server failure
  - Redis failure (application should continue with degraded rate limiting)
  - Network partition between app and database
- [ ] Test recovery procedure on staging quarterly

---

## PHASE 5: Deployment Hardening

### 5.1 Docker Production Configuration

- [ ] Verify Dockerfile uses multi-stage build with non-root user (already done)
- [ ] Add `VITE_API_URL` as build ARG in frontend Dockerfile
- [ ] Configure nginx `server_name _` (catch-all) instead of `localhost`
- [ ] Remove HSTS from HTTP-only server block (or add HTTPS)
- [ ] Add Content-Security-Policy header to nginx config
- [ ] Set resource limits in docker-compose: `mem_limit`, `cpus`

### 5.2 Environment Configuration

- [ ] `SECRET_KEY` — generate 64+ character random key, store securely
- [ ] `DEBUG=False` — enforced by `validate_production_config()`
- [ ] `CORS_ORIGINS` — set to production domain only (no localhost)
- [ ] `DATABASE_URL` — MariaDB connection string
- [ ] `REDIS_URL` — Redis connection string
- [ ] `SENTRY_DSN` — error tracking endpoint
- [ ] All secrets via environment variables or secret manager (never in files)

### 5.3 TLS/HTTPS

- [ ] Obtain TLS certificate (Let's Encrypt or client-provided)
- [ ] Configure nginx HTTPS server block with TLS 1.2+ only
- [ ] Enable HSTS header (after HTTPS is confirmed working)
- [ ] Redirect HTTP to HTTPS
- [ ] Test with SSL Labs (aim for A+ rating)

---

## PHASE 6: Performance Baseline

### 6.1 Load Testing

Before go-live, establish performance baselines:

- [ ] Tool: `locust` or `k6` with realistic user scenarios
- [ ] Test scenarios:
  - 10 concurrent users submitting production entries
  - 5 users loading KPI dashboards simultaneously
  - 1 user running capacity planning while 10 do data entry
  - Bulk CSV upload (1000 rows) during normal operations
- [ ] Measure: response times (p50/p95/p99), error rate, DB connection utilization
- [ ] Document acceptable thresholds (e.g., p95 < 500ms for dashboards)

### 6.2 Database Optimization

- [ ] Run `EXPLAIN` on top 10 most frequent queries
- [ ] Add indexes for common filter patterns (client_id + date range)
- [ ] Verify MariaDB query cache configuration
- [ ] Set `innodb_buffer_pool_size` to 70-80% of available RAM

---

## Execution Order

| Phase | Blocks | Dependency |
|-------|--------|------------|
| Phase 0 (Credentials) | Go-live | Phase 1 complete (migration done) |
| Phase 1 (MariaDB) | Phase 0 | Client provides MariaDB credentials |
| Phase 2 (Redis) | Go-live | Redis instance provisioned |
| Phase 3 (Observability) | Parallel | Can start immediately |
| Phase 4 (Backup) | Go-live | MariaDB + Redis configured |
| Phase 5 (Deployment) | Go-live | All infrastructure ready |
| Phase 6 (Performance) | Go-live | Application deployed to staging |

**Critical path:** Phase 1 → Phase 0 → Phase 2 → Phase 5 → Phase 6 → Go-live
**Parallel track:** Phase 3 + Phase 4 (can run alongside Phases 1-2)

---

## Gate Criteria

The application is production-ready when ALL of these are true:

- [ ] All demo users and demo clients marked inactive (no known credentials active)
- [ ] Production admin account created with strong credentials
- [ ] SECRET_KEY rotated (all demo JWTs invalidated)
- [ ] MariaDB migration verified on staging (row counts match, no data loss)
- [ ] Redis token blacklist + rate limiting functional
- [ ] Error tracking capturing and alerting on unhandled exceptions
- [ ] Health checks returning accurate readiness status
- [ ] Automated daily backups running and verified
- [ ] TLS/HTTPS configured with A+ SSL Labs rating
- [ ] Load test confirms p95 < 500ms for dashboard views under expected load
- [ ] Disaster recovery procedure documented and tested
- [ ] All CI checks passing (backend-tests, frontend-lint-and-tests, docker-build)
- [ ] `validate_production_config()` passes with no warnings
