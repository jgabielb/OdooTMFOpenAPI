# TMF / ODA End-to-End Business Scenarios

Real-world telco journeys expressed purely through the TMF Open APIs exposed by
this platform, exercising the ODA component wiring (`tmfc*_wiring`) along the
way. Each scenario is executable: `tools/e2e_scenarios.py` drives it against a
live instance and asserts the observable outcomes.

```
python tools/e2e_scenarios.py                       # run all scenarios
python tools/e2e_scenarios.py --only s1,s4          # run a subset
python tools/e2e_scenarios.py --base-url http://host:8069
```

Conventions: every record is created through the public TMF APIs (no direct
ORM access), ids are `tmf_id` UUIDs, and cross-references always use
`{"id": ..., "@type": ...}` TMF Ref shapes so the ODA side-cars can resolve
them by `tmf_id`.

---

## Scenario S1 — Residential fiber onboarding (order-to-cash)

**Actor:** consumer "Ana Martins" ordering *Fiber 1000* + *Mesh WiFi add-on*
for her home address.

**ODA components exercised:** TMFC001 (catalog), TMFC028/TMFC020 (party),
TMFC014 (location), TMFC027 (qualification), TMFC002 (quote/cart capture),
TMFC003 (order delivery orchestration), TMFC024 (billing account),
TMFC040 (usage), TMFC030/031 (bill).

| # | Step | TMF API | What the platform must do |
|---|------|---------|---------------------------|
| 1 | Design the commercial catalog: category, 2 product specs, price, 2 offerings | TMF620 | catalog events published (`ProductOffering*Event`); TMFC001 side-car resolves spec/party refs |
| 2 | Register the customer | TMF632 `individual` | party available for cross-refs by `tmf_id` |
| 3 | Validate the installation address | TMF673 `geographicAddressValidation` | address usable as `place` ref |
| 4 | Qualify the offering at the address | TMF679 `checkProductOfferingQualification` | TMFC027 resolves party/offering/place refs |
| 5 | Open a billing account | TMF666 `billingAccount` | TMFC024 resolves owner party |
| 6 | Quote both offerings | TMF648 `quote` | TMFC002 resolves quote-level party/offering refs |
| 7 | Put items in a cart | TMF663 `shoppingCart` | capture surface |
| 8 | Place the product order (2 items, place + relatedParty) | TMF622 `productOrder` | order created against `sale.order` |
| 9 | Start delivery: PATCH order → `inProgress` | TMF622 | **TMFC003** spawns one TMF641 service order per line + TMF701 flows |
| 10 | Field ops complete each service order | TMF641 PATCH `completed` | TMFC003 aggregates child states → product order `completed` |
| 11 | Rate usage against the product | TMF635 `usage` | TMFC040 resolves party/product refs |
| 12 | Produce the first bill | TMF678 `customerBill` | TMFC031 resolves billingAccount/party/usage refs |

**Success criteria:** order reaches `completed` purely through child
service-order transitions; every GET echoes the cross-refs intact.

---

## Scenario S2 — Mobile subscription with multiple resources

**Actor:** customer "Bruno Costa" activating a *5G Mobile* line (SIM card +
MSISDN) and a *5G Home Router* — three physical/logical resources across two
services.

**ODA components exercised:** TMFC010 (resource catalog), TMFC012 (resource
inventory), TMFC008 (service inventory), TMFC007 (service ordering),
TMFC011 (resource ordering).

| # | Step | TMF API | What the platform must do |
|---|------|---------|---------------------------|
| 1 | Define resource specs: *SIM Card*, *MSISDN*, *5G Router* | TMF634 `resourceSpecification` | TMFC010 catalog surface |
| 2 | Seed inventory: 1 SIM (ICCID), 1 MSISDN, 1 router (S/N), all `available` | TMF639 `resource` | resources exist as `stock.lot` |
| 3 | Define the *5G Mobile Line* service spec | TMF633 `serviceSpecification` | TMFC006 catalog surface |
| 4 | Activate the mobile service claiming SIM + MSISDN | TMF638 `service` (supportingResource ×2) | **inventory flow:** both resources leave `available` (reserved) |
| 5 | Activate the broadband service claiming the router | TMF638 `service` | router leaves `available` |
| 6 | Raise a service order referencing the mobile service | TMF641 `serviceOrder` | TMFC007 resolves service refs |
| 7 | Raise a resource order to replace the SIM | TMF652 `resourceOrder` | TMFC011 resolves order/resource refs |

**Success criteria:** after step 4/5, `GET resource/{id}` shows
`resourceStatus != available` for all three resources — ordering a device
decrements usable inventory.

---

## Scenario S3 — B2B multi-site enterprise (agreement-driven)

**Actor:** "Acme Retail Lda" — an organization with two shop locations, buying
*MPLS Access* per site plus one *Managed SD-WAN* overlay, under a framework
agreement.

**ODA components exercised:** TMFC028 (party/organization), TMFC014
(sites/locations), TMFC039 (agreement), TMFC009 (service qualification),
TMFC001/TMFC002 (catalog + order capture).

| # | Step | TMF API | What the platform must do |
|---|------|---------|---------------------------|
| 1 | Register the organization | TMF632 `organization` | org party by `tmf_id` |
| 2 | Register 2 shop addresses + 2 geographic sites | TMF673 / TMF674 | sites carry `place` + `relatedParty`; TMFC014 resolves party refs |
| 3 | Design 2 offerings: *MPLS Access*, *Managed SD-WAN* | TMF620 | catalog refs for the agreement |
| 4 | Sign the framework agreement (engagedParty + both offerings) | TMF651 `agreement` | TMFC039 resolves engaged party + offering refs |
| 5 | Qualify service at each site | TMF645 `checkServiceQualification` (×2, with `place`) | TMFC009 resolves place/party refs |
| 6 | Order: 3 items (MPLS site A, MPLS site B, SD-WAN) referencing the agreement | TMF622 `productOrder` | multi-item order capture |
| 7 | Orchestrate delivery | TMF622 PATCH `inProgress` | TMFC003 spawns 3 service orders (one per line) |

**Success criteria:** agreement echoes both offering refs and the engaged
party; 3 service orders exist for the enterprise order.

---

## Scenario S4 — Assurance: alarm → problem → ticket (+ thresholds)

**Actor:** NOC operator handling a fiber-cut alarm on Ana's access service.

**ODA components exercised:** TMFC043 (fault management, incl. ODA event
reconciliation through its listeners), TMFC037/038 (performance thresholds via
the TMF649 surface).

| # | Step | TMF API | What the platform must do |
|---|------|---------|---------------------------|
| 1 | Network raises a critical alarm | TMF642 `alarm` | alarm record created |
| 2 | Upstream publishes `AlarmStateChangeEvent` (cleared) | POST `/tmfc043/listener/alarm` | **ODA reconciliation:** local alarm state becomes `cleared` |
| 3 | NOC opens a service problem referencing the alarm | TMF656 `serviceProblem` | problem record created |
| 4 | Problem resolution event arrives | POST `/tmfc043/listener/serviceProblem` | local problem state becomes `resolved` |
| 5 | Customer-facing trouble ticket | TMF621 `troubleTicket` | ticket created |
| 6 | Ticket resolution event arrives | POST `/tmfc043/listener/troubleTicket` | local ticket status reconciled |
| 7 | Define a performance threshold + job | TMF649 `threshold`, `thresholdJob` | new TMFC037/038 exposed surface answers CRUD |

**Success criteria:** steps 2/4/6 prove the listener contract *changes local
state* (GET shows the new state after the event) — not just acknowledgement.

---

## Data relationships across scenarios

```
Party (TMF632) ──owns──> BillingAccount (TMF666) ──billed-by──> CustomerBill (TMF678)
   │                                                     ▲
   │ relatedParty                                        │ usage (TMF635)
   ▼                                                     │
ProductOrder (TMF622) ──TMFC003──> ServiceOrder (TMF641) ──> ResourceOrder (TMF652)
   │ productOffering                    │ service                 │ resource
   ▼                                    ▼                         ▼
ProductOffering (TMF620)         Service (TMF638) ──supporting──> Resource (TMF639/stock.lot)
   │ productSpecification               │ serviceSpecification
   ▼                                    ▼
ProductSpec (TMF620)             ServiceSpec (TMF633) ── ResourceSpec (TMF634)
   │ place                              │ place
   ▼                                    ▼
GeographicAddress (TMF673) ── GeographicSite (TMF674) ── Agreement (TMF651)
```

## Notes / known limitations

- The runner uses only public (CTK-facing) endpoints; side-car relational
  fields (`tmfc*_...`) are asserted indirectly through observable behaviour
  (state reconciliation, ref echo, inventory status transitions). Direct field
  assertions need Odoo auth (see `verify_wiring.py` `_check_odoo_field`).
- TMFC003 spawns one service order per sale-order line **only when the
  product order has lines**; the TMF622 controller creates lines from
  `productOrderItem` using catalog offerings, falling back to a generic
  product when the offering has no Odoo variant.
- Scenario data is uniquely tagged per run (`E2E_<tag>`), so repeated runs
  don't collide; nothing is cleaned up on purpose — the records double as demo
  data.
