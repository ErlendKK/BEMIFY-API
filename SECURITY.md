# Security Policy

Bemify takes the security of its software and services seriously. This document
explains how to report vulnerabilities and gives a high-level overview of how
the Bemify Simulation API (`api.bemify.no`) is built and operated.

## Reporting a vulnerability

If you believe you have found a security vulnerability in the Bemify Simulation
API or any related code in this repository, please report it privately.

**Email:** security@bemify.no (fallback: erlend@bemify.no)

Please include:

- A description of the issue and its potential impact
- Steps to reproduce, or a proof of concept
- Any relevant logs, requests, or screenshots
- Your name and how you would like to be credited (optional)

**Please do not** open a public GitHub issue, discuss the vulnerability in
public forums, or test against production systems in ways that could affect
other users.

### What to expect

| Stage | Target |
|-------|--------|
| Acknowledgement of report | Within 3 business days |
| Initial assessment | Within 7 business days |
| Status updates | At least every 14 days until resolved |
| Coordinated disclosure | By mutual agreement, typically after a fix is deployed |

Bemify does not currently run a paid bug bounty program, but we are happy to
publicly credit researchers who report issues responsibly.

## Supported versions

The Bemify Simulation API is operated as a hosted service at `api.bemify.no`.
Only the currently deployed version is supported. There are no long-term
support branches or self-hosted releases at this time.

## Scope

In scope for security reports:

- The `api.bemify.no` HTTP API and its endpoints
- Code in this repository under `src/server/`
- Authentication and authorization logic
- Handling of uploaded `.sxi` and `.epw` files

Out of scope:

- The Bemify web app (`app.bemify.no`) and its Supabase backend
- The marketing site (`bemify.no`)
- Third-party services and infrastructure providers
- Denial-of-service tests against production
- Social engineering of Bemify staff or customers
- Findings from automated scanners without a demonstrated impact

## Security overview

The API is designed and operated according to established web application
security practices. Internally, the system is reviewed against:

- **OWASP ASVS 4.0** Level 1 verification requirements
- **OWASP API Security Top 10** (2023)
- **STRIDE** threat modeling per component

### Authentication and authorization

- All simulation endpoints require a Bearer token in the `Authorization` header
- Tokens are generated using a cryptographically secure random source
- Only SHA-256 hashes of tokens are stored server-side
- Each job is bound to the API key that created it; cross-key access is denied
- There is a single role; there are no privilege escalation paths within the API

### Transport and network

- All public traffic is served over HTTPS with automatic certificate management
- TLS 1.2 or higher with modern cipher suites
- CORS is restricted to a small allowlist of Bemify-owned origins
- Standard security headers are set on all responses

### Input handling

- Uploaded files are limited to `.sxi` and `.epw` extensions
- Maximum file size is 10 MB per file, 2 files per request
- Uploaded files are held in memory only and never written to disk
- Request parameters are validated against allowlists where applicable
- All database queries use parameterized statements

### Resource protection

- Global IP-based rate limiting on all endpoints
- Per-key rate limiting on authenticated endpoints
- Global queue cap and per-key concurrent job cap
- Simulations run in isolated worker threads with execution timeouts
- Long-running or pathological jobs can be terminated without affecting the
  rest of the service

### Data handling

- API key metadata and SHA-256 hashes are stored in a local SQLite database
- Simulation logs contain only metadata (filenames, durations, status), not
  model contents
- Simulation results are kept in memory for 30 minutes after completion, then
  discarded
- No end-user personal data is processed by the API; data subjects are limited
  to business contacts at customer organizations

For details on data processing under GDPR, please contact erlend@bemify.no.

### Operations

- Runs as a low-privilege OS user behind a reverse proxy
- Process supervisor restarts the service on failure
- Dependencies are reviewed periodically for known vulnerabilities
- Incident response procedures are documented internally and include
  notification of affected customers within 72 hours where required by GDPR
  Art. 33

## Disclosure policy

Bemify follows coordinated disclosure. Once a report is received:

1. We confirm and reproduce the issue
2. We develop and deploy a fix
3. We agree on a public disclosure date with the reporter
4. We publish a brief advisory if the issue affected production users

We aim to fix high-severity issues within 30 days of confirmation.

## Changes to this policy

This policy may be updated as the service evolves. The current version is
always available at the root of this repository.
