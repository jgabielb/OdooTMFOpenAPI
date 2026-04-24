# Advanced B2C Test Suite

Complements [`tests/b2c_e2e/`](../b2c_e2e/) with real-world telco scenarios
beyond basic order-to-activate.

Gherkin source: [`tests/b2c_advanced.feature`](../b2c_advanced.feature).

## What it covers

| Area | File | What it exercises |
|---|---|---|
| Product design | `test_product_catalog_design.py` | Offering → Spec linkage, characteristics, bundles, resource specs |
| Product variants | `test_product_variants.py` | Same spec / different characteristic values (FIBER_200/600/1G) |
| Inventory | `test_inventory.py` | TMF639 resource inventory, serials, stock decrement |
| Multi-account | `test_multi_account.py` | One partner → multiple accounts, per-account billing |
| Plan change | `test_plan_change.py` | Upgrade/downgrade, service identity preservation, proration |
| Promotion | `test_promotion.py` | Apply/swap/remove promotion on active service |
| Device exchange | `test_device_exchange.py` | CPE swap, warranty charge logic |
| SVAs | `test_sva.py` | Value-added services attached as child services |
| Address change | `test_address_change.py` | Relocation with feasibility gate |
| Owner change | `test_owner_change.py` | Ownership transfer, balance retention |
| Data integrity | `test_data_integrity.py` | Cross-system invariants |

## Run

```powershell
cd tests/b2c_advanced
pytest -v

# Only one area
pytest -v -m plan_change

# Only the currently-passing ones (skip xfails)
pytest -v -m "not xfail"
```

## Interpretation

Most tests are **`xfail`** on purpose — they document contracts for
features that don't exist yet. As each feature lands, remove its
`@pytest.mark.xfail` line and it becomes a real gate.

**PASSED xfails** (marked `XPASS`) mean the feature is now working and
the xfail marker should be removed.
