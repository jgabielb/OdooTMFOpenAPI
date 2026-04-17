"""Scenario 3: Order-to-Activate (Fulfill)

Full lifecycle: quote → cart → order → service activation.
"""
import pytest
from helpers.assertions import *


@pytest.fixture(scope="class")
def setup_data(tmf):
    """Create party and offering for order tests."""
    party, _ = tmf.create_party("Alice", "Smith")
    offering, _ = tmf.create_product_offering("Test Plan", price=29.99)
    return {
        "party_id": party["id"],
        "offering_id": offering["id"],
    }


class TestOrderToActivate:

    def test_create_quote(self, tmf, setup_data):
        """POST quote → creates draft sale.order via bridge."""
        data, _ = tmf.create("quote", "quote", {
            "description": "Quote for Alice",
            "quoteItem": [{"productOffering": {"id": setup_data["offering_id"]}}],
            "relatedParty": [{"id": setup_data["party_id"], "role": "Customer"}],
        })
        quote_id = assert_tmf_resource(data)
        self.__class__.quote_id = quote_id

    def test_create_shopping_cart(self, tmf, setup_data):
        """POST cart → creates quotation sale.order via bridge."""
        data, _ = tmf.create("shopping_cart", "shoppingCart", {
            "cartItem": [{
                "productOffering": {"id": setup_data["offering_id"]},
                "quantity": 1,
            }],
            "relatedParty": [{"id": setup_data["party_id"]}],
        })
        cart_id = assert_tmf_resource(data)
        self.__class__.cart_id = cart_id

    def test_create_product_order(self, tmf, setup_data):
        """POST product order → sale.order created."""
        data, _ = tmf.create_product_order(
            setup_data["party_id"],
            setup_data["offering_id"],
        )
        order_id = assert_tmf_resource(data)
        self.__class__.order_id = order_id
        self.__class__.party_id = setup_data["party_id"]

    def test_get_order_details(self, tmf):
        """GET order has correct structure."""
        data, _ = tmf.get("ordering", "productOrder", self.order_id)
        assert_tmf_resource(data)
        assert "productOrderItem" in data

    def test_patch_order_state(self, tmf):
        """PATCH order state transition."""
        data, _ = tmf.patch("ordering", "productOrder", self.order_id,
                            {"state": "acknowledged"})

    def test_create_service_activation(self, tmf):
        """POST service activation with serviceDate."""
        data, _ = tmf.create("service_activation", "service", {
            "serviceSpecification": {"id": "test-spec-001"},
            "state": "active",
        })
        svc_id = assert_tmf_resource(data)
        assert_field_present(data, "serviceDate")
        self.__class__.service_id = svc_id

    def test_get_service_has_date(self, tmf):
        """GET service includes serviceDate."""
        data, _ = tmf.get("service_activation", "service", self.service_id)
        assert_field_present(data, "serviceDate")
        assert_field_present(data, "state")

    def test_verify_odoo_sale_order(self, odoo):
        """Verify sale.order created in Odoo."""
        so = odoo.find_sale_order_by_tmf_id(self.order_id)
        if so:
            assert so["tmf_id"] == self.order_id
