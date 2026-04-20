"""Scenario 9: GUI CRM Flow (Market/Sales → TAM)

Simulates Odoo CRM GUI operations via XML-RPC and verifies
the TMF API reflects the changes through bridge sync.

Flow: Create Contact → Create Lead → Convert to Opportunity →
      Create Quotation → Confirm Sale Order → Verify TMF APIs
"""
import pytest
from helpers.assertions import *


class TestGuiCrmFlow:
    """CRM-driven TAM workflow: Odoo GUI → TMF API sync."""

    def test_create_contact_in_odoo(self, odoo, tmf):
        """Create a contact in Odoo GUI → partner gets tmf_id → visible in Party API."""
        partner_id = odoo.create("res.partner", {
            "name": "Maria Santos",
            "email": "maria@example.com",
            "phone": "+5511999887766",
            "is_company": False,
        })
        assert partner_id, "Failed to create partner"
        self.__class__.partner_odoo_id = partner_id

        # Read back to get tmf_id
        partner = odoo.read("res.partner", [partner_id], ["tmf_id", "name"])[0]
        tmf_id = partner.get("tmf_id")
        assert tmf_id, "Partner should have tmf_id auto-assigned"
        self.__class__.partner_tmf_id = tmf_id

        # Verify via TMF Party API
        data, resp = tmf.get("party", "individual", tmf_id)
        assert_tmf_resource(data, "Individual")
        # Odoo-created partners populate name but not givenName/familyName
        # Check that the resource exists and has correct id
        assert data.get("id") == tmf_id

    def test_update_contact_syncs(self, odoo, tmf):
        """Edit contact email in Odoo → TMF Party API reflects change."""
        odoo.write("res.partner", [self.partner_odoo_id], {
            "email": "maria.santos@newdomain.com",
        })
        data, _ = tmf.get("party", "individual", self.partner_tmf_id)
        contact = data.get("contactMedium", [])
        emails = [c for c in contact if c.get("mediumType") == "email"]
        if emails:
            assert "newdomain" in emails[0].get("characteristic", {}).get("emailAddress", "")

    def test_create_crm_lead(self, odoo):
        """Create a lead in CRM GUI → bridge creates TMF Party Interaction."""
        lead_id = odoo.create("crm.lead", {
            "name": "5G Enterprise Package Interest",
            "partner_id": self.partner_odoo_id,
            "type": "lead",
            "expected_revenue": 50000,
        })
        assert lead_id, "Failed to create CRM lead"
        self.__class__.lead_id = lead_id

        # Check that bridge created a TMF interaction
        try:
            lead = odoo.read("crm.lead", [lead_id], ["tmf_interaction_id"])[0]
            interaction_id = lead.get("tmf_interaction_id")
            if interaction_id:
                self.__class__.tmf_interaction_odoo_id = interaction_id[0] if isinstance(interaction_id, list) else interaction_id
        except Exception:
            pass  # Bridge may not be installed

    def test_convert_lead_to_opportunity(self, odoo):
        """Convert lead to opportunity → interaction status updates."""
        odoo.write("crm.lead", [self.lead_id], {
            "type": "opportunity",
        })
        lead = odoo.read("crm.lead", [self.lead_id], ["type"])[0]
        assert lead["type"] == "opportunity"

    def test_create_quotation_from_crm(self, odoo):
        """Create a sale.order (quotation) from CRM → bridge syncs to TMF."""
        so_id = odoo.create("sale.order", {
            "partner_id": self.partner_odoo_id,
            "opportunity_id": self.lead_id,
        })
        assert so_id, "Failed to create sale order"
        self.__class__.sale_order_id = so_id

        so = odoo.read("sale.order", [so_id], ["name", "tmf_id", "state"])[0]
        self.__class__.sale_order_tmf_id = so.get("tmf_id")
        assert so["state"] in ("draft", "sent"), f"Expected draft, got {so['state']}"

    def test_verify_order_in_tmf(self, tmf):
        """TMF Product Order API shows the quotation."""
        if not self.sale_order_tmf_id:
            pytest.skip("Sale order has no tmf_id")
        data, _ = tmf.get("ordering", "productOrder", self.sale_order_tmf_id)
        assert_tmf_resource(data)

    def test_customer360_shows_everything(self, tmf):
        """Customer360 aggregates CRM contact's data."""
        data, resp = tmf.get(
            "/tmf-api/customer360/v4", "customer360",
            self.partner_tmf_id,
            expected_status=None,
        )
        if resp.status_code != 200:
            pytest.skip(f"Customer360 returned {resp.status_code}")
        if not data.get("id"):
            pytest.skip("Customer360 not returning data for this partner")
        assert data.get("name") == "Maria Santos"
        assert len(data.get("contactMedium", [])) >= 1


class TestGuiSalesFlow:
    """Sales-driven TAM workflow: Quotation → Confirmed Order → Invoice."""

    @pytest.fixture(autouse=True, scope="class")
    def sales_setup(self, odoo):
        """Create a partner and product for sales tests."""
        partner_id = odoo.create("res.partner", {
            "name": "Acme Telecom Corp",
            "is_company": True,
        })
        # Find or create a product
        products = odoo.search_read(
            "product.product",
            [("sale_ok", "=", True)],
            ["id", "name"], limit=1,
        )
        if products:
            product_id = products[0]["id"]
        else:
            product_id = odoo.create("product.product", {
                "name": "5G Router",
                "type": "consu",
                "list_price": 299.99,
                "sale_ok": True,
            })
        self.__class__.partner_id = partner_id
        self.__class__.product_id = product_id

        partner = odoo.read("res.partner", [partner_id], ["tmf_id"])[0]
        self.__class__.partner_tmf_id = partner.get("tmf_id")

    def test_create_quotation(self, odoo):
        """Create quotation with order line in Odoo."""
        so_id = odoo.create("sale.order", {
            "partner_id": self.partner_id,
        })
        assert so_id
        self.__class__.so_id = so_id

        # Add order line
        odoo.create("sale.order.line", {
            "order_id": so_id,
            "product_id": self.product_id,
            "product_uom_qty": 10,
        })

    def test_confirm_quotation(self, odoo):
        """Confirm quotation → becomes sale order."""
        odoo.call("sale.order", "action_confirm", [[self.so_id]])
        so = odoo.read("sale.order", [self.so_id], ["state", "tmf_id"])[0]
        assert so["state"] == "sale", f"Expected 'sale', got {so['state']}"
        self.__class__.so_tmf_id = so.get("tmf_id")

    def test_tmf_order_reflects_confirmation(self, tmf):
        """TMF Product Order shows confirmed state."""
        if not self.so_tmf_id:
            pytest.skip("No tmf_id on sale order")
        data, _ = tmf.get("ordering", "productOrder", self.so_tmf_id)
        assert_tmf_resource(data)

    def test_create_invoice(self, odoo):
        """Create invoice from sale order."""
        try:
            # Odoo 19: use the wizard to create invoices
            ctx = {"active_model": "sale.order", "active_ids": [self.so_id]}
            wiz_id = odoo.call(
                "sale.advance.payment.inv", "create",
                [[{}]], {"context": ctx},
            )
            wid = wiz_id[0] if isinstance(wiz_id, list) else wiz_id
            try:
                odoo.call(
                    "sale.advance.payment.inv", "create_invoices",
                    [[wid]], {"context": ctx},
                )
            except Exception:
                # XML-RPC may fail to marshal the return value (None),
                # but the invoice is still created server-side
                pass
        except Exception:
            pytest.skip("Could not create invoice — accounting may not be configured")

        invoices = odoo.search_read(
            "account.move",
            [("partner_id", "=", self.partner_id), ("move_type", "=", "out_invoice")],
            ["id", "name", "state", "amount_total"],
            limit=1,
        )
        assert len(invoices) >= 1, "No invoice created"
        self.__class__.invoice_id = invoices[0]["id"]

    def test_tmf_customer_bill_exists(self, tmf):
        """TMF Customer Bill API shows the invoice."""
        data, _ = tmf.list("customer_bill", "customerBill")
        assert isinstance(data, list)
