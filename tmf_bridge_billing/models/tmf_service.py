import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class TMFServiceBilling(models.Model):
    """
    Bridge: when a tmf.service transitions to 'active', create an Odoo
    invoice from the originating sale order and a TMF CustomerBill record.

    Flow:
      Service.state -> 'active'
        -> Find the sale order (via order_line_id)
        -> Create invoice from sale order (if not already invoiced)
        -> Create tmf.customer.bill linked to the invoice + BillingAccount
    """
    _inherit = "tmf.service"

    billing_account_id = fields.Many2one(
        "tmf.account",
        string="Billing Account",
        domain="[('resource_type', '=', 'BillingAccount')]",
        ondelete="set null",
    )
    customer_bill_id = fields.Many2one(
        "tmf.customer.bill",
        string="Customer Bill",
        ondelete="set null",
    )

    def write(self, vals):
        # Detect services transitioning TO 'active'
        if vals.get("state") == "active" and not self.env.context.get("skip_tmf_bridge"):
            services_to_bill = self.filtered(lambda s: s.state != "active")
        else:
            services_to_bill = self.env["tmf.service"]

        res = super().write(vals)

        if services_to_bill:
            services_to_bill.sudo()._trigger_billing()
            # Cascade: activate child RFS services when parent CFS becomes active
            for svc in services_to_bill:
                children = svc.child_service_ids.filtered(lambda c: c.state != "active")
                if children:
                    children.with_context(skip_tmf_bridge=True).write({"state": "active"})
                    _logger.info(
                        "TMF Billing: cascaded active state to %d child RFS for CFS %s",
                        len(children), svc.tmf_id,
                    )

        return res

    def _trigger_billing(self):
        """Create invoices and TMF CustomerBills for newly activated services."""
        for service in self:
            try:
                service._create_billing_for_service()
            except Exception:
                _logger.exception(
                    "TMF Billing Bridge: failed to create billing for service %s (%s)",
                    service.tmf_id, service.name,
                )

    def _create_billing_for_service(self):
        """Create invoice + CustomerBill for a single service."""
        self.ensure_one()

        # Already billed?
        if self.customer_bill_id:
            _logger.info("TMF Billing: service %s already has bill %s, skipping",
                         self.tmf_id, self.customer_bill_id.tmf_id)
            return

        sale_order = self.sale_order_id
        if not sale_order:
            _logger.info("TMF Billing: service %s has no sale order, skipping", self.tmf_id)
            return

        partner = self.partner_id
        if not partner:
            return

        # Find or resolve the BillingAccount
        billing_account = self._resolve_billing_account()

        # Create invoice from sale order (if not already done)
        invoice = self._get_or_create_invoice(sale_order)
        if not invoice:
            return

        # Create TMF CustomerBill linked to the invoice
        bill = self._create_customer_bill(invoice, billing_account)

        # Link back to service
        self.with_context(skip_tmf_bridge=True).write({
            "customer_bill_id": bill.id,
            "billing_account_id": billing_account.id if billing_account else False,
        })

        _logger.info(
            "TMF Billing: created bill %s (invoice %s) for service %s on account %s",
            bill.tmf_id, invoice.name, self.tmf_id,
            billing_account.name if billing_account else "N/A",
        )

    def _resolve_billing_account(self):
        """Find or create the BillingAccount for this service's account."""
        self.ensure_one()
        TMFAccount = self.env["tmf.account"].sudo()

        # If the service already has a billing account, use it
        if self.billing_account_id:
            return self.billing_account_id

        # Find BillingAccount linked to the same partner
        party_account = self.account_id
        partner = self.partner_id

        if party_account:
            # Look for a BillingAccount with a name matching this PartyAccount
            billing = TMFAccount.search([
                ("partner_id", "=", partner.id),
                ("resource_type", "=", "BillingAccount"),
                ("name", "ilike", party_account.name.split(" - ", 1)[-1] if " - " in party_account.name else party_account.name),
            ], limit=1)
            if billing:
                return billing

        # Fallback: any BillingAccount for this partner
        billing = TMFAccount.search([
            ("partner_id", "=", partner.id),
            ("resource_type", "=", "BillingAccount"),
        ], limit=1)
        if billing:
            return billing

        # Auto-create a BillingAccount
        acct_name = party_account.name if party_account else partner.name
        billing = TMFAccount.with_context(skip_tmf_bridge=True).create({
            "name": f"Billing - {acct_name}",
            "resource_type": "BillingAccount",
            "partner_id": partner.id,
            "state": "active",
        })
        _logger.info("TMF Billing: auto-created BillingAccount %s for %s",
                      billing.tmf_id, partner.name)
        return billing

    def _get_or_create_invoice(self, sale_order):
        """Create an invoice from the sale order if not already invoiced."""
        # Check if the order already has invoices
        existing_invoices = sale_order.invoice_ids.filtered(
            lambda m: m.move_type == "out_invoice" and m.state != "cancel"
        )
        if existing_invoices:
            return existing_invoices[0]

        # Create invoice from sale order using Odoo's standard method
        try:
            invoice = sale_order._create_invoices()
            if invoice:
                _logger.info("TMF Billing: created invoice %s for order %s",
                             invoice.name, sale_order.name)
                return invoice[0] if len(invoice) > 1 else invoice
        except Exception:
            _logger.exception("TMF Billing: failed to create invoice for order %s",
                              sale_order.name)
        return None

    def _create_customer_bill(self, invoice, billing_account):
        """Create a TMF CustomerBill linked to the Odoo invoice."""
        self.ensure_one()
        TMFBill = self.env["tmf.customer.bill"].sudo()

        # Check if a bill already exists for this invoice
        existing = TMFBill.search([("move_id", "=", invoice.id)], limit=1)
        if existing:
            return existing

        now = fields.Datetime.now()
        bill_vals = {
            "name": f"Bill - {self.name}",
            "partner_id": self.partner_id.id,
            "move_id": invoice.id,
            "state": "new",
            "bill_date": now,
            "billing_period_start": self.start_date or now,
            "billing_period_end": self.end_date or False,
        }

        # Build payload with cross-API refs for TMFC031 wiring resolution
        payload = {}

        # TMF666 billingAccount ref — also sync tmf.billing.account for wiring
        if billing_account:
            tmf666 = self._sync_billing_account_tmf666(billing_account)
            payload["billingAccount"] = {
                "id": tmf666.tmf_id if tmf666 else (billing_account.tmf_id or str(billing_account.id)),
                "name": billing_account.name,
                "@type": "BillingAccountRef",
                "@referredType": "BillingAccount",
            }

        # TMF632 relatedParty — so TMFC031 wiring can resolve partners
        partner = self.partner_id
        payload["relatedParty"] = [
            {
                "id": partner.tmf_id or str(partner.id),
                "name": partner.name,
                "role": "Customer",
                "@type": "RelatedParty",
                "@referredType": "Individual" if partner.company_type == "person" else "Organization",
            },
        ]

        # TMF637 productRef — trace service → order line → product → tmf.product
        tmf_product = self._resolve_tmf_product()
        if tmf_product:
            product_ref = {
                "id": tmf_product.tmf_id or str(tmf_product.id),
                "name": tmf_product.name,
                "@type": "ProductRef",
                "@referredType": "Product",
            }
            payload["productRef"] = [product_ref]
            payload["product"] = [product_ref]  # alt key the resolver also checks

        # Add service ref
        payload["relatedEntity"] = [
            {
                "id": self.tmf_id or str(self.id),
                "name": self.name,
                "@referredType": "Service",
                "@type": "RelatedEntity",
            },
        ]

        # TMF669 PartyRole — append "Account Holder" role for the customer party
        party_role = self.env["tmf.party.role"].sudo().search(
            [("name", "=", "Account Holder")], limit=1,
        )
        if party_role:
            payload["relatedParty"].append({
                "id": party_role.tmf_id or str(party_role.id),
                "name": party_role.name,
                "role": "AccountHolder",
                "@type": "PartyRole",
                "@referredType": "PartyRole",
            })

        # TMF635 Usage — link a stub usage record (created on the fly if absent)
        Usage = self.env["tmf.usage"].sudo()
        usage_name = f"Usage for service {self.tmf_id or self.id}"
        usage = Usage.search([("name", "=", usage_name)], limit=1)
        if not usage:
            usage = Usage.with_context(skip_tmf_bridge=True).create({
                "name": usage_name,
                "description": "Auto-generated usage record",
                "status": "rated",
            })
        if usage:
            payload["usage"] = [{
                "id": usage.tmf_id or str(usage.id),
                "name": usage.name,
                "@type": "UsageRef",
                "@referredType": "Usage",
            }]

        # TMF701 ProcessFlow — reference the canonical Order-to-Cash flow
        proc_flow = self.env["tmf.process.flow"].sudo().search(
            [("name", "=", "Order-to-Cash Flow")], limit=1,
        )
        if proc_flow:
            payload["processFlow"] = {
                "id": proc_flow.tmf_id or str(proc_flow.id),
                "name": proc_flow.name,
                "@type": "ProcessFlowRef",
                "@referredType": "ProcessFlow",
            }

        bill_vals["payload"] = payload

        bill = TMFBill.create(bill_vals)
        return bill

    def _resolve_tmf_product(self):
        """Find the tmf.product (TMF637) linked to this service's sale order line product."""
        self.ensure_one()
        order_line = self.order_line_id
        if not order_line or not order_line.product_id:
            return None
        return self.env["tmf.product"].sudo().search([
            ("odoo_product_id", "=", order_line.product_id.id),
        ], limit=1)

    def _sync_billing_account_tmf666(self, billing_account):
        """Ensure a tmf.billing.account (TMF666) record exists for the tmf.account BillingAccount."""
        TMF666 = self.env["tmf.billing.account"].sudo()
        # Match by name + partner
        existing = TMF666.search([
            ("partner_id", "=", billing_account.partner_id.id),
            ("name", "=", billing_account.name),
        ], limit=1)
        if existing:
            return existing
        return TMF666.with_context(skip_tmf_bridge=True).create({
            "name": billing_account.name,
            "partner_id": billing_account.partner_id.id,
            "state": "active",
        })
