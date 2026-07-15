"""
Feature: Product variants — same spec, different characteristic values
(e.g., FIBER_200M vs FIBER_600M vs FIBER_1G share "Internet Fiber" spec).
"""
import uuid
import pytest


def _seed_spec_with_characteristics(tmf, name):
    """Create a productSpecification with a productSpecCharacteristic."""
    characteristic = [{
        "@type": "ProductSpecCharacteristic",
        "name": "downlinkSpeed",
        "valueType": "string",
        "productSpecCharacteristicValue": [{"value": "200Mbps", "isDefault": True}],
    }]
    r = tmf.post("/tmf-api/productCatalogManagement/v5/productSpecification", json={
        "@type": "ProductSpecification",
        "name": name,
        "lifecycleStatus": "Active",
        "productSpecCharacteristic": characteristic,
    })
    assert r.status_code == 201, f"Could not create spec: {r.text}"
    return r.json()


def _seed_offering(tmf, name, spec_id):
    r = tmf.post("/tmf-api/productCatalogManagement/v5/productOffering", json={
        "@type": "ProductOffering",
        "name": name,
        "lifecycleStatus": "Active",
        "productSpecification": {"id": spec_id},
    })
    assert r.status_code == 201, f"Could not create offering: {r.text}"
    return r.json()


def _place_order(tmf, party_id, offering_id):
    r = tmf.post("/tmf-api/productOrderingManagement/v5/productOrder", json={
        "@type": "ProductOrder",
        "relatedParty": [{"@type": "RelatedParty", "id": party_id, "role": "Customer"}],
        "productOrderItem": [{
            "@type": "ProductOrderItem",
            "id": "1",
            "quantity": 1,
            "action": "add",
            "productOffering": {"id": offering_id},
        }],
    })
    if r.status_code == 201:
        order_id = r.json().get("id")
        # Confirm the order so action_confirm() runs and services are created
        tmf.patch(
            f"/tmf-api/productOrderingManagement/v5/productOrder/{order_id}",
            json={"state": "inProgress"},
        )
    return r


@pytest.mark.variants
class TestProductVariants:

    def test_filter_offerings_by_characteristic_value(self, tmf):
        """Characteristic-based query should at least return 200 without crashing."""
        r = tmf.get(
            "/tmf-api/productCatalogManagement/v5/productOffering"
            "?productSpecCharacteristic.downlinkSpeed=600Mbps"
        )
        assert r.status_code == 200

    def test_ordering_variant_sets_service_characteristic(self, tmf, created_party):
        name = f"FIBER-{uuid.uuid4().hex[:6]}"
        spec = _seed_spec_with_characteristics(tmf, f"Spec-{name}")
        spec_id = spec["id"]
        offering = _seed_offering(tmf, name, spec_id)

        r = _place_order(tmf, created_party["id"], offering["id"])
        assert r.status_code == 201, f"Order failed: {r.text}"

        party_id = created_party["id"]
        # Fetch all services for this party so we don't miss the new one
        r2 = tmf.get(
            f"/tmf-api/serviceInventoryManagement/v5/service"
            f"?relatedParty.id={party_id}&limit=100"
        )
        assert r2.status_code == 200
        services = r2.json()

        matching = [
            s for s in services
            if spec_id and (s.get("serviceSpecification") or {}).get("id") == spec_id
        ]

        assert matching, (
            f"No service found with serviceSpecification.id={spec_id!r}. "
            f"Total services for party: {len(services)}. "
            f"Spec IDs seen: {list({(s.get('serviceSpecification') or {}).get('id') for s in services})}"
        )

        svc = matching[0]
        assert "serviceCharacteristic" in svc, (
            f"Service {svc.get('id')} missing serviceCharacteristic after ordering variant offering. "
            f"Full service: {svc}"
        )
        char_names = [c.get("name") for c in svc["serviceCharacteristic"]]
        assert "downlinkSpeed" in char_names, (
            f"Expected 'downlinkSpeed' characteristic, got {char_names}"
        )
