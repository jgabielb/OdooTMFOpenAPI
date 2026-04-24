"""
Feature: Plan change — upgrade / downgrade / modify

Covers in-life plan modifications: the service identity (tmf_id) must be
preserved across a plan change, billing must prorate, and contract
commitments must block downgrades while active.
"""
import pytest

from conftest import product_order_body


@pytest.mark.plan_change
class TestPlanChange:

    @pytest.mark.xfail(reason="ProductOrderItem.action='modify' handling not implemented")
    def test_upgrade_preserves_service_identity(self, tmf, active_service_for_party,
                                                two_distinct_offerings):
        old_off, new_off = two_distinct_offerings
        # Modify order targeting the upgrade
        body = product_order_body(
            active_service_for_party["party_id"],
            new_off["id"],
            description="Upgrade plan",
            action="modify",
        )
        r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json=body)
        assert r.status_code == 201
        # After completion, original service tmf_id must persist. Endpoint to
        # verify this is not implemented yet.
        pytest.xfail("post-modify service identity check pending")

    @pytest.mark.xfail(reason="Contract commitment term not modeled")
    def test_downgrade_blocked_during_commitment(self, tmf):
        pytest.xfail("commitment terms not modeled")

    @pytest.mark.xfail(reason="Proration not implemented in billing bridge")
    def test_plan_change_prorates_current_cycle(self, tmf):
        pytest.xfail("proration pending")
