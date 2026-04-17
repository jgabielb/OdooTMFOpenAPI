"""Scenario 6: Resource & Shipment (Deliver)

Resource ordering, warehouse allocation, shipment tracking.
"""
import pytest
from helpers.assertions import *


class TestResourceShipment:

    def test_create_geographic_site(self, tmf):
        """POST geographic site → stock.warehouse via bridge."""
        data, _ = tmf.create("geographic_site", "geographicSite", {
            "name": "Warehouse East",
            "description": "Main distribution center",
        })
        site_id = assert_tmf_resource(data)
        self.__class__.site_id = site_id

    def test_create_geographic_address(self, tmf):
        """POST geographic address."""
        data, _ = tmf.create("geographic_address", "geographicAddress", {
            "streetName": "Main Street",
            "streetNr": "123",
            "city": "New York",
            "postcode": "10001",
            "country": "United States",
        })
        addr_id = assert_tmf_resource(data)
        self.__class__.addr_id = addr_id

    def test_create_resource_order(self, tmf):
        """POST resource order → purchase.order via bridge."""
        party, _ = tmf.create_party("Supplier", "Corp")
        data, _ = tmf.create("resource_order", "resourceOrder", {
            "description": "Order 5G SIM cards",
            "category": "SIM",
            "orderItem": [{
                "action": "add",
                "quantity": 100,
            }],
            "relatedParty": [{"id": party["id"], "role": "Supplier"}],
        })
        ro_id = assert_tmf_resource(data)
        self.__class__.resource_order_id = ro_id

    def test_create_shipment(self, tmf):
        """POST shipment → stock.picking via bridge."""
        data, _ = tmf.create("shipment", "shipment", {
            "name": "SHIP-001",
            "description": "SIM card shipment",
            "state": "acknowledged",
        })
        ship_id = assert_tmf_resource(data)
        self.__class__.shipment_id = ship_id

    def test_create_shipping_order(self, tmf):
        """POST shipping order."""
        data, _ = tmf.create("shipping_order", "shippingOrder", {
            "shippingOrderItem": [{"product": {"id": "sim-batch-001"}}],
            "expectedShippingStartDate": "2026-04-18",
        })
        so_id = assert_tmf_resource(data)
        self.__class__.shipping_order_id = so_id

    def test_update_shipment_state(self, tmf):
        """PATCH shipment to inTransit → delivered."""
        tmf.patch("shipment", "shipment", self.shipment_id,
                  {"state": "inTransit"})
        data, _ = tmf.patch("shipment", "shipment", self.shipment_id,
                            {"state": "delivered"})

    def test_get_address(self, tmf):
        """GET address has correct fields."""
        data, _ = tmf.get("geographic_address", "geographicAddress", self.addr_id)
        assert_field_present(data, "city")
        assert_field_value(data, "city", "New York")
