"""
Shared fixtures for the B2C order-to-activate test suite.

Maps the Gherkin feature `b2c_order_to_activate.feature` scenarios to
runnable pytest tests. Each test hits the real TMF API of a running Odoo
instance; no mocks.

Run:
    pytest tests/b2c_e2e/ -v

Environment:
    TMF_BASE_URL   base URL (default http://localhost:8069)
    TMF_API_KEY    optional X-API-Key header
"""
import os
import uuid
import pytest
import requests


BASE_URL = os.environ.get("TMF_BASE_URL", "http://localhost:8069")
API_KEY  = os.environ.get("TMF_API_KEY", "")


def api_headers():
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


class TMFClient:
    """Thin wrapper so scenarios read like the Gherkin steps."""

    def __init__(self, base_url=BASE_URL):
        self.base = base_url.rstrip("/")

    def _url(self, path):
        return f"{self.base}{path}"

    def get(self, path, **kw):
        return requests.get(self._url(path), headers=api_headers(), timeout=30, **kw)

    def post(self, path, json=None, **kw):
        return requests.post(self._url(path), headers=api_headers(), json=json, timeout=30, **kw)

    def patch(self, path, json=None, **kw):
        return requests.patch(self._url(path), headers=api_headers(), json=json, timeout=30, **kw)

    def delete(self, path, **kw):
        return requests.delete(self._url(path), headers=api_headers(), timeout=30, **kw)


@pytest.fixture(scope="session")
def tmf():
    return TMFClient()


@pytest.fixture(scope="session")
def ensure_platform_up(tmf):
    """Gherkin: 'the BSS platform is running and all ODA components are healthy'."""
    r = tmf.get("/tmf-api/productCatalogManagement/v5/productOffering?limit=1")
    assert r.status_code == 200, f"Platform unreachable: {r.status_code} {r.text[:200]}"
    return True


@pytest.fixture
def unique_email():
    return f"e2e+{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture
def unique_external_id():
    return f"ext-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def any_offering(tmf, ensure_platform_up):
    """Pick any active offering from the catalog."""
    r = tmf.get("/tmf-api/productCatalogManagement/v5/productOffering?limit=5")
    assert r.status_code == 200
    offerings = r.json()
    assert offerings, "No offerings in catalog — seed data first"
    return offerings[0]


def build_individual_body(email, given="Test", family="User"):
    """TMF632 Individual — `@type` is the spec-required discriminator."""
    return {
        "@type": "Individual",
        "givenName": given,
        "familyName": family,
        "contactMedium": [
            {
                "@type": "ContactMedium",
                "mediumType": "email",
                "characteristic": {
                    "@type": "EmailContactMedium",
                    "emailAddress": email,
                },
            }
        ],
    }


@pytest.fixture
def created_party(tmf, ensure_platform_up, unique_email):
    """Gherkin: 'a registered party' — creates one and returns its id."""
    body = build_individual_body(unique_email)
    r = tmf.post("/tmf-api/partyManagement/v5/individual", json=body)
    assert r.status_code in (200, 201), f"Party create failed: {r.status_code} {r.text}"
    data = r.json()
    yield data
    # (no cleanup — Odoo retains the partner)
