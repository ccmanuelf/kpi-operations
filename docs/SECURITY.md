# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it privately:

1. Do NOT open a public GitHub issue
2. Email: security@novalink.com
3. Include: description, reproduction steps, and impact assessment

## Response Timeline

- Acknowledgment: within 48 hours
- Assessment: within 7 days
- Fix deployment: based on severity

## Security Practices

- All data access is filtered by `client_id` for multi-tenant isolation
- JWT tokens with configurable expiry (default 30 minutes)
- Role-based access control: Admin, PowerUser, Leader, Operator
- Input validation via Pydantic models on all API endpoints
- SQL injection prevention via SQLAlchemy ORM (no raw SQL in routes)
- CORS restricted to configured origins
- Security headers: CSP, HSTS, X-Frame-Options, X-Content-Type-Options

## JWT Authentication Flow

1. **Login**: Client sends `POST /api/auth/login` with username and password. Server validates credentials with bcrypt, generates a JWT access token signed with HS256, and returns it in the response body.

2. **Authenticated requests**: Client includes the token in the `Authorization: Bearer <token>` header on every subsequent request. The `get_current_user` dependency validates the token signature, checks expiry, and extracts the user identity.

3. **Token expiry**: Access tokens expire after 30 minutes by default (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` in config). There is no refresh token; the client must re-authenticate after expiry.

4. **Logout**: `POST /api/auth/logout` adds the token's JTI to an in-memory blacklist. Blacklisted tokens are rejected by the authentication middleware even if they have not expired.

5. **Password management**: `POST /api/auth/change-password` for authenticated users; `POST /api/auth/forgot-password` and `POST /api/auth/reset-password` for recovery flows. Passwords are hashed with bcrypt before storage.

## CORS Configuration

CORS is configured in `backend/main.py` via FastAPI's `CORSMiddleware`:

- **Allowed origins**: Configured via `CORS_ORIGINS` environment variable (comma-separated list). Defaults to `http://localhost:5173` (Vite dev server) in development.
- **Allowed methods**: All methods (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `OPTIONS`).
- **Allowed headers**: All headers (including `Authorization`).
- **Credentials**: Enabled (`allow_credentials=True`) to support cookie-based sessions if needed.
- **Production**: Set `CORS_ORIGINS` to the exact production frontend domain(s). Never use `*` with credentials enabled.

## Rate Limiting

| Endpoint Category | Limit |
|-------------------|-------|
| Authentication (`/api/auth/*`) | 5 requests/minute |
| API endpoints | 100 requests/minute |
| CSV upload | 10 requests/minute |
| Report generation | 5 requests/minute |

Rate limit headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`) are included in responses.

## Security Headers

The following headers are set via middleware on all responses:

| Header | Value | Purpose |
|--------|-------|---------|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'` | Prevent XSS by restricting resource origins |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force HTTPS in production |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer information leakage |

## Known Limitations

1. **Token storage**: The frontend stores the JWT access token in `localStorage`. This is vulnerable to XSS attacks. A future improvement would be to use `httpOnly` cookies with `SameSite=Strict`.

2. **No refresh tokens**: When the access token expires, the user must log in again. Long sessions require re-authentication.

3. **In-memory token blacklist**: The logout blacklist is stored in application memory and is lost on server restart. A Redis-backed blacklist is recommended for production.

4. **Default SECRET_KEY**: The `config.py` file contains a default `SECRET_KEY` value used for JWT signing. This MUST be overridden via the `SECRET_KEY` environment variable in production.

5. **Rate limiting scope**: Rate limits are per-process. In a multi-worker deployment without shared state, each worker tracks limits independently. Consider a Redis-backed rate limiter for production.

6. **No CSRF protection**: Since the API uses Bearer token authentication (not cookies), CSRF is not applicable for API requests. However, if cookie-based auth is added in the future, CSRF tokens will be required.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
