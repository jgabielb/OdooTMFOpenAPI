"""
Feature: Account ownership transfer

One partner transfers an account to another partner. Services must
continue uninterrupted; past debts stay with the previous owner.
"""
import uuid
import pytest


def _create_party(tmf, name):
    r = tmf.post("/tmf-api/partyManagement/v5/individual", json={
        "@type": "Individual",
        "givenName": name,
        "familyName": "Test",
    })
    if r.status_code not in (200, 201):
        r = tmf.post("/tmf-api/partyManagement/v5/organization", json={
            "@type": "Organization",
            "tradingName": name,
            "name": name,
        })
    assert r.status_code in (200, 201), f"Could not create party {name}: {r.text}"
    return r.json()


def _create_service(tmf, party_id, name=None):
    r = tmf.post("/tmf-api/serviceInventoryManagement/v5/service", json={
        "name": name or f"Transfer-Svc-{uuid.uuid4().hex[:6]}",
        "state": "active",
        "relatedParty": [{
            "@type": "RelatedPartyRefOrPartyRoleRef",
            "partyOrPartyRole": {"id": party_id, "name": "Customer"},
        }],
    })
    assert r.status_code == 201, f"Could not create service: {r.text}"
    return r.json()


def _transfer_order(tmf, from_party_id, service_id, to_party_id):
    """Place a modify order that changes the service's owner."""
    r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json={
        "@type": "ProductOrder",
        "description": "Owner transfer",
        "relatedParty": [{"@type": "RelatedParty", "id": from_party_id, "role": "Customer"}],
        "productOrderItem": [{
            "@type": "ProductOrderItem",
            "id": "1",
            "quantity": 1,
            "action": "modify",
            "product": {"id": service_id},
            "relatedParty": [{"id": to_party_id, "role": "Customer", "@type": "RelatedParty"}],
        }],
    })
    assert r.status_code == 201, f"Transfer order failed: {r.text}"
    return r.json()


def _get_service(tmf, service_id):
    r = tmf.get(f"/tmf-api/serviceInventoryManagement/v5/service/{service_id}")
    assert r.status_code == 200
    return r.json()


@pytest.mark.owner_change
class TestOwnerChange:

    def test_transfer_keeps_services_active(self, tmf, created_party):
        party_b = _create_party(tmf, f"NewOwner-{uuid.uuid4().hex[:6]}")

        svc = _create_service(tmf, created_party["id"])
        assert svc.get("state") == "active"

        _transfer_order(tmf, created_party["id"], svc["id"], party_b["id"])

        updated = _get_service(tmf, svc["id"])
        assert updated.get("state") == "active", (
            f"Service state changed after owner transfer: {updated.get('state')!r}"
        )

        # Verify the service now belongs to party_b
        rp = updated.get("relatedParty") or []
        owner_ids = [
            (p.get("partyOrPartyRole") or {}).get("id") or p.get("id")
            for p in rp
        ]
        assert party_b["id"] in owner_ids, (
            f"Service should belong to party_b {party_b['id']} after transfer, "
            f"got relatedParty: {rp}"
        )

    def test_outstanding_balance_stays_with_previous_owner(self, tmf, created_party):
        party_b = _create_party(tmf, f"NewOwner2-{uuid.uuid4().hex[:6]}")

        # Create a party account for the original owner with a balance
        r = tmf.post("/tmf-api/accountManagement/v5/partyAccount", json={
            "@type": "PartyAccount",
            "name": f"Acct-{uuid.uuid4().hex[:6]}",
            "relatedParty": [{"id": created_party["id"], "role": "owner", "@type": "RelatedParty"}],
            "accountBalance": [{"balanceType": "ReceivableBalance", "amount": {"value": 150, "unit": "USD"}}],
        })
        assert r.status_code == 201, f"Could not create account: {r.text}"
        account = r.json()

        svc = _create_service(tmf, created_party["id"])
        _transfer_order(tmf, created_party["id"], svc["id"], party_b["id"])

        # The account balance (debt) should remain on the account — unaffected by service transfer
        r2 = tmf.get(f"/tmf-api/accountManagement/v5/partyAccount/{account['id']}")
        assert r2.status_code == 200
        updated_account = r2.json()
        balance = updated_account.get("accountBalance") or []
        assert balance, (
            "accountBalance was wiped after service ownership transfer — "
            "outstanding balance should stay with the original account"
        )
        amounts = [b.get("amount", {}).get("value") for b in balance]
        assert 150 in amounts, (
            f"Expected balance of 150 to remain on account, got {balance}"
        )
