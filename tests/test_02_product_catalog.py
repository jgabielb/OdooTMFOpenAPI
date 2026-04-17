"""Scenario 2: Product Catalog Setup (Design)

Create specs, offerings, and promotions — verify Odoo product sync.
"""
import pytest
from helpers.assertions import *


class TestProductCatalog:

    def test_create_service_specification(self, tmf, odoo):
        """POST service spec → product.template(type=service) via bridge."""
        data, _ = tmf.create("service_catalog", "serviceSpecification", {
            "name": "Mobile Data Plan",
            "lifecycleStatus": "Active",
            "serviceSpecCharacteristic": [
                {"name": "dataAllowance", "valueType": "string"},
                {"name": "speed", "valueType": "string"},
            ],
        })
        spec_id = assert_tmf_resource(data)
        assert_field_value(data, "name", "Mobile Data Plan")
        self.__class__.service_spec_id = spec_id

    def test_create_resource_specification(self, tmf):
        """POST resource spec → product.template(type=consu) via bridge."""
        data, _ = tmf.create("resource_catalog", "resourceSpecification", {
            "name": "5G SIM Card",
            "lifecycleStatus": "Active",
        })
        spec_id = assert_tmf_resource(data)
        self.__class__.resource_spec_id = spec_id

    def test_create_product_offering(self, tmf):
        """POST product offering with price."""
        data, _ = tmf.create_product_offering(
            "5G Unlimited Plan",
            price=49.99,
        )
        offering_id = assert_tmf_resource(data)
        assert_field_value(data, "name", "5G Unlimited Plan")
        self.__class__.offering_id = offering_id

    def test_create_promotion(self, tmf):
        """POST promotion → product.pricelist via bridge."""
        data, _ = tmf.create("promotion", "promotion", {
            "name": "First Month Free",
            "lifecycleStatus": "Active",
            "pattern": [{"action": {"actionType": "discount"}}],
        })
        promo_id = assert_tmf_resource(data)
        self.__class__.promo_id = promo_id

    def test_list_active_offerings(self, tmf):
        """GET offerings filtered by lifecycleStatus."""
        data, resp = tmf.list("catalog", "productOffering",
                              params={"lifecycleStatus": "Active"})
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_offering_has_price(self, tmf):
        """GET offering by ID has price details."""
        data, _ = tmf.get("catalog", "productOffering", self.offering_id)
        assert_tmf_resource(data)
        prices = data.get("productOfferingPrice", [])
        assert len(prices) >= 1, "No price on offering"

    def test_field_selection(self, tmf):
        """GET with ?fields= returns only requested + mandatory."""
        data, _ = tmf.get("catalog", "productOffering", self.offering_id,
                          params={"fields": "name"})
        assert "name" in data
        assert "id" in data
        assert "href" in data

    def test_patch_offering(self, tmf):
        """PATCH offering name."""
        data, _ = tmf.patch("catalog", "productOffering", self.offering_id,
                            {"name": "5G Unlimited Pro"})
        assert_field_value(data, "name", "5G Unlimited Pro")

    def test_offering_not_found(self, tmf):
        """GET non-existent offering → 404."""
        tmf.get("catalog", "productOffering", "nonexistent-uuid-12345",
                expected_status=404)
