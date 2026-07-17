# Commercialization Roadmap — OdooTMFOpenAPI

Purpose: track the work needed to turn this repository into a **commercial, production-ready,
TM Forum-compliant BSS stack**. This file is the single tracking point: items are only added,
checked, or re-scoped by editing it in a PR, so `git log docs/ROADMAP.md` is the audit trail.

Last reviewed: 2026-07-17 · Review cadence: monthly and at every phase gate.

Conventions:
- `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` deferred/waived (reason inline)
- Every `[x]` item MUST carry an evidence link (file path, commit SHA, CI run URL, or doc anchor) —
  same rule as [TMFC_IMPLEMENTATION_STATUS.md](TMFC_IMPLEMENTATION_STATUS.md).

## Status snapshot

| Phase | Status | Gate criterion | Last change |
|---|---|---|---|
| 0 — Now (protect & declare) | ⚠️ gate met; 2 items deferred | CI green on default branch + ODA conformance docs published | 2026-07-17 |
| 1 — Open API certification | ❌ not started | TM Forum conformance certificates for top-10 APIs | — |
| 2 — ODA Components & Canvas | ❌ not started | ≥1 component certified/running on ODA Canvas | — |
| 3 — Production hardening | ❌ not started | Reference deployment passes load + security review | — |
| 4 — SID depth | ⚠️ baseline done | ≥50% SID entity coverage on Customer/Product/Service/Resource | 2026-07-15 |
| 5 — Commercial packaging | ❌ not started | Sellable, versioned, documented release | — |

Legend: ✅ complete · ⚠️ in progress · ❌ not started

## Phase 0 — Now (protect & declare)

Goal: stop compliance regressions and turn existing work into declarable evidence.
Exit criteria: CI pipeline green on the default branch; ODA conformance declarations generated
for all 34 documented TMFC components; evidence artifacts tracked in git.

- [x] GitHub Actions CI: lint + full addon install + API smoke + pytest suites — green on master (run 29603615370: 362/362 smoke steps, 157 tests, 0 failures) — evidence: `.github/workflows/ci.yml`, PR #9 merged as c948dfb (2026-07-17)
- [x] ODA conformance generator (`tools/gen_oda_conformance.py`) joining TMFC spec requirements with SID coverage — evidence: [ODA_CONFORMANCE.md](ODA_CONFORMANCE.md): 20 declarable / 13 partial / 1 not declarable / 1 waived (2026-07-16)
- [x] SID ABE → Odoo coverage matrix generator + baseline — evidence: [SID_ABE_COVERAGE_MATRIX.md](SID_ABE_COVERAGE_MATRIX.md), `tools/gen_sid_coverage.py` (2026-07-15)
- [x] Reconcile stale `oda_component_specs/ODA_COMPONENT_REGISTRY.md` wiring statuses — evidence: registry "Last reconciled: 2026-07-16" header
- [x] Root `requirements-dev.txt` aggregating test/tool dependencies — evidence: `requirements-dev.txt` (2026-07-16)
- [x] Track generated evidence (SID coverage JSON/MD, conformance outputs) in git — evidence: commit eb9d2f7 (2026-07-16)
- [ ] CI iteration 2: run `mock_oss/oss_simulator.py` in CI and enable the `-m e2e` pytest marker
- [ ] Move the working clone off OneDrive (sync + .git corruption risk); keep OneDrive for documents only — user action

### Phase 0 backlog / stretch
- [ ] Ratchet thresholds for `tools/audit_gaps.py` / `audit_controllers.py` (currently informational)
- [ ] Normalize addon manifest `version` keys to `19.0.x.y.z` scheme
- [ ] Fix capitalized-alias route generation in generated controllers: `path.replace("resource", "Resource")` also rewrites the API base (e.g. `/tmf-api/WarrantyManagement/v4/Warranty`), so base-resource aliases 404 (found by the CI smoke gate 2026-07-16)
- [ ] Restore full CRUD in the TMF638 smoke entry once the in-progress `tmf_service_inventory` supportingResource rework lands (entry reduced to read-only 2026-07-16)

## Phase 1 — Open API certification

Goal: convert CTK green runs into official, marketable TM Forum conformance certificates.
Exit criteria: certificates issued and listed for the top-10 commercial APIs.

- [ ] TM Forum membership active (prerequisite for the conformance program)
- [ ] Submit CTK evidence for: TMF620, TMF622, TMF629, TMF632, TMF637, TMF638, TMF641, TMF666, TMF676, TMF678
- [ ] Port `tools/run_ctk_batch.py` from Windows `run.bat` launchers to Linux/newman so CTK joins CI
- [ ] Nightly/weekly CTK batch in CI once ported (protects the 100% claim continuously)
- [ ] Publish certification badges + certificate links in `README.md`
- [ ] Extend certification to the remaining CTK-covered APIs (48 total, see `oda_component_specs/TMF_API_REGISTRY.md`)

## Phase 2 — ODA Components & Canvas

Goal: package the stack as ODA Components deployable on an ODA Canvas — where telco procurement is heading.
Exit criteria: at least one component (target: TMFC001 Product Catalog) certified/running on a Canvas.

- [ ] Containerize the app stack: odoo + postgres compose (extend `deploy/` beyond the nginx edge)
- [ ] Health/readiness/metrics endpoints per ODA component management function
- [ ] Generate `component.yaml` envelopes per TMFC from the local spec YAMLs (`ODAComponentDocumentation/`) + `docs/oda_conformance.json`
- [ ] ODA Canvas (Kubernetes) deployment PoC with one component exposed via the Canvas API gateway
- [ ] Security function wiring (Canvas-managed authN) for the PoC component
- [ ] Expand to the CoreCommerce component set (TMFC001/002/003/005/027)

## Phase 3 — Production hardening

Goal: a reference deployment a paying customer can run.
Exit criteria: load tests pass agreed SLOs; security review passes; ops runbook exists.

- [ ] OAuth2/OIDC (Keycloak) replacing/augmenting `tmf.api.key`; scope model per API
- [ ] Rate limiting + audit logging on all TMF endpoints
- [ ] Event hub hardening: retry, dead-letter, at-least-once delivery for `/hub` listeners
- [ ] Billing run load tests (k6/locust): usage → rating → `account.move` at realistic volumes, with SLOs
- [ ] Postgres HA + backup/restore drills (documented RPO/RTO)
- [ ] Observability: structured logs, metrics dashboards, alerting
- [ ] Ops runbook: install, upgrade, DB migration, incident response

## Phase 4 — SID depth

Goal: raise SID information-model coverage where it matters commercially.
Exit criteria: ≥50% entity coverage on Customer, Product, Service, Resource domains
(baseline 2026-07-15: 6% overall — see [SID_ABE_COVERAGE_MATRIX.md](SID_ABE_COVERAGE_MATRIX.md)).

- [x] Baseline matrix + curation loop in place — evidence: `tools/gen_sid_coverage.py`, `mappings/sid_abe_map.json` (2026-07-15)
- [ ] Curate `docs/sid_abe_coverage.todo.json` queue: Customer domain to ≥50%
- [ ] Product domain to ≥50%
- [ ] Service + Resource domains to ≥50%
- [ ] Re-run matrix on each GB922 release (current: v25.5)
- [ ] eTOM (Business Process Framework) mapping document for RFP responses

## Phase 5 — Commercial packaging

Goal: something a customer can buy, install, and get supported on.
Exit criteria: versioned release with docs, demo, listing, and a support model.

- [ ] Versioned releases (git tags + changelog + upgrade notes)
- [ ] Installation & sizing documentation (from Phase 3 reference deployment)
- [ ] Public demo environment with seeded scenario data (`mock_oss/seed_demo_data.py`)
- [ ] TM Forum solution directory / marketplace listing (uses Phase 1 certificates)
- [ ] Licensing review: LGPL-3 addons + Odoo Community baseline; commercial edition strategy
- [ ] Pricing, support tiers, SLA definitions

## Parking lot (unphased)

- Multi-tenancy strategy (one instance per operator vs shared; interacts with the RUT→Accounts→Services model)
- AI/Intent APIs productization (TMF915/TMF921 family already scaffolded)
- Open Gateway (CAMARA) exposure of the `tmf_open_gateway_*` addons

## Decision log

| Date | Decision | Rationale | Link |
|---|---|---|---|
| 2026-07-15 | SID coverage tooling: curated JSON overrides, Patterns domain summarized, container ABEs = N/A | Keep matrix honest and regeneration deterministic | `tools/gen_sid_coverage.py` |
| 2026-07-16 | CTK excluded from CI phase 0; stays a local Windows task until ported to newman | Launchers are Windows-only, kits are not redistributable in-repo | `tools/run_ctk_batch.py` |
| 2026-07-16 | TMFC→ABE requirements extracted from local ODA component YAMLs into tracked `mappings/tmfc_requirements.json` | Machine-readable, authoritative, keeps CI stdlib-only | `tools/gen_oda_conformance.py` |
| 2026-07-16 | `tmf_service_level_objective` excluded from CI install | Depends on Enterprise-only `helpdesk` | `tools/ci/compute_install_list.py` |
| 2026-07-17 | PR #9 merged — CI now protects master on every push/PR | Phase 0 gate met; regressions to the 100% CTK / conformance evidence now blocked | commit c948dfb |
