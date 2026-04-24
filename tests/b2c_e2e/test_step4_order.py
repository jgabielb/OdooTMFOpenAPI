"""
STEP 4 — Product order submission (TMF622 ProductOrdering)
"""
import pytest


@pytest.fixture
def order_body(any_offering, created_party):
    return {
        "@type": "ProductOrder",
        "description": "New B2C subscription",
        "relatedParty": [
            {
                "@type": "RelatedParty",
                "id": created_party["id"],
                "role": "Customer",
                "@referredType": "Individual",
            }
        ],
        "productOrderItem": [
            {
                "@type": "ProductOrderItem",
                "id": "1",
                "quantity": 1,
                "action": "add",
                "productOffering": {
                    "@type": "ProductOfferingRef",
                    "id": any_offering["id"],
                },
            }
        ],
    }


@pytest.mark.order
class TestOrderSubmission:
    """Gherkin: STEP 4 — Product order submission"""

    def test_successful_order_submission_returns_201(self, tmf, order_body):
        r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json=order_body)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data.get("id")
        assert data["state"] in ("acknowledged", "inProgress")

    def test_order_exposes_related_party(self, tmf, order_body, created_party):
        r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json=order_body)
        assert r.status_code == 201
        rp = r.json().get("relatedParty", [])
        assert any(p.get("id") == created_party["id"] for p in rp)

    def test_duplicate_submission_is_idempotent(self, tmf, order_body, unique_external_id):
        """Scenario: Duplicate order submission is idempotent (externalId-based)."""
        body = {**order_body, "externalId": unique_external_id}

        r1 = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json=body)
        assert r1.status_code == 201
        first_id = r1.json()["id"]

        r2 = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json=body)
        assert r2.status_code == 200, "Second submission should return 200 (not 201)"
        assert r2.json()["id"] == first_id, "Same externalId must map to same order"


@pytest.mark.order_state
class TestOrderStateTransitions:
    """Scenarios: state transitions via PATCH."""

    def _create(self, tmf, order_body):
        r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json=order_body)
        assert r.status_code == 201
        return r.json()["id"]

    def test_transition_to_held(self, tmf, order_body):
        oid = self._create(tmf, order_body)
        r = tmf.patch(
            f"/tmf-api/productOrderingManagement/v5/productOrder/{oid}",
            json={"state": "held"},
        )
        assert r.status_code == 200
        assert r.json()["state"] == "held"

    def test_transition_held_back_to_inProgress(self, tmf, order_body):
        oid = self._create(tmf, order_body)
        tmf.patch(
            f"/tmf-api/productOrderingManagement/v5/productOrder/{oid}",
            json={"state": "held"},
        )
        r = tmf.patch(
            f"/tmf-api/productOrderingManagement/v5/productOrder/{oid}",
            json={"state": "inProgress"},
        )
        assert r.status_code == 200
        assert r.json()["state"] == "inProgress"

    def test_transition_to_completed(self, tmf, order_body):
        oid = self._create(tmf, order_body)
        r = tmf.patch(
            f"/tmf-api/productOrderingManagement/v5/productOrder/{oid}",
            json={"state": "completed"},
        )
        assert r.status_code == 200
        assert r.json()["state"] == "completed"

    def test_transition_to_cancelled(self, tmf, order_body):
        oid = self._create(tmf, order_body)
        r = tmf.patch(
            f"/tmf-api/productOrderingManagement/v5/productOrder/{oid}",
            json={"state": "cancelled"},
        )
        assert r.status_code == 200
        assert r.json()["state"] == "cancelled"

    def test_invalid_state_returns_400(self, tmf, order_body):
        oid = self._create(tmf, order_body)
        r = tmf.patch(
            f"/tmf-api/productOrderingManagement/v5/productOrder/{oid}",
            json={"state": "not-a-real-state"},
        )
        assert r.status_code == 400
