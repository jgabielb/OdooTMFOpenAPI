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
                "name": f"Usage {getattr(rec, 'name', '') or rec.tmf_id}",
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
