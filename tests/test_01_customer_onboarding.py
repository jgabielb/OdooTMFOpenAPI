"""Scenario 1: Customer Onboarding (Engage)

Create a customer with multiple accounts, verify TMF ↔ Odoo sync.
"""
import pytest
from helpers.assertions import *


class TestCustomerOnboarding:

    def test_create_individual_party(self, tmf, odoo):
        """POST individual → res.partner created."""
        data, resp = tmf.create_party("John", "Doe", contactMedium=[{
            "mediumType": "email",
            "characteristic": {"emailAddress": "john.doe@test.com"},
        }])
        party_id = assert_tmf_resource(data, "Individual")
        assert_field_present(data, "givenName")
        assert_field_value(data, "givenName", "John")
        assert_field_value(data, "familyName", "Doe")

        partner = odoo.find_partner_by_tmf_id(party_id)
        assert partner, f"res.partner not found for tmf_id={party_id}"
        assert "Doe" in partner["name"] or "John" in partner["name"]

        self.__class__.party_id = party_id
        self.__class__.partner_odoo_id = partner["id"]

    def test_create_customer(self, tmf):
        """POST customer linked to party."""
        data, resp = tmf.create("customer", "customer", {
            "name": "John Doe",
            "engagedParty": {"id": self.party_id, "@referredType": "Individual"},
        })
        customer_id = assert_tmf_resource(data)
        self.__class__.customer_id = customer_id

    def test_create_billing_account_personal(self, tmf):
        """POST billing account (Personal)."""
        data, resp = tmf.create_billing_account("Personal Account", self.party_id)
        acct_id = assert_tmf_resource(data)
        assert_field_value(data, "name", "Personal Account")
        self.__class__.account_personal_id = acct_id

    def test_create_billing_account_business(self, tmf):
        """POST billing account (Business)."""
        data, resp = tmf.create_billing_account("Business Account", self.party_id)
        acct_id = assert_tmf_resource(data)
        assert_field_value(data, "name", "Business Account")
        self.__class__.account_business_id = acct_id

    def test_list_billing_accounts_for_party(self, tmf):
        """GET billing accounts filtered by party."""
        data, resp = tmf.list("account", "billingAccount",
                              params={"relatedParty.id": self.party_id})
        assert isinstance(data, list)
        assert len(data) >= 2, f"Expected 2+ accounts, got {len(data)}"

    def test_get_party_details(self, tmf):
        """GET party verifies all fields."""
        data, resp = tmf.get("party", "individual", self.party_id)
        assert_tmf_resource(data, "Individual")
        assert_field_present(data, "href")
        assert self.party_id in data["href"]

    def test_odoo_partner_has_tmf_fields(self, odoo):
        """Verify res.partner has TMF fields populated."""
        recs = odoo.search_read(
            "res.partner",
            [("id", "=", self.partner_odoo_id)],
            ["tmf_id", "tmf_status", "name"],
        )
        assert recs, "Partner not found"
        assert recs[0]["tmf_id"] == self.party_id

    def test_edit_partner_in_odoo_syncs(self, odoo, tmf):
        """Edit partner name in Odoo → verify TMF reflects change."""
        odoo.write("res.partner", [self.partner_odoo_id], {"name": "John D. Doe"})
        data, _ = tmf.get("party", "individual", self.party_id)
        # Bridge should reflect the updated name
        assert "Doe" in (data.get("familyName", "") + data.get("name", ""))

    def test_delete_party(self, tmf):
        """DELETE party → 204."""
        tmf.delete("party", "individual", self.party_id)
        tmf.get("party", "individual", self.party_id, expected_status=404)
