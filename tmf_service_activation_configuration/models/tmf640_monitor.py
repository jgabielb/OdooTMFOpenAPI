from odoo import fields, models
import json

class TMF640Monitor(models.Model):
    _name = "tmf640.monitor"
    _description = "TMF640 Monitor"
    _inherit = ["tmf.model.mixin"]

    tmf640_id = fields.Char(index=True)
    href = fields.Char()

    # Spec: InProgress, InError, Completed :contentReference[oaicite:5]{index=5}
    state = fields.Selection([
        ("InProgress", "InProgress"),
        ("InError", "InError"),
        ("completed", "completed"),
    ], default="InProgress", required=True)

    source_href = fields.Char()

    # request/response store as json blobs for flexibility
    request_json = fields.Text()
    response_json = fields.Text()

    tmf_type = fields.Char(string="@type", default="Monitor")

    def to_tmf_json(self):
        self.ensure_one()
        mid = self.tmf640_id or self.tmf_id or str(self.id)
        href = self.href or f"/tmf-api/ServiceActivationAndConfiguration/v4/monitor/{mid}"

        def _load(text):
            if not text:
                return None
            try:
                return json.loads(text)
            except Exception:
                return None

        payload = {
            "id": mid,
            "href": href,
            "state": self.state,
            "sourceHref": self.source_href,
            "request": _load(self.request_json),
            "response": _load(self.response_json),
            "@type": self.tmf_type or "Monitor",
        }
        return {k: v for k, v in payload.items() if v is not None}
