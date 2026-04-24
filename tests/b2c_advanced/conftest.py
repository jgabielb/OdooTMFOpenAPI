"""
Shared fixtures for the advanced B2C suite.

Covers real-world telco scenarios beyond the basic order-to-activate:
catalog design, inventory, variants, multi-account, plan change, promo
change, device exchange, SVAs, address change, owner transfer.

Many scenarios touch features that are not implemented yet — those
tests are marked xfail so the suite documents the contract without
blocking CI.
"""
import os
import uuid
import pytest
import requests


BASE_URL = os.environ.get("TMF_BASE_URL", "http://localhost:8069")
API_KEY  = os.environ.get("TMF_API_KEY", "")


def _headers():
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


class TMFClient:
    def __init__(self, base=BASE_URL):
        self.base = base.rstrip("/")

    def _u(self, path):
        return f"{self.base}{path}"

    def get(self, path, **kw):
        return requests.get(self._u(path), headers=_headers(), timeout=30, **kw)

    def post(self, path, json=None, **kw):
        return requests.post(self._u(path), headers=_headers(), json=json, timeout=30, **kw)

    def patch(self, path, json=None, **kw):
        return requests.patch(self._u(path), headers=_headers(), json=json, timeout=30, **kw)

    def delete(self, path, **kw):
        return requests.delete(self._u(path), headers=_headers(), timeout=30, **kw)


@pytest.fixture(scope="session")
def tmf():
    return TMFClient()


@pytest.fixture(scope="session")
def ensure_platform_up(tmf):
    r = tmf.get("/tmf-api/productCatalogManagement/v5/productOffering?limit=1")
    assert r.status_code == 200, f"Platform unreachable: {r.status_code} {r.text[:200]}"
    return True


# ---------- body builders ----------

def individual_body(email, given="Test", family="User"):
    return {
        "@type": "Individual",
        "givenName": given,
        "familyName": family,
        "contactMedium": [{
            "@type": "ContactMedium",
            "mediumType": "email",
            "characteristic": {
                "@type": "EmailContactMedium",
                "emailAddress": email,
            },
        }],
    }


def product_order_body(party_id, offering_id, *,
                       qty=1, description="Order", action="add", external_id=None,
                       extra_items=None):
    items = [{
        "@type": "ProductOrderItem",
        "id": "1",
        "quantity": qty,
        "action": action,
        "productOffering": {"@type": "ProductOfferingRef", "id": offering_id},
    }]
    for i, off in enumerate(extra_items or [], start=2):
        items.append({
            "@type": "ProductOrderItem",
            "id": str(i),
            "quantity": 1,
            "action": action,
            "productOffering": {"@type": "ProductOfferingRef", "id": off},
        })
    body = {
        "@type": "ProductOrder",
        "description": description,
        "relatedParty": [{
            "@type": "RelatedParty",
            "id": party_id,
            "role": "Customer",
            "@referredType": "Individual",
        }],
        "productOrderItem": items,
    }
    if external_id:
        body["externalId"] = external_id
    return body


# ---------- helper fixtures ----------

@pytest.fixture
def unique_email():
    return f"adv+{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture
def unique_external_id():
    return f"ext-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def any_offering(tmf, ensure_platform_up):
    r = tmf.get("/tmf-api/productCatalogManagement/v5/productOffering?limit=5")
    assert r.status_code == 200
    offerings = r.json()
    assert offerings, "No offerings seeded"
    return offerings[0]


@pytest.fixture
def two_distinct_offerings(tmf, ensure_platform_up):
    r = tmf.get("/tmf-api/productCatalogManagement/v5/productOffering?limit=10")
    assert r.status_code == 200
    offerings = r.json()
    if len(offerings) < 2:
        pytest.skip("Need at least 2 offerings to exercise multi-offering scenarios")
    return offerings[0], offerings[1]


@pytest.fixture
def created_party(tmf, ensure_platform_up, unique_email):
    r = tmf.post("/tmf-api/partyManagement/v5/individual",
                 json=individual_body(unique_email, "Adv", "Tester"))
    assert r.status_code in (200, 201), r.text
    return r.json()


@pytest.fixture
def active_service_for_party(tmf, created_party, any_offering):
    """Create an order and PATCH it to completed so downstream tests can
    modify an 'active' service."""
    body = product_order_body(created_party["id"], any_offering["id"])
    r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json=body)
    assert r.status_code == 201, r.text
    order_id = r.json()["id"]
    # Drive through to completed (services themselves depend on the OSS
    # simulator if you want them to reach 'active' — but the order itself
    # can be marked completed here).
    tmf.patch(
        f"/tmf-api/productOrderingManagement/v5/productOrder/{order_id}",
        json={"state": "inProgress"},
    )
    tmf.patch(
        f"/tmf-api/productOrderingManagement/v5/productOrder/{order_id}",
        json={"state": "completed"},
    )
    return {"order_id": order_id, "party_id": created_party["id"],
            "offering_id": any_offering["id"]}
