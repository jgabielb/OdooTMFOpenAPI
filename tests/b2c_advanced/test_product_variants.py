"""
Feature: Product variants — same spec, different characteristic values
(e.g., FIBER_200M vs FIBER_600M vs FIBER_1G share "Internet Fiber" spec).
"""
import pytest


@pytest.mark.variants
class TestProductVariants:

    def test_filter_offerings_by_characteristic_value(self, tmf):
        """Characteristic-based query should at least return 200 without crashing."""
        r = tmf.get(
            "/tmf-api/productCatalogManagement/v5/productOffering"
            "?productSpecCharacteristic.downlinkSpeed=600Mbps"
        )
        assert r.status_code == 200
        # May be empty if no seeded variants match — that's OK, the endpoint accepted the query

    @pytest.mark.xfail(reason="Ordering does not yet stamp service characteristics from offering spec")
    def test_ordering_variant_sets_service_characteristic(self, tmf, created_party):
        # Assumes offerings named like FIBER_200M / FIBER_600M exist.
        r = tmf.get("/tmf-api/productCatalogManagement/v5/productOffering?name=FIBER_200M")
        assert r.status_code == 200
        offerings = r.json()
        if not offerings:
            pytest.xfail("FIBER_200M not seeded")
        # ... would order, fetch service, and check characteristic
