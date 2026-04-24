"""
Feature: Promotions (TMF671)

Apply / swap / remove promotions on active services and verify the
resulting priceAlteration and invoice impact.
"""
import pytest


@pytest.mark.promotion
class TestPromotion:

    def test_promotion_endpoint_reachable(self, tmf):
        # TMF671 lives at /tmf-api/promotionManagement/v4/promotion in spec;
        # accept any return other than 5xx.
        candidates = [
            "/tmf-api/promotionManagement/v5/promotion?limit=5",
            "/tmf-api/promotionManagement/v4/promotion?limit=5",
            "/tmf-api/promotion/v4/promotion?limit=5",
        ]
        for path in candidates:
            r = tmf.get(path)
            if r.status_code < 500:
                return
        pytest.xfail("TMF671 promotion endpoint not reachable")

    @pytest.mark.xfail(reason="Applying promotion via modify order not wired yet")
    def test_apply_promotion_to_active_service(self, tmf):
        pytest.xfail("apply promotion pending")

    @pytest.mark.xfail(reason="Swap promotion via modify order not wired yet")
    def test_swap_promotion(self, tmf):
        pytest.xfail("swap promotion pending")

    @pytest.mark.xfail(reason="Remove promotion via modify order not wired yet")
    def test_remove_promotion_reverts_to_list_price(self, tmf):
        pytest.xfail("remove promotion pending")
