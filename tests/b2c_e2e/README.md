# B2C Order-to-Activate — E2E Test Suite

Runnable pytest mapping of `tests/b2c_order_to_activate.feature` against a
live Odoo + TMF API instance.

## Layout

One file per Gherkin feature step:

| File | Covers |
|---|---|
| `conftest.py` | shared TMFClient, fixtures (`tmf`, `any_offering`, `created_party`) |
| `test_step1_registration.py` | TMF632 PartyMgmt — new customer self-registration |
| `test_step2_credit_check.py` | TMF645 CreditManagement — `xfail` until endpoint lands |
| `test_step3_catalog.py` | TMF620 ProductCatalog — browse, pricing |
| `test_step4_order.py` | TMF622 ProductOrdering — create + state transitions + idempotency |
| `test_step5_service_order.py` | TMF641 ServiceOrdering — decomposition (partial) |
| `test_step6_resilience.py` | held-state + sibling-isolation |
| `test_step7_activation.py` | completion + invoice (billing bridge) |
| `test_happy_path_e2e.py` | full combined happy-path scenario |

## Setup

```powershell
cd tests/b2c_e2e
pip install -r requirements.txt
```

## Run

```powershell
# Full suite (Odoo must be running on localhost:8069)
pytest -v

# Only the smoke tests
pytest -v -m smoke

# Only the full happy-path
pytest -v -m happy_path

# Against a different Odoo
$env:TMF_BASE_URL = "https://localhost"   # via nginx
pytest -v

# With API auth enabled
$env:TMF_API_KEY = "your-key-here"
pytest -v
```

## Interpretation

- **PASSED** — endpoint works as specified
- **XFAIL** — scenario documented but feature not yet implemented (expected)
- **FAILED** — regression; fix it

As features land, remove the corresponding `xfail` marker so the test
becomes a real gate.

## Full flow with OSS simulator

Steps 5–7 exercise provisioning via the TMF API directly. For the *full*
service-activation flow (which triggers billing automatically), run the
mock OSS container in parallel so services advance through
feasabilityChecked → designed → reserved → active:

```powershell
cd ../../mock_oss
docker compose up -d
cd ../tests/b2c_e2e
pytest -v -m e2e
```
