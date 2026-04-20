"""Lightweight TMF API client for integration tests."""
import json
import requests
import uuid


class TMFClient:
    """Wrapper around requests for TMF Open API calls."""

    def __init__(self, base_url="http://localhost:8069"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self._created = []

    # -- API base paths --
    APIS = {
        "party": "/tmf-api/partyManagement/v5",
        "customer": "/tmf-api/customerManagement/v5",
        "account": "/tmf-api/accountManagement/v4",
        "catalog": "/tmf-api/productCatalogManagement/v5",
        "ordering": "/tmf-api/productOrderingManagement/v5",
        "service_inventory": "/tmf-api/serviceInventoryManagement/v5",
        "resource_inventory": "/tmf-api/resourceInventoryManagement/v4",
        "billing": "/tmf-api/accountManagement/v4",
        "customer_bill": "/tmf-api/customerBillManagement/v4",
        "payment": "/tmf-api/paymentManagement/v4",
        "trouble_ticket": "/tmf-api/troubleTicketManagement/v5",
        "incident": "/tmf-api/Incident/v4",
        "work": "/tmf-api/workManagement/v4",
        "appointment": "/tmf-api/appointmentManagement/v4",
        "alarm": "/tmf-api/alarmManagement/v5",
        "agreement": "/tmf-api/agreementManagement/v4",
        "document": "/tmf-api/document/v4",
        "communication": "/tmf-api/communicationManagement/v4",
        "geographic_address": "/tmf-api/geographicAddressManagement/v4",
        "geographic_site": "/tmf-api/geographicSiteManagement/v4",
        "quote": "/tmf-api/quoteManagement/v4",
        "shopping_cart": "/tmf-api/shoppingCartManagement/v5",
        "shipping_order": "/tmf-api/shippingOrder/v4.0",
        "shipment": "/tmf-api/shipmentManagement/v4",
        "promotion": "/tmf-api/promotionManagement/v4",
        "usage": "/tmf-api/usageManagement/v4",
        "service_catalog": "/tmf-api/serviceCatalogManagement/v4",
        "resource_catalog": "/tmf-api/resourceCatalogManagement/v5",
        "resource_order": "/tmf-api/resourceOrdering/v4",
        "service_order": "/tmf-api/serviceOrdering/v4",
        "service_activation": "/tmf-api/ServiceActivationAndConfiguration/v4",
        "party_interaction": "/tmf-api/partyInteractionManagement/v5",
    }

    def url(self, api_name, resource, rid=None):
        base = self.APIS.get(api_name, api_name)
        path = f"{self.base_url}{base}/{resource}"
        if rid:
            path = f"{path}/{rid}"
        return path

    # -- Helpers --

    @staticmethod
    def _parse_json(resp):
        if not resp.content:
            return {}
        try:
            return resp.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            return {}

    # -- CRUD --

    def create(self, api_name, resource, body, expected_status=201):
        url = self.url(api_name, resource)
        resp = self.session.post(url, json=body)
        if expected_status:
            assert resp.status_code == expected_status, (
                f"POST {url} → {resp.status_code}: {resp.text[:500]}"
            )
        data = self._parse_json(resp)
        if isinstance(data, dict) and "id" in data:
            self._created.append((api_name, resource, data["id"]))
        return data, resp

    def get(self, api_name, resource, rid=None, params=None, expected_status=200):
        url = self.url(api_name, resource, rid)
        resp = self.session.get(url, params=params)
        if expected_status:
            assert resp.status_code == expected_status, (
                f"GET {url} → {resp.status_code}: {resp.text[:500]}"
            )
        return self._parse_json(resp), resp

    def patch(self, api_name, resource, rid, body, expected_status=200):
        url = self.url(api_name, resource, rid)
        resp = self.session.patch(url, json=body)
        if expected_status:
            assert resp.status_code == expected_status, (
                f"PATCH {url} → {resp.status_code}: {resp.text[:500]}"
            )
        return self._parse_json(resp), resp

    def delete(self, api_name, resource, rid, expected_status=204):
        url = self.url(api_name, resource, rid)
        resp = self.session.delete(url)
        if expected_status:
            assert resp.status_code == expected_status, (
                f"DELETE {url} → {resp.status_code}: {resp.text[:500]}"
            )
        return resp

    def list(self, api_name, resource, params=None, expected_status=200):
        return self.get(api_name, resource, params=params, expected_status=expected_status)

    # -- Cleanup --

    def cleanup(self):
        """Delete all created records in reverse order."""
        for api_name, resource, rid in reversed(self._created):
            try:
                self.delete(api_name, resource, rid, expected_status=None)
            except Exception:
                pass
        self._created.clear()

    # -- Convenience shortcuts --

    def create_party(self, given_name, family_name, **extra):
        body = {
            "givenName": given_name,
            "familyName": family_name,
            "@type": "Individual",
            **extra,
        }
        return self.create("party", "individual", body)

    def create_organization(self, name, **extra):
        body = {"tradingName": name, "@type": "Organization", **extra}
        return self.create("party", "organization", body)

    def create_billing_account(self, name, party_id, **extra):
        body = {
            "name": name,
            "relatedParty": [{"id": party_id, "role": "Customer", "@type": "RelatedParty"}],
            **extra,
        }
        return self.create("account", "billingAccount", body)

    def create_product_offering(self, name, spec_id=None, price=None, **extra):
        body = {"name": name, "lifecycleStatus": "Active", **extra}
        if spec_id:
            body["productSpecification"] = {"id": spec_id}
        if price:
            body["productOfferingPrice"] = [{
                "name": "Price",
                "priceType": "recurring",
                "price": {"amount": price, "units": "USD"},
            }]
        return self.create("catalog", "productOffering", body)

    def create_product_order(self, party_id, offering_id, **extra):
        body = {
            "productOrderItem": [{
                "action": "add",
                "productOffering": {"id": offering_id},
            }],
            "relatedParty": [{"id": party_id, "role": "Customer"}],
            **extra,
        }
        return self.create("ordering", "productOrder", body)

    def create_trouble_ticket(self, description, party_id=None, **extra):
        body = {"description": description, **extra}
        if party_id:
            body["relatedParty"] = [{"id": party_id, "role": "Customer"}]
        return self.create("trouble_ticket", "troubleTicket", body)

    def create_payment(self, amount, account_id, currency="USD", **extra):
        body = {
            "description": extra.pop("description", "Payment"),
            "totalAmount": {"unit": currency, "value": amount},
            "account": {"id": account_id, "@referredType": "BillingAccount"},
            "paymentMethod": {"name": "Credit Card"},
            **extra,
        }
        return self.create("payment", "payment", body)
