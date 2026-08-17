"""
Bemify Simulation API - Test Script

Tests all API endpoints: health, klimasteder, simulate, job polling.
Prints formatted results including energimerke and TEK17 validation.

Usage:
    python test_api.py --token bmf_... --sxi building.sxi
    python test_api.py --token bmf_... --sxi building.sxi --klimasted Oslo
    python test_api.py --token bmf_... --sxi building.sxi --simuleringstype tek17
    python test_api.py --token bmf_... --sxi building.sxi --epw oslo.epw
    python test_api.py --token bmf_... --sxi building.sxi --modellversjon 2.1

Requirements:
    pip install requests
"""

import argparse
import sys
import time

import requests

# region ANSI colors

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def supports_color():
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    return True


if not supports_color():
    GREEN = RED = YELLOW = CYAN = BOLD = DIM = RESET = ""


def ok(msg):
    print(f"  {GREEN}OK{RESET} {msg}")


def fail(msg):
    print(f"  {RED}FAIL{RESET} {msg}")


def info(msg):
    print(f"  {DIM}{msg}{RESET}")


def header(msg):
    print(f"\n{BOLD}{msg}{RESET}")
    print(f"  {'=' * len(msg)}")


# endregion

# region API calls


def test_health(base_url):
    header("1. GET /health")
    try:
        resp = requests.get(f"{base_url}/health", timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("status") == "ok":
            ok(f"Server is healthy (queue: {data['queue']['length']} jobs)")
            return True
        else:
            fail(f"Unexpected response: {data}")
            return False
    except requests.exceptions.ConnectionError:
        fail(f"Could not connect to {base_url}")
        return False
    except Exception as e:
        fail(str(e))
        return False


def test_klimasteder(base_url):
    header("2. GET /klimasteder")
    try:
        resp = requests.get(f"{base_url}/klimasteder", timeout=10)
        data = resp.json()
        locations = data.get("locations", [])
        count = data.get("count", 0)
        ok(f"{count} climate locations available")
        # Show first 10
        preview = locations[:10]
        info(f"  First 10: {', '.join(preview)}")
        if count > 10:
            info(f"  ... and {count - 10} more")
        return locations
    except Exception as e:
        fail(str(e))
        return []


def start_simulation(base_url, token, sxi_path, klimasted=None, epw_path=None, simuleringstype="aarssimulering", modellversjon=None):
    header("3. POST /simulate")

    headers = {"Authorization": f"Bearer {token}"}
    files = {}
    data = {}

    try:
        files["model"] = ("model.sxi", open(sxi_path, "rb"), "application/octet-stream")
    except FileNotFoundError:
        fail(f"SXI file not found: {sxi_path}")
        return None

    if epw_path:
        try:
            files["climate"] = ("climate.epw", open(epw_path, "rb"), "text/plain")
        except FileNotFoundError:
            fail(f"EPW file not found: {epw_path}")
            return None

    if klimasted:
        data["klimasted"] = klimasted

    if simuleringstype != "aarssimulering":
        data["simuleringstype"] = simuleringstype

    if modellversjon:
        data["modellversjon"] = modellversjon

    info(f"Model: {sxi_path}")
    if klimasted:
        info(f"Klimasted: {klimasted}")
    if epw_path:
        info(f"EPW: {epw_path}")
    info(f"Simuleringstype: {simuleringstype}")
    info(f"Modellversjon: {modellversjon if modellversjon else 'server default (newest)'}")

    try:
        resp = requests.post(f"{base_url}/simulate", headers=headers, files=files, data=data, timeout=30)

        if resp.status_code == 202:
            job = resp.json()
            ok(f"Job created: {job['jobId']} (position {job['position']})")
            if job.get("modelVersion"):
                info(f"Model version used by server: {job['modelVersion']}")
            return job["jobId"]
        else:
            error = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            fail(f"HTTP {resp.status_code}: {error}")
            return None
    except Exception as e:
        fail(str(e))
        return None
    finally:
        for f in files.values():
            f[1].close()


def poll_job(base_url, token, job_id, timeout_seconds=300, interval=3):
    header("4. GET /job/:id (polling)")

    headers = {"Authorization": f"Bearer {token}"}
    start = time.time()
    last_status = None

    while True:
        elapsed = time.time() - start
        if elapsed > timeout_seconds:
            fail(f"Timeout after {timeout_seconds}s")
            return None

        try:
            resp = requests.get(f"{base_url}/job/{job_id}", headers=headers, timeout=10)
            data = resp.json()
            status = data.get("status")

            if status != last_status:
                info(f"Status: {status} ({elapsed:.0f}s)")
                last_status = status

            if status == "completed":
                ok(f"Simulation completed in {elapsed:.1f}s")
                return data.get("result")
            elif status == "error":
                fail(f"Simulation failed: {data.get('error')}")
                return None

        except Exception as e:
            fail(f"Poll error: {e}")

        time.sleep(interval)


# endregion

# region Result display


def print_results(result):
    header("5. Results")

    # Zones
    zones = result.get("zones", [])
    if zones:
        total_area = sum(z.get("area", 0) for z in zones)
        ok(f"{len(zones)} zone(s), total area: {total_area:.1f} m2")
        for z in zones:
            info(f"  - {z.get('navn', z.get('id', '?'))}: {z.get('area', 0):.1f} m2")

    # Beregningspunkter
    bp = result.get("beregningspunkter", {})
    if bp:
        print()
        info("Beregningspunkter (kWh/year):")
        netto = bp.get("netto", {})
        levert = bp.get("levert", {})

        if netto.get("energyResults"):
            netto_total = sum(v for v in netto["energyResults"].values() if isinstance(v, (int, float)))
            info(f"  A (netto):  {netto_total:.0f} kWh")

        if levert.get("levertEnergi"):
            levert_total = sum(v for v in levert["levertEnergi"].values() if isinstance(v, (int, float)))
            info(f"  D (levert): {levert_total:.0f} kWh")
            for key, val in levert["levertEnergi"].items():
                if isinstance(val, (int, float)) and val > 0:
                    info(f"    {key}: {val:.0f} kWh")

    # Energimerke (only returned for simuleringstype=energimerke)
    em = result.get("energimerke")
    if em:
        print()
        grade = em.get("energimerke", "?")
        color = GREEN if grade in ("A", "B", "C") else YELLOW if grade == "D" else RED
        print(f"  {BOLD}Energimerke: {color}{grade}{RESET}")
        info(f"  Klimakorrigert vektet spesifikk: {em.get('klimakorrigertVektetSpesifikk', 0):.1f} kWh/(m2*year)")
        info(f"  Total delivered: {em.get('sumLevertEnergi', 0):.0f} kWh/year")
        info(f"  Correction factor: {em.get('korreksjonsfaktor', 1.0):.3f}")

        items = em.get("items", [])
        if items:
            info("  Breakdown:")
            for item in items:
                info(f"    {item['kilde']}: {item['spesifikk_kWhm2']:.1f} kWh/m2 (x{item['vektingsfaktor']})")
    else:
        print()
        info("  No energimerke in this result. It is only returned for")
        info("  --simuleringstype energimerke, and requires a valid kommune")
        info("  and bygningskategori in the model.")

    # TEK17 (only returned for simuleringstype=tek17)
    tek = result.get("tek17")
    if tek:
        print()
        compliant = tek.get("erSamsvarsende", False)
        status_color = GREEN if compliant else RED
        status_text = "OPPFYLT" if compliant else "IKKE OPPFYLT"
        print(f"  {BOLD}TEK17: {status_color}{status_text}{RESET}")

        # Energiramme
        er = tek.get("energiramme", {})
        if er:
            er_status = er.get("status", "")
            info(f"  Energiramme: {er.get('totalBeregnet', 0):.1f} / {er.get('forskriftskrav', 0):.1f} kWh/m2 [{er_status}]")
            for p in er.get("poster", []):
                info(f"    {p.get('post', '')} {p.get('beskrivelse', '')}: {p.get('spesifikk_kWhm2', 0):.1f} kWh/m2")

        # Minstekrav
        mk = tek.get("minstekrav", {})
        if mk:
            info(f"  Minstekrav: [{mk.get('samletStatus', '')}]")
            for r in mk.get("rader", []):
                s = r.get("status", "")
                v = f"{r.get('faktiskVerdi', '-')}" if r.get("faktiskVerdi") is not None else "-"
                marker = GREEN + "v" + RESET if s == "oppfylt" else RED + "x" + RESET
                info(f"    {marker} {r.get('bygningsdel', '')}: {v} (krav: {r.get('kravVerdi', '')})")

        # Luftmengder
        lm = tek.get("luftmengder", {})
        if lm:
            info(f"  Luftmengder: [{lm.get('samletStatus', '')}]")
            for r in lm.get("rader", []):
                s = r.get("status", "")
                v = f"{r.get('faktiskVerdi', '-')}" if r.get("faktiskVerdi") is not None else "-"
                marker = GREEN + "v" + RESET if s == "oppfylt" else RED + "x" + RESET
                info(f"    {marker} {r.get('beskrivelse', '')}: {v} (krav: {r.get('kravVerdi', '')})")

        # Energiforsyning
        ef = tek.get("energiforsyning", {})
        if ef:
            info(f"  Energiforsyning: [{ef.get('status', '')}]")
            if ef.get("brukerFossilBrensel"):
                info(f"    Fossil sources: {', '.join(ef.get('fossilKilder', []))}")
            if ef.get("sentralAndelProsent") is not None:
                info(f"    Central supply share: {ef['sentralAndelProsent']:.1f}%")

        # Oppsummering
        opps = tek.get("oppsummering", {})
        if opps:
            info(f"  Summary: {opps.get('antallOppfylt', 0)} passed, {opps.get('antallIkkeOppfylt', 0)} failed, {opps.get('antallIkkeRelevant', 0)} N/A")
    else:
        print()
        info("  No tek17 block in this result. Re-run with --simuleringstype tek17.")


# endregion

# region Main


def main():
    parser = argparse.ArgumentParser(
        description="Bemify Simulation API test script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_api.py --token bmf_... --sxi building.sxi --klimasted Oslo
  python test_api.py --token bmf_... --sxi building.sxi --simuleringstype tek17
  python test_api.py --token bmf_... --sxi building.sxi --epw oslo.epw
  python test_api.py --token bmf_... --sxi building.sxi --klimasted Oslo --modellversjon 2.1
        """,
    )
    parser.add_argument("--url", default="https://api.bemify.no", help="API base URL (default: https://api.bemify.no)")
    parser.add_argument("--token", required=True, help="API token (bmf_...)")
    parser.add_argument("--sxi", required=True, help="Path to .sxi model file")
    parser.add_argument("--klimasted", default=None, help="Climate location (e.g. Oslo, Bergen)")
    parser.add_argument("--epw", default=None, help="Path to .epw climate file")
    parser.add_argument("--simuleringstype", default="aarssimulering", choices=["aarssimulering", "energimerke", "tek17"], help="Simulation type (default: aarssimulering)")
    parser.add_argument("--modellversjon", default=None, help="Calculation model version, e.g. 2.1 (default: newest, decided by the server). See GET /modellversjoner")
    parser.add_argument("--timeout", type=int, default=300, help="Max polling time in seconds (default: 300)")

    args = parser.parse_args()

    # Validate inputs
    if args.klimasted and args.epw:
        print(f"{RED}Error: specify either --klimasted or --epw, not both{RESET}")
        sys.exit(1)

    if args.simuleringstype != "tek17" and not args.klimasted and not args.epw:
        print(f"{YELLOW}Warning: no climate data specified. Using --klimasted Oslo as default.{RESET}")
        args.klimasted = "Oslo"

    base_url = args.url.rstrip("/")

    print(f"{BOLD}Bemify Simulation API Test{RESET}")
    print(f"  URL: {base_url}")
    print(f"  Token: {args.token[:8]}...")

    # 1. Health check
    if not test_health(base_url):
        sys.exit(1)

    # 2. List klimasteder
    test_klimasteder(base_url)

    # 3. Start simulation
    job_id = start_simulation(
        base_url,
        args.token,
        args.sxi,
        klimasted=args.klimasted,
        epw_path=args.epw,
        simuleringstype=args.simuleringstype,
        modellversjon=args.modellversjon,
    )
    if not job_id:
        sys.exit(1)

    # 4. Poll for results
    result = poll_job(base_url, args.token, job_id, timeout_seconds=args.timeout)
    if not result:
        sys.exit(1)

    # 5. Print results
    print_results(result)

    print(f"\n{GREEN}{BOLD}Done!{RESET}")


if __name__ == "__main__":
    main()

# endregion
