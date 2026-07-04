# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in the Bemify Simulation API, please report it responsibly.

**Email:** [erlend@bemify.no](mailto:erlend@bemify.no)

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### What to expect

- Acknowledgment within **2 business days**
- Status update within **5 business days**
- We will work with you to understand and resolve the issue before any public disclosure

Please do **not** open a public GitHub issue for security vulnerabilities.

There is no formal bug bounty program at this time.

## Scope

### In scope

- The Bemify Simulation API (`api.bemify.no`)
- Authentication and authorization mechanisms
- Input validation and file handling
- Data exposure or leakage

### Out of scope

- The Bemify web application (`app.bemify.no`)
- The marketing site (`bemify.no`)
- Third-party dependencies (report these to the upstream project)
- Denial-of-service attacks (we have rate limiting in place; please do not test this against production)

## Security Measures

The following security measures are in place:

### Transport security

- All traffic is encrypted via TLS (HTTPS enforced, HTTP redirected)
- TLS 1.2+ with forward secrecy (ECDHE key exchange)
- Automatic certificate management via Let's Encrypt
- OCSP stapling enabled by default

### Authentication

- API access requires a Bearer token in the `Authorization` header
- Tokens are cryptographically generated using a CSPRNG (`crypto.randomBytes`)
- Tokens are stored as SHA-256 hashes -- plaintext tokens are never persisted
- Tokens are validated server-side on every authenticated request

### Rate limiting

- Global rate limiting per IP address
- Per-API-key rate limiting on simulation and polling endpoints
- Per-API-key limits on concurrent active jobs
- Queue depth limits to prevent resource exhaustion

### Input validation

- File uploads restricted to allowed extensions (`.sxi`, `.epw`)
- File size limits enforced
- Upload count limits per request
- Simulation type restricted to an allowlist of valid values
- sxi files are parsed with [fast-xml-parser](https://github.com/NaturalIntelligence/fast-xml-parser),
  a pure JavaScript XML parser that never fetches external resources (no file://, http://,
  or external DTD loading), eliminating classic XXE file-disclosure and SSRF vectors.
  Internal entity expansion is bounded by the parser's built-in limits to prevent
  billion-laughs style DoS.
- The import pipeline only extracts a fixed set of known fields from the parsed XML; unrecognized elements (including any file path references) are silently discarded. No filesystem access is performed based on uploaded file contents.
- All SQL queries use parameterized statements

### HTTP security

- Security headers set via [helmet](https://helmetjs.github.io/) (CSP, HSTS, X-Frame-Options, etc.)
- CORS restricted to specific allowed origins
- Tokens transmitted in headers only, never in URLs

### Data isolation

- Simulation jobs are isolated per API key -- users can only access their own jobs
- Cross-key job access returns 404 (no information leakage)
- Error messages to clients are generic; detailed errors are logged server-side only

### Data handling

- Uploaded files are held in memory only and never written to disk
- Simulation results are held in memory with a short time-to-live and automatically deleted
- No end-user personal data is processed -- only building energy model data

### Monitoring

- All HTTP requests are logged with IP address, method, path, status code, and user agent
- Failed authentication attempts and rate limit violations are logged with IP, endpoint, and timestamp
- Request bodies and Authorization headers are never logged
- Security logs are retained for 30 days, then automatically purged (aligned with data minimization principles)
- Availability monitoring via UptimeRobot with alerts on downtime
- Security events are reviewed via an authenticated admin dashboard (`/admin/security`), gated by Supabase JWT and a hard-coded admin user allowlist. The dashboard groups events per IP with heuristic classification (noise / normal / suspicious) to surface anomalies. CLI tooling (`manage-keys.ts logs`) remains available for deeper forensics.
- Application-level exceptions are captured via PostHog and surfaced in the same admin dashboard (`/admin/errors`)


## Supported Versions

This API is a single continuously deployed service. Security fixes are applied to the current production version.

| Version              | Supported |
| -------------------- | --------- |
| Current (production) | Yes       |
| Previous versions    | No        |
