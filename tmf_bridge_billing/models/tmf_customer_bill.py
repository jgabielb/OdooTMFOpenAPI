"""TMFC031 wiring helpers for CustomerBill.

Two responsibilities:

1. Automatic backfill on create — if a bill is created without a payload but
   with a partner/move/account, build the same payload shape the bridge
   produces so cross-API wiring resolves out-of-the-box. This catches bills
   created via the basic API POST, manual UI, BillCycle/OnDemand paths, etc.

2. Manual rebuild action — `action_rebuild_tmfc031_wiring` on the form/list
   for fixing existing bills with NULL payload.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TmfCustomerBillBackfill(models.Model):
    _inherit = "tmf.customer.bill"

    # ------------------------------------------------------------------
    # Auto-backfill on create
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            # Treat empty dict / list as "no payload" so a thin API POST still
            # gets enriched. Only skip when the payload already contains real
            # cross-API references.
            existing = rec.payload or {}
            has_refs = any(existing.get(k) for k in (
                "billingAccount", "relatedParty", "productRef", "product", "relatedEntity"
            )) if isinstance(existing, dict) else False
            if has_refs:
                continue
            # No payload was provided — try to construct one from the linked
            # records so cross-API wiring can resolve. Skip silently if the
            # bill has no partner and no move — there's nothing to derive from.
            try:
                svc = rec._find_service_for_bill()
                if svc:
                    payload = rec._backfill_payload_from_service(svc)
                else:
                    payload = rec._backfill_payload_minimal()
                if payload:
                    rec.with_context(skip_tmf_wiring=True).write({"payload": payload})
                    if hasattr(rec, "_resolve_tmf_refs"):
                        rec._resolve_tmf_refs()
            except Exception:
                _logger.exception(
                    "TMFC031 auto-backfill failed for bill %s", rec.id,
                )
        return recs

    def _backfill_payload_minimal(self):
        """Build a minimal payload from the bill's own partner / move when no
        originating service can be found."""
        self.ensure_one()
        payload = {}
        partner = self.partner_id
        if partner:
            payload["relatedParty"] = [{
                "id": partner.tmf_id or str(partner.id),
                "name": partner.name,
                "role": "Customer",
                "@type": "RelatedParty",
                "@referredType": ("Individual" if partner.company_type == "person"
                                  else "Organization"),
            }]
        move = getattr(self, "move_id", False)
        if move:
            payload["relatedEntity"] = [{
                "id": move.tmf_id or str(move.id) if hasattr(move, "tmf_id") else str(move.id),
                "name": move.name or f"Invoice {move.id}",
                "@referredType": "Invoice",
                "@type": "RelatedEntity",
            }]
        return payload

    def _backfill_payload_from_service(self, service):
        """Build the same payload shape `tmf_bridge_billing` produces."""
        self.ensure_one()
        partner = service.partner_id or self.partner_id
        billing_account = service.billing_account_id

        payload = {}

        if billing_account:
            tmf666 = service._sync_billing_account_tmf666(billing_account) \
                if hasattr(service, "_sync_billing_account_tmf666") else None
            payload["billingAccount"] = {
                "id": (tmf666.tmf_id if tmf666 else
                       (billing_account.tmf_id or str(billing_account.id))),
                "name": billing_account.name,
                "@type": "BillingAccountRef",
                "@referredType": "BillingAccount",
            }

        if partner:
            payload["relatedParty"] = [{
                "id": partner.tmf_id or str(partner.id),
                "name": partner.name,
                "role": "Customer",
                "@type": "RelatedParty",
                "@referredType": ("Individual" if partner.company_type == "person"
                                  else "Organization"),
            }]

        tmf_product = (service._resolve_tmf_product()
                       if hasattr(service, "_resolve_tmf_product") else None)
        if tmf_product:
            product_ref = {
                "id": tmf_product.tmf_id or str(tmf_product.id),
                "name": tmf_product.name,
                "@type": "ProductRef",
                "@referredType": "Product",
            }
            payload["productRef"] = [product_ref]
            payload["product"] = [product_ref]

        payload["relatedEntity"] = [{
            "id": service.tmf_id or str(service.id),
            "name": service.name,
            "@referredType": "Service",
            "@type": "RelatedEntity",
        }]

        # TMF669 PartyRole
        party_role = self.env["tmf.party.role"].sudo().search(
            [("name", "=", "Account Holder")], limit=1,
        )
        if party_role:
            payload.setdefault("relatedParty", []).append({
                "id": party_role.tmf_id or str(party_role.id),
                "name": party_role.name,
                "role": "AccountHolder",
                "@type": "PartyRole",
                "@referredType": "PartyRole",
            })

        # TMF635 Usage — pick an existing usage or create a stub
        Usage = self.env["tmf.usage"].sudo()
        usage_name = f"Usage for bill #{self.id}"
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

        # TMF701 ProcessFlow
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

        return payload

    def _find_service_for_bill(self):
        """Best-effort: find the tmf.service that originated this bill."""
        self.ensure_one()
        Service = self.env["tmf.service"].sudo()

        # 1. service already linked back through customer_bill_id
        svc = Service.search([("customer_bill_id", "=", self.id)], limit=1)
        if svc:
            return svc

        # 2. via move -> sale order -> service.sale_order_id
        move = getattr(self, "move_id", False)
        if move:
            sale_orders = move.invoice_line_ids.sale_line_ids.order_id \
                if hasattr(move, "invoice_line_ids") else False
            if sale_orders:
                svc = Service.search(
                    [("sale_order_id", "in", sale_orders.ids),
                     ("state", "=", "active")], limit=1
                )
                if svc:
                    return svc

        # 3. last resort: any active service for the partner
        if self.partner_id:
            svc = Service.search(
                [("partner_id", "=", self.partner_id.id),
                 ("state", "=", "active")], limit=1
            )
        return svc

    def action_rebuild_tmfc031_wiring(self):
        """Server action exposed on the bill form: rebuild payload + resolve refs."""
        for bill in self:
            svc = bill._find_service_for_bill()
            if not svc:
                raise UserError(_(
                    "Cannot rebuild wiring for bill %s: no originating tmf.service "
                    "could be located. Bill needs at least a partner or a linked invoice."
                ) % (bill.tmf_id or bill.id))
            payload = bill._backfill_payload_from_service(svc)
            bill.with_context(skip_tmf_wiring=True).write({"payload": payload})
            # Trigger the resolver so the relational wiring fields get populated.
            if hasattr(bill, "_resolve_tmf_refs"):
                bill._resolve_tmf_refs()
            _logger.info(
                "TMFC031 backfill: bill %s rebuilt from service %s",
                bill.tmf_id, svc.tmf_id,
            )
        return True
