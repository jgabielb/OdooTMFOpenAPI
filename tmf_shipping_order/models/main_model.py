from datetime import datetime, timezone
from odoo import api, fields, models


class TMFShippingOrder(models.Model):
    _name = "tmf.shipping.order"
    _description = "TMF700 ShippingOrder"
    _inherit = ["tmf.model.mixin"]

    external_id = fields.Char(string="externalId")
    state = fields.Char(default="acknowledged")
    creation_date = fields.Char(string="creationDate")
    status_change_date = fields.Char(string="statusChangeDate")
    shipping_order_date = fields.Char(string="shippingOrderDate")
    expected_shipping_start_date = fields.Char(string="expectedShippingStartDate")
    expected_shipping_completion_date = fields.Char(string="expectedShippingCompletionDate")
    completion_date = fields.Char(string="completionDate")
    requested_shipping_start_date = fields.Char(string="requestedShippingStartDate")
    requested_shipping_completion_date = fields.Char(string="requestedShippingCompletionDate")
    note = fields.Json(default=list)
    shipping_order_item = fields.Json(default=list)
    related_party = fields.Json(default=list)
    related_shipping_order = fields.Json(default=list)
    related_shipment = fields.Json(default=list)
    place = fields.Json(default=list)
    extra_json = fields.Json(default=dict)

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _get_tmf_api_path(self):
        return "/shippingOrder/v4.0/shippingOrder"

    def to_tmf_json(self):
        self.ensure_one()
        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "@type": "ShippingOrder",
            "state": self.state or "acknowledged",
            "shippingOrderItem": self.shipping_order_item or [],
            "creationDate": self.creation_date or self._now_iso(),
            "statusChangeDate": self.status_change_date or self.creation_date or self._now_iso(),
        }
        if self.external_id:
            payload["externalId"] = self.external_id
        if self.shipping_order_date:
            payload["shippingOrderDate"] = self.shipping_order_date
        if self.expected_shipping_start_date:
            payload["expectedShippingStartDate"] = self.expected_shipping_start_date
        if self.expected_shipping_completion_date:
            payload["expectedShippingCompletionDate"] = self.expected_shipping_completion_date
        if self.completion_date:
            payload["completionDate"] = self.completion_date
        if self.requested_shipping_start_date:
            payload["requestedShippingStartDate"] = self.requested_shipping_start_date
        if self.requested_shipping_completion_date:
            payload["requestedShippingCompletionDate"] = self.requested_shipping_completion_date
        if self.note:
            payload["note"] = self.note
        if self.related_party:
            payload["relatedParty"] = self.related_party
        if self.related_shipping_order:
            payload["relatedShippingOrder"] = self.related_shipping_order
        if self.related_shipment:
            payload["relatedShipment"] = self.related_shipment
        if self.place:
            payload["place"] = self.place
        if isinstance(self.extra_json, dict):
            for key, value in self.extra_json.items():
                if key not in payload:
                    payload[key] = value
        return payload

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="shippingOrder",
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            created = vals.get("creation_date") or self._now_iso()
            vals.setdefault("creation_date", created)
            vals.setdefault("status_change_date", vals.get("status_change_date") or created)
        recs = super().create(vals_list)
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        vals = dict(vals)
        previous = {rec.id: rec.state for rec in self}
        if "state" in vals and "status_change_date" not in vals:
            vals["status_change_date"] = self._now_iso()
        res = super().write(vals)
        for rec in self:
            self._notify("update", rec)
            if "state" in vals and previous.get(rec.id) != rec.state:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="shippingOrder",
                    event_type="delete",
                    resource_json=resource,
                )
            except Exception:
                pass
        return res
