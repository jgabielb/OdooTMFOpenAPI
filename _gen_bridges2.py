#!/usr/bin/env python3
"""Generate remaining reverse-bridge addons for 100% TAM coverage."""
import os, textwrap

ROOT = os.path.dirname(os.path.abspath(__file__))

BRIDGES = [
    {
        "addon": "tmf_bridge_agreement",
        "summary": "Bridge: Odoo Sale Order ↔ TMF Agreement",
        "depends": ["sale", "tmf_agreement"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class SaleOrderAgreement(models.Model):
                _inherit = "sale.order"

                tmf_agreement_id = fields.Many2one(
                    "tmf.agreement", string="TMF Agreement",
                    ondelete="set null", copy=False,
                )

            class TMFAgreementBridge(models.Model):
                _inherit = "tmf.agreement"

                sale_order_id = fields.Many2one(
                    "sale.order", string="Odoo Sale Order",
                    ondelete="set null", copy=False,
                )

                def _sync_sale_order(self):
                    SO = self.env["sale.order"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge") or rec.sale_order_id:
                            continue
                        partner = rec.partner_id or self.env.ref("base.partner_admin", False)
                        if not partner:
                            continue
                        so = SO.with_context(skip_tmf_bridge=True).create({
                            "partner_id": partner.id,
                            "note": rec.description or rec.name or "",
                            "tmf_agreement_id": rec.id,
                        })
                        rec.with_context(skip_tmf_bridge=True).write({"sale_order_id": so.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_sale_order()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs
        """),
    },
    {
        "addon": "tmf_bridge_quote",
        "summary": "Bridge: Odoo Quotation ↔ TMF Quote",
        "depends": ["sale", "tmf_quote_management"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class TMFQuoteBridge(models.Model):
                _inherit = "tmf.quote"

                sale_order_id = fields.Many2one(
                    "sale.order", string="Odoo Quotation",
                    ondelete="set null", copy=False,
                )

                def _sync_quotation(self):
                    SO = self.env["sale.order"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge") or rec.sale_order_id:
                            continue
                        partner = rec.partner_id if hasattr(rec, "partner_id") and rec.partner_id else self.env.ref("base.partner_admin", False)
                        if not partner:
                            continue
                        so = SO.with_context(skip_tmf_bridge=True).create({
                            "partner_id": partner.id,
                            "note": rec.description if hasattr(rec, "description") else "",
                        })
                        rec.with_context(skip_tmf_bridge=True).write({"sale_order_id": so.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_quotation()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs
        """),
    },
    {
        "addon": "tmf_bridge_shopping_cart",
        "summary": "Bridge: Odoo Draft SO ↔ TMF Shopping Cart",
        "depends": ["sale", "tmf_shopping_cart"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class TMFShoppingCartBridge(models.Model):
                _inherit = "tmf.shopping.cart"

                sale_order_id = fields.Many2one(
                    "sale.order", string="Odoo Draft Order",
                    ondelete="set null", copy=False,
                )

                def _sync_draft_order(self):
                    SO = self.env["sale.order"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge") or rec.sale_order_id:
                            continue
                        partner = rec.partner_id if hasattr(rec, "partner_id") and rec.partner_id else self.env.ref("base.partner_admin", False)
                        if not partner:
                            continue
                        so = SO.with_context(skip_tmf_bridge=True).create({
                            "partner_id": partner.id,
                        })
                        rec.with_context(skip_tmf_bridge=True).write({"sale_order_id": so.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_draft_order()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs
        """),
    },
    {
        "addon": "tmf_bridge_customer_bill",
        "summary": "Bridge: Odoo Invoice ↔ TMF Customer Bill",
        "depends": ["account", "tmf_customer_bill_management"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class AccountMoveTMFBill(models.Model):
                _inherit = "account.move"

                tmf_customer_bill_id = fields.Many2one(
                    "tmf.customer.bill", string="TMF Customer Bill",
                    ondelete="set null", copy=False,
                )

                def _sync_tmf_customer_bill(self):
                    Bill = self.env["tmf.customer.bill"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge"):
                            continue
                        if rec.move_type != "out_invoice":
                            continue
                        vals = {
                            "name": rec.name or "Invoice",
                            "state": "validated" if rec.state == "posted" else "new",
                            "partner_id": rec.partner_id.id if rec.partner_id else False,
                        }
                        if hasattr(rec, "tmf_customer_bill_id") and rec.tmf_customer_bill_id and rec.tmf_customer_bill_id.exists():
                            rec.tmf_customer_bill_id.with_context(skip_tmf_bridge=True).write(vals)
                            continue
                        bill = Bill.with_context(skip_tmf_bridge=True).create(vals)
                        rec.with_context(skip_tmf_bridge=True).write({"tmf_customer_bill_id": bill.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_tmf_customer_bill()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs

                def write(self, vals):
                    res = super().write(vals)
                    if not self.env.context.get("skip_tmf_bridge") and "state" in vals:
                        try:
                            self._sync_tmf_customer_bill()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return res
        """),
    },
    {
        "addon": "tmf_bridge_service_catalog",
        "summary": "Bridge: Odoo Product Template ↔ TMF Service Specification",
        "depends": ["product", "tmf_service_catalog"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class TMFServiceSpecBridge(models.Model):
                _inherit = "tmf.service.specification"

                product_tmpl_id = fields.Many2one(
                    "product.template", string="Odoo Product Template",
                    ondelete="set null", copy=False,
                )

                def _sync_product_template(self):
                    PT = self.env["product.template"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge") or rec.product_tmpl_id:
                            continue
                        tmpl = PT.with_context(skip_tmf_bridge=True).create({
                            "name": rec.name or f"Service Spec {rec.tmf_id}",
                            "type": "service",
                        })
                        rec.with_context(skip_tmf_bridge=True).write({"product_tmpl_id": tmpl.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_product_template()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs
        """),
    },
    {
        "addon": "tmf_bridge_resource_catalog",
        "summary": "Bridge: Odoo Product Template ↔ TMF Resource Specification",
        "depends": ["product", "tmf_resource_catalog"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class TMFResourceSpecBridge(models.Model):
                _inherit = "tmf.resource.specification"

                product_tmpl_id = fields.Many2one(
                    "product.template", string="Odoo Product Template",
                    ondelete="set null", copy=False,
                )

                def _sync_product_template(self):
                    PT = self.env["product.template"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge") or rec.product_tmpl_id:
                            continue
                        tmpl = PT.with_context(skip_tmf_bridge=True).create({
                            "name": rec.name or f"Resource Spec {rec.tmf_id}",
                            "type": "consu",
                        })
                        rec.with_context(skip_tmf_bridge=True).write({"product_tmpl_id": tmpl.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_product_template()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs
        """),
    },
    {
        "addon": "tmf_bridge_service_order",
        "summary": "Bridge: Odoo Sale Order ↔ TMF Service Order",
        "depends": ["sale", "tmf_service_order"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class TMFServiceOrderBridge(models.Model):
                _inherit = "tmf.service.order"

                sale_order_id = fields.Many2one(
                    "sale.order", string="Odoo Sale Order",
                    ondelete="set null", copy=False,
                )

                def _sync_sale_order(self):
                    SO = self.env["sale.order"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge") or rec.sale_order_id:
                            continue
                        partner = rec.partner_id if hasattr(rec, "partner_id") and rec.partner_id else self.env.ref("base.partner_admin", False)
                        if not partner:
                            continue
                        so = SO.with_context(skip_tmf_bridge=True).create({
                            "partner_id": partner.id,
                            "note": f"TMF Service Order {rec.tmf_id}",
                        })
                        rec.with_context(skip_tmf_bridge=True).write({"sale_order_id": so.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_sale_order()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs
        """),
    },
    {
        "addon": "tmf_bridge_resource_order",
        "summary": "Bridge: Odoo Purchase Order ↔ TMF Resource Order",
        "depends": ["purchase", "tmf_resource_order"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class TMFResourceOrderBridge(models.Model):
                _inherit = "tmf.resource.order"

                purchase_order_id = fields.Many2one(
                    "purchase.order", string="Odoo Purchase Order",
                    ondelete="set null", copy=False,
                )

                def _sync_purchase_order(self):
                    PO = self.env["purchase.order"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge") or rec.purchase_order_id:
                            continue
                        partner = rec.partner_id if hasattr(rec, "partner_id") and rec.partner_id else self.env.ref("base.partner_admin", False)
                        if not partner:
                            continue
                        po = PO.with_context(skip_tmf_bridge=True).create({
                            "partner_id": partner.id,
                            "notes": f"TMF Resource Order {rec.tmf_id}",
                        })
                        rec.with_context(skip_tmf_bridge=True).write({"purchase_order_id": po.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_purchase_order()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs
        """),
    },
    {
        "addon": "tmf_bridge_document",
        "summary": "Bridge: Odoo Attachment ↔ TMF Document",
        "depends": ["base", "tmf_document"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class TMFDocumentBridge(models.Model):
                _inherit = "tmf.document"

                attachment_id = fields.Many2one(
                    "ir.attachment", string="Odoo Attachment",
                    ondelete="set null", copy=False,
                )

                def _sync_attachment(self):
                    Att = self.env["ir.attachment"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge") or rec.attachment_id:
                            continue
                        att = Att.with_context(skip_tmf_bridge=True).create({
                            "name": rec.name or f"TMF Document {rec.tmf_id}",
                            "type": "url",
                            "url": rec.href if hasattr(rec, "href") else "",
                        })
                        rec.with_context(skip_tmf_bridge=True).write({"attachment_id": att.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_attachment()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs

            class IrAttachmentTMF(models.Model):
                _inherit = "ir.attachment"

                tmf_document_id = fields.Many2one(
                    "tmf.document", string="TMF Document",
                    ondelete="set null", copy=False,
                )
        """),
    },
    {
        "addon": "tmf_bridge_party_interaction",
        "summary": "Bridge: Odoo Mail ↔ TMF Party Interaction",
        "depends": ["mail", "tmf_party_interaction"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class TMFPartyInteractionBridge(models.Model):
                _inherit = "tmf.party.interaction"

                mail_message_id = fields.Many2one(
                    "mail.message", string="Odoo Mail Message",
                    ondelete="set null", copy=False,
                )

                def _sync_mail_message(self):
                    Msg = self.env["mail.message"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge") or rec.mail_message_id:
                            continue
                        partner = rec.partner_id if hasattr(rec, "partner_id") and rec.partner_id else False
                        msg = Msg.with_context(skip_tmf_bridge=True).create({
                            "body": rec.description if hasattr(rec, "description") else f"Party Interaction {rec.tmf_id}",
                            "message_type": "comment",
                            "subtype_id": self.env.ref("mail.mt_note").id,
                            "author_id": partner.id if partner else False,
                        })
                        rec.with_context(skip_tmf_bridge=True).write({"mail_message_id": msg.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_mail_message()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs
        """),
    },
    {
        "addon": "tmf_bridge_geographic_site",
        "summary": "Bridge: Odoo Warehouse ↔ TMF Geographic Site",
        "depends": ["stock", "tmf_geographic_site"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class TMFGeoSiteBridge(models.Model):
                _inherit = "tmf.geographic.site"

                warehouse_id = fields.Many2one(
                    "stock.warehouse", string="Odoo Warehouse",
                    ondelete="set null", copy=False,
                )

                def _sync_warehouse(self):
                    WH = self.env["stock.warehouse"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge") or rec.warehouse_id:
                            continue
                        name = rec.name or f"Site {rec.tmf_id}"
                        code = (name[:5].upper().replace(" ", "")) or "SITE"
                        existing = WH.search([("code", "=", code)], limit=1)
                        if existing:
                            rec.with_context(skip_tmf_bridge=True).write({"warehouse_id": existing.id})
                        else:
                            wh = WH.with_context(skip_tmf_bridge=True).create({
                                "name": name,
                                "code": code,
                            })
                            rec.with_context(skip_tmf_bridge=True).write({"warehouse_id": wh.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_warehouse()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs

            class StockWarehouseTMF(models.Model):
                _inherit = "stock.warehouse"

                tmf_geographic_site_id = fields.Many2one(
                    "tmf.geographic.site", string="TMF Geographic Site",
                    ondelete="set null", copy=False,
                )
        """),
    },
    {
        "addon": "tmf_bridge_alarm",
        "summary": "Bridge: Odoo Activity ↔ TMF Alarm",
        "depends": ["mail", "tmf_alarm"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class TMFAlarmBridge(models.Model):
                _inherit = "tmf.alarm"

                activity_id = fields.Many2one(
                    "mail.activity", string="Odoo Activity",
                    ondelete="set null", copy=False,
                )

                def _sync_activity(self):
                    Activity = self.env["mail.activity"].sudo()
                    act_type = self.env.ref("mail.mail_activity_data_todo", False)
                    if not act_type:
                        return
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge") or rec.activity_id:
                            continue
                        user = self.env.user
                        activity = Activity.with_context(skip_tmf_bridge=True).create({
                            "activity_type_id": act_type.id,
                            "summary": f"Alarm: {rec.name or rec.tmf_id}",
                            "note": rec.description if hasattr(rec, "description") else "",
                            "res_model_id": self.env["ir.model"]._get_id("tmf.alarm"),
                            "res_id": rec.id,
                            "user_id": user.id,
                        })
                        rec.with_context(skip_tmf_bridge=True).write({"activity_id": activity.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_activity()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs
        """),
    },
    {
        "addon": "tmf_bridge_promotion",
        "summary": "Bridge: Odoo Pricelist ↔ TMF Promotion",
        "depends": ["product", "tmf_promotion_management"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class TMFPromotionBridge(models.Model):
                _inherit = "tmf.promotion"

                pricelist_id = fields.Many2one(
                    "product.pricelist", string="Odoo Pricelist",
                    ondelete="set null", copy=False,
                )

                def _sync_pricelist(self):
                    PL = self.env["product.pricelist"].sudo()
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge") or rec.pricelist_id:
                            continue
                        pl = PL.with_context(skip_tmf_bridge=True).create({
                            "name": rec.name or f"Promotion {rec.tmf_id}",
                        })
                        rec.with_context(skip_tmf_bridge=True).write({"pricelist_id": pl.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_pricelist()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs
        """),
    },
    {
        "addon": "tmf_bridge_usage",
        "summary": "Bridge: Odoo Analytic Line ↔ TMF Usage",
        "depends": ["analytic", "tmf_usage"],
        "model_file": textwrap.dedent("""\
            from odoo import api, fields, models
            import logging
            _logger = logging.getLogger(__name__)

            class TMFUsageBridge(models.Model):
                _inherit = "tmf.usage"

                analytic_line_id = fields.Many2one(
                    "account.analytic.line", string="Odoo Analytic Line",
                    ondelete="set null", copy=False,
                )

                def _sync_analytic_line(self):
                    Line = self.env["account.analytic.line"].sudo()
                    plan = self.env["account.analytic.plan"].sudo().search([], limit=1)
                    if not plan:
                        return
                    account = self.env["account.analytic.account"].sudo().search([("plan_id", "=", plan.id)], limit=1)
                    if not account:
                        account = self.env["account.analytic.account"].sudo().create({
                            "name": "TMF Usage Metering",
                            "plan_id": plan.id,
                        })
                    for rec in self:
                        if rec.env.context.get("skip_tmf_bridge") or rec.analytic_line_id:
                            continue
                        line = Line.with_context(skip_tmf_bridge=True).create({
                            "name": f"Usage {rec.name or rec.tmf_id}",
                            "account_id": account.id,
                            "amount": 0,
                        })
                        rec.with_context(skip_tmf_bridge=True).write({"analytic_line_id": line.id})

                @api.model_create_multi
                def create(self, vals_list):
                    recs = super().create(vals_list)
                    if not self.env.context.get("skip_tmf_bridge"):
                        try:
                            recs._sync_analytic_line()
                        except Exception:
                            _logger.warning("TMF bridge sync failed", exc_info=True)
                    return recs
        """),
    },
]


def gen_manifest(b):
    deps = ", ".join(f'"{d}"' for d in b["depends"])
    return f'''# -*- coding: utf-8 -*-
{{
    "name": "{b['summary']}",
    "version": "17.0.1.0.0",
    "category": "TMF/Bridge",
    "summary": "{b['summary']}",
    "depends": [{deps}],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}}
'''


def main():
    ok = 0
    for b in BRIDGES:
        addon_dir = os.path.join(ROOT, b["addon"])
        models_dir = os.path.join(addon_dir, "models")
        security_dir = os.path.join(addon_dir, "security")
        os.makedirs(models_dir, exist_ok=True)
        os.makedirs(security_dir, exist_ok=True)

        with open(os.path.join(addon_dir, "__manifest__.py"), "w", encoding="utf-8", newline="\n") as f:
            f.write(gen_manifest(b))
        with open(os.path.join(addon_dir, "__init__.py"), "w", encoding="utf-8", newline="\n") as f:
            f.write("from . import models\n")
        with open(os.path.join(models_dir, "__init__.py"), "w", encoding="utf-8", newline="\n") as f:
            f.write("from . import main\n")
        with open(os.path.join(models_dir, "main.py"), "w", encoding="utf-8", newline="\n") as f:
            f.write(b["model_file"])
        with open(os.path.join(security_dir, "ir.model.access.csv"), "w", encoding="utf-8", newline="\n") as f:
            f.write("id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n")

        print(f"  OK: {b['addon']}")
        ok += 1

    print(f"\n=== {ok} bridge addons generated ===")


if __name__ == "__main__":
    main()
