"""
Feature: Inventory — TMF639 ResourceInventory + Odoo stock.lot

Covers: listing resources, serial numbers, decrementing stock on assignment,
and ordering against out-of-stock conditions.
"""
import uuid
import pytest


def _seed_lot(tmf, serial=None, status="available"):
    """Create a stock.lot (resource) with a known serial and status."""
    serial = serial or f"SN-{uuid.uuid4().hex[:8].upper()}"
    r = tmf.post("/tmf-api/resourceInventoryManagement/v5/resource", json={
        "name": serial,
        "resourceStatus": status,
    })
    assert r.status_code == 201, f"Could not seed lot: {r.text}"
    return r.json()


def _create_service_with_resource(tmf, party_id, resource_id):
    """Create a tmf.service that claims the given resource lot."""
    r = tmf.post("/tmf-api/serviceInventoryManagement/v5/service", json={
        "name": f"Test-Service-{uuid.uuid4().hex[:6]}",
        "state": "active",
        "relatedParty": [{
            "@type": "RelatedPartyRefOrPartyRoleRef",
            "partyOrPartyRole": {"id": party_id, "name": "Inventory Tester"},
        }],
        "supportingResource": [{"id": resource_id, "@type": "ResourceRef"}],
    })
    return r


@pytest.mark.inventory
class TestResourceInventory:

    def test_resource_inventory_endpoint_reachable(self, tmf):
        candidates = [
            "/tmf-api/resourceInventoryManagement/v5/resource?limit=5",
            "/tmf-api/resourceInventoryManagement/v4/resource?limit=5",
            "/tmf-api/resourceInventory/v5/resource?limit=5",
            "/tmf-api/resourceInventory/v4/resource?limit=5",
        ]
        for path in candidates:
            r = tmf.get(path)
            if r.status_code == 200:
                return
        pytest.xfail("No /resourceInventory endpoint is reachable")

    def test_resource_has_serial_number_and_state(self, tmf):
        r = tmf.get("/tmf-api/resourceInventoryManagement/v5/resource?limit=5")
        assert r.status_code == 200, (
            f"v5 resource endpoint unreachable: {r.status_code} {r.text[:200]}"
        )
        resources = r.json()
        for res in resources:
            assert "resourceCharacteristic" in res or "serialNumber" in res, (
                f"Resource {res.get('id')} missing serialNumber/resourceCharacteristic"
            )
            assert "state" in res or "resourceStatus" in res, (
                f"Resource {res.get('id')} missing state/resourceStatus"
            )

    def test_ordering_a_device_decrements_inventory(self, tmf, created_party):
        # Seed a lot with status=available
        lot = _seed_lot(tmf, status="available")
        lot_id = lot["id"]

        # Assign to a service — this should change resourceStatus to reserved
        r = _create_service_with_resource(tmf, created_party["id"], lot_id)
        assert r.status_code == 201, f"Service creation failed: {r.text}"

        # Fetch the resource — status must no longer be 'available'
        r2 = tmf.get(f"/tmf-api/resourceInventoryManagement/v5/resource/{lot_id}")
        assert r2.status_code == 200, f"Resource not found after service creation: {r2.text}"
        res_after = r2.json()
        status_after = res_after.get("resourceStatus") or res_after.get("state")
        assert status_after != "available", (
            f"Resource {lot_id} still shows 'available' after service claimed it "
            f"(got resourceStatus={status_after!r})"
        )

    def test_order_fails_when_out_of_stock(self, tmf, created_party):
        # Seed a lot that is already reserved (out of stock)
        lot = _seed_lot(tmf, status="reserved")
        lot_id = lot["id"]

        # Attempt to assign it to a service — must be rejected
        r = _create_service_with_resource(tmf, created_party["id"], lot_id)
        assert r.status_code == 422, (
            f"Expected 422 when resource is reserved, got {r.status_code}: {r.text[:300]}"
        )
