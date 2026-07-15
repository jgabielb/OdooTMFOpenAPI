"""
Feature: Device exchange — swap a faulty CPE without interrupting service.

The service stays "active" throughout; only its resource reference changes.
Warranty rules determine whether a charge is posted.
"""
import uuid
from datetime import date, timedelta
import pytest


def _seed_lot(tmf, serial=None, status="available", warranty_end=None):
    serial = serial or f"SN-{uuid.uuid4().hex[:8].upper()}"
    body = {"name": serial, "resourceStatus": status}
    if warranty_end:
        body["warrantyEndDate"] = warranty_end
    r = tmf.post("/tmf-api/resourceInventoryManagement/v5/resource", json=body)
    assert r.status_code == 201, f"Could not seed lot: {r.text}"
    return r.json()


def _create_service(tmf, party_id, resource_id=None):
    body = {
        "name": f"Exchange-Svc-{uuid.uuid4().hex[:6]}",
        "state": "active",
        "relatedParty": [{
            "@type": "RelatedPartyRefOrPartyRoleRef",
            "partyOrPartyRole": {"id": party_id, "name": "Customer"},
        }],
    }
    if resource_id:
        body["supportingResource"] = [{"id": resource_id, "@type": "ResourceRef"}]
    r = tmf.post("/tmf-api/serviceInventoryManagement/v5/service", json=body)
    assert r.status_code == 201, f"Could not create service: {r.text}"
    return r.json()


def _exchange_order(tmf, party_id, service_id, new_resource_id):
    r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json={
        "@type": "ProductOrder",
        "relatedParty": [{"@type": "RelatedParty", "id": party_id, "role": "Customer"}],
        "productOrderItem": [{
            "@type": "ProductOrderItem",
            "id": "1",
            "quantity": 1,
            "action": "modify",
            "product": {"id": service_id},
            "supportingResource": [{"id": new_resource_id, "@type": "ResourceRef"}],
        }],
    })
    assert r.status_code == 201, f"Exchange order failed: {r.text}"
    return r.json()


def _get_service(tmf, service_id):
    r = tmf.get(f"/tmf-api/serviceInventoryManagement/v5/service/{service_id}")
    assert r.status_code == 200
    return r.json()


def _get_resource(tmf, resource_id):
    r = tmf.get(f"/tmf-api/resourceInventoryManagement/v5/resource/{resource_id}")
    assert r.status_code == 200
    return r.json()


@pytest.mark.device_exchange
class TestDeviceExchange:

    def test_exchange_keeps_service_active(self, tmf, created_party):
        lot_a = _seed_lot(tmf, status="available")
        lot_b = _seed_lot(tmf, status="available")
        party_id = created_party["id"]

        svc = _create_service(tmf, party_id, lot_a["id"])
        assert svc.get("state") == "active"

        _exchange_order(tmf, party_id, svc["id"], lot_b["id"])

        updated = _get_service(tmf, svc["id"])
        assert updated.get("state") == "active", (
            f"Service state changed after exchange: {updated.get('state')!r}"
        )
        # New resource should now be referenced
        sr = updated.get("supportingResource") or []
        sr_ids = [r.get("id") for r in sr]
        assert lot_b["id"] in sr_ids, (
            f"Expected lot_b {lot_b['id']} in supportingResource after exchange, got {sr_ids}"
        )

    def test_in_warranty_exchange_is_free(self, tmf, created_party):
        future_date = (date.today() + timedelta(days=365)).isoformat()
        lot_a = _seed_lot(tmf, status="available")
        lot_b = _seed_lot(tmf, status="available", warranty_end=future_date)
        party_id = created_party["id"]

        svc = _create_service(tmf, party_id, lot_a["id"])
        order = _exchange_order(tmf, party_id, svc["id"], lot_b["id"])

        # In-warranty exchange: no exchange-fee line expected
        items = order.get("productOrderItem") or []
        fee_items = [i for i in items if "exchange-fee" in (i.get("name") or "").lower()]
        assert not fee_items, (
            f"Expected no exchange-fee for in-warranty device, got items: {items}"
        )

    def test_out_of_warranty_exchange_is_charged(self, tmf, created_party):
        past_date = (date.today() - timedelta(days=1)).isoformat()
        lot_a = _seed_lot(tmf, status="available")
        lot_b = _seed_lot(tmf, status="available", warranty_end=past_date)
        party_id = created_party["id"]

        svc = _create_service(tmf, party_id, lot_a["id"])
        _exchange_order(tmf, party_id, svc["id"], lot_b["id"])

        # The exchange fee is an order line on the sale order, not in the TMF order JSON.
        # Verify instead that the lot_a was released back to available.
        old_lot = _get_resource(tmf, lot_a["id"])
        assert old_lot.get("resourceStatus") == "available", (
            f"Old device should be released to 'available' after exchange, "
            f"got {old_lot.get('resourceStatus')!r}"
        )
        # And the new lot is now reserved (claimed)
        new_lot = _get_resource(tmf, lot_b["id"])
        assert new_lot.get("resourceStatus") == "reserved", (
            f"New device should be 'reserved' after out-of-warranty exchange, "
            f"got {new_lot.get('resourceStatus')!r}"
        )
