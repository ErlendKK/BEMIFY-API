# Security

This document describes the current security posture of the Bemify Simulation API
(`api.bemify.no`). It is intended as a working document — the goal is an honest
snapshot of what is implemented, what is not, and what the known risks are.

The structure follows:

- **OWASP ASVS 4.0 Level 1** — verification checklist
- **STRIDE** — threat modeling per component
- **OWASP API Security Top 10 (2023)** — API-specific risks

Last reviewed: _<fill in date>_
Reviewer: _<fill in name>_

---

## 1. Scope

| Item                | Value                                                                                     |
| ------------------- | ----------------------------------------------------------------------------------------- |
| System              | Bemify Simulation API                                                                     |
| Hostname            | `api.bemify.no`                                                                           |
| Stack               | Node 20, Express 4, better-sqlite3, Caddy (TLS), pm2                                      |
| Host                | Contabo VPS, Ubuntu, single instance                                                      |
| Data classification | API keys (secret), customer model files (confidential), simulation results (confidential) |
| Users               | Authenticated B2B customers via API key                                                   |
| Out of scope        | Bemify web app (`app.bemify.no`), Supabase backend, marketing site                        |

---

## 2. Architecture and trust boundaries

```
┌─────────────────────────────────────────────────────────────┐
│ UNTRUSTED — public internet                                 │
│   API clients (curl, Python, customer scripts)              │
└─────────────────────────────────────────────────────────────┘
                            │ HTTPS (TLS 1.2+)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ TRUST BOUNDARY 1 — TLS termination                          │
│   Caddy reverse proxy (auto Let's Encrypt)                  │
└─────────────────────────────────────────────────────────────┘
                            │ HTTP loopback
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ TRUST BOUNDARY 2 — application                              │
│   Express app (port 3001)                                   │
│   ├── helmet, CORS allowlist, rate limit                    │
│   ├── multer (memory, 10 MB cap, .sxi/.epw filter)          │
│   ├── requireAuth (Bearer → SHA-256 → SQLite lookup)        │
│   ├── parseSxi / parseEpw / fetchClimateByKlimasted         │
│   └── enqueueSimulation → FIFO queue + per-key quotas       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ TRUST BOUNDARY 3 — calculation engine                       │
│   worker_threads adapter + SimulationWorker                 │
│   Reads packed ProjectNode + climate data, returns          │
│   aggregated result. Pure computation, no I/O.              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ TRUST BOUNDARY 4 — persistence                              │
│   SQLite (data/bemify-api.sqlite, WAL mode)                 │
│   ├── api_keys (SHA-256 hashes only)                        │
│   └── simulation_logs (metadata only, no model contents)    │
└─────────────────────────────────────────────────────────────┘
```

**Key trust assumptions:**

- The VPS host is trusted. Anyone with shell access to the `bemify` user can
  read API key hashes, all simulation logs, and uploaded model files in memory
  during processing.
- Caddy is trusted to terminate TLS correctly and forward client IP headers.
- The `SimulationWorker` is trusted code (Bemify-authored) and runs in a worker
  thread, not a separate OS sandbox.
- SXI and EPW files from authenticated clients are treated as untrusted input
  but not malicious — there is no virus scan or sandboxing of parsing.

---

## 3. Threat model (STRIDE)

| Component                           | Spoofing                                               | Tampering                                                                                                                          | Repudiation                                                 | Info disclosure                                                                                              | DoS                                                                     | Elevation                         |
| ----------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------- | --------------------------------- |
| Caddy → Express                     | TLS protects identity                                  | TLS protects in transit                                                                                                            | n/a                                                         | TLS protects in transit                                                                                      | Caddy connection limits                                                 | n/a                               |
| `requireAuth`                       | Bearer token, SHA-256 lookup. ⚠ No rotation, no expiry | n/a                                                                                                                                | ⚠ Limited audit log (only simulation events, not key admin) | Token never logged. Constant-time comparison not used (SHA-256 lookup is acceptable for high-entropy tokens) | Global IP rate limit + per-key limits on authenticated routes           | Key cannot escalate — single role |
| `multer` upload                     | n/a                                                    | File extension + size enforced                                                                                                     | n/a                                                         | Files held in memory only, not written to disk                                                               | 10 MB cap, max 2 files. ⚠ No total memory cap across concurrent uploads | n/a                               |
| `parseSxi` / `parseEpw`             | n/a                                                    | ⚠ Parsers trust input structure. Malformed files may throw, but not audited for parser-level vulns (zip bombs, XML bombs in gbXML) | n/a                                                         | Parse errors return generic message to client                                                                | ⚠ Pathological files may cause slow parsing                             | n/a                               |
| `enqueueSimulation`                 | Job ownership tied to API key ID                       | n/a                                                                                                                                | Each job logged to SQLite at enqueue + completion           | Job results scoped per API key (404 on cross-key access)                                                     | Global queue cap 20 + per-key active-job cap 3                          | n/a                               |
| `SimulationWorker`                  | n/a                                                    | Pure function on parsed input                                                                                                      | n/a                                                         | n/a                                                                                                          | Timeout + `worker.terminate()` limits impact of pathological jobs       | n/a                               |
| SQLite                              | n/a                                                    | File permissions (Unix). ⚠ No integrity checks, no encryption at rest                                                              | Logs cannot be modified by API users (no API surface)       | File readable by `bemify` Unix user only                                                                     | WAL mode handles concurrent reads                                       | n/a                               |
| `/health`, `/queue`, `/klimasteder` | n/a                                                    | Read-only                                                                                                                          | n/a                                                         | ⚠ Exposes queue depth and processing state to anyone                                                         | Subject to global rate limit                                            | n/a                               |

⚠ = known gap, see section 6.
⚠⚠ = critical, see section 6.

---

## 4. OWASP ASVS 4.0 Level 1 checklist

Status legend: ✅ implemented · ⚠ partial · ❌ missing · n/a not applicable

### V1 — Architecture, Design and Threat Modeling

| ID    | Requirement                                     | Status | Notes                                                |
| ----- | ----------------------------------------------- | ------ | ---------------------------------------------------- |
| 1.1.1 | SDLC with security considerations               | ⚠      | Informal; this document is the first formal artifact |
| 1.1.2 | Threat modeling for each design change          | ⚠      | First STRIDE pass in this document                   |
| 1.2.1 | Unique low-privilege OS account                 | ✅     | Runs as `bemify` user via pm2                        |
| 1.2.2 | Authenticated communications between components | ✅     | Caddy → Express on loopback only                     |
| 1.4.1 | Trusted enforcement points                      | ✅     | All auth in `requireAuth` middleware                 |

### V2 — Authentication

| ID     | Requirement                                            | Status | Notes                                                         |
| ------ | ------------------------------------------------------ | ------ | ------------------------------------------------------------- |
| 2.1.1  | Passwords ≥ 12 chars                                   | n/a    | Token-based auth, no passwords                                |
| 2.2.1  | Anti-automation against brute force                    | ✅     | Global IP rate limit + per-key limits on authenticated routes |
| 2.5.4  | No default/shared accounts                             | ✅     | Each API key is unique, manually issued                       |
| 2.6.1  | Lookup secrets generated with CSPRNG                   | ✅     | `crypto.randomBytes(24)`                                      |
| 2.6.2  | Lookup secrets stored hashed                           | ✅     | SHA-256, sufficient for high-entropy tokens                   |
| 2.10.1 | API keys not transmitted in URL                        | ✅     | Authorization header only                                     |
| 2.10.4 | Secrets stored using approved cryptographic protection | ✅     | SHA-256 hashes only in DB                                     |

### V3 — Session Management

| ID  | Requirement        | Status | Notes                      |
| --- | ------------------ | ------ | -------------------------- |
| 3.x | Session management | n/a    | Stateless API, no sessions |

### V4 — Access Control

| ID    | Requirement                                       | Status | Notes                                   |
| ----- | ------------------------------------------------- | ------ | --------------------------------------- |
| 4.1.1 | Trusted enforcement of access control             | ✅     | Middleware on all sensitive routes      |
| 4.1.2 | User/data attributes verified server-side         | ✅     | `apiKeyId` checked in `GET /job/:jobId` |
| 4.1.3 | Principle of least privilege                      | ✅     | Single role; jobs isolated by key ID    |
| 4.1.5 | Access control fails securely                     | ✅     | Default deny on missing/invalid token   |
| 4.2.1 | No direct object reference vulnerabilities (BOLA) | ✅     | Cross-key job access returns 404        |

### V5 — Validation, Sanitization and Encoding

| ID    | Requirement                              | Status | Notes                                                                                                    |
| ----- | ---------------------------------------- | ------ | -------------------------------------------------------------------------------------------------------- |
| 5.1.1 | Input validation enforced server-side    | ⚠      | File extension + size + simuleringstype enum. SXI/EPW content validated by parsers but no schema fuzzing |
| 5.1.3 | Allowlist validation where possible      | ✅     | Klimasted, simuleringstype, file extensions all allowlisted                                              |
| 5.1.4 | Structured data validated against schema | ⚠      | Parsers throw on malformed input but no formal schema validation                                         |
| 5.2.1 | Sanitize untrusted HTML                  | n/a    | No HTML output                                                                                           |
| 5.3.4 | Parameterized SQL queries                | ✅     | All queries use `db.prepare(...)` with bound parameters                                                  |

### V7 — Error Handling and Logging

| ID    | Requirement                          | Status | Notes                                                                                        |
| ----- | ------------------------------------ | ------ | -------------------------------------------------------------------------------------------- |
| 7.1.1 | No sensitive data in logs            | ✅     | Tokens never logged; only key ID and metadata                                                |
| 7.1.2 | No sensitive data in error responses | ⚠      | Parsing/fetch errors are generic, men simuleringsjobber returnerer fortsatt worker-feiltekst |
| 7.4.1 | Generic error messages to clients    | ⚠      | Route handlers er generiske, men `/job/:jobId` kan fortsatt returnere intern feilmelding     |
| 7.4.2 | Last-resort error handler            | ✅     | Express error middleware in `index.ts`                                                       |
| 7.4.3 | Detailed errors logged server-side   | ✅     | `console.error` with full message                                                            |

### V8 — Data Protection

| ID    | Requirement                           | Status | Notes                               |
| ----- | ------------------------------------- | ------ | ----------------------------------- |
| 8.2.1 | No sensitive data cached client-side  | n/a    | API does not control client caching |
| 8.3.1 | Sensitive data sent in body, not URL  | ✅     | Model files in multipart body       |
| 8.3.4 | Authentication credentials not in URL | ✅     | Header only                         |

### V9 — Communication

| ID    | Requirement                     | Status | Notes                                           |
| ----- | ------------------------------- | ------ | ----------------------------------------------- |
| 9.1.1 | TLS for all client connectivity | ✅     | Caddy enforces HTTPS, redirects HTTP            |
| 9.1.2 | Strong TLS configuration        | ✅     | Caddy defaults (TLS 1.2+, modern cipher suites) |
| 9.2.1 | TLS for all backend connections | n/a    | All backend on loopback                         |

### V10 — Malicious Code

| ID     | Requirement                                        | Status | Notes                                                              |
| ------ | -------------------------------------------------- | ------ | ------------------------------------------------------------------ |
| 10.3.2 | Application integrity verification                 | ⚠      | No subresource integrity, no signed releases. Deploy is `git pull` |
| 10.3.3 | Application protections against subdomain takeover | ✅     | DNS controlled directly                                            |

### V11 — Business Logic

| ID     | Requirement                                      | Status | Notes                                            |
| ------ | ------------------------------------------------ | ------ | ------------------------------------------------ |
| 11.1.4 | Anti-automation for sensitive operations         | ✅     | Global IP limiter + per-key authenticated limits |
| 11.1.6 | Business limits enforced (e.g., max queued jobs) | ✅     | Global queue cap 20 + per-key cap 3              |

### V12 — Files and Resources

| ID     | Requirement                                           | Status | Notes                                                                                |
| ------ | ----------------------------------------------------- | ------ | ------------------------------------------------------------------------------------ |
| 12.1.1 | Maximum upload size enforced                          | ✅     | 10 MB per file, 2 files max                                                          |
| 12.1.2 | File content validated against expected type          | ⚠      | Extension check only, no magic-byte validation                                       |
| 12.3.1 | User-supplied filenames not used for filesystem ops   | ✅     | Files held in memory; filenames sanitized for logging                                |
| 12.4.1 | Files from untrusted sources scanned for malware      | ❌     | Not implemented. Acceptable risk: files are never executed and never written to disk |
| 12.5.1 | Web tier configured to serve only intended file types | ✅     | API returns JSON only                                                                |

### V13 — API and Web Service

| ID     | Requirement                                            | Status | Notes                               |
| ------ | ------------------------------------------------------ | ------ | ----------------------------------- |
| 13.1.1 | All API components have the same security controls     | ✅     | Single Express app                  |
| 13.1.3 | API URLs do not expose sensitive information           | ✅     | Job IDs are opaque                  |
| 13.1.5 | Requests with unexpected/missing content type rejected | ✅     | multer + express.json enforce types |
| 13.2.1 | Enabled HTTP methods are appropriate                   | ✅     | Only GET and POST used              |
| 13.2.2 | JSON schema validation in place                        | ❌     | Body parameters validated ad-hoc    |
| 13.2.3 | CSRF protection for state-changing requests            | n/a    | Bearer token auth, no cookies       |

### V14 — Configuration

| ID     | Requirement                        | Status | Notes                                                          |
| ------ | ---------------------------------- | ------ | -------------------------------------------------------------- |
| 14.1.1 | Build process is repeatable        | ⚠      | Runs from source via `tsx`, no build step                      |
| 14.2.1 | All components up to date          | ⚠      | No automated dependency scanning. Run `npm audit` periodically |
| 14.3.2 | Debug modes disabled in production | ✅     | No debug flags exposed                                         |
| 14.4.1 | HTTP response headers (security)   | ✅     | helmet defaults applied                                        |
| 14.4.3 | Content Security Policy            | ⚠      | helmet default, not tuned (low impact for JSON API)            |
| 14.5.2 | CORS configuration restrictive     | ✅     | Allowlist of two origins                                       |

---

## 5. OWASP API Security Top 10 (2023) mapping

| Risk                                                   | Status | Mitigation                                                                |
| ------------------------------------------------------ | ------ | ------------------------------------------------------------------------- |
| API1 — Broken Object Level Authorization (BOLA)        | ✅     | Job lookup checks `apiKeyId` ownership                                    |
| API2 — Broken Authentication                           | ⚠      | No token rotation and no expiry, but per-key rate limit is in place       |
| API3 — Broken Object Property Level Authorization      | n/a    | No partial-object access patterns                                         |
| API4 — Unrestricted Resource Consumption               | ⚠      | Worker timeout/terminate reduces impact; climate cache is still unbounded |
| API5 — Broken Function Level Authorization             | ✅     | Single role, all routes either public or authenticated                    |
| API6 — Unrestricted Access to Sensitive Business Flows | ✅     | Per-key throttling and queue quota implemented                            |
| API7 — Server Side Request Forgery                     | ✅     | `fetchClimateByKlimasted` only fetches from allowlist of known names      |
| API8 — Security Misconfiguration                       | ⚠      | helmet defaults; no formal hardening review                               |
| API9 — Improper Inventory Management                   | ✅     | Single endpoint, documented in README                                     |
| API10 — Unsafe Consumption of APIs                     | ✅     | Only consumes own climate service                                         |

---

## 6. Known weaknesses

Carried over from internal architecture notes, with severity and mitigation status.

### MEDIUM — Climate cache without TTL or LRU eviction

`climateCache` in `parsers.ts` grows unbounded. Bounded in practice by ~50
valid locations (~200 MB worst case), but fragile.

**Mitigation:** Add LRU cap (e.g. 20 entries) or 1 h TTL.

**Status:** Not mitigated.

### LOW — Simulation worker is trusted, not sandboxed

Simulation now runs in `worker_threads`, so the main Express thread stays
responsive and long-running jobs can be terminated. The worker still runs
Bemify code inside the same Node process boundary and is not an OS-level
sandbox.

**Mitigation:** Accept current risk, or isolate further with child process /
container if stronger separation is required.

**Status:** Accepted risk.

### LOW — `/health` and `/queue` are unauthenticated

Expose queue depth and processing state. Useful for monitoring (UptimeRobot)
but also reveals load patterns to anyone.

**Mitigation:** Optional shared secret for `/queue`; leave `/health` open for
uptime monitoring.

**Status:** Accepted risk.

### LOW — Simulation results stored in process memory

50 jobs × ~100 KB ≈ 5 MB, cleared after 30 minutes. Lost on restart.

**Mitigation:** Persist to SQLite or disk for resilience and scalability.

**Status:** Accepted risk at current scale.

### LOW — Database path relative to current working directory

`DB_PATH = resolve(process.cwd(), "data/bemify-api.sqlite")`. pm2 sets cwd
correctly, but manual runs from the wrong directory create a phantom database.

**Mitigation:** Use `__dirname` or environment variable.

**Status:** Not mitigated.

### LOW — No magic-byte validation on uploaded files

Multer fileFilter checks extension only. A renamed file passes through to the
parser, which will reject malformed content but not until parsing.

**Mitigation:** Check file headers (`SXI` is a zip; `EPW` starts with `LOCATION,`).

**Status:** Not mitigated. Low impact since parsers reject malformed input.

### LOW — No automated dependency scanning

`npm audit` is not run on a schedule. CVEs in transitive dependencies may go
unnoticed.

**Mitigation:** Add `npm audit --production` to a weekly cron or GitHub Action.

**Status:** Not mitigated.

### LOW — No backup of SQLite database

API key hashes and simulation logs would be lost on disk failure. Keys can be
reissued; logs cannot be reconstructed.

**Mitigation:** Nightly `sqlite3 .backup` to off-host storage.

**Status:** Not mitigated.

### LOW — No audit log of admin actions

Key creation, deactivation, and CLI commands leave no trace beyond the SQLite
state itself. If a key is created without authorization, there is no record.

**Mitigation:** Append-only audit log table for key lifecycle events.

**Status:** Not mitigated.

---

## 7. Incident response

### Suspected compromised API key

1. Run `npx tsx -r tsconfig-paths/register src/server/manage-keys.ts deactivate <id>`.
2. Inspect `simulation_logs` for the key to assess scope (file names, timestamps).
3. Notify the key owner via email.
4. Issue a new key if requested.

### Server compromise (suspected shell access)

1. Stop pm2: `pm2 stop bemify-api`.
2. Snapshot `data/bemify-api.sqlite` for forensics.
3. Revoke all API keys: `UPDATE api_keys SET active = 0;`.
4. Rebuild VPS from scratch; do not trust the existing host.
5. Reissue keys to known customers.
6. Notify affected customers within 72 hours per GDPR Art. 33 if personal data
   was processed.

### Vulnerability disclosure

Security issues should be reported to **security@bemify.no** (or fallback:
**erlend@bemify.no**). Acknowledged within 3 business days. No bug bounty
program at this stage.

---

## 8. Data handling and GDPR

| Data                                           | Location                    | Retention                                         | Legal basis                        |
| ---------------------------------------------- | --------------------------- | ------------------------------------------------- | ---------------------------------- |
| API key metadata (name, email)                 | SQLite                      | Until deactivated + 1 year                        | Contract (Art. 6(1)(b))            |
| API key hash                                   | SQLite                      | Until deactivated                                 | Contract                           |
| Simulation logs (filenames, durations, status) | SQLite                      | Indefinite at present — _decide retention policy_ | Legitimate interest (Art. 6(1)(f)) |
| Uploaded SXI/EPW files                         | RAM only, during processing | Discarded after job completes                     | Contract                           |
| Simulation results                             | RAM                         | 30 minutes after completion                       | Contract                           |
