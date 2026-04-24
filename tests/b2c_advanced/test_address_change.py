"""
Feature: Service address change (relocation)

The customer keeps the same service (same tmf_id) but the physical
installation moves. Feasibility at the new address must be approved
before the change is accepted.
"""
import pytest


@pytest.mark.address_change
class TestAddressChange:

    @pytest.mark.xfail(reason="Service.place modify action not yet defined")
    def test_relocate_service_with_approved_feasibility(self, tmf):
        pytest.xfail("relocation pending")

    @pytest.mark.xfail(reason="Feasibility-gated relocation not implemented")
    def test_relocation_blocked_when_feasibility_denied(self, tmf):
        pytest.xfail("feasibility gate pending")
