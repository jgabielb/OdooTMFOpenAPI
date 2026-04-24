# Mock OSS Simulator

Containerized service that simulates an external OSS system. It polls the
Odoo TMF638 Service Inventory API and advances services through the
provisioning lifecycle.

## Lifecycle

```
feasabilityChecked -> designed -> reserved -> inactive -> active
```

Each polling cycle advances services ONE step. With default settings (15s poll,
5s step delay), a service goes from `feasabilityChecked` to `active` in about
80 seconds.

## Quick Start (Docker Compose)

```bash
# 1. Copy and edit config
cp config.env.example config.env

# 2. Build and run
docker compose up -d

# 3. View logs
docker compose logs -f
```

## Run Standalone (Docker)

```bash
docker build -t mock-oss .
docker run --rm \
  -e ODOO_BASE_URL=http://host.docker.internal:8069 \
  -e POLL_INTERVAL=15 \
  -e STEP_DELAY=5 \
  mock-oss
```

## Run Locally (no Docker)

```bash
pip install -r requirements.txt
python oss_simulator.py
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ODOO_BASE_URL` | `http://host.docker.internal:8069` | Odoo instance URL |
| `ODOO_API_KEY` | (empty) | API key sent as `X-API-Key` header |
| `POLL_INTERVAL` | `15` | Seconds between polling cycles |
| `STEP_DELAY` | `5` | Seconds between individual state transitions |
| `DRY_RUN` | `false` | Log transitions without PATCHing |
| `LOG_LEVEL` | `INFO` | Python log level |

## How It Works

1. Waits for Odoo to be reachable
2. Auto-discovers the TMF638 API path (tries v5 then v4)
3. Each cycle: queries for services in each non-terminal state
4. PATCHes each service to the next state in the lifecycle
5. Sleeps `STEP_DELAY` between transitions, `POLL_INTERVAL` between cycles
6. Handles SIGTERM/SIGINT for graceful shutdown

## Seed Scripts (separate purpose)

The seed scripts create initial test data via Odoo XML-RPC (not the TMF API):

- `seed_demo_data.py` -- creates a demo telecom customer with multiple accounts
  and services
- `seed_condell_order.py` -- creates a realistic B2B order based on a real
  Siebel migration scenario

Run them before starting the simulator to have services to advance:

```bash
python seed_demo_data.py --host localhost --port 8069
python seed_condell_order.py --host localhost --port 8069
```

## Architecture

```
  seed scripts (XML-RPC)         mock OSS simulator (TMF API)
  ───────────────────────        ────────────────────────────
  Create customers, accounts,    Poll GET /tmf-api/.../service?state=X
  orders, services via Odoo      Advance via PATCH /tmf-api/.../service/{id}
  internal API                   Runs as standalone container
```
