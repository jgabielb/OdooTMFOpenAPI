#!/usr/bin/env python3
"""
Mock OSS Simulator (Containerized)
===================================
Simulates an external OSS system that consumes the TMF638 Service Inventory API
to advance services through the provisioning lifecycle.

Lifecycle:
  feasabilityChecked -> designed -> reserved -> inactive -> active

This service is meant to run as a standalone container that polls the Odoo TMF API
and advances service states, simulating real OSS processing time.

All configuration is via environment variables (see config.env.example).
"""

import json
import logging
import os
import signal
import sys
import time

import requests

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [OSS-SIM] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("oss_simulator")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ODOO_BASE_URL = os.getenv("ODOO_BASE_URL", "http://host.docker.internal:8069")
API_KEY = os.getenv("ODOO_API_KEY", "")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))
STEP_DELAY = int(os.getenv("STEP_DELAY", "5"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")

# TMF638 provisioning lifecycle
LIFECYCLE = [
    "feasabilityChecked",
    "designed",
    "reserved",
    "inactive",
    "active",
]

STATE_INDEX = {s: i for i, s in enumerate(LIFECYCLE)}

# API paths to try (in order of preference)
API_PATHS = [
    "/tmf-api/serviceInventory/v5/service",
    "/tmf-api/serviceInventoryManagement/v5/service",
    "/tmf-api/serviceInventory/v4/service",
]

# Graceful shutdown
_running = True


def _shutdown(signum, frame):
    global _running
    log.info("Received signal %s, shutting down gracefully...", signum)
    _running = False


signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _headers():
    """Build common request headers."""
    h = {
        "Accept": "application/json",
        "Content-Type": "application/merge-patch+json",
    }
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


def _get(url, params=None):
    """GET request with error handling."""
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        log.warning("GET %s -> %d: %s", url, e.response.status_code, e.response.text[:200])
        return None
    except requests.exceptions.RequestException as e:
        log.error("GET %s failed: %s", url, e)
        return None


def _patch(url, data):
    """PATCH request with error handling."""
    try:
        resp = requests.patch(url, headers=_headers(), json=data, timeout=30)
        resp.raise_for_status()
        return True, resp.json() if resp.text.strip() else None
    except requests.exceptions.HTTPError as e:
        log.warning("PATCH %s -> %d: %s", url, e.response.status_code, e.response.text[:200])
        return False, None
    except requests.exceptions.RequestException as e:
        log.error("PATCH %s failed: %s", url, e)
        return False, None


# ---------------------------------------------------------------------------
# API discovery
# ---------------------------------------------------------------------------
def discover_api():
    """Try API paths and return the first one that responds."""
    for path in API_PATHS:
        url = f"{ODOO_BASE_URL}{path}"
        try:
            resp = requests.get(url, headers=_headers(), params={"limit": 1}, timeout=10)
            if resp.status_code == 200:
                log.info("Discovered TMF API at %s", path)
                return path
        except requests.exceptions.RequestException:
            continue
    log.warning("No API path responded, using default: %s", API_PATHS[0])
    return API_PATHS[0]


# ---------------------------------------------------------------------------
# Provisioning logic
# ---------------------------------------------------------------------------
def fetch_services(api_path, state):
    """Fetch services in a given state."""
    url = f"{ODOO_BASE_URL}{api_path}"
    data = _get(url, params={"state": state})
    if isinstance(data, list):
        return data
    return []


def advance_service(api_path, service_id, current_state, next_state):
    """PATCH a service to the next lifecycle state."""
    url = f"{ODOO_BASE_URL}{api_path}/{service_id}"
    ok, resp = _patch(url, {"state": next_state})
    return ok


def provision_cycle(api_path):
    """
    Single provisioning pass: find services in non-terminal states and
    advance each one step.
    """
    total = 0

    for state in LIFECYCLE[:-1]:  # skip 'active' (terminal)
        next_state = LIFECYCLE[STATE_INDEX[state] + 1]
        services = fetch_services(api_path, state)

        if not services:
            continue

        log.info("Found %d service(s) in '%s'", len(services), state)

        for svc in services:
            svc_id = svc.get("id", "?")
            svc_name = svc.get("name", "unnamed")
            svc_id_short = svc_id[:12] if isinstance(svc_id, str) else str(svc_id)

            if DRY_RUN:
                log.info("  [DRY-RUN] [%s] %s: %s -> %s", svc_id_short, svc_name, state, next_state)
                total += 1
                continue

            ok = advance_service(api_path, svc_id, state, next_state)
            if ok:
                log.info("  [%s] %s: %s -> %s", svc_id_short, svc_name, state, next_state)
                total += 1
            else:
                log.warning("  [%s] %s: FAILED %s -> %s", svc_id_short, svc_name, state, next_state)

            if STEP_DELAY > 0 and _running:
                time.sleep(STEP_DELAY)

    return total


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    log.info("=" * 60)
    log.info("Mock OSS Simulator starting")
    log.info("  Odoo URL:       %s", ODOO_BASE_URL)
    log.info("  API Key:        %s", "***" if API_KEY else "(none)")
    log.info("  Poll interval:  %ds", POLL_INTERVAL)
    log.info("  Step delay:     %ds", STEP_DELAY)
    log.info("  Dry run:        %s", DRY_RUN)
    log.info("  Lifecycle:      %s", " -> ".join(LIFECYCLE))
    log.info("=" * 60)

    # Wait for Odoo to be reachable before starting
    log.info("Waiting for Odoo at %s ...", ODOO_BASE_URL)
    while _running:
        try:
            resp = requests.get(f"{ODOO_BASE_URL}/web/login", timeout=5)
            if resp.status_code == 200:
                log.info("Odoo is reachable.")
                break
        except requests.exceptions.RequestException:
            pass
        log.info("  Odoo not ready, retrying in 5s...")
        time.sleep(5)

    if not _running:
        return

    # Discover API path
    api_path = discover_api()

    pass_num = 0
    while _running:
        pass_num += 1
        log.info("--- Pass #%d ---", pass_num)

        advanced = provision_cycle(api_path)

        if advanced == 0:
            log.info("No services to advance. Idle.")
        else:
            log.info("Advanced %d service(s) this pass.", advanced)

        # Sleep in small increments to allow graceful shutdown
        for _ in range(POLL_INTERVAL):
            if not _running:
                break
            time.sleep(1)

    log.info("Mock OSS Simulator stopped.")


if __name__ == "__main__":
    main()
