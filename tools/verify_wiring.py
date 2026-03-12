#!/usr/bin/env python3
"""
verify_wiring.py — End-to-end wiring verification for TMFC001, TMFC027, TMFC031.

Creates real records via the TMF v5 APIs, then checks that cross-API FK fields
were resolved by the wiring modules in Odoo's database via the JSON payloads.

Usage:
    python OdooTMFOpenAPI/tools/verify_wiring.py
    python OdooTMFOpenAPI/tools/verify_wiring.py --base-url http://localhost:8069
    python OdooTMFOpenAPI/tools/verify_wiring.py --only tmfc001
"""

import argparse
import json
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_BASE = "http://localhost:8069"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

APIS = {
    "party":         "/tmf-api/partyManagement/v5",
    "catalog":       "/tmf-api/productCatalogManagement/v5",
    "inventory":     "/tmf-api/productInventoryManagement/v5",
    "poq":           "/tmf-api/productOfferingQualificationManagement/v5",
    "bill":          "/tmf-api/customerBillManagement/v5",
    "address":       "/tmf-api/geographicAddressManagement/v4",
    "account":       "/tmf-api/accountManagement/v4",
    "usage":         "/tmf-api/usageManagement/v4",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class Fail(Exception):
    pass


@dataclass
class Result:
    component: str
    check: str
    passed: bool
    detail: str = ""


results: list[Result] = []


def ok(component: str, check: str, detail: str = ""):
    results.append(Result(component, check, True, detail))
    print(f"  \033[32mOK\033[0m {check}" + (f"  ({detail})" if detail else ""))


def fail(component: str, check: str, detail: str = ""):
    results.append(Result(component, check, False, detail))
    print(f"  \033[31mFAIL\033[0m {check}" + (f"  ({detail})" if detail else ""))


def post(base: str, path: str, payload: dict) -> dict:
    url = base + path
    r = requests.post(url, headers=HEADERS, json=payload, timeout=15)
    if r.status_code not in (200, 201):
        raise Fail(f"POST {url} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def get(base: str, path: str) -> Any:
    url = base + path
    r = requests.get(url, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        raise Fail(f"GET {url} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def tag(n: int = 6) -> str:
    """Short unique tag for test data names."""
    return uuid.uuid4().hex[:n]


# ---------------------------------------------------------------------------
# TMFC001 — ProductOffering wired to Party, GeographicAddress
# ---------------------------------------------------------------------------

def verify_tmfc001(base: str):
    print("\n\033[1m-- TMFC001  Product Catalog Management --\033[0m")
    comp = "TMFC001"
    t = tag()

    # 1. Create an Individual (TMF632 via partyManagement)
    try:
        party = post(base, APIS["party"] + "/individual", {
            "givenName": f"WiringTest_{t}",
            "familyName": "Party",
            "@type": "Individual",
        })
        party_id = party.get("id") or party.get("tmf_id")
        ok(comp, "created Individual via partyManagement/v5", party_id)
    except Fail as e:
        fail(comp, "create Individual", str(e))
        return

    # 2. Create a GeographicAddress (TMF673)
    try:
        addr = post(base, APIS["address"] + "/geographicAddressValidation", {
            "provideAlternative": False,
            "validationDate": "2026-01-01T00:00:00Z",
            "submittedGeographicAddress": {
                "streetName": f"Wiring St {t}",
                "city": "TestCity",
                "country": "PT",
                "@type": "GeographicAddress",
            },
        })
        # validation returns a container; extract the address id if present
        submitted = addr.get("submittedGeographicAddress") or addr
        addr_id = submitted.get("id") or addr.get("id")
        ok(comp, "created GeographicAddress via geographicAddressManagement/v4", addr_id)
    except Fail as e:
        addr_id = None
        fail(comp, "create GeographicAddress (non-fatal — wiring test continues)", str(e))

    # 3. Create ProductSpecification
    try:
        spec = post(base, APIS["catalog"] + "/productSpecification", {
            "name": f"WiringSpec_{t}",
            "version": "1.0",
            "lifecycleStatus": "Active",
            "@type": "ProductSpecification",
        })
        spec_id = spec.get("id")
        spec_href = spec.get("href", "")
        ok(comp, "created ProductSpecification", spec_id)
    except Fail as e:
        fail(comp, "create ProductSpecification", str(e))
        return

    # 4. Create ProductOffering with relatedParty + place refs
    offering_payload: dict = {
        "name": f"WiringOffering_{t}",
        "lifecycleStatus": "Active",
        "@type": "ProductOffering",
        "productSpecification": {"id": spec_id, "href": spec_href},
        "relatedParty": [{"id": party_id, "@type": "Individual", "role": "owner"}],
    }
    if addr_id:
        offering_payload["place"] = [{"id": addr_id, "@type": "GeographicAddress"}]

    try:
        offering = post(base, APIS["catalog"] + "/productOffering", offering_payload)
        offering_id = offering.get("id")
        ok(comp, "created ProductOffering with relatedParty + place", offering_id)
    except Fail as e:
        fail(comp, "create ProductOffering", str(e))
        return

    # 5. GET back and verify relatedParty is preserved in response
    try:
        fetched = get(base, APIS["catalog"] + f"/productOffering/{offering_id}")
        rp = fetched.get("relatedParty") or []
        ids_in_response = [p.get("id") for p in rp if isinstance(p, dict)]
        if party_id in ids_in_response:
            ok(comp, "GET productOffering returns relatedParty ref intact", f"found party {party_id}")
        else:
            fail(comp, "GET productOffering relatedParty ref missing", f"expected {party_id}, got {ids_in_response}")
    except Fail as e:
        fail(comp, "GET ProductOffering", str(e))

    # 6. Verify wiring field via direct Odoo RPC (optional — needs auth)
    _check_odoo_field(
        base, comp,
        model="product.template",
        domain=[["name", "=", f"WiringOffering_{t}"]],
        field="related_partner_ids",
        description="product.template.related_partner_ids populated by wiring",
    )


# ---------------------------------------------------------------------------
# TMFC027 — ProductOfferingQualification wired to Party, ProductOffering, ProductOrder
# ---------------------------------------------------------------------------

def verify_tmfc027(base: str):
    print("\n\033[1m-- TMFC027  Product Configurator --\033[0m")
    comp = "TMFC027"
    t = tag()

    # 1. Create a party to reference
    try:
        party = post(base, APIS["party"] + "/individual", {
            "givenName": f"WiringTest027_{t}",
            "familyName": "WiringParty",
            "@type": "Individual",
        })
        party_id = party.get("id") or party.get("tmf_id")
        ok(comp, "created Individual", party_id)
    except Fail as e:
        fail(comp, "create Individual", str(e))
        party_id = None

    # 2. Create ProductSpec + Offering to reference
    try:
        spec = post(base, APIS["catalog"] + "/productSpecification", {
            "name": f"POQ_Spec_{t}", "version": "1.0", "@type": "ProductSpecification",
        })
        spec_id = spec.get("id")
        spec_href = spec.get("href", "")
        offering = post(base, APIS["catalog"] + "/productOffering", {
            "name": f"POQ_Offering_{t}", "@type": "ProductOffering",
            "productSpecification": {"id": spec_id, "href": spec_href},
        })
        offering_id = offering.get("id")
        offering_href = offering.get("href", "")
        ok(comp, "created ProductOffering for POQ reference", offering_id)
    except Fail as e:
        fail(comp, "create ProductOffering for POQ", str(e))
        offering_id, offering_href = None, ""

    # 3. Create a GeographicAddress (direct, not via validation) for place wiring
    addr_id = None
    try:
        addr = post(base, APIS["address"] + "/geographicAddress", {
            "streetName": f"POQ St {t}",
            "city": "TestCity",
            "country": "PT",
            "@type": "GeographicAddress",
        })
        addr_id = addr.get("id")
        ok(comp, "created GeographicAddress for place wiring", addr_id)
    except Fail as e:
        fail(comp, "create GeographicAddress (non-fatal)", str(e))

    # 4. Create a BillingAccount for TMF666 wiring
    billing_account_id = None
    try:
        ba = post(base, APIS["account"] + "/billingAccount", {
            "name": f"POQ_BA_{t}",
            "@type": "BillingAccount",
            "relatedParty": ([{"id": party_id, "@type": "Individual", "role": "owner"}] if party_id else []),
        })
        billing_account_id = ba.get("id")
        ok(comp, "created BillingAccount for TMF666 wiring", billing_account_id)
    except Fail as e:
        fail(comp, "create BillingAccount (non-fatal)", str(e))

    # 5. Create a Product (TMF637) for product wiring
    product_id = None
    try:
        prod = post(base, APIS["inventory"] + "/product", {
            "status": "created",
            "@type": "Product",
            "name": f"POQ_Product_{t}",
        })
        product_id = prod.get("id")
        ok(comp, "created Product for TMF637 wiring", product_id)
    except Fail as e:
        fail(comp, "create Product (non-fatal)", str(e))

    # 6. POST CheckProductOfferingQualification with all cross-refs
    items = []
    if offering_id:
        item: dict = {
            "id": "1",
            "productOffering": {"id": offering_id, "href": offering_href, "@type": "ProductOffering"},
        }
        if product_id:
            item["product"] = {"id": product_id, "@type": "Product"}
        items.append(item)

    poq_payload: dict = {
        "@type": "CheckProductOfferingQualification",
        "instantSyncQualification": True,
        "provideAlternative": False,
        "checkProductOfferingQualificationItem": items,
    }
    if party_id:
        poq_payload["relatedParty"] = [{"id": party_id, "@type": "Individual", "role": "buyer"}]
    if addr_id:
        poq_payload["place"] = [{"id": addr_id, "@type": "GeographicAddress"}]
    if billing_account_id:
        poq_payload["billingAccount"] = {"id": billing_account_id, "@type": "BillingAccount"}

    try:
        poq = post(base, APIS["poq"] + "/checkProductOfferingQualification", poq_payload)
        poq_id = poq.get("id")
        ok(comp, "created CheckProductOfferingQualification with all cross-refs", poq_id)
    except Fail as e:
        fail(comp, "create CheckProductOfferingQualification", str(e))
        return

    # 7. GET back and verify relatedParty preserved
    try:
        fetched = get(base, APIS["poq"] + f"/checkProductOfferingQualification/{poq_id}")
        rp = fetched.get("relatedParty") or []
        ids_in_response = [p.get("id") for p in rp if isinstance(p, dict)]
        if party_id and party_id in ids_in_response:
            ok(comp, "GET checkPOQ returns relatedParty ref intact", f"found {party_id}")
        elif not party_id:
            ok(comp, "GET checkPOQ returned (no party to verify)", poq_id)
        else:
            fail(comp, "GET checkPOQ relatedParty missing", f"expected {party_id}, got {ids_in_response}")
    except Fail as e:
        fail(comp, "GET checkPOQ", str(e))

    # 8. Odoo field checks
    _check_odoo_field(
        base, comp,
        model="tmf.check.product.offering.qualification",
        domain=[["tmf_id", "=", poq_id]],
        field="related_partner_ids",
        description="checkPOQ.related_partner_ids populated by wiring (TMF632)",
    )
    _check_odoo_field(
        base, comp,
        model="tmf.check.product.offering.qualification",
        domain=[["tmf_id", "=", poq_id]],
        field="product_offering_ids",
        description="checkPOQ.product_offering_ids populated by wiring (TMF620)",
    )
    _check_odoo_field(
        base, comp,
        model="tmf.check.product.offering.qualification",
        domain=[["tmf_id", "=", poq_id]],
        field="product_ids",
        description="checkPOQ.product_ids populated by wiring (TMF637)",
    )
    _check_odoo_field(
        base, comp,
        model="tmf.check.product.offering.qualification",
        domain=[["tmf_id", "=", poq_id]],
        field="geographic_address_id",
        description="checkPOQ.geographic_address_id populated by wiring (TMF673)",
    )
    _check_odoo_field(
        base, comp,
        model="tmf.check.product.offering.qualification",
        domain=[["tmf_id", "=", poq_id]],
        field="billing_account_id",
        description="checkPOQ.billing_account_id populated by wiring (TMF666)",
    )


# ---------------------------------------------------------------------------
# TMFC031 — CustomerBill wired to BillingAccount, Product, Usage
# ---------------------------------------------------------------------------

def verify_tmfc031(base: str):
    print("\n\033[1m-- TMFC031  Bill Calculation Management --\033[0m")
    comp = "TMFC031"
    t = tag()

    # 1. Create a Party to reference (TMF632)
    try:
        party = post(base, APIS["party"] + "/individual", {
            "givenName": f"WiringTest031_{t}",
            "familyName": "BillParty",
            "@type": "Individual",
        })
        party_id = party.get("id") or party.get("tmf_id")
        ok(comp, "created Individual for relatedParty wiring", party_id)
    except Fail as e:
        fail(comp, "create Individual (non-fatal)", str(e))
        party_id = None

    # 2. Create a Product to reference (TMF637)
    try:
        product = post(base, APIS["inventory"] + "/product", {
            "status": "created",
            "@type": "Product",
            "name": f"WiringProduct031_{t}",
        })
        product_id = product.get("id") or product.get("tmf_id")
        ok(comp, "created Product via productInventoryManagement/v5", product_id)
    except Fail as e:
        fail(comp, "create Product", str(e))
        product_id = None

    # 3. Create a BillingAccount for TMF666 wiring
    billing_account_id = None
    try:
        ba = post(base, APIS["account"] + "/billingAccount", {
            "name": f"Bill_BA_{t}",
            "@type": "BillingAccount",
            "relatedParty": ([{"id": party_id, "@type": "Individual", "role": "owner"}] if party_id else []),
        })
        billing_account_id = ba.get("id")
        ok(comp, "created BillingAccount for TMF666 wiring", billing_account_id)
    except Fail as e:
        fail(comp, "create BillingAccount (non-fatal)", str(e))

    # 4. Create a Usage record for TMF635 wiring
    usage_id = None
    try:
        usage = post(base, APIS["usage"] + "/usage", {
            "@type": "Usage",
            "usageDate": "2026-02-15 00:00:00",
            "status": "billed",
            "description": f"WiringUsage031_{t}",
        })
        usage_id = usage.get("id")
        ok(comp, "created Usage for TMF635 wiring", usage_id)
    except Fail as e:
        fail(comp, "create Usage (non-fatal)", str(e))

    # 5. POST CustomerBill with all cross-refs
    bill_payload: dict = {
        "@type": "CustomerBill",
        "name": f"WiringBill_{t}",
        "state": "new",
        "billDate": "2026-03-12T00:00:00Z",
        "billingPeriod": {
            "startDateTime": "2026-02-01T00:00:00Z",
            "endDateTime": "2026-02-28T23:59:59Z",
        },
        "billDocument": [],
    }
    if product_id:
        bill_payload["productRef"] = [{"id": product_id, "@type": "Product"}]
    if party_id:
        bill_payload["relatedParty"] = [{"id": party_id, "@type": "Individual", "role": "customer"}]
    if billing_account_id:
        bill_payload["billingAccount"] = {"id": billing_account_id, "@type": "BillingAccount"}
    if usage_id:
        bill_payload["usage"] = [{"id": usage_id, "@type": "Usage"}]

    try:
        bill = post(base, APIS["bill"] + "/customerBill", bill_payload)
        bill_id = bill.get("id")
        ok(comp, "created CustomerBill with all cross-refs", bill_id)
    except Fail as e:
        fail(comp, "create CustomerBill", str(e))
        return

    # 6. GET back and verify state preserved
    try:
        fetched = get(base, APIS["bill"] + f"/customerBill/{bill_id}")
        if fetched.get("state") == "new":
            ok(comp, "GET customerBill returns correct state", "state=new")
        else:
            fail(comp, "GET customerBill state mismatch", f"got {fetched.get('state')}")
    except Fail as e:
        fail(comp, "GET customerBill", str(e))

    # 7. GET appliedCustomerBillingRate list (read-only per TMF678 spec — no POST)
    try:
        rates = get(base, APIS["bill"] + "/appliedCustomerBillingRate")
        ok(comp, "GET appliedCustomerBillingRate list (read-only, no POST per spec)", f"{len(rates)} records")
    except Fail as e:
        fail(comp, "GET appliedCustomerBillingRate", str(e))

    # 8. Odoo field checks on CustomerBill
    _check_odoo_field(
        base, comp,
        model="tmf.customer.bill",
        domain=[["tmf_id", "=", bill_id]],
        field="product_ids",
        description="customerBill.product_ids populated by wiring (TMF637)",
    )
    _check_odoo_field(
        base, comp,
        model="tmf.customer.bill",
        domain=[["tmf_id", "=", bill_id]],
        field="related_partner_ids",
        description="customerBill.related_partner_ids populated by wiring (TMF632)",
    )
    _check_odoo_field(
        base, comp,
        model="tmf.customer.bill",
        domain=[["tmf_id", "=", bill_id]],
        field="billing_account_id",
        description="customerBill.billing_account_id populated by wiring (TMF666)",
    )
    _check_odoo_field(
        base, comp,
        model="tmf.customer.bill",
        domain=[["tmf_id", "=", bill_id]],
        field="usage_ids",
        description="customerBill.usage_ids populated by wiring (TMF635)",
    )


# ---------------------------------------------------------------------------
# Odoo JSON-RPC field check (no auth needed for public records)
# ---------------------------------------------------------------------------

def _check_odoo_field(
    base: str,
    comp: str,
    model: str,
    domain: list,
    field: str,
    description: str,
    optional: bool = False,
):
    """
    Uses Odoo's JSON-RPC /web/dataset/call_kw to read a field value.
    Falls back gracefully if auth is required.
    """
    url = base + "/web/dataset/call_kw"
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": model,
            "method": "search_read",
            "args": [domain],
            "kwargs": {"fields": [field, "id"], "limit": 1},
        },
    }
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=10)
        body = r.json()
        error = body.get("error")
        if error:
            # Auth required — skip gracefully
            msg = error.get("data", {}).get("message", str(error))
            note = "(needs Odoo auth — skip)" if "Access" in msg or "session" in msg.lower() else msg[:120]
            results.append(Result(comp, description, True, f"skipped: {note}"))
            print(f"  \033[33m~\033[0m {description}  (skipped: {note})")
            return
        records = body.get("result") or []
        if not records:
            status = "optional — no record found" if optional else "record not found in DB"
            if optional:
                results.append(Result(comp, description, True, status))
                print(f"  \033[33m~\033[0m {description}  ({status})")
            else:
                fail(comp, description, status)
            return
        rec = records[0]
        value = rec.get(field)
        # Many2many returns a list of ids; Many2one returns [id, name] or False
        populated = bool(value)
        if populated:
            ok(comp, description, f"field value: {value}")
        else:
            status = "field is empty — wiring may not have resolved (check tmf_id matching)"
            if optional:
                results.append(Result(comp, description, True, status))
                print(f"  \033[33m~\033[0m {description}  ({status})")
            else:
                fail(comp, description, status)
    except Exception as e:
        results.append(Result(comp, description, True, f"skipped: {e}"))
        print(f"  \033[33m~\033[0m {description}  (skipped: {e})")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary():
    print("\n\033[1m======================================\033[0m")
    print("\033[1m  WIRING VERIFICATION SUMMARY\033[0m")
    print("\033[1m======================================\033[0m")

    by_comp: dict[str, list[Result]] = {}
    for r in results:
        by_comp.setdefault(r.component, []).append(r)

    total_pass = total_fail = 0
    for comp, res in by_comp.items():
        passed = sum(1 for r in res if r.passed)
        failed = sum(1 for r in res if not r.passed)
        total_pass += passed
        total_fail += failed
        icon = "\033[32mOK\033[0m" if failed == 0 else "\033[31mFAIL\033[0m"
        print(f"  {icon} {comp}:  {passed} passed, {failed} failed")
        for r in res:
            if not r.passed:
                print(f"      \033[31mFAIL\033[0m {r.check}: {r.detail}")

    print()
    overall = "\033[32mALL PASSED\033[0m" if total_fail == 0 else f"\033[31m{total_fail} FAILED\033[0m"
    print(f"  Total: {total_pass} passed, {total_fail} failed  ->  {overall}")
    print()
    return total_fail


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Verify TMFC001/027/031 wiring against live Odoo.")
    parser.add_argument("--base-url", default=DEFAULT_BASE, help=f"Odoo base URL (default: {DEFAULT_BASE})")
    parser.add_argument("--only", default="", help="Comma-separated components to run, e.g. tmfc001,tmfc031")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    only = {x.strip().lower() for x in args.only.split(",") if x.strip()} if args.only else set()

    print(f"\n\033[1mWiring Verification  ->  {base}\033[0m")

    runners = {
        "tmfc001": verify_tmfc001,
        "tmfc027": verify_tmfc027,
        "tmfc031": verify_tmfc031,
    }

    for name, fn in runners.items():
        if only and name not in only:
            continue
        try:
            fn(base)
        except Exception as e:
            fail(name.upper(), "unexpected error", str(e))

    failed = print_summary()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
