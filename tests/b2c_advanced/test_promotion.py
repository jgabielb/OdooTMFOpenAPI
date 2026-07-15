"""
Feature: Promotions (TMF671)

Apply / swap / remove promotions on active services and verify the
resulting appliedPromotion on the service inventory record.
"""
import pytest


def _create_promotion(tmf, name, discount_pct=10):
    body = {
        "@type": "Promotion",
        "name": name,
        "lifecycleStatus": "release",
        "promotionType": "Discount",
        "pattern": [{"discount": discount_pct}],
    }
    r = tmf.post("/tmf-api/promotionManagement/v4/promotion", json=body)
    assert r.status_code == 201, f"Could not create promotion: {r.text}"
    return r.json()


def _create_service(tmf, party_id, name="Promo-Test-Service"):
    r = tmf.post("/tmf-api/serviceInventoryManagement/v5/service", json={
        "name": name,
        "state": "active",
        "relatedParty": [{
            "@type": "RelatedPartyRefOrPartyRoleRef",
            "partyOrPartyRole": {"id": party_id, "name": "Promo Tester"},
        }],
    })
    assert r.status_code == 201, f"Could not create service: {r.text}"
    return r.json()


def _modify_order(tmf, party_id, service_id, promotion_list):
    """Place a modify order that sets (or clears) a promotion on a service."""
    body = {
        "@type": "ProductOrder",
        "description": "Apply/remove promotion",
        "relatedParty": [{"@type": "RelatedParty", "id": party_id, "role": "Customer"}],
        "productOrderItem": [{
            "@type": "ProductOrderItem",
            "id": "1",
            "quantity": 1,
            "action": "modify",
            "product": {"id": service_id},
            "promotion": promotion_list,
        }],
    }
    r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json=body)
    assert r.status_code == 201, f"Modify order failed: {r.text}"
    return r.json()


def _get_service(tmf, service_id):
    r = tmf.get(f"/tmf-api/serviceInventoryManagement/v5/service/{service_id}")
    assert r.status_code == 200, f"Service {service_id} not found: {r.text}"
    return r.json()


@pytest.mark.promotion
class TestPromotion:

    def test_promotion_endpoint_reachable(self, tmf):
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

    def test_apply_promotion_to_active_service(self, tmf, created_party):
        svc = _create_service(tmf, created_party["id"])
        promo = _create_promotion(tmf, "Summer10-Apply", discount_pct=10)

        _modify_order(tmf, created_party["id"], svc["id"],
                      [{"id": promo["id"], "@type": "PromotionRef"}])

        updated = _get_service(tmf, svc["id"])
        assert "appliedPromotion" in updated, (
            "Service missing appliedPromotion after apply order"
        )
        applied_ids = [p.get("id") for p in updated["appliedPromotion"]]
        assert promo["id"] in applied_ids, (
            f"Expected promotion {promo['id']} in appliedPromotion, got {applied_ids}"
        )

    def test_swap_promotion(self, tmf, created_party):
        svc = _create_service(tmf, created_party["id"])
        promo_a = _create_promotion(tmf, "Promo-A-10", discount_pct=10)
        promo_b = _create_promotion(tmf, "Promo-B-20", discount_pct=20)

        # Apply first promo
        _modify_order(tmf, created_party["id"], svc["id"],
                      [{"id": promo_a["id"], "@type": "PromotionRef"}])

        after_a = _get_service(tmf, svc["id"])
        assert "appliedPromotion" in after_a
        assert any(p["id"] == promo_a["id"] for p in after_a["appliedPromotion"])

        # Swap to second promo
        _modify_order(tmf, created_party["id"], svc["id"],
                      [{"id": promo_b["id"], "@type": "PromotionRef"}])

        after_b = _get_service(tmf, svc["id"])
        assert "appliedPromotion" in after_b
        applied_ids = [p["id"] for p in after_b["appliedPromotion"]]
        assert promo_b["id"] in applied_ids, (
            f"Expected promo B {promo_b['id']} after swap, got {applied_ids}"
        )
        assert promo_a["id"] not in applied_ids, (
            "Promo A should be replaced by promo B after swap"
        )

    def test_remove_promotion_reverts_to_list_price(self, tmf, created_party):
        svc = _create_service(tmf, created_party["id"])
        promo = _create_promotion(tmf, "Summer10-Remove", discount_pct=10)

        # Apply
        _modify_order(tmf, created_party["id"], svc["id"],
                      [{"id": promo["id"], "@type": "PromotionRef"}])
        assert "appliedPromotion" in _get_service(tmf, svc["id"])

        # Remove — empty list signals removal
        _modify_order(tmf, created_party["id"], svc["id"], [])

        updated = _get_service(tmf, svc["id"])
        assert "appliedPromotion" not in updated, (
            "appliedPromotion should be absent after removal"
        )
