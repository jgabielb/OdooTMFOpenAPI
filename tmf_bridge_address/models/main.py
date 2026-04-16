from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class ResPartnerTMFAddress(models.Model):
    _inherit = "res.partner"

    tmf_geographic_address_id = fields.Many2one(
        "tmf.geographic.address", string="TMF Geographic Address",
        ondelete="set null", copy=False,
    )

    def _sync_tmf_geographic_address(self):
        Addr = self.env["tmf.geographic.address"].sudo()
        for rec in self:
            if rec.env.context.get("skip_tmf_bridge"):
                continue
            if not any([rec.street, rec.city, rec.zip, rec.country_id]):
                continue
            vals = {
                "street_name": rec.street or "",
                "street_nr": rec.street2 or "",
                "city": rec.city or "",
                "postcode": rec.zip or "",
                "state_or_province": rec.state_id.name if rec.state_id else "",
                "country": rec.country_id.name if rec.country_id else "",
                "name": f"{rec.street or ''}, {rec.city or ''}".strip(", "),
                "partner_id": rec.id,
            }
            if rec.tmf_geographic_address_id and rec.tmf_geographic_address_id.exists():
                rec.tmf_geographic_address_id.with_context(skip_tmf_bridge=True).write(vals)
                continue
            addr = Addr.with_context(skip_tmf_bridge=True).create(vals)
            rec.with_context(skip_tmf_bridge=True).write({"tmf_geographic_address_id": addr.id})

    def write(self, vals):
        res = super().write(vals)
        trigger = {"street", "street2", "city", "zip", "state_id", "country_id"}
        if not self.env.context.get("skip_tmf_bridge") and trigger & set(vals):
            try:
                self._sync_tmf_geographic_address()
            except Exception:
                _logger.warning("TMF bridge sync failed on res.partner address write", exc_info=True)
        return res
