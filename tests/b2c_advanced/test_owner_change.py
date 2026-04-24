"""
Feature: Account ownership transfer

One partner transfers an account to another partner. Services must
continue uninterrupted; past debts stay with the previous owner.
"""
import pytest


@pytest.mark.owner_change
class TestOwnerChange:

    @pytest.mark.xfail(reason="Account.partner_id transfer endpoint not implemented")
    def test_transfer_keeps_services_active(self, tmf):
        pytest.xfail("owner-change pending")

    @pytest.mark.xfail(reason="Outstanding-balance retention logic not implemented")
    def test_outstanding_balance_stays_with_previous_owner(self, tmf):
        pytest.xfail("balance retention pending")
