# Bemify Simulation API

REST API for building energy simulation using the [Bemify](https://bemify.no) calculation engine. Upload a SIMIEN Pro model (.sxi) and get back energy performance results, energy labels (A-G), and TEK17 compliance checks.

**Base URL:** `https://api.bemify.no`

## Quick Start

```bash
# Run a simulation with server-side climate data
curl -X POST https://api.bemify.no/simulate \
  -H "Authorization: Bearer bmf_YOUR_TOKEN" \
  -F "model=@building.sxi" \
  -F "klimasted=Oslo"

# Poll for results
curl https://api.bemify.no/job/job_123456_1 \
  -H "Authorization: Bearer bmf_YOUR_TOKEN"
```

## Authentication

All simulation endpoints require a Bearer token in the `Authorization` header:

```
Authorization: Bearer bmf_YOUR_TOKEN
```

Contact erlend@bemify.no for API access.

## Endpoints

### POST /simulate

Start a new simulation. Returns a job ID for polling.

**Content-Type:** `multipart/form-data`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | file | Yes | SIMIEN Pro project file (.sxi) |
| `climate` | file | No | EnergyPlus weather file (.epw). Not allowed with `tek17`. |
| `klimasted` | string | No | Municipality name (e.g. `Oslo`, `Bergen`). Alternative to `climate`. Not allowed with `tek17`. |
| `simuleringstype` | string | No | `aarssimulering` (default), `energimerke`, or `tek17` |

**Climate data rules:**
- Provide either `klimasted` or `climate` file, not both
- For `tek17`: climate data is always the TEK17 reference climate. Do **not** provide `klimasted` or `climate` — the request will be rejected with 400
- Use `GET /klimasteder` to list valid municipality names

**Per-key limits:**
- `POST /simulate`: max 6 requests per minute per API key
- `GET /job/:jobId`: max 120 requests per minute per API key
- Max 3 active jobs (`queued` + `running`) per API key

**Response (202):**
```json
{
  "jobId": "job_1712832645123_1",
  "position": 1,
  "message": "Simulering lagt i kø (posisjon 1). Poll /job/job_1712832645123_1 for status."
}
```

### GET /job/:jobId

Check job status and retrieve results. Requires authentication.

**Statuses:** `queued` | `running` | `completed` | `error`

**Response when completed (200):**
```json
{
  "jobId": "job_1712832645123_1",
  "status": "completed",
  "queuedAt": "2026-04-11T10:30:45.123Z",
  "startedAt": "2026-04-11T10:30:50.456Z",
  "completedAt": "2026-04-11T10:32:15.789Z",
  "result": {
    "beregningspunkter": { "netto": { ... }, "brutto": { ... }, "tilfort": { ... }, "levert": { ... } },
    "zones": [ { "id": "sone-1", "name": "Sone 1", "area": 150.0 } ],
    "energimerke": { ... },
    "tek17": { ... }
  }
}
```

**Response when error (200):**
```json
{
  "jobId": "job_1712832645123_1",
  "status": "error",
  "completedAt": "2026-04-11T10:32:15.789Z",
  "error": "Error message"
}
```

Results are kept for up to 30 minutes after completion, but may be deleted earlier
if the in-memory completed-job cap is reached.

### GET /klimasteder

List all available climate locations. No authentication required.

**Response (200):**
```json
{
  "locations": ["TEK17 Referanseklima", "Oslo", "Bergen", "Trondheim", ...],
  "count": 51
}
```

### GET /health

Server health check. No authentication required.

**Response (200):**
```json
{
  "status": "ok",
  "timestamp": "2026-04-11T10:30:45.123Z",
  "queue": { "length": 0, "processing": false }
}
```

### GET /queue

Queue status. No authentication required.

**Response (200):**
```json
{ "queueLength": 0, "isProcessing": false }
```

## Simulation Types

| Value | Description | Climate | Extra result fields |
|-------|-------------|---------|---------------------|
| `aarssimulering` | Full year simulation (default) | klimasted or EPW | `energimerke` |
| `energimerke` | Energy labeling | klimasted or EPW | `energimerke` |
| `tek17` | TEK17 compliance check | Automatic (reference, no input allowed) | `energimerke`, `tek17` |

## Result Format

### Energy Label (`result.energimerke`)

Computed automatically when the project has a valid municipality and building category.

```json
{
  "energimerke": "B",
  "totalArea": 250.0,
  "korreksjonsfaktor": 1.05,
  "klimakorrigertVektetSpesifikk": 92.3,
  "sumVektetSpesifikk": 96.9,
  "sumLevertEnergi": 24075,
  "sumSpesifikk": 96.3,
  "vektetKlimaavhengig": 42.1,
  "vektetIkkeKlimaavhengig": 54.8,
  "items": [
    {
      "kilde": "1 Levert elektrisitet",
      "levertEnergi_kWh": 21500,
      "spesifikk_kWhm2": 86.0,
      "vektingsfaktor": 1.0,
      "vektetSpesifikk_kWhm2": 86.0
    }
  ]
}
```

| Field | Unit | Description |
|-------|------|-------------|
| `energimerke` | A-G | Energy label grade |
| `klimakorrigertVektetSpesifikk` | kWh/(m2*year) | Climate-corrected weighted specific delivered energy (determines grade) |
| `sumVektetSpesifikk` | kWh/(m2*year) | Weighted specific delivered energy (before climate correction) |
| `sumLevertEnergi` | kWh/year | Total delivered energy |
| `korreksjonsfaktor` | - | Climate correction factor for municipality/building type |
| `items` | array | Breakdown per energy carrier |

### TEK17 Validation (`result.tek17`)

Only present when `simuleringstype=tek17`.

```json
{
  "erSamsvarsende": true,
  "energiramme": {
    "poster": [
      { "post": "1a", "beskrivelse": "Romoppvarming", "spesifikk_kWhm2": 12.3 }
    ],
    "totalBeregnet": 105.2,
    "forskriftskrav": 115.0,
    "status": "oppfylt",
    "bygningskategori": "Kontorbygning"
  },
  "minstekrav": {
    "rader": [
      { "bygningsdel": "U-verdi yttervegger", "faktiskVerdi": 0.18, "kravVerdi": 0.22, "status": "oppfylt" }
    ],
    "samletStatus": "oppfylt"
  },
  "luftmengder": {
    "rader": [
      { "beskrivelse": "Spesifikk vifteeffekt (SFP)", "faktiskVerdi": 1.50, "kravVerdi": 2.00, "status": "oppfylt" }
    ],
    "samletStatus": "oppfylt"
  },
  "energiforsyning": {
    "brukerFossilBrensel": false,
    "fossilKilder": [],
    "punkt2Gjelder": true,
    "harSentralVarmesentral": true,
    "sentralAndelProsent": 85.2,
    "status": "oppfylt"
  },
  "oppsummering": {
    "antallOppfylt": 4,
    "antallIkkeOppfylt": 0,
    "antallIkkeRelevant": 0
  }
}
```

Possible `status` values: `"oppfylt"`, `"ikke_oppfylt"`, `"ikke_relevant"`.

### Calculation Points (`result.beregningspunkter`)

Results are grouped into four calculation points per NS 3031:

| Point | Key | Description |
|-------|-----|-------------|
| A | `netto` | Net energy demand (building needs) |
| B | `brutto` | Gross energy demand (including system losses) |
| C | `tilfort` | Supplied energy (from energy sources) |
| D | `levert` | Delivered energy (from grid/carriers) |

Each contains `energyResults` with annual totals per energy post (space heating, ventilation heating, hot water, cooling, lighting, etc.).

## Error Codes

| Code | Meaning | Example |
|------|---------|---------|
| 400 | Bad request | Missing model file, invalid simuleringstype, both klimasted and climate provided, invalid file type |
| 401 | Unauthorized | Missing Authorization header |
| 403 | Forbidden | Invalid or deactivated API key |
| 404 | Not found | Job not found or expired |
| 413 | Payload too large | File exceeds 10 MB limit |
| 429 | Rate limited | Too many requests globally, too many requests for one API key, or too many active jobs for one API key |
| 502 | Bad gateway | Failed to fetch climate data from upstream |
| 503 | Queue full | Max 20 concurrent jobs |

## Examples

### curl

```bash
# Standard simulation with municipality climate data
curl -X POST https://api.bemify.no/simulate \
  -H "Authorization: Bearer bmf_YOUR_TOKEN" \
  -F "model=@building.sxi" \
  -F "klimasted=Oslo"

# Energy label simulation
curl -X POST https://api.bemify.no/simulate \
  -H "Authorization: Bearer bmf_YOUR_TOKEN" \
  -F "model=@building.sxi" \
  -F "klimasted=Oslo" \
  -F "simuleringstype=energimerke"

# TEK17 compliance check (climate data fetched automatically)
curl -X POST https://api.bemify.no/simulate \
  -H "Authorization: Bearer bmf_YOUR_TOKEN" \
  -F "model=@building.sxi" \
  -F "simuleringstype=tek17"

# Simulation with custom EPW file
curl -X POST https://api.bemify.no/simulate \
  -H "Authorization: Bearer bmf_YOUR_TOKEN" \
  -F "model=@building.sxi" \
  -F "climate=@oslo.epw"

# Poll for results
curl https://api.bemify.no/job/job_123456_1 \
  -H "Authorization: Bearer bmf_YOUR_TOKEN"
```

### Python

```python
import requests
import time

API_URL = "https://api.bemify.no"
TOKEN = "bmf_YOUR_TOKEN"
headers = {"Authorization": f"Bearer {TOKEN}"}

# Start simulation
with open("building.sxi", "rb") as model:
    resp = requests.post(
        f"{API_URL}/simulate",
        headers=headers,
        files={"model": model},
        data={"klimasted": "Oslo", "simuleringstype": "energimerke"},
    )

job_id = resp.json()["jobId"]
print(f"Job started: {job_id}")

# Poll for results
while True:
    status = requests.get(f"{API_URL}/job/{job_id}", headers=headers).json()
    if status["status"] in ("completed", "error"):
        break
    print(f"Status: {status['status']}...")
    time.sleep(2)

if status["status"] == "completed":
    result = status["result"]

    # Energy label
    if "energimerke" in result:
        em = result["energimerke"]
        print(f"Energy label: {em['energimerke']}")
        print(f"Weighted specific: {em['klimakorrigertVektetSpesifikk']:.1f} kWh/(m2*year)")

    # TEK17 (only for simuleringstype=tek17)
    if "tek17" in result:
        tek = result["tek17"]
        print(f"TEK17 compliant: {tek['erSamsvarsende']}")
else:
    print(f"Error: {status['error']}")
```

See [examples/test_api.py](examples/test_api.py) for a more complete example script.

## Limits

| Limit | Value |
|-------|-------|
| Rate limit | 30 requests per minute |
| Per-key `POST /simulate` | 6 requests per minute |
| Per-key `GET /job/:jobId` | 120 requests per minute |
| Max active jobs per API key | 3 |
| Max file size | 10 MB per file |
| Max queue depth | 20 jobs |
| Simulation timeout | 10 minutes |
| Result TTL | 30 minutes |
