"""
Bemify Simulation API - Test Script Base

Prints results including energimerke and TEK17 validation.

Usage:
    python test_api_base.py

Requirements:
    pip install requests
"""

import requests
import time

API_URL = "https://api.bemify.no"
TOKEN = "bmf_YOUR_TOKEN"
SIMULERINGSTYPE = "energimerke"  # "aarssimulering" | "energimerke" | "tek17"
KLIMASTED = "Oslo"
MODELL_FIL = "Bolig.sxi"

headers = {"Authorization": f"Bearer {TOKEN}"}

# Start simulering
with open(MODELL_FIL, "rb") as model:
    resp = requests.post(
        f"{API_URL}/simulate",
        headers=headers,
        files={"model": model},
        data={"klimasted": KLIMASTED, "simuleringstype": SIMULERINGSTYPE},
    )

print(f"Status: {resp.status_code}")
print(f"Respons: {resp.text}")
resp.raise_for_status()

job_id = resp.json()["jobId"]
print(f"Jobb startet: {job_id}")

# Poll for resultater
while True:
    status = requests.get(f"{API_URL}/job/{job_id}", headers=headers).json()
    if status["status"] in ("completed", "error"):
        break
    print(f"Status: {status['status']}...")
    time.sleep(2)

if status["status"] == "completed":
    result = status["result"]

    # Energimerke
    if "energimerke" in result:
        em = result["energimerke"]
        print(f"Energimerke: {em['energimerke']}")
        print(f"Vektet spesifikk: {em['klimakorrigertVektetSpesifikk']:.1f} kWh/(m²·år)")

    # TEK17 (kun for simuleringstype=tek17)
    if "tek17" in result:
        tek = result["tek17"]
        print(f"TEK17-samsvar: {tek['erSamsvarsende']}")
else:
    print(f"Feil: {status['error']}")
