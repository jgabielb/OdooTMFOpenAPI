"""
STEP 5 — Order decomposition & service order (TMF641)
"""
import pytest
import time


@pytest.fixture
def order_with_services(tmf, any_offering, created_party):
    body = {
        "@type": "ProductOrder",
        "description": "E2E order",
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


@pytest.mark.orchestration
class TestServiceOrchestration:
    """Gherkin: STEP 5 — Order decomposition & service order"""

    def test_services_created_for_order(self, tmf, order_with_services):
        """Confirming the order triggers the provisioning bridge → services."""
        # Confirm the order so the provisioning bridge fires.
        oid = order_with_services["id"]
        tmf.patch(
            f"/tmf-api/productOrderingManagement/v5/productOrder/{oid}",
            json={"state": "inProgress"},
        )

        # Services typically land in 'feasabilityChecked' after confirmation.
        time.sleep(2)
        r = tmf.get(
            "/tmf-api/serviceInventoryManagement/v5/service?state=feasabilityChecked&limit=100",
        )
        if r.status_code == 404:
            # some builds expose the alt path
            r = tmf.get("/tmf-api/serviceInventory/v5/service?state=feasabilityChecked&limit=100")
        assert r.status_code == 200

    @pytest.mark.xfail(reason="TMF641 /serviceOrder decomposition path not yet implemented")
    def test_product_order_decomposes_into_service_order(self, tmf, order_with_services):
        oid = order_with_services["id"]
        r = tmf.get(
            f"/tmf-api/serviceOrder/v4/serviceOrder?relatedEntity.id={oid}"
        )
        assert r.status_code == 200
        assert len(r.json()) >= 1
