# Mock OSS Provisioner

Simulates an external OSS/provisioning system that advances TMF638 service
states through the lifecycle via the TMF API.

## Lifecycle

```
feasabilityChecked -> designed -> reserved -> inactive -> active
```

Each polling cycle advances services ONE step. With default settings (10s poll,
3s step delay), a service goes from `feasabilityChecked` to `active` in ~52s.

## Run locally

```bash
# Default: localhost:8069, 10s poll
python oss_provisioner.py

# Custom host/timing
python oss_provisioner.py --host 192.168.1.5 --port 8069 --interval 5 --step-delay 1

# Single pass (useful for testing)
python oss_provisioner.py --once
```

## Run as Docker container

```bash
docker build -t mock-oss .
docker run --rm mock-oss

# Or with custom settings
docker run --rm -e OSS_HOST=192.168.1.5 -e OSS_INTERVAL=5 -e OSS_STEP_DELAY=1 mock-oss
```

## How it works

1. Polls TMF638 API for services in each non-terminal state
2. PATCHes each service to the next state in the lifecycle
3. Sleeps `step-delay` seconds between individual transitions
4. Sleeps `interval` seconds between full polling cycles
5. Repeats forever (or once with `--once`)

No dependencies beyond Python stdlib.
