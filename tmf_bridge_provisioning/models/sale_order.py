import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrderProvisioning(models.Model):
    """
    Bridge: when a sale.order is confirmed (draft -> sale), auto-create
    TMF638 Service records for each order line whose product has a
    ProductSpecification with linked ServiceSpecifications.

    This follows the TMF provisioning lifecycle:
      Order confirmed -> Service(feasabilityChecked) -> ... -> active

    External OSS systems advance the service state via TMF638 PATCH API.
    """
    _inherit = "sale.order"

    tmf_account_id = fields.Many2one(
        "tmf.account",
        string="TMF Account",
        domain="[('partner_id', '=', partner_id), ('resource_type', '=', 'PartyAccount')]",
        help="Account to provision services against. If empty, a default account is created automatically.",
    )

    def write(self, vals):
        # Capture which orders are transitioning to 'sale' state
        if vals.get("state") == "sale" and not self.env.context.get("skip_tmf_bridge"):
            orders_to_provision = self.filtered(lambda o: o.state in ("draft", "sent"))
        else:
            orders_to_provision = self.env["sale.order"]

        res = super().write(vals)

        if orders_to_provision:
            orders_to_provision._provision_tmf_services()

        return res

    def _get_or_create_tmf_account(self, partner):
        """Find existing PartyAccount for partner, or create one."""
        TMFAccount = self.env["tmf.account"].sudo()
        account = TMFAccount.search([
            ("partner_id", "=", partner.id),
            ("resource_type", "=", "PartyAccount"),
        ], limit=1)
        if account:
            return account
        account = TMFAccount.with_context(skip_tmf_bridge=True).create({
            "name": f"{partner.name} - Default Account",
            "resource_type": "PartyAccount",
            "partner_id": partner.id,
            "state": "active",
        })
        _logger.info("TMF Provisioning: created account %s for partner %s", account.tmf_id, partner.name)
        return account

    def _create_rfs_for_cfs(self, cfs_service, product_spec, partner, account):
        """Auto-create RFS (Resource-Facing Services) for a CFS based on resource specifications."""
        TMFService = self.env["tmf.service"].sudo()
        res_specs = getattr(product_spec, "resource_specification_ids", None)
        if not res_specs:
            return

        for res_spec in res_specs:
            try:
                rfs = TMFService.with_context(skip_tmf_bridge=True).create({
                    "name": f"RFS - {res_spec.name}",
                    "partner_id": partner.id,
                    "account_id": account.id,
                    "parent_service_id": cfs_service.id,
                    "state": "feasabilityChecked",
                    "category": "RFS",
                    "service_type": "device",
                    "is_service_enabled": True,
                    "has_started": False,
                    "start_mode": "2",  # Automatically by owning device
                    "is_stateful": True,
                })
                _logger.info(
                    "TMF Provisioning: created RFS %s (%s) -> parent CFS %s",
                    rfs.tmf_id, res_spec.name, cfs_service.tmf_id,
                )
            except Exception:
                _logger.exception(
                    "TMF Provisioning: failed to create RFS for spec %s under CFS %s",
                    res_spec.name, cfs_service.tmf_id,
                )

    def _provision_tmf_services(self):
        """Create TMF638 Service records for confirmed order lines."""
        TMFService = self.env["tmf.service"].sudo()

        for order in self:
            partner = order.partner_id
            if not partner:
                _logger.warning("TMF Provisioning: order %s has no partner, skipping", order.name)
                continue

            account = order.tmf_account_id or self._get_or_create_tmf_account(partner)

            for line in order.order_line:
                # Skip non-product lines (sections, notes, delivery)
                if not line.product_id:
                    continue

                product = line.product_id.product_tmpl_id
                spec = getattr(product, "product_specification_id", None)
                if not spec:
                    continue

                # Get service specifications linked to this product spec
                svc_specs = getattr(spec, "service_specification_ids", self.env["tmf.service.specification"].browse())
                if not svc_specs:
                    # No service specs -> this product doesn't need provisioning
                    continue

                # Check if services already exist for this order line
                existing = TMFService.search([("order_line_id", "=", line.id)])
                if existing:
                    _logger.info(
                        "TMF Provisioning: services already exist for line %s, skipping",
                        line.id,
                    )
                    continue

                # Create one CFS per service specification, with qty support
                qty = int(line.product_uom_qty) or 1
                for svc_spec in svc_specs:
                    for i in range(qty):
                        suffix = f" #{i + 1}" if qty > 1 else ""
                        svc_vals = {
                            "name": f"{product.name} - {svc_spec.name}{suffix}",
                            "partner_id": partner.id,
                            "account_id": account.id,
                            "order_line_id": line.id,
                            "state": "feasabilityChecked",
                            "category": "CFS",
                            "service_type": getattr(svc_spec, "service_type", None) or "voice/data",
                        }

                        # Link to product specification if the field exists
                        if "product_specification_id" in TMFService._fields:
                            svc_vals["product_specification_id"] = spec.id

                        try:
                            service = TMFService.with_context(skip_tmf_bridge=True).create(svc_vals)
                            _logger.info(
                                "TMF Provisioning: created CFS %s (%s) for order %s line %s",
                                service.tmf_id, svc_spec.name, order.name, line.product_id.name,
                            )

                            # Auto-create RFS for each resource specification
                            self._create_rfs_for_cfs(service, spec, partner, account)

                        except Exception:
                            _logger.exception(
                                "TMF Provisioning: failed to create service for order %s line %s spec %s",
                                order.name, line.product_id.name, svc_spec.name,
                            )
