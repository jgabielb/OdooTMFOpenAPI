#!/usr/bin/env python3
"""e2e_scenarios.py — Real-world TMF/ODA business scenarios, executable.

Design document: docs/TMF_E2E_SCENARIOS.md

Scenarios (run all, or --only s1,s3):
  s1  Residential fiber onboarding (order-to-cash, TMFC003 orchestration)
  s2  Mobile subscription with multiple resources (inventory flows)
  s3  B2B multi-site enterprise (agreement-driven, multiple service products)
  s4  Assurance: alarm -> problem -> ticket (+ TMF649 thresholds)

Usage:
    python tools/e2e_scenarios.py
    python tools/e2e_scenarios.py --base-url http://localhost:8069 --only s1,s4
"""

import argparse
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any

import requests

DEFAULT_BASE = "http://localhost:8069"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

API = {
    "party":      "/tmf-api/partyManagement/v5",
    "catalog":    "/tmf-api/productCatalogManagement/v5",
    "poq":        "/tmf-api/productOfferingQualificationManagement/v5",
    "address":    "/tmf-api/geographicAddressManagement/v4",
    "site":       "/tmf-api/geographicSiteManagement/v4",
    "account":    "/tmf-api/accountManagement/v4",
    "quote":      "/tmf-api/quoteManagement/v4",
    "cart":       "/tmf-api/shoppingCartManagement/v5",
    "order":      "/tmf-api/productOrderingManagement/v5",
    "sorder":     "/tmf-api/serviceOrdering/v4",
    "rorder":     "/tmf-api/resourceOrdering/v4",
    "scatalog":   "/tmf-api/serviceCatalogManagement/v4",
    "rcatalog":   "/tmf-api/resourceCatalogManagement/v5",
    "sinv":       "/tmf-api/serviceInventoryManagement/v5",
    "rinv":       "/tmf-api/resourceInventoryManagement/v5",
    "sq":         "/tmf-api/serviceQualificationManagement/v4",
    "agreement":  "/tmf-api/agreementManagement/v4",
    "usage":      "/tmf-api/usageManagement/v4",
    "bill":       "/tmf-api/customerBillManagement/v5",
    "alarm":      "/tmf-api/alarmManagement/v5",
    "problem":    "/tmf-api/serviceProblemManagement/v5",
    "ticket":     "/tmf-api/troubleTicketManagement/v5",
    "threshold":  "/tmf-api/thresholdManagement/v4",
}


class Fail(Exception):
    pass


@dataclass
class Result:
    scenario: str
    check: str
    passed: bool
    detail: str = ""


results: list[Result] = []


def ok(scenario: str, check: str, detail: str = ""):
    results.append(Result(scenario, check, True, detail))
    print(f"  \033[32mOK\033[0m {check}" + (f"  ({detail})" if detail else ""))


def fail(scenario: str, check: str, detail: str = ""):
    results.append(Result(scenario, check, False, detail))
    print(f"  \033[31mFAIL\033[0m {check}" + (f"  ({detail})" if detail else ""))


def note(check: str, detail: str = ""):
    print(f"  \033[36m--\033[0m {check}" + (f"  ({detail})" if detail else ""))


def post(base: str, path: str, payload: dict, expect=(200, 201)) -> dict:
    url = base + path
    r = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    if r.status_code not in expect:
        raise Fail(f"POST {path} -> {r.status_code}: {r.text[:250]}")
    try:
        return r.json()
    except Exception:
        return {}


def patch(base: str, path: str, payload: dict, expect=(200, 201)) -> dict:
    url = base + path
    r = requests.patch(url, headers=HEADERS, json=payload, timeout=30)
    if r.status_code not in expect:
        raise Fail(f"PATCH {path} -> {r.status_code}: {r.text[:250]}")
    try:
        return r.json()
    except Exception:
        return {}


def get(base: str, path: str) -> Any:
    url = base + path
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        raise Fail(f"GET {path} -> {r.status_code}: {r.text[:250]}")
    return r.json()


def tag(n: int = 6) -> str:
    return uuid.uuid4().hex[:n]


def rid(payload: dict) -> str:
    return str(payload.get("id") or payload.get("tmf_id") or "")


# ---------------------------------------------------------------------------
# Shared builders
# ---------------------------------------------------------------------------

def make_individual(base, s, given, family):
    party = post(base, API["party"] + "/individual", {
        "givenName": given, "familyName": family, "@type": "Individual",
    })
    ok(s, f"party: registered {given} {family}", rid(party))
    return party


def make_address(base, s, street, city="Lisboa"):
    addr = post(base, API["address"] + "/geographicAddress", {
        "streetName": street, "city": city, "country": "PT",
        "@type": "GeographicAddress",
    })
    ok(s, f"address: {street}, {city}", rid(addr))
    return addr


def make_offering(base, s, name, spec_name=None, price=None):
    spec = post(base, API["catalog"] + "/productSpecification", {
        "name": spec_name or f"{name} Spec", "version": "1.0",
        "lifecycleStatus": "Active", "@type": "ProductSpecification",
    })
    offering_payload = {
        "name": name, "lifecycleStatus": "Active", "@type": "ProductOffering",
        "productSpecification": {"id": rid(spec), "href": spec.get("href", "")},
    }
    offering = post(base, API["catalog"] + "/productOffering", offering_payload)
    detail = rid(offering)
    if price is not None:
        try:
            pop = post(base, API["catalog"] + "/productOfferingPrice", {
                "name": f"{name} Monthly", "@type": "ProductOfferingPrice",
                "priceType": "recurring",
                "price": {"unit": "EUR", "value": price},
            })
            detail += f", price {rid(pop)}"
        except Fail:
            pass
    ok(s, f"catalog: offering '{name}'", detail)
    return offering, spec


# ---------------------------------------------------------------------------
# S1 — Residential fiber onboarding (order-to-cash)
# ---------------------------------------------------------------------------

def scenario_s1(base: str):
    s = "S1-FIBER"
    t = tag()
    print(f"\n\033[1m== S1  Residential fiber onboarding (order-to-cash)  [{t}] ==\033[0m")

    # 1. Catalog design
    try:
        category = post(base, API["catalog"] + "/category", {
            "name": f"E2E Residential Broadband {t}", "@type": "Category",
        })
        ok(s, "catalog: category", rid(category))
    except Fail as e:
        fail(s, "catalog: category", str(e))
    try:
        fiber, _ = make_offering(base, s, f"E2E Fiber 1000 {t}", price=39.99)
        mesh, _ = make_offering(base, s, f"E2E Mesh WiFi Add-on {t}", price=5.0)
    except Fail as e:
        fail(s, "catalog design", str(e))
        return

    # 2. Customer + 3. address
    try:
        ana = make_individual(base, s, f"Ana_{t}", "Martins")
        home = make_address(base, s, f"Rua das Flores {t}")
    except Fail as e:
        fail(s, "party/address", str(e))
        return

    # 4. Qualification at the address
    try:
        poq = post(base, API["poq"] + "/checkProductOfferingQualification", {
            "@type": "CheckProductOfferingQualification",
            "provideAlternative": False,
            "relatedParty": [{"id": rid(ana), "@type": "Individual", "role": "customer"}],
            "place": [{"id": rid(home), "@type": "GeographicAddress"}],
            "checkProductOfferingQualificationItem": [{
                "id": "1", "@type": "CheckProductOfferingQualificationItem",
                "productOffering": {"id": rid(fiber), "@type": "ProductOfferingRef"},
            }],
        })
        ok(s, "qualification: offering serviceable at address", rid(poq))
    except Fail as e:
        fail(s, "qualification (non-fatal)", str(e))

    # 5. Billing account
    ba_id = None
    try:
        ba = post(base, API["account"] + "/billingAccount", {
            "name": f"E2E BA Ana {t}", "@type": "BillingAccount",
            "relatedParty": [{"id": rid(ana), "@type": "Individual", "role": "owner"}],
        })
        ba_id = rid(ba)
        ok(s, "billing: account opened", ba_id)
    except Fail as e:
        fail(s, "billing account (non-fatal)", str(e))

    # 6. Quote
    try:
        quote = post(base, API["quote"] + "/quote", {
            "@type": "Quote",
            "description": f"E2E Quote {t}",
            "relatedParty": [{"id": rid(ana), "@type": "Individual", "role": "customer"}],
            "quoteItem": [
                {"id": "1", "action": "add", "quantity": 1,
                 "productOffering": {"id": rid(fiber), "name": fiber.get("name")}},
                {"id": "2", "action": "add", "quantity": 1,
                 "productOffering": {"id": rid(mesh), "name": mesh.get("name")}},
            ],
        })
        ok(s, "quote: 2 items quoted", rid(quote))
    except Fail as e:
        fail(s, "quote (non-fatal)", str(e))

    # 7. Shopping cart
    try:
        cart = post(base, API["cart"] + "/shoppingCart", {
            "@type": "ShoppingCart",
            "relatedParty": [{"id": rid(ana), "@type": "Individual", "role": "customer"}],
            "cartItem": [
                {"id": "1", "action": "add", "quantity": 1,
                 "productOffering": {"id": rid(fiber)}},
                {"id": "2", "action": "add", "quantity": 1,
                 "productOffering": {"id": rid(mesh)}},
            ],
        })
        ok(s, "cart: items carted", rid(cart))
    except Fail as e:
        fail(s, "shopping cart (non-fatal)", str(e))

    # 8. Product order with two items
    try:
        order = post(base, API["order"] + "/productOrder", {
            "@type": "ProductOrder",
            "externalId": f"E2E-{t}",
            "description": f"E2E fiber order {t}",
            "relatedParty": [{"id": rid(ana), "@type": "Individual", "role": "Customer"}],
            "productOrderItem": [
                {"id": "1", "action": "add", "quantity": 1,
                 "productOffering": {"id": rid(fiber), "name": fiber.get("name")},
                 "place": [{"id": rid(home), "@type": "GeographicAddress", "role": "installation"}]},
                {"id": "2", "action": "add", "quantity": 1,
                 "productOffering": {"id": rid(mesh), "name": mesh.get("name")}},
            ],
        })
        order_id = rid(order)
        ok(s, "order: placed with 2 items", order_id)
    except Fail as e:
        fail(s, "product order", str(e))
        return

    # 9. Start delivery — TMFC003 orchestration.
    # PATCH confirms the commercial order; the ODA trigger is the TMF622
    # state-change event, which writes tmf_status and fires TMFC003.
    try:
        patch(base, API["order"] + f"/productOrder/{order_id}", {"state": "inProgress"})
        post(base, API["order"] + "/listener/productOrderStateChangeEvent", {
            "eventType": "ProductOrderStateChangeEvent",
            "event": {"productOrder": {"id": order_id, "state": "inProgress"}},
        })
        ok(s, "order: delivery started (state -> inProgress via state-change event)")
    except Fail as e:
        fail(s, "order: start delivery", str(e))
        return

    # find the spawned service orders (TMFC003 tags them with the order ref)
    spawned = []
    try:
        time.sleep(1)
        sorders = get(base, API["sorder"] + "/serviceOrder?limit=1000")
        needle = order_id
        spawned = [so for so in sorders
                   if needle and needle in str(so.get("description") or "")]
        if spawned:
            ok(s, "orchestration: TMFC003 spawned service orders",
               f"{len(spawned)} for order {order_id}")
        else:
            fail(s, "orchestration: no spawned service orders found",
                 f"searched description for {needle} in {len(sorders)} orders")
    except Fail as e:
        fail(s, "orchestration: list service orders", str(e))

    # 10. Complete service orders -> product order aggregates to completed
    for so in spawned:
        so_id = rid(so)
        try:
            patch(base, API["sorder"] + f"/serviceOrder/{so_id}", {"state": "completed"})
            ok(s, f"field ops: service order {so_id[:8]}… completed")
        except Fail as e:
            fail(s, f"complete service order {so_id[:8]}…", str(e))
    if spawned:
        try:
            time.sleep(1)
            final = get(base, API["order"] + f"/productOrder/{order_id}")
            state = final.get("state")
            if state == "completed":
                ok(s, "orchestration: product order aggregated to completed")
            else:
                fail(s, "orchestration: product order state after children complete",
                     f"expected completed, got {state}")
        except Fail as e:
            fail(s, "GET product order after completion", str(e))

    # 11. Usage + 12. first bill
    usage_id = None
    try:
        usage = post(base, API["usage"] + "/usage", {
            "@type": "Usage", "usageDate": "2026-07-01 00:00:00",
            "status": "rated", "description": f"E2E usage {t}",
        })
        usage_id = rid(usage)
        ok(s, "usage: rated usage recorded", usage_id)
    except Fail as e:
        fail(s, "usage (non-fatal)", str(e))
    try:
        bill_payload = {
            "@type": "CustomerBill", "name": f"E2E Bill {t}", "state": "new",
            "billDate": "2026-08-01T00:00:00Z",
            "billingPeriod": {"startDateTime": "2026-07-01T00:00:00Z",
                              "endDateTime": "2026-07-31T23:59:59Z"},
            "relatedParty": [{"id": rid(ana), "@type": "Individual", "role": "customer"}],
        }
        if ba_id:
            bill_payload["billingAccount"] = {"id": ba_id, "@type": "BillingAccount"}
        if usage_id:
            bill_payload["usage"] = [{"id": usage_id, "@type": "Usage"}]
        bill = post(base, API["bill"] + "/customerBill", bill_payload)
        ok(s, "billing: first bill produced", rid(bill))
    except Fail as e:
        fail(s, "customer bill", str(e))


# ---------------------------------------------------------------------------
# S2 — Mobile subscription with multiple resources (inventory flows)
# ---------------------------------------------------------------------------

def scenario_s2(base: str):
    s = "S2-MOBILE"
    t = tag()
    print(f"\n\033[1m== S2  Mobile subscription, multiple resources  [{t}] ==\033[0m")

    # 1. Resource catalog
    spec_ids = {}
    for spec_name in ("SIM Card", "MSISDN", "5G Router"):
        try:
            spec = post(base, API["rcatalog"] + "/resourceSpecification", {
                "name": f"E2E {spec_name} Spec {t}", "version": "1.0",
                "@type": "ResourceSpecification",
            })
            spec_ids[spec_name] = rid(spec)
            ok(s, f"resource catalog: '{spec_name}' spec", rid(spec))
        except Fail as e:
            fail(s, f"resource spec {spec_name} (non-fatal)", str(e))

    # 2. Seed inventory — 3 resources, all available
    resources = {}
    seeds = {
        "SIM":    f"ICCID-{t.upper()}-001",
        "MSISDN": f"+3519{t[:2]}{t[2:5]}{t[3:6]}",
        "Router": f"SN-RTR-{t.upper()}",
    }
    for kind, serial in seeds.items():
        try:
            res = post(base, API["rinv"] + "/resource", {
                "name": serial, "resourceStatus": "available", "@type": "Resource",
            })
            resources[kind] = rid(res)
            ok(s, f"inventory: seeded {kind}", f"{serial} -> {rid(res)}")
        except Fail as e:
            fail(s, f"seed {kind}", str(e))
    if len(resources) < 3:
        fail(s, "inventory seeding incomplete — aborting scenario")
        return

    # 3. Party + service spec
    try:
        bruno = make_individual(base, s, f"Bruno_{t}", "Costa")
        sspec = post(base, API["scatalog"] + "/serviceSpecification", {
            "name": f"E2E 5G Mobile Line Spec {t}", "@type": "ServiceSpecification",
        })
        ok(s, "service catalog: mobile line spec", rid(sspec))
    except Fail as e:
        fail(s, "party/service spec", str(e))
        return

    # 4/5. Activate three services, each claiming one resource.
    # (The platform binds supportingResource[0] to the service's resource_id,
    #  so each physical/logical resource gets its own CFS — one line service,
    #  one number service, one CPE service.)
    mobile = {}
    service_plan = [
        ("Mobile Line", "SIM", {"serviceSpecification": {
            "id": rid(sspec), "@type": "ServiceSpecificationRef"}}),
        ("Voice Number", "MSISDN", {}),
        ("5G Home Internet", "Router", {}),
    ]
    for svc_name, res_kind, extra in service_plan:
        try:
            payload = {
                "name": f"E2E {svc_name} {t}", "state": "active", "@type": "Service",
                "relatedParty": [{
                    "@type": "RelatedPartyRefOrPartyRoleRef",
                    "partyOrPartyRole": {"id": rid(bruno), "name": "Bruno Costa"},
                }],
                "supportingResource": [
                    {"id": resources[res_kind], "@type": "ResourceRef"}],
            }
            payload.update(extra)
            svc = post(base, API["sinv"] + "/service", payload)
            if svc_name == "Mobile Line":
                mobile = svc
            ok(s, f"service: {svc_name} active ({res_kind} claimed)", rid(svc))
        except Fail as e:
            fail(s, f"service {svc_name}", str(e))

    # Inventory flow assertion: all three resources left 'available'
    for kind, res_id in resources.items():
        try:
            res = get(base, API["rinv"] + f"/resource/{res_id}")
            status = res.get("resourceStatus") or res.get("state")
            if status and status != "available":
                ok(s, f"inventory: {kind} decremented", f"status={status}")
            else:
                fail(s, f"inventory: {kind} still available after assignment",
                     f"status={status}")
        except Fail as e:
            fail(s, f"inventory check {kind}", str(e))

    # 6. Service order referencing the mobile service
    try:
        so = post(base, API["sorder"] + "/serviceOrder", {
            "@type": "ServiceOrder",
            "description": f"E2E provisioning order {t}",
            "relatedParty": [{"id": rid(bruno), "role": "customer",
                              "@referredType": "Individual"}],
            "serviceOrderItem": [{
                "id": "1", "action": "add", "quantity": 1,
                "service": {"id": rid(mobile) or None,
                            "name": f"E2E Mobile Line {t}", "serviceType": "CFS"},
            }],
        })
        ok(s, "service order: raised for mobile line", rid(so))
    except Fail as e:
        fail(s, "service order (non-fatal)", str(e))

    # 7. Resource order — SIM replacement
    try:
        ro = post(base, API["rorder"] + "/resourceOrder", {
            "@type": "ResourceOrder",
            "description": f"E2E SIM swap {t}",
            "externalReference": [{"name": f"E2E-RO-{t}",
                                   "externalReferenceType": "swap"}],
            "orderItem": [{
                "id": "1", "action": "add", "quantity": 1,
                "resource": {"name": f"ICCID-{t.upper()}-REPL",
                             "@type": "LogicalResource"},
            }],
        })
        ok(s, "resource order: SIM replacement raised", rid(ro))
    except Fail as e:
        fail(s, "resource order (non-fatal)", str(e))


# ---------------------------------------------------------------------------
# S3 — B2B multi-site enterprise (agreement-driven)
# ---------------------------------------------------------------------------

def scenario_s3(base: str):
    s = "S3-B2B"
    t = tag()
    print(f"\n\033[1m== S3  B2B multi-site enterprise  [{t}] ==\033[0m")

    # 1. Organization
    try:
        org = post(base, API["party"] + "/organization", {
            "tradingName": f"E2E Acme Retail {t}",
            "name": f"E2E Acme Retail {t}",
            "@type": "Organization",
        })
        ok(s, "party: organization registered", rid(org))
    except Fail as e:
        fail(s, "organization", str(e))
        return

    # 2. Two shop addresses + sites
    sites = []
    for shop in ("Chiado", "Porto Baixa"):
        try:
            addr = make_address(base, s, f"E2E {shop} {t}",
                                city="Lisboa" if shop == "Chiado" else "Porto")
            site = post(base, API["site"] + "/geographicSite", {
                "name": f"E2E Shop {shop} {t}", "@type": "GeographicSite",
                "place": [{"id": rid(addr), "@type": "GeographicAddressRef"}],
                "relatedParty": [{"id": rid(org), "@type": "RelatedParty",
                                  "@referredType": "Organization",
                                  "role": "occupant"}],
            })
            sites.append(site)
            ok(s, f"site: shop {shop}", rid(site))
        except Fail as e:
            fail(s, f"site {shop}", str(e))
    if len(sites) < 2:
        fail(s, "need 2 sites — aborting scenario")
        return

    # 3. Offerings
    try:
        mpls, _ = make_offering(base, s, f"E2E MPLS Access {t}", price=199.0)
        sdwan, _ = make_offering(base, s, f"E2E Managed SD-WAN {t}", price=99.0)
    except Fail as e:
        fail(s, "offerings", str(e))
        return

    # 4. Framework agreement
    try:
        agreement = post(base, API["agreement"] + "/agreement", {
            "@type": "Agreement",
            "name": f"E2E Frame Agreement Acme {t}",
            "agreementType": "commercial",
            "engagedParty": [{"id": rid(org), "name": org.get("tradingName") or org.get("name"),
                              "@type": "Organization", "role": "buyer"}],
            "agreementItem": [{
                "productOffering": [
                    {"id": rid(mpls), "name": mpls.get("name")},
                    {"id": rid(sdwan), "name": sdwan.get("name")},
                ],
            }],
        })
        agr_id = rid(agreement)
        ok(s, "agreement: framework signed", agr_id)
        fetched = get(base, API["agreement"] + f"/agreement/{agr_id}")
        engaged = fetched.get("engagedParty") or []
        if any(str(p.get("id")) == rid(org) for p in engaged if isinstance(p, dict)):
            ok(s, "agreement: engagedParty echoed intact")
        else:
            fail(s, "agreement: engagedParty missing on GET", str(engaged)[:120])
    except Fail as e:
        fail(s, "agreement", str(e))
        agr_id = None

    # 5. Service qualification per site
    for site in sites:
        try:
            sq = post(base, API["sq"] + "/checkServiceQualification", {
                "@type": "CheckServiceQualification",
                "description": f"E2E SQ {site.get('name')}",
                "relatedParty": [{"id": rid(org), "role": "customer",
                                  "@referredType": "Organization"}],
                "serviceQualificationItem": [{
                    "id": "1",
                    "service": {
                        "serviceType": "CFS",
                        "place": [{"id": rid(site), "@type": "GeographicSiteRef",
                                   "role": "delivery"}],
                    },
                }],
            })
            ok(s, f"qualification: {site.get('name', '')[:28]}…", rid(sq))
        except Fail as e:
            fail(s, f"service qualification (non-fatal)", str(e))

    # 6. Enterprise order — 3 items (MPLS per site + SD-WAN overlay)
    try:
        items = [
            {"id": "1", "action": "add", "quantity": 1,
             "productOffering": {"id": rid(mpls), "name": mpls.get("name")},
             "place": [{"id": rid(sites[0]), "@type": "GeographicSiteRef"}]},
            {"id": "2", "action": "add", "quantity": 1,
             "productOffering": {"id": rid(mpls), "name": mpls.get("name")},
             "place": [{"id": rid(sites[1]), "@type": "GeographicSiteRef"}]},
            {"id": "3", "action": "add", "quantity": 1,
             "productOffering": {"id": rid(sdwan), "name": sdwan.get("name")}},
        ]
        payload = {
            "@type": "ProductOrder",
            "externalId": f"E2E-B2B-{t}",
            "description": f"E2E enterprise order {t}",
            "relatedParty": [{"id": rid(org), "@type": "Organization",
                              "role": "Customer"}],
            "productOrderItem": items,
        }
        if agr_id:
            payload["agreement"] = [{"id": agr_id, "@type": "AgreementRef"}]
        order = post(base, API["order"] + "/productOrder", payload)
        order_id = rid(order)
        ok(s, "order: enterprise order placed (3 items)", order_id)
    except Fail as e:
        fail(s, "enterprise order", str(e))
        return

    # 7. Orchestrate and verify one service order per line
    try:
        patch(base, API["order"] + f"/productOrder/{order_id}", {"state": "inProgress"})
        post(base, API["order"] + "/listener/productOrderStateChangeEvent", {
            "eventType": "ProductOrderStateChangeEvent",
            "event": {"productOrder": {"id": order_id, "state": "inProgress"}},
        })
        time.sleep(1)
        sorders = get(base, API["sorder"] + "/serviceOrder?limit=1000")
        spawned = [so for so in sorders
                   if order_id and order_id in str(so.get("description") or "")]
        if len(spawned) >= 3:
            ok(s, "orchestration: 3 service orders spawned (one per line)",
               f"{len(spawned)} found")
        elif spawned:
            fail(s, "orchestration: expected 3 service orders",
                 f"got {len(spawned)}")
        else:
            fail(s, "orchestration: no service orders spawned", order_id)
    except Fail as e:
        fail(s, "orchestration", str(e))


# ---------------------------------------------------------------------------
# S4 — Assurance: alarm -> problem -> ticket (+ thresholds)
# ---------------------------------------------------------------------------

def _oda_event(base, s, path, event_type, resource_id, state, check_desc):
    """POST an ODA event to a wiring listener and expect 201."""
    payload = {
        "eventId": uuid.uuid4().hex,
        "eventType": event_type,
        "event": {"resource": {"id": resource_id, "state": state}},
    }
    r = requests.post(base + path, headers=HEADERS, json=payload, timeout=30)
    if r.status_code == 201:
        ok(s, check_desc)
        return True
    fail(s, check_desc, f"HTTP {r.status_code}: {r.text[:150]}")
    return False


def scenario_s4(base: str):
    s = "S4-ASSURANCE"
    t = tag()
    print(f"\n\033[1m== S4  Assurance: alarm -> problem -> ticket  [{t}] ==\033[0m")

    # 1. Critical alarm raised by the network
    alarm_id = None
    try:
        alarm = post(base, API["alarm"] + "/alarm", {
            "@type": "Alarm",
            "alarmType": "communicationsAlarm",
            "perceivedSeverity": "critical",
            "probableCause": "fiberCut",
            "state": "raised",
            "alarmRaisedTime": "2026-07-14T10:00:00Z",
            "sourceSystemId": f"e2e-noc-{t}",
            "alarmedObject": {"id": f"olt-{t}", "name": f"OLT-{t.upper()}"},
        })
        alarm_id = rid(alarm)
        ok(s, "alarm: critical fiber-cut raised", alarm_id)
    except Fail as e:
        fail(s, "alarm create", str(e))

    # 2. Upstream clears it via the TMFC043 listener — local state must follow
    if alarm_id:
        if _oda_event(base, s, "/tmfc043/listener/alarm", "AlarmStateChangeEvent",
                      alarm_id, "cleared",
                      "ODA event: AlarmStateChangeEvent(cleared) accepted"):
            try:
                after = get(base, API["alarm"] + f"/alarm/{alarm_id}")
                state = after.get("state") or after.get("status")
                if state == "cleared":
                    ok(s, "reconciliation: local alarm state -> cleared")
                else:
                    fail(s, "reconciliation: alarm state unchanged", f"state={state}")
            except Fail as e:
                fail(s, "GET alarm after event", str(e))

    # 3. Service problem referencing the alarm
    problem_id = None
    try:
        problem = post(base, API["problem"] + "/serviceProblem", {
            "@type": "ServiceProblem",
            "description": f"E2E fiber cut problem {t}",
            "category": "network",
            "priority": 1,
            "reason": "Fiber cut detected on OLT uplink",
            "originatorParty": {"name": "NOC", "@type": "RelatedParty"},
            "status": "acknowledged",
            "underlyingAlarm": ([{"id": alarm_id, "@type": "AlarmRef"}]
                                if alarm_id else []),
        })
        problem_id = rid(problem)
        ok(s, "problem: service problem opened", problem_id)
    except Fail as e:
        fail(s, "service problem create (non-fatal)", str(e))

    # 4. Problem resolved upstream — reconcile through the listener
    if problem_id:
        if _oda_event(base, s, "/tmfc043/listener/serviceProblem",
                      "ServiceProblemStateChangeEvent", problem_id, "resolved",
                      "ODA event: ServiceProblemStateChangeEvent(resolved) accepted"):
            try:
                after = get(base, API["problem"] + f"/serviceProblem/{problem_id}")
                state = after.get("status") or after.get("state")
                if state == "resolved":
                    ok(s, "reconciliation: local problem -> resolved")
                else:
                    fail(s, "reconciliation: problem state unchanged", f"state={state}")
            except Fail as e:
                fail(s, "GET problem after event", str(e))

    # 5. Customer-facing trouble ticket
    ticket_id = None
    try:
        ticket = post(base, API["ticket"] + "/troubleTicket", {
            "@type": "TroubleTicket",
            "name": f"E2E ticket {t}",
            "description": "Customer reports no internet (fiber cut)",
            "severity": "critical",
            "ticketType": "incident",
        })
        ticket_id = rid(ticket)
        ok(s, "ticket: trouble ticket opened", ticket_id)
    except Fail as e:
        fail(s, "trouble ticket create (non-fatal)", str(e))

    # 6. Ticket resolution event
    if ticket_id:
        _oda_event(base, s, "/tmfc043/listener/troubleTicket",
                   "TroubleTicketStateChangeEvent", ticket_id, "resolved",
                   "ODA event: TroubleTicketStateChangeEvent(resolved) accepted")

    # 7. Performance thresholds (TMF649 — TMFC037/038 exposed surface)
    try:
        threshold = post(base, API["threshold"] + "/threshold", {
            "@type": "Threshold",
            "name": f"E2E OLT RX power {t}",
            "description": "Alert when optical RX power drops below -28 dBm",
        })
        th_id = rid(threshold)
        ok(s, "performance: threshold defined", th_id)
        job = post(base, API["threshold"] + "/thresholdJob", {
            "@type": "ThresholdJob",
            "name": f"E2E RX power sweep {t}",
        })
        ok(s, "performance: threshold job scheduled", rid(job))
        back = get(base, API["threshold"] + f"/threshold/{th_id}")
        if rid(back) == th_id:
            ok(s, "performance: threshold readable by id")
        else:
            fail(s, "performance: GET threshold by id", str(back)[:120])
    except Fail as e:
        fail(s, "TMF649 thresholds", str(e))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SCENARIOS = {
    "s1": ("Residential fiber onboarding (order-to-cash)", scenario_s1),
    "s2": ("Mobile subscription with multiple resources", scenario_s2),
    "s3": ("B2B multi-site enterprise", scenario_s3),
    "s4": ("Assurance: alarm -> problem -> ticket", scenario_s4),
}


def print_summary() -> int:
    print("\n======================================")
    print("  E2E SCENARIO SUMMARY")
    print("======================================")
    failed_total = 0
    for key in SCENARIOS:
        name = {"s1": "S1-FIBER", "s2": "S2-MOBILE",
                "s3": "S3-B2B", "s4": "S4-ASSURANCE"}[key]
        mine = [r for r in results if r.scenario == name]
        if not mine:
            continue
        passed = sum(1 for r in mine if r.passed)
        failed = sum(1 for r in mine if not r.passed)
        failed_total += failed
        mark = "\033[32mOK\033[0m" if failed == 0 else "\033[31mFAIL\033[0m"
        print(f"  {mark} {name}:  {passed} passed, {failed} failed")
        for r in mine:
            if not r.passed:
                print(f"      \033[31mFAIL\033[0m {r.check}: {r.detail}")
    total_pass = sum(1 for r in results if r.passed)
    print(f"\n  Total: {total_pass} passed, {failed_total} failed"
          + (f"  ->  {failed_total} FAILED" if failed_total else "  ->  ALL GREEN"))
    return failed_total


def main():
    parser = argparse.ArgumentParser(description="Run TMF/ODA e2e business scenarios.")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--only", default="",
                        help="Comma-separated scenario keys, e.g. s1,s4")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    only = {x.strip().lower() for x in args.only.split(",") if x.strip()}

    print(f"\n\033[1mTMF/ODA E2E Scenarios  ->  {base}\033[0m")
    for key, (label, fn) in SCENARIOS.items():
        if only and key not in only:
            continue
        try:
            fn(base)
        except Exception as e:  # noqa: BLE001 — keep other scenarios running
            fail(key.upper(), "unexpected error", str(e))

    sys.exit(1 if print_summary() else 0)


if __name__ == "__main__":
    main()
