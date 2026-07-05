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

> **Note (Windows):** Use `curl.exe --ssl-no-revoke`. The Windows build of curl performs a TLS certificate revocation check that fails against Let's Encrypt certificates.

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
| `climate` | file | No | EnergyPlus weather file (.epw). Not allowed with `energimerke` or `tek17`. |
| `klimasted` | string | No | Municipality name (e.g. `Oslo`, `Bergen`). Alternative to `climate`. Not allowed with `tek17`. |
| `simuleringstype` | string | No | `aarssimulering` (default), `energimerke`, or `tek17` |

**Climate data rules:**
- Provide either `klimasted` or `climate` file, not both
- For `tek17`: climate data is always the TEK17 reference climate. Do **not** provide `klimasted` or `climate`; the request will be rejected with 400
- For `energimerke`: only `klimasted` is accepted — EPW files are rejected with 400. Energy labeling requires a standard Norwegian climate location for the climate correction factor
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

### POST /validate

Validate an SXI file without running the simulation. Returns a structured list of
errors, warnings, and missing fields detected during parsing and conversion to the
Bemify intermediate format. Useful for iterating on model files before committing
to a full simulation.

**Content-Type:** `multipart/form-data`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | file | Yes | SIMIEN Pro project file (.sxi) |

**Per-key limits:**
- `POST /validate`: max 20 requests per minute per API key

**Response (200):**
```json
{
  "isValid": true,
  "errors": [],
  "warnings": [
    {
      "nodeId": "zone-1",
      "field": "setpoint",
      "message": "Default value used",
      "defaultValue": 21
    }
  ],
  "missingData": [
    {
      "nodeId": "zone-1",
      "nodeType": "Sone",
      "missingFields": [
        { "field": "buildingSimulationProperties", "defaultValue": null }
      ]
    }
  ]
}
```

`isValid: false` means the file could be parsed but contains structural errors,
the response is still `200`. HTTP `400` is only returned when the file cannot be
parsed at all (malformed XML, missing `.sxi`-file, etc.).

### GET /job/:jobId

Check job status and retrieve results. Requires authentication.

**Statuses:** `queued` | `running` | `completed` | `error`

**Response when queued (200):**
```json
{
  "jobId": "job_1712832645123_1",
  "status": "queued",
  "queuedAt": "2026-04-11T10:30:45.123Z",
  "queueLength": 3
}
```

`queueLength` is the current queue depth (only included for `queued` status).

**Response when completed (200):**
```jsonc
{
  "jobId": "job_1712832645123_1",
  "status": "completed",
  "queuedAt": "2026-04-11T10:30:45.123Z",
  "startedAt": "2026-04-11T10:30:50.456Z",
  "completedAt": "2026-04-11T10:32:15.789Z",
  "result": {
    "beregningspunkter": {
      "netto":      { "energyResults": {}, "energyTotal": 0, "powerDemand": {}, /* ... */ },
      "brutto":     { "energyResults": {}, /* ... */ },
      "tilfort":    { "tilfortEnergi": {}, /* ... */ },
      "levert":     { "levertEnergi": {}, "klimafordeling": {}, /* ... */ },
      "nzebLevert": { "levertEnergi": {}, /* ... */ }
    },
    "zones": [
      { "id": "sone-1", "navn": "Sone 1", "area": 150.0 }
      // ... en per sone
    ],
    "energimerke": { /* se egen seksjon */ },
    "tek17": { /* se egen seksjon */ }
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
| `energimerke` | Energy labeling | klimasted only | `energimerke` |
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

```jsonc
{
  "erSamsvarsende": true,
  "energiramme": {
    "poster": [
      { "post": "1a", "beskrivelse": "Romoppvarming", "spesifikk_kWhm2": 12.3 }
      // ... en post per energipost
    ],
    "totalBeregnet": 105.2,
    "forskriftskrav": 115.0,
    "status": "oppfylt",
    "bygningskategori": "Kontorbygning"
  },
  "minstekrav": {
    "rader": [
      { "bygningsdel": "U-verdi yttervegger", "faktiskVerdi": 0.18, "kravVerdi": 0.22, "status": "oppfylt" }
      // ... en rad per bygningsdel
    ],
    "samletStatus": "oppfylt"
  },
  "luftmengder": {
    "rader": [
      { "beskrivelse": "Spesifikk vifteeffekt (SFP)", "faktiskVerdi": 1.50, "kravVerdi": 2.00, "status": "oppfylt" }
      // ... en rad per krav
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

Results are grouped into calculation points per NS 3031. **Important:** the points do
*not* share a common shape. The field holding the annual per-category totals is named
differently in each point. Read the correct field per point:

| Point | Key | Description | Annual totals field |
|-------|-----|-------------|---------------------|
| A | `netto` | Net energy demand (building needs) | `energyResults` |
| B | `brutto` | Gross energy demand (including system losses) | `energyResults` |
| C | `tilfort` | Supplied energy (from energy sources) | `tilfortEnergi` |
| D | `levert` | Delivered energy (per energy carrier) | `levertEnergi` |
| D (nZEB) | `nzebLevert` | Delivered energy, nZEB variant (excludes certain posts, no export credit) | `levertEnergi` |

`energyResults` and `tilfortEnergi` are keyed by energy post (`"1a Romoppvarming"`,
`"1b Ventilasjonsvarme"`, `"2 Varmtvann"`, `"3a Romkjøling"`, `"3b Ventilasjonskjøling"`,
`"5 Belysning"`, ...) in kWh/year.

`levertEnergi` (points D) is keyed by energy carrier (`"1 Levert elektrisitet"`,
`"3 Levert fjernvarme"`, `"4 Levert fjernkjøling"`, ...) in kWh/year.

Full field list per point:

```jsonc
{
  // A: netto, B: brutto -- keyed by energy post
  "netto": {
    "energyResults": { "1a Romoppvarming": 12345, "2 Varmtvann": 6789 },
    "energyTotal": 0,
    "powerDemand": {},
    "peakTimestamps": {},
    "totalPeakPower": {}
  },
  "brutto": {
    // samme form som "netto"
  },

  // C: tilfort -- keyed by energy post
  "tilfort": {
    "tilfortEnergi": {},
    "tilfortEnergiTotal": 0,
    "levertEffekt": {},
    "levertEffektTimestamps": {},
    "levertEffektTotal": {}
  },

  // D: levert -- keyed by energy carrier
  "levert": {
    "levertEnergi": { "1 Levert elektrisitet": 59989 },
    "total": 0,
    "elektriskBudsjett": {},
    "klimafordeling": {
      "klimaavhengig": {},
      "ikkeKlimaavhengig": {}
    },
    "oppvarmingOutput_kWh": {},
    "kjoelingOutput_kWh": {},
    "apentIldstedBio_kWh": 0,
    "monthlyLevertPerKilde": {},
    "monthlyMakseffektPerKilde": {}
  },

  "nzebLevert": {
    // samme form som "levert"
  }
}
```


### Additional result fields

Beyond `beregningspunkter`, `zones`, `energimerke` and `tek17`, the `result` object also
contains the following top-level fields (mainly for detailed analysis; most integrations
only need the four above):

| Field | Description |
|-------|-------------|
| `outputMode` | Always `"aggregated"` for API results |
| `sentralAndelSone` | Central supply share of heat demand per zone [kWh] |
| `distribusjonsOgAkkumuleringstap` | Annual distribution + accumulation losses [kWh] |
| `energyPerPostPerZone` | Annual energy per post, per zone [kWh] |
| `monthlyEnergyPerPostPerZone` | Monthly energy per post, per zone [kWh] |
| `monthlyThermalPerZone` | Monthly heating/cooling per zone [kWh] |
| `monthlyTemperaturesPerZone` | Monthly min/avg/max temperatures per zone |
| `quarterlyEffektPerZone` / `quarterlyTemperaturPerZone` | 15-min power / temperature time series per zone |
| `ventilasjonStatsPerZone` | Ventilation stats per zone |
| `varmetapstallPerSone` | Heat loss coefficients per zone |
| `solcelleProduction` / `vindturbinProduction` | PV / wind production |
| `kildeSPF` / `kildeOutput` | SPF and thermal output per central energy source |
| `warnings` | Simulation warnings |
| `metadata` | `{ simulationTime, totalSteps, stepDuration, totalHours }` |

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

On Windows, add `--ssl-no-revoke` to all `curl.exe` commands (see note under Quick Start).

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

# Validate an SXI file without running a simulation
curl -X POST https://api.bemify.no/validate \
  -H "Authorization: Bearer bmf_YOUR_TOKEN" \
  -F "model=@building.sxi"

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

See [scripts/test_api.py](scripts/test_api.py) for a more complete example script.

## Limits

| Limit | Value |
|-------|-------|
| Rate limit | 30 requests per minute |
| Per-key `POST /simulate` | 6 requests per minute |
| Per-key `POST /validate` | 20 requests per minute |
| Per-key `GET /job/:jobId` | 120 requests per minute |
| Max active jobs per API key | 3 |
| Max file size | 10 MB per file |
| Max queue depth | 20 jobs |
| Simulation timeout | 10 minutes |
| Result TTL | 30 minutes |
