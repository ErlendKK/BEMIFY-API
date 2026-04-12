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
- Modern TLS configuration (TLS 1.2+)

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

## Supported Versions

This API is a single continuously deployed service. Security fixes are applied to the current production version.

| Version              | Supported |
| -------------------- | --------- |
| Current (production) | Yes       |
| Previous versions    | No        |
