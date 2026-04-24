"""
STEP 6 — Provisioning failure & partial rollback
"""
import pytest


@pytest.fixture
def active_order(tmf, any_offering, created_party):
    body = {
        "@type": "ProductOrder",
        "description": "Resilience test",
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


@pytest.mark.resilience
class TestProvisioningResilience:
    """Gherkin: STEP 6 — Provisioning failure & partial rollback"""

    def test_held_order_does_not_affect_sibling_orders(self, tmf, any_offering, created_party):
        """Scenario: Partial rollback does not affect other concurrent active orders."""
        def _new_order(desc):
            body = {
                "@type": "ProductOrder",
                "description": desc,
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
            return r.json()["id"]

        ok_id = _new_order("stays green")
        hold_id = _new_order("will hold")

        # Hold one of them
        r = tmf.patch(
            f"/tmf-api/productOrderingManagement/v5/productOrder/{hold_id}",
            json={"state": "held"},
        )
        assert r.status_code == 200 and r.json()["state"] == "held"

        # The sibling must still be in a non-held state
        r2 = tmf.get(f"/tmf-api/productOrderingManagement/v5/productOrder/{ok_id}")
        assert r2.status_code == 200
        assert r2.json()["state"] != "held"

    def test_retry_from_held_back_to_inProgress(self, tmf, active_order):
        """Scenario: Service order retry succeeds after transient error."""
        oid = active_order["id"]
        tmf.patch(f"/tmf-api/productOrderingManagement/v5/productOrder/{oid}",
                  json={"state": "held"})
        r = tmf.patch(f"/tmf-api/productOrderingManagement/v5/productOrder/{oid}",
                      json={"state": "inProgress"})
        assert r.status_code == 200
        assert r.json()["state"] == "inProgress"
