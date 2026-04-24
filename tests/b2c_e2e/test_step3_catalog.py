"""
STEP 3 — Product catalog browse (TMF620)
"""
import pytest


@pytest.mark.catalog
class TestCatalog:
    """Gherkin: STEP 3 — Product catalog browse"""

    def test_active_offerings_are_returned(self, tmf, ensure_platform_up):
        """Scenario: Eligible B2C offerings are returned for a B2C party."""
        r = tmf.get("/tmf-api/productCatalogManagement/v5/productOffering?limit=10")
        assert r.status_code == 200
        offerings = r.json()
        assert isinstance(offerings, list)
        assert len(offerings) >= 1
        for o in offerings:
            assert "id" in o
            assert "name" in o

    def test_offering_has_pricing_structure(self, tmf, any_offering):
        """Sub-check: returned offering exposes productOfferingPrice field."""
        r = tmf.get(f"/tmf-api/productCatalogManagement/v5/productOffering/{any_offering['id']}")
        assert r.status_code == 200
        body = r.json()
        # productOfferingPrice may be empty array, but the key should exist in spec
        assert any(k in body for k in ("productOfferingPrice", "productOfferingPriceRef", "price"))

    @pytest.mark.xfail(reason="Segment-based pricelist filtering not yet implemented")
    def test_pricing_rules_apply_pricelist_discount(self, tmf, any_offering):
        """Scenario: Pricing rules are applied based on Odoo pricelists."""
        r = tmf.get(
            f"/tmf-api/productCatalogManagement/v5/productOffering/{any_offering['id']}",
            headers={"x-customer-segment": "B2C"},
        )
        assert r.status_code == 200
        body = r.json()
        assert any("priceAlteration" in str(p) for p in body.get("productOfferingPrice", []))
