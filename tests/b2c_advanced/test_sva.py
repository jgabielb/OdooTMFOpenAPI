"""
Feature: SVAs (Servicios de Valor Agregado / value-added services)

Add-ons like STATIC_IP, INT_CALLS_100, STREAMING_BUNDLE attach to a parent
broadband service as child services (CFS → child CFS/RFS hierarchy).
"""
import pytest


def _create_parent_service(tmf, party_id):
    """Create a standalone active service to act as the SVA parent."""
    r = tmf.post("/tmf-api/serviceInventoryManagement/v5/service", json={
        "name": "Broadband-Parent",
        "state": "active",
        "relatedParty": [{
            "@type": "RelatedPartyRefOrPartyRoleRef",
            "partyOrPartyRole": {"id": party_id, "name": "SVA Test Customer"},
        }],
    })
    assert r.status_code == 201, f"Could not create parent service: {r.text}"
    return r.json()


def _sva_order_item(idx, offering_id, parent_service_id):
    return {
        "@type": "ProductOrderItem",
        "id": str(idx),
        "quantity": 1,
        "action": "add",
        "productOffering": {"id": offering_id},
        "product": {
            "productRelationship": [{
                "relationshipType": "isChildOf",
                "product": {"id": parent_service_id},
            }],
        },
    }


def _place_order(tmf, party_id, items, description="SVA order"):
    body = {
        "@type": "ProductOrder",
        "description": description,
        "relatedParty": [{"@type": "RelatedParty", "id": party_id, "role": "Customer"}],
        "productOrderItem": items,
    }
    r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json=body)
    assert r.status_code == 201, f"Order creation failed: {r.text}"
    return r.json()


@pytest.mark.sva
class TestSVA:

    def test_add_sva_to_active_service(self, tmf, created_party, any_offering):
        parent = _create_parent_service(tmf, created_party["id"])
        parent_id = parent["id"]

        _place_order(
            tmf,
            created_party["id"],
            [_sva_order_item(1, any_offering["id"], parent_id)],
            "Add single SVA",
        )

        r = tmf.get(f"/tmf-api/serviceInventoryManagement/v5/service/{parent_id}")
        assert r.status_code == 200
        updated = r.json()
        assert "supportingService" in updated, (
            "Parent service has no supportingService after adding SVA"
        )
        assert len(updated["supportingService"]) >= 1

    def test_add_multiple_svas_in_one_order(self, tmf, created_party, two_distinct_offerings):
        off1, off2 = two_distinct_offerings
        parent = _create_parent_service(tmf, created_party["id"])
        parent_id = parent["id"]

        _place_order(
            tmf,
            created_party["id"],
            [
                _sva_order_item(1, off1["id"], parent_id),
                _sva_order_item(2, off2["id"], parent_id),
            ],
            "Add two SVAs",
        )

        r = tmf.get(f"/tmf-api/serviceInventoryManagement/v5/service/{parent_id}")
        assert r.status_code == 200
        updated = r.json()
        assert "supportingService" in updated
        assert len(updated["supportingService"]) >= 2

    def test_remove_sva_keeps_parent_active(self, tmf, created_party, any_offering):
        parent = _create_parent_service(tmf, created_party["id"])
        parent_id = parent["id"]

        # Add an SVA first
        _place_order(
            tmf,
            created_party["id"],
            [_sva_order_item(1, any_offering["id"], parent_id)],
            "Add SVA for removal test",
        )

        r = tmf.get(f"/tmf-api/serviceInventoryManagement/v5/service/{parent_id}")
        sva_list = r.json().get("supportingService") or []
        assert sva_list, "SVA was not created under the parent service"
        sva_id = sva_list[0]["id"]

        # Remove the SVA via a delete order
        del_body = {
            "@type": "ProductOrder",
            "description": "Remove SVA",
            "relatedParty": [
                {"@type": "RelatedParty", "id": created_party["id"], "role": "Customer"}
            ],
            "productOrderItem": [{
                "@type": "ProductOrderItem",
                "id": "1",
                "quantity": 1,
                "action": "delete",
                "product": {"id": sva_id},
            }],
        }
        rd = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json=del_body)
        assert rd.status_code == 201, rd.text

        # SVA child must be terminated
        r_sva = tmf.get(f"/tmf-api/serviceInventoryManagement/v5/service/{sva_id}")
        assert r_sva.status_code == 200
        assert r_sva.json()["state"] == "terminated", (
            f"SVA service should be 'terminated', got {r_sva.json().get('state')}"
        )

        # Parent must still be active
        r_parent = tmf.get(f"/tmf-api/serviceInventoryManagement/v5/service/{parent_id}")
        assert r_parent.status_code == 200
        assert r_parent.json()["state"] == "active", (
            f"Parent service should remain 'active', got {r_parent.json().get('state')}"
        )
