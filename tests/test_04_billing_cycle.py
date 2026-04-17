"""Scenario 4: Billing Cycle (Bill)

Invoice generation, payment, and bill management.
"""
import pytest
from helpers.assertions import *


@pytest.fixture(scope="class")
def billing_setup(tmf):
    party, _ = tmf.create_party("Bob", "Wilson")
    account, _ = tmf.create_billing_account("Bob Personal", party["id"])
    return {"party_id": party["id"], "account_id": account["id"]}


class TestBillingCycle:

    def test_create_payment(self, tmf, odoo, billing_setup):
        """POST payment → account.payment created via bridge."""
        data, _ = tmf.create_payment(
            59.99,
            billing_setup["account_id"],
            description="Monthly payment",
        )
        payment_id = assert_tmf_resource(data)
        assert_field_present(data, "totalAmount")
        self.__class__.payment_id = payment_id

    def test_get_payment_details(self, tmf):
        """GET payment has correct amount."""
        data, _ = tmf.get("payment", "payment", self.payment_id)
        assert_tmf_resource(data)
        amount = data.get("totalAmount", {})
        assert amount.get("value") == 59.99 or str(amount.get("value")) == "59.99"

    def test_create_customer_bill(self, tmf, billing_setup):
        """POST customer bill."""
        data, _ = tmf.create("customer_bill", "customerBill", {
            "name": "Bill-2026-04",
            "billingAccount": {"id": billing_setup["account_id"]},
            "state": "new",
        })
        bill_id = assert_tmf_resource(data)
        self.__class__.bill_id = bill_id

    def test_list_payments(self, tmf):
        """GET payments returns at least 1."""
        data, _ = tmf.list("payment", "payment")
        assert isinstance(data, list)
        assert len(data) >= 1
