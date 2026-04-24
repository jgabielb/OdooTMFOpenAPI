"""
STEP 7 — Activation confirmation & invoice generation
"""
import pytest


@pytest.fixture
def pending_order(tmf, any_offering, created_party):
    body = {
        "@type": "ProductOrder",
        "description": "Activation test",
        "relatedParty": [
            {"@type": "RelatedParty", "id": created_party["id"],
             "role": "Customer", "@referredType": "Individual"}
        ],
        "productOrderItem": [
            {"@type": "ProductOrderItem", "id": "1", "quantity": 1, "action": "add",
             "productOffering": {"@type": "ProductOfferingRef", "id": any_offering["id"]}}
        ],
    }
    r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json=body)
    assert r.status_code == 201
    return r.json()


@pytest.mark.activation
class TestActivation:
    """Gherkin: STEP 7 — Activation & invoice generation"""

    def test_completed_order_state_retrievable_via_get(self, tmf, pending_order):
        """Scenario: Completed order state is retrievable via GET."""
        oid = pending_order["id"]
        tmf.patch(f"/tmf-api/productOrderingManagement/v5/productOrder/{oid}",
                  json={"state": "completed"})
        r = tmf.get(f"/tmf-api/productOrderingManagement/v5/productOrder/{oid}")
        assert r.status_code == 200
        body = r.json()
        assert body["state"] == "completed"
        assert "completionDate" in body
        for item in body.get("productOrderItem", []):
            # Items inherit order state in current to_tmf_json
            assert item["state"] == "completed"

    @pytest.mark.xfail(reason="Invoice generation requires services to reach 'active' via OSS mock")
    def test_completed_order_produces_invoice(self, tmf, pending_order):
        """Scenario: Completed order triggers invoice generation in Odoo.

        This requires the full flow via the OSS simulator (services → active →
        billing bridge). The PATCH-to-completed shortcut bypasses service
        activation and therefore does not currently produce an invoice.
        """
        oid = pending_order["id"]
        tmf.patch(f"/tmf-api/productOrderingManagement/v5/productOrder/{oid}",
                  json={"state": "completed"})
        r = tmf.get(f"/tmf-api/customerBillManagement/v5/customerBill")
        assert r.status_code == 200
        bills = r.json()
        assert any(oid in str(b) for b in bills), "no bill created for completed order"
