#!/usr/bin/env python3
"""Simulate a 2-step revision flow for ProductOrder (TMF622-ish) via HTTP-only.

Scenario (Spanish):
- Submit revision 1 with product + discount
  * TNT Sports HD
  * Descuento TNT Sports 2 Meses al 95
- While "en espera" modify the order removing the discount
- Submit revision 2

Notes:
- Current tmf_product_ordering PATCH implementation only supports updating `description`.
- This script therefore simulates the business intent by:
  1) Creating catalog ProductOfferings (product + discount) so item refs are realistic.
  2) Creating a ProductOrder with 2 productOrderItem lines.
  3) PATCHing the order description to mark "held" and "revision 2".

Usage:
  python tools/simulate_tnt_revisions.py --base-url http://localhost:8069
"""

import argparse
import json
import uuid
import requests

HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def post(base: str, path: str, payload: dict):
    r = requests.post(base + path, headers=HEADERS, json=payload, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"POST {path} -> {r.status_code}: {r.text[:400]}")
    return r.json()


def patch(base: str, path: str, payload: dict):
    r = requests.patch(base + path, headers=HEADERS, json=payload, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"PATCH {path} -> {r.status_code}: {r.text[:400]}")
    return r.json()


def get(base: str, path: str):
    r = requests.get(base + path, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"GET {path} -> {r.status_code}: {r.text[:400]}")
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8069")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    t = uuid.uuid4().hex[:6]

    # Create minimal catalog objects so we can reference productOffering.id
    spec_product = post(base, "/tmf-api/productCatalogManagement/v5/productSpecification", {
        "name": f"TNT Sports HD Spec {t}",
        "version": "1.0",
        "lifecycleStatus": "Active",
        "@type": "ProductSpecification",
    })
    spec_discount = post(base, "/tmf-api/productCatalogManagement/v5/productSpecification", {
        "name": f"Descuento TNT 2 Meses 95 Spec {t}",
        "version": "1.0",
        "lifecycleStatus": "Active",
        "@type": "ProductSpecification",
    })

    offering_product = post(base, "/tmf-api/productCatalogManagement/v5/productOffering", {
        "name": f"TNT Sports HD {t}",
        "lifecycleStatus": "Active",
        "@type": "ProductOffering",
        "productSpecification": {"id": spec_product["id"], "href": spec_product.get("href", "")},
    })

    offering_discount = post(base, "/tmf-api/productCatalogManagement/v5/productOffering", {
        "name": f"Descuento TNT Sports 2 Meses al 95 {t}",
        "lifecycleStatus": "Active",
        "@type": "ProductOffering",
        "productSpecification": {"id": spec_discount["id"], "href": spec_discount.get("href", "")},
    })

    # Revision 1: create order with 2 items (product + discount)
    po = post(base, "/tmf-api/productOrderingManagement/v5/productOrder", {
        "description": f"Revision 1 - TNT bundle {t}",
        "@type": "ProductOrder",
        "state": "acknowledged",
        "productOrderItem": [
            {
                "id": "1",
                "quantity": 1,
                "@type": "ProductOrderItem",
                "action": "add",
                "productOffering": {"id": offering_product["id"], "@type": "ProductOfferingRef"},
            },
            {
                "id": "2",
                "quantity": 1,
                "@type": "ProductOrderItem",
                "action": "add",
                "productOffering": {"id": offering_discount["id"], "@type": "ProductOfferingRef"},
            },
        ],
    })

    po_id = po.get("id")

    # "En espera": current controller doesn't support state updates, so we annotate description
    po_held = patch(base, f"/tmf-api/productOrderingManagement/v5/productOrder/{po_id}", {
        "description": f"EN ESPERA - remove discount next - {t}",
    })

    # Revision 2: simulate "discount removed" as a second submission step
    po_rev2 = patch(base, f"/tmf-api/productOrderingManagement/v5/productOrder/{po_id}", {
        "description": f"Revision 2 - discount removed (simulated) - {t}",
    })

    final = get(base, f"/tmf-api/productOrderingManagement/v5/productOrder/{po_id}")

    out = {
        "tag": t,
        "productOffering": {"id": offering_product["id"], "name": offering_product.get("name")},
        "discountOffering": {"id": offering_discount["id"], "name": offering_discount.get("name")},
        "productOrder": {
            "id": po_id,
            "rev1_description": po.get("description"),
            "held_description": po_held.get("description"),
            "rev2_description": po_rev2.get("description"),
            "final_description": final.get("description"),
        },
        "note": "Item-level removal requires implementing PATCH semantics for productOrderItem; currently simulated via description only.",
    }

    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
