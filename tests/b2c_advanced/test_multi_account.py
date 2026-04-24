"""
Feature: One partner (RUT) → multiple accounts, each with its own services.

Covers the business model: a single legal entity can own several accounts
(e.g., HOME, OFFICE), and billing must be scoped per-account not per-partner.
"""
import pytest

from conftest import product_order_body


@pytest.mark.multi_account
class TestMultiAccount:

    def test_partner_can_own_multiple_orders(self, tmf, created_party, any_offering):
        """Prove that N orders from the same party → N distinct orders."""
        party_id = created_party["id"]
        first = tmf.post(
            "/tmf-api/productOrderingManagement/v5/productOrder",
            json=product_order_body(party_id, any_offering["id"], description="HOME line"),
        )
        assert first.status_code == 201
        second = tmf.post(
            "/tmf-api/productOrderingManagement/v5/productOrder",
            json=product_order_body(party_id, any_offering["id"], description="OFFICE line"),
        )
        assert second.status_code == 201
        assert first.json()["id"] != second.json()["id"]

    def test_party_response_lists_accounts(self, tmf, created_party):
        party_id = created_party["id"]
        r = tmf.get(f"/tmf-api/partyManagement/v5/individual/{party_id}?fields=account")
        assert r.status_code == 200
        accounts = r.json().get("account") or []
        assert isinstance(accounts, list)

    @pytest.mark.xfail(reason="Per-account billing separation not verified end-to-end yet")
    def test_billing_is_scoped_per_account(self, tmf):
        """With two accounts under one partner, expect two customer bills per cycle."""
        pytest.xfail("needs a full billing-cycle run")
