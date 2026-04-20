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
    partner_id = fields.Many2one("res.partner", string="Customer", copy=False, index=True)
    picking_id = fields.Many2one("stock.picking", string="Delivery Picking", copy=False, index=True)

    @staticmethod
    def from_tmf_json(data, partial=False):
        FIELD_MAP = {
            "externalId": "external_id",
            "state": "state",
            "creationDate": "creation_date",
            "statusChangeDate": "status_change_date",
            "shippingOrderDate": "shipping_order_date",
            "expectedShippingStartDate": "expected_shipping_start_date",
            "expectedShippingCompletionDate": "expected_shipping_completion_date",
            "completionDate": "completion_date",
            "requestedShippingStartDate": "requested_shipping_start_date",
            "requestedShippingCompletionDate": "requested_shipping_completion_date",
            "note": "note",
            "shippingOrderItem": "shipping_order_item",
            "relatedParty": "related_party",
            "relatedShippingOrder": "related_shipping_order",
            "relatedShipment": "related_shipment",
            "place": "place",
        }
        vals = {}
        extra = {}
        for k, v in data.items():
            if k.startswith("@") or k in ("id", "href"):
                continue
            if k in FIELD_MAP:
                vals[FIELD_MAP[k]] = v
            else:
                extra[k] = v
        if extra:
            vals["extra_json"] = extra
        return vals

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
        return self._tmf_normalize_payload(payload)

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="shippingOrder",
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    def _resolve_partner(self):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        entries = self.related_party if isinstance(self.related_party, list) else []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            pid = str(entry.get("id") or "").strip()
            pname = str(entry.get("name") or "").strip()
            if pid and "tmf_id" in Partner._fields:
                partner = Partner.search([("tmf_id", "=", pid)], limit=1)
                if partner:
                    return partner
            if pname:
                partner = Partner.search([("name", "=", pname)], limit=1)
                if partner:
                    return partner
                create_vals = {"name": pname}
                if pid and "tmf_id" in Partner._fields:
                    create_vals["tmf_id"] = pid
                return Partner.create(create_vals)
        return Partner

    def _resolve_picking(self):
        self.ensure_one()
        Picking = self.env["stock.picking"].sudo()
        candidates = []
        if self.external_id:
            candidates.append(self.external_id)
        if self.tmf_id:
            candidates.append(self.tmf_id)
        for rel in self.related_shipment or []:
            if isinstance(rel, dict):
                rid = str(rel.get("id") or "").strip()
                if rid:
                    candidates.append(rid)
        for token in candidates:
            picking = Picking.search(
                ["|", ("origin", "=", token), ("name", "=", token)],
                limit=1,
                order="id desc",
            )
            if picking:
                return picking
        return Picking

    def _sync_odoo_links(self):
        for rec in self:
            vals = {}
            partner = rec._resolve_partner()
            if partner and rec.partner_id != partner:
                vals["partner_id"] = partner.id
            picking = rec._resolve_picking()
            if picking and rec.picking_id != picking:
                vals["picking_id"] = picking.id
            if vals:
                rec.with_context(skip_tmf700_sync=True).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            created = vals.get("creation_date") or self._now_iso()
            vals.setdefault("creation_date", created)
            vals.setdefault("status_change_date", vals.get("status_change_date") or created)
        recs = super().create(vals_list)
        recs._sync_odoo_links()
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        vals = dict(vals)
        previous = {rec.id: rec.state for rec in self}
        if "state" in vals and "status_change_date" not in vals:
            vals["status_change_date"] = self._now_iso()
        res = super().write(vals)
        if not self.env.context.get("skip_tmf700_sync"):
            self._sync_odoo_links()
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
