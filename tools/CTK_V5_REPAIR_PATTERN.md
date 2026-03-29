# CTK v5 Repair Pattern

## Purpose

Some TM Forum v5 CTK bundles are shipped with a broken wrapper image or launcher logic.
The TMF638 v5 CTK bundle in our environment was one such case: the official image recursively tried to invoke Docker from inside the container and failed before executing any conformance tests.

This document captures the repair pattern used to recover a runnable local CTK while preserving a clear distinction between:

1. **bundle/runtime defects**
2. **real API conformance defects**

---

## Symptom Pattern

Typical failure signals from a broken v5 CTK bundle:

- `docker: command not found` inside the CTK container
- launcher requires `platform` env var but still does not run tests
- container exits before producing `reports/index.html` or `reports/index.json`
- image contents only include wrapper files (`run.sh`, `run.bat`, `docker-compose.yaml`, `config.json`) and do **not** include the actual CTK engine files

When this happens, treat the issue as a **packaging/runtime problem**, not as an API failure.

---

## Reference Architecture

Use a **known-good TM Forum v5 CTK engine image** as the execution base.

For TMF638 we used:

- base engine image: `tmforumorg/tmf620-v5.0.0-ctk:1.0.0`

Why this works:

- it already contains the healthy v5 Cypress CTK execution engine under `/ctk/DO_NOT_CHANGE`
- it copies reports to `/reports`
- it accepts mounted `/config/config.json`
- it behaves like the newer healthy TM Forum v5 CTKs used elsewhere in this repository

This is a **runtime substitution pattern**, not a claim that TMF620 semantics are reused. Only the **CTK engine shell** is reused; the target API spec and CTK test manifest must be replaced.

---

## Repair Strategy

### Step 1 — Confirm the official bundle is structurally broken

Inspect:

- `run.bat`
- `run.sh`
- `docker-compose.yaml`
- image contents via `docker run --entrypoint sh ...`

If the image only contains wrapper files and tries to call Docker again from inside itself, the bundle is broken.

### Step 2 — Build a local repaired image

Create a local `Dockerfile` like this:

```dockerfile
FROM tmforumorg/tmf620-v5.0.0-ctk:1.0.0
USER root
COPY repair_assets/oas.yaml /ctk/DO_NOT_CHANGE/oas.yaml
COPY repair_assets/ctk.json /ctk/DO_NOT_CHANGE/cypress/fixtures/ctk.json
```

### Step 3 — Replace compose to build the local image

Example:

```yaml
name: tmf638-ctk-v5

networks:
  tmf:
    external: true

services:
  ctk:
    build:
      context: .
      dockerfile: Dockerfile
    image: local/tmf638-v5.0.0-ctk-fixed:1.0.0
    platform: linux/amd64
    container_name: tmf638-ctk-v5
    volumes:
      - ./reports:/reports:rw
      - ./config.json:/config/config.json:ro
    networks:
      - tmf
```

### Step 4 — Provide repair assets

Under `repair_assets/` add:

- `oas.yaml` → target API v5 OpenAPI spec
- `ctk.json` → test manifest for the target API

### Step 5 — Run CTK and separate failures

After the runtime repair, test failures should be interpreted as **real conformance defects** unless proven otherwise.

---

## TMF638 v5 Case Study

### Bundle defect

The official `tmforumorg/tmf638-v5.0.0-ctk:1.0.0` image was broken as a launcher artifact:

- it exposed only wrapper files in `/ctk`
- it set `/ctk/run.sh` as entrypoint
- `run.sh` attempted `docker compose run -d ctk` from inside the container
- the image did not contain a functional nested Docker setup

So the original bundle failed before performing meaningful CTK validation.

### Local repair result

After rebuilding the bundle on top of a healthy TM Forum v5 engine and wiring TMF638-specific assets, the CTK became runnable and exposed real API defects.

### Real TMF638 v5 conformance defects found

1. `endDate` emitted as `null` while schema expected a string when present
2. `relatedParty.partyOrPartyRole` created a `oneOf` ambiguity

### Fix pattern in the API

TMF638 required **version-aware serialization**:

- **v4 surface**: explicit null-shaped payloads helped satisfy the older CTK expectations
- **v5 surface**: omit nullable or ambiguous optional fields when not required

This let us keep:

- TMF638 v4 CTK = PASS
- TMF638 repaired v5 CTK = PASS

---

## Design Rules

### 1. Do not pretend a broken official CTK is healthy

Call the repaired bundle what it is:

- **local repaired CTK bundle**

That preserves auditability.

### 2. Repair runtime first, API second

Never chase serializer/controller bugs while the CTK cannot even execute.

### 3. Reuse a healthy engine, not a broken wrapper

The engine is the valuable part. Broken wrapper images should be replaced, not endlessly patched.

### 4. Keep version behavior explicit

If v4 and v5 require different payload shapes, isolate that intentionally in serializer/controller logic.

---

## Recommended Reuse Template for Future Broken v5 CTKs

When another TM Forum v5 CTK bundle is broken:

1. verify the official bundle is wrapper-broken
2. pick a healthy v5 CTK engine image already validated locally
3. replace only:
   - `oas.yaml`
   - `ctk.json`
   - `config.json`
4. run CTK
5. fix real conformance issues in the API
6. document the result as a **local repair**

---

## Scope Note

This pattern repairs execution reliability in our environment.
It does **not** make the local repaired bundle an official TM Forum artifact.
For formal certification workflows, always prefer an official fixed CTK release from TM Forum when available.
