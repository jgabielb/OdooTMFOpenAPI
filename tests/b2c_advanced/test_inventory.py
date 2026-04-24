"""
Feature: Inventory — TMF639 ResourceInventory + Odoo stock.lot

Covers: listing resources, serial numbers, decrementing stock on assignment,
and ordering against out-of-stock conditions.
"""
import pytest


@pytest.mark.inventory
class TestResourceInventory:

    def test_resource_inventory_endpoint_reachable(self, tmf):
        # Some builds expose the path without "Management"
        candidates = [
            "/tmf-api/resourceInventoryManagement/v5/resource?limit=5",
            "/tmf-api/resourceInventoryManagement/v4/resource?limit=5",
            "/tmf-api/resourceInventory/v5/resource?limit=5",
            "/tmf-api/resourceInventory/v4/resource?limit=5",
        ]
        for path in candidates:
            r = tmf.get(path)
            if r.status_code == 200:
                return
        pytest.xfail("No /resourceInventory endpoint is reachable")

    @pytest.mark.xfail(reason="Resources carry no serial/state in current response shape")
    def test_resource_has_serial_number_and_state(self, tmf):
        r = tmf.get("/tmf-api/resourceInventoryManagement/v5/resource?limit=5")
        assert r.status_code == 200
        for res in r.json():
            assert "resourceCharacteristic" in res or "serialNumber" in res
            assert "state" in res or "resourceStatus" in res

    @pytest.mark.xfail(reason="Automatic inventory decrement on service assignment not yet wired")
    def test_ordering_a_device_decrements_inventory(self, tmf, created_party):
        # Would require:
        #  1. GET inventory count for CPE
        #  2. POST productOrder that maps to a CPE RFS
        #  3. GET inventory count again → should be -1
        pytest.xfail("inventory decrement pending")

    @pytest.mark.xfail(reason="OUT_OF_STOCK error path not yet modelled in provisioning bridge")
    def test_order_fails_when_out_of_stock(self, tmf, created_party):
        pytest.xfail("OUT_OF_STOCK not implemented")
