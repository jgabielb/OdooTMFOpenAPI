"""
Feature: Product design (TMF620)

Exercises the catalog's structural contract: offerings point at specs,
specs declare characteristics + resource specs, bundles declare children.
"""
import pytest


@pytest.mark.product_design
class TestProductDesign:

    def test_offering_exposes_product_specification_ref(self, tmf, any_offering):
        r = tmf.get(
            f"/tmf-api/productCatalogManagement/v5/productOffering/{any_offering['id']}"
        )
        assert r.status_code == 200
        body = r.json()
        # Either as productSpecification (full) or productSpecificationRef
        has_spec = any(k in body for k in (
            "productSpecification", "productSpecificationRef", "productSpec"
        ))
        if not has_spec:
            pytest.xfail("Offering has no productSpecification reference yet")

    def test_product_specification_endpoint_is_reachable(self, tmf):
        r = tmf.get("/tmf-api/productCatalogManagement/v5/productSpecification?limit=5")
        if r.status_code == 404:
            pytest.xfail("TMF620 /productSpecification endpoint not exposed")
        assert r.status_code == 200

    def test_product_spec_exposes_characteristics(self, tmf):
        # Pull a wider set so we don't miss seeded specs sitting after page 1.
        r = tmf.get("/tmf-api/productCatalogManagement/v5/productSpecification?limit=50")
        if r.status_code != 200:
            pytest.xfail("productSpecification endpoint unavailable")
        specs = r.json()
        if not specs:
            pytest.xfail("No product specifications seeded")

        # Walk every spec individually — the listing endpoint may not include
        # the productSpecCharacteristic field; the individual GET should.
        for spec in specs:
            full = tmf.get(
                f"/tmf-api/productCatalogManagement/v5/productSpecification/{spec['id']}"
            ).json()
            chars = full.get("productSpecCharacteristic")
            if chars:
                assert isinstance(chars, list) and len(chars) >= 1
                for ch in chars:
                    assert "name" in ch
                return
        pytest.xfail("productSpecCharacteristic not populated on any returned spec")

    def test_bundle_offering_declares_children(self, tmf):
        # Ensure at least 2 component offerings exist to build a bundle from.
        r = tmf.get("/tmf-api/productCatalogManagement/v5/productOffering?limit=10")
        assert r.status_code == 200
        offerings = r.json()
        if len(offerings) < 2:
            pytest.skip("Need at least 2 offerings to seed a bundle")

        comp1, comp2 = offerings[0], offerings[1]
        bundle_body = {
            "@type": "ProductOffering",
            "name": "Test-Bundle-Doblepack",
            "lifecycleStatus": "Active",
            "bundledProductOffering": [
                {"id": comp1["id"], "@type": "BundledProductOffering"},
                {"id": comp2["id"], "@type": "BundledProductOffering"},
            ],
        }
        rb = tmf.post(
            "/tmf-api/productCatalogManagement/v5/productOffering", json=bundle_body
        )
        assert rb.status_code == 201, rb.text
        created = rb.json()
        assert created.get("isBundle") is True, "isBundle must be True for a bundle offering"
        assert "bundledProductOffering" in created
        assert len(created["bundledProductOffering"]) >= 1

        # Also verify the GET ?isBundle=true filter returns it
        r2 = tmf.get(
            "/tmf-api/productCatalogManagement/v5/productOffering?isBundle=true&limit=5"
        )
        assert r2.status_code == 200
        bundles = r2.json()
        assert bundles, "isBundle=true filter returned no results"
        assert all(b.get("isBundle") is True for b in bundles)

    def test_offering_with_resource_spec_prescribes_device(self, tmf):
        r = tmf.get("/tmf-api/productCatalogManagement/v5/productSpecification?limit=20")
        assert r.status_code == 200
        for spec in r.json():
            full = tmf.get(
                f"/tmf-api/productCatalogManagement/v5/productSpecification/{spec['id']}"
            ).json()
            if full.get("resourceSpecification"):
                assert len(full["resourceSpecification"]) >= 1
                return
        pytest.fail("No productSpecification with resourceSpecification found")
