"""
Feature: Plan change — upgrade / downgrade / modify

Covers in-life plan modifications: the service identity (tmf_id) must be
preserved across a plan change, billing must prorate, and contract
commitments must block downgrades while active.
"""
import pytest


@pytest.mark.plan_change
class TestPlanChange:

    def test_upgrade_preserves_service_identity(self, tmf, created_party,
                                                two_distinct_offerings):
        old_off, new_off = two_distinct_offerings

        # Stand up a service to act as the target of the modify order.
        r_svc = tmf.post("/tmf-api/serviceInventoryManagement/v5/service", json={
            "name": "Plan-Change-Target",
            "state": "active",
            "relatedParty": [{
                "@type": "RelatedPartyRefOrPartyRoleRef",
                "partyOrPartyRole": {"id": created_party["id"], "name": "Plan Tester"},
            }],
        })
        assert r_svc.status_code == 201, r_svc.text
        service_id = r_svc.json()["id"]

        # Place a modify order targeting that service with the new offering.
        body = {
            "@type": "ProductOrder",
            "description": "Upgrade plan",
            "relatedParty": [{
                "@type": "RelatedParty",
                "id": created_party["id"],
                "role": "Customer",
            }],
            "productOrderItem": [{
                "@type": "ProductOrderItem",
                "id": "1",
                "quantity": 1,
                "action": "modify",
                "productOffering": {"id": new_off["id"]},
                "product": {"id": service_id},
            }],
        }
        r_order = tmf.post(
            "/tmf-api/productOrderingManagement/v5/productOrder", json=body
        )
        assert r_order.status_code == 201, r_order.text

        # The service must still exist under its original tmf_id — identity preserved.
        r_check = tmf.get(
            f"/tmf-api/serviceInventoryManagement/v5/service/{service_id}"
        )
        assert r_check.status_code == 200, (
            f"Service {service_id} not found after modify order — identity lost"
        )

    @pytest.mark.xfail(reason="Contract commitment term not modeled")
    def test_downgrade_blocked_during_commitment(self, tmf):
        pytest.xfail("commitment terms not modeled")

    @pytest.mark.xfail(reason="Proration not implemented in billing bridge")
    def test_plan_change_prorates_current_cycle(self, tmf):
        pytest.xfail("proration pending")
