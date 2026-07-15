"""
Feature: Service address change (relocation)

The customer keeps the same service (same tmf_id) but the physical
installation moves. Feasibility at the new address must be approved
before the change is accepted.
"""
import uuid
import pytest


def _create_service(tmf, party_id):
    r = tmf.post("/tmf-api/serviceInventoryManagement/v5/service", json={
        "name": f"Relocate-Svc-{uuid.uuid4().hex[:6]}",
        "state": "active",
        "relatedParty": [{
            "@type": "RelatedPartyRefOrPartyRoleRef",
            "partyOrPartyRole": {"id": party_id, "name": "Customer"},
        }],
    })
    assert r.status_code == 201, f"Could not create service: {r.text}"
    return r.json()


def _relocation_order(tmf, party_id, service_id, new_place):
    r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json={
        "@type": "ProductOrder",
        "relatedParty": [{"@type": "RelatedParty", "id": party_id, "role": "Customer"}],
        "productOrderItem": [{
            "@type": "ProductOrderItem",
            "id": "1",
            "quantity": 1,
            "action": "modify",
            "product": {"id": service_id},
            "place": new_place,
        }],
    })
    return r


@pytest.mark.address_change
class TestAddressChange:

    def test_relocate_service_with_approved_feasibility(self, tmf, created_party):
        party_id = created_party["id"]
        svc = _create_service(tmf, party_id)
        svc_id = svc["id"]

        new_place = [{"id": str(uuid.uuid4()), "name": "456 New Street", "@type": "PlaceRef"}]
        r = _relocation_order(tmf, party_id, svc_id, new_place)
        assert r.status_code == 201, f"Relocation order failed: {r.text}"

        r2 = tmf.get(f"/tmf-api/serviceInventoryManagement/v5/service/{svc_id}")
        assert r2.status_code == 200
        updated = r2.json()
        place = updated.get("place") or []
        assert place, (
            "Service place was not updated after modify order with place"
        )
        place_names = [p.get("name") for p in place]
        assert "456 New Street" in place_names, (
            f"Expected '456 New Street' in place after relocation, got {place}"
        )

    def test_relocation_blocked_when_feasibility_denied(self, tmf, created_party):
        party_id = created_party["id"]
        svc = _create_service(tmf, party_id)
        svc_id = svc["id"]

        # Mark relocation as denied via PATCH on the service
        r_patch = tmf.patch(
            f"/tmf-api/serviceInventoryManagement/v5/service/{svc_id}",
            json={"relocationFeasibility": "denied"},
        )
        assert r_patch.status_code == 200, f"Could not set feasibility: {r_patch.text}"

        new_place = [{"id": str(uuid.uuid4()), "name": "789 Blocked Ave", "@type": "PlaceRef"}]
        r = _relocation_order(tmf, party_id, svc_id, new_place)
        assert r.status_code == 422, (
            f"Expected 422 when relocation feasibility is denied, got {r.status_code}: {r.text}"
        )
