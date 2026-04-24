"""
FULL E2E HAPPY PATH — combined scenario from the feature file.

Goes party → order → state transitions → completed in one test, mirroring
the @happy-path scenario. For the full real flow with OSS simulation,
run `docker compose up` in mock_oss/ between steps and watch services
advance to 'active' (which fires the billing bridge).
"""
import pytest
from conftest import build_individual_body


@pytest.mark.happy_path
@pytest.mark.e2e
def test_full_b2c_order_to_activate_happy_path(tmf, unique_email, unique_external_id, any_offering):
    """Gherkin: Full B2C order-to-activate happy path end-to-end."""

    # 1. Registration
    party_body = build_individual_body(unique_email, "E2E", "Customer")
    r = tmf.post("/tmf-api/partyManagement/v5/individual", json=party_body)
    assert r.status_code in (200, 201), r.text
    party_id = r.json()["id"]

    # 2. Catalog browse (already have `any_offering` fixture)
    assert any_offering["id"]

    # 3. Order submission (idempotent)
    order_body = {
        "@type": "ProductOrder",
        "description": "Happy path",
        "externalId": unique_external_id,
        "relatedParty": [
            {"@type": "RelatedParty", "id": party_id,
             "role": "Customer", "@referredType": "Individual"}
        ],
        "productOrderItem": [
            {"@type": "ProductOrderItem", "id": "1", "quantity": 1, "action": "add",
             "productOffering": {"@type": "ProductOfferingRef", "id": any_offering["id"]}}
        ],
    }
    r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json=order_body)
    assert r.status_code == 201, r.text
    order_id = r.json()["id"]

    # 3b. Idempotency check
    r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json=order_body)
    assert r.status_code == 200
    assert r.json()["id"] == order_id

    # 4. Move to inProgress explicitly
    r = tmf.patch(
        f"/tmf-api/productOrderingManagement/v5/productOrder/{order_id}",
        json={"state": "inProgress"},
    )
    assert r.status_code == 200
    assert r.json()["state"] == "inProgress"

    # 5. Complete the order
    r = tmf.patch(
        f"/tmf-api/productOrderingManagement/v5/productOrder/{order_id}",
        json={"state": "completed"},
    )
    assert r.status_code == 200
    assert r.json()["state"] == "completed"

    # 6. State is retrievable via GET
    r = tmf.get(f"/tmf-api/productOrderingManagement/v5/productOrder/{order_id}")
    assert r.status_code == 200
    assert r.json()["state"] == "completed"
    assert r.json().get("externalId") == unique_external_id
