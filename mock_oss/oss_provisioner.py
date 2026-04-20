#!/usr/bin/env python3
"""
Mock OSS Provisioner
====================
Simulates an external OSS/provisioning system that advances TMF638 service
states through the provisioning lifecycle via the TMF API.

Lifecycle:
  feasabilityChecked -> designed -> reserved -> inactive -> active

Usage:
  python oss_provisioner.py                         # defaults: localhost:8069, 10s poll
  python oss_provisioner.py --host 192.168.1.5 --port 8069 --interval 5
  python oss_provisioner.py --once                  # single pass, then exit

Environment variables (alternative to CLI args):
  OSS_HOST=localhost  OSS_PORT=8069  OSS_INTERVAL=10  OSS_STEP_DELAY=3
"""

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [OSS] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("oss")

# TMF638 provisioning lifecycle — each state transitions to the next
LIFECYCLE = [
    "feasabilityChecked",
    "designed",
    "reserved",
    "inactive",
    "active",
]

STATE_INDEX = {s: i for i, s in enumerate(LIFECYCLE)}

# API paths to try (v5 first, then v4 fallback)
API_PATHS = [
    "/tmf-api/serviceInventory/v5/service",
    "/tmf-api/serviceInventoryManagement/v5/service",
    "/tmf-api/serviceInventory/v4/service",
]


def _request(url, method="GET", data=None):
    """Simple HTTP request, returns (status, parsed_json_or_None)."""
    headers = {"Content-Type": "application/merge-patch+json", "Accept": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw.strip() else None
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode()[:200]
        except Exception:
            pass
        log.warning("HTTP %s %s -> %d %s", method, url, e.code, body_text)
        return e.code, None
    except Exception as e:
        log.error("Request failed: %s %s -> %s", method, url, e)
        return 0, None


def discover_api(base_url):
    """Try API paths and return the first one that responds."""
    for path in API_PATHS:
        url = f"{base_url}{path}?limit=1"
        status, _ = _request(url)
        if status == 200:
            log.info("Discovered API at %s", path)
            return path
    return API_PATHS[0]  # fallback


def fetch_services_by_state(base_url, api_path, state):
    """GET services filtered by state."""
    url = f"{base_url}{api_path}?state={state}"
    status, data = _request(url)
    if status == 200 and isinstance(data, list):
        return data
    return []


def advance_service(base_url, api_path, service_id, next_state):
    """PATCH a service to the next state."""
    url = f"{base_url}{api_path}/{service_id}"
    patch_body = {"state": next_state}
    status, data = _request(url, method="PATCH", data=patch_body)
    return status in (200, 204), data


def provision_cycle(base_url, api_path, step_delay):
    """
    Single provisioning pass:
    Find all services in non-terminal states and advance them one step.
    """
    total_advanced = 0

    for state in LIFECYCLE[:-1]:  # skip 'active' — it's the terminal state
        next_state = LIFECYCLE[STATE_INDEX[state] + 1]
        services = fetch_services_by_state(base_url, api_path, state)

        if not services:
            continue

        log.info("Found %d service(s) in '%s' state", len(services), state)

        for svc in services:
            svc_id = svc.get("id", "?")
            svc_name = svc.get("name", "unnamed")

            ok, _ = advance_service(base_url, api_path, svc_id, next_state)
            if ok:
                log.info(
                    "  [%s] %s: %s -> %s",
                    svc_id[:8], svc_name, state, next_state,
                )
                total_advanced += 1
            else:
                log.warning(
                    "  [%s] %s: FAILED %s -> %s",
                    svc_id[:8], svc_name, state, next_state,
                )

            if step_delay > 0:
                time.sleep(step_delay)

    return total_advanced


def main():
    parser = argparse.ArgumentParser(description="Mock OSS Provisioner for TMF638 services")
    parser.add_argument("--host", default=os.getenv("OSS_HOST", "localhost"), help="Odoo host")
    parser.add_argument("--port", default=int(os.getenv("OSS_PORT", "8069")), type=int, help="Odoo port")
    parser.add_argument("--interval", default=int(os.getenv("OSS_INTERVAL", "10")), type=int,
                        help="Poll interval in seconds")
    parser.add_argument("--step-delay", default=int(os.getenv("OSS_STEP_DELAY", "3")), type=int,
                        help="Delay between state transitions in seconds (simulates provisioning time)")
    parser.add_argument("--once", action="store_true", help="Run one pass and exit")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"

    log.info("=" * 60)
    log.info("Mock OSS Provisioner starting")
    log.info("  Target: %s", base_url)
    log.info("  Poll interval: %ds, Step delay: %ds", args.interval, args.step_delay)
    log.info("=" * 60)

    # Discover working API path
    api_path = discover_api(base_url)

    pass_num = 0
    while True:
        pass_num += 1
        log.info("--- Pass #%d ---", pass_num)

        advanced = provision_cycle(base_url, api_path, args.step_delay)

        if advanced == 0:
            log.info("No services to advance. Idle.")
        else:
            log.info("Advanced %d service(s) this pass.", advanced)

        if args.once:
            log.info("Single pass mode. Exiting.")
            break

        log.info("Sleeping %ds...", args.interval)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
