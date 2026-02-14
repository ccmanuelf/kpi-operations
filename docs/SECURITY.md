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

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
