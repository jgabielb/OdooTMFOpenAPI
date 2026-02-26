import json
from odoo import api, fields, models


def _dumps(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else False


def _loads(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _compact(payload):
    return {k: v for k, v in payload.items() if v is not None and v is not False}


def _state_from_picking(state):
    mapping = {
        "draft": "created",
        "waiting": "inProgress",
        "confirmed": "inProgress",
        "assigned": "inProgress",
        "done": "delivered",
        "cancel": "cancelled",
    }
    return mapping.get((state or "").lower(), "inProgress")


class TMFShipmentTracking(models.Model):
    _name = "tmf.shipment.tracking"
    _description = "TMF684 ShipmentTracking"
    _inherit = ["tmf.model.mixin"]

    name = fields.Char(string="name")
    description = fields.Char(string="description")
    status = fields.Char(string="status", default="created")
    tracking_number = fields.Char(string="trackingNumber")
    estimated_delivery_date = fields.Char(string="estimatedDeliveryDate")
    actual_delivery_date = fields.Char(string="actualDeliveryDate")
    last_update = fields.Char(string="lastUpdate")
    tmf_type_value = fields.Char(string="@type")
    base_type = fields.Char(string="@baseType")
    schema_location = fields.Char(string="@schemaLocation")

    external_identifier_json = fields.Text(string="externalIdentifier")
    related_party_json = fields.Text(string="relatedParty")
    shipment_json = fields.Text(string="shipment")
    current_location_json = fields.Text(string="currentLocation")
    event_json = fields.Text(string="event")
    note_json = fields.Text(string="note")
    payload_json = fields.Text(string="payload")

    partner_id = fields.Many2one("res.partner", string="Customer", copy=False, index=True)
    picking_id = fields.Many2one("stock.picking", string="Stock Picking", copy=False, index=True)

    def _get_tmf_api_path(self):
        return "/shipmentTracking/v4/shipmentTracking"

    def to_tmf_json(self):
        self.ensure_one()
        payload = _loads(self.payload_json) or {}
        payload["id"] = self.tmf_id
        payload["href"] = self.href
        payload["@type"] = self.tmf_type_value or payload.get("@type") or "ShipmentTracking"
        payload["name"] = self.name
        payload["description"] = self.description
        payload["status"] = self.status
        payload["trackingNumber"] = self.tracking_number
        payload["estimatedDeliveryDate"] = self.estimated_delivery_date
        payload["actualDeliveryDate"] = self.actual_delivery_date
        payload["lastUpdate"] = self.last_update
        if self.base_type:
            payload["@baseType"] = self.base_type
        if self.schema_location:
            payload["@schemaLocation"] = self.schema_location
        payload["externalIdentifier"] = _loads(self.external_identifier_json)
        payload["relatedParty"] = _loads(self.related_party_json)
        payload["shipment"] = _loads(self.shipment_json)
        payload["currentLocation"] = _loads(self.current_location_json)
        payload["event"] = _loads(self.event_json)
        payload["note"] = _loads(self.note_json)
        if self.picking_id:
            tracking_ref = self.picking_id.carrier_tracking_ref if "carrier_tracking_ref" in self.picking_id._fields else False
            payload.setdefault("trackingNumber", tracking_ref or self.picking_id.name)
            payload.setdefault("status", _state_from_picking(self.picking_id.state))
            if not payload.get("shipment"):
                payload["shipment"] = {
                    "id": self.picking_id.origin or self.picking_id.name,
                    "@type": "ShipmentRef",
                }
        return self._tmf_normalize_payload(_compact(payload))

    def from_tmf_json(self, data, partial=False):
        vals = {"payload_json": _dumps(data)}
        for key, field_name in [
            ("name", "name"),
            ("description", "description"),
            ("status", "status"),
            ("trackingNumber", "tracking_number"),
            ("estimatedDeliveryDate", "estimated_delivery_date"),
            ("actualDeliveryDate", "actual_delivery_date"),
            ("lastUpdate", "last_update"),
            ("@type", "tmf_type_value"),
            ("@baseType", "base_type"),
            ("@schemaLocation", "schema_location"),
        ]:
            if key in data:
                vals[field_name] = data.get(key)
        for key, field_name in [
            ("externalIdentifier", "external_identifier_json"),
            ("relatedParty", "related_party_json"),
            ("shipment", "shipment_json"),
            ("currentLocation", "current_location_json"),
            ("event", "event_json"),
            ("note", "note_json"),
        ]:
            if key in data:
                vals[field_name] = _dumps(data.get(key))
        return vals

    def _resolve_partner(self):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        related = _loads(self.related_party_json)
        entries = related if isinstance(related, list) else [related]
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
        has_tracking_ref = "carrier_tracking_ref" in Picking._fields
        candidates = []
        if self.tracking_number:
            candidates.append(self.tracking_number)
        shipment = _loads(self.shipment_json)
        if isinstance(shipment, dict):
            sid = str(shipment.get("id") or "").strip()
            if sid:
                candidates.append(sid)
        ext = _loads(self.external_identifier_json)
        if isinstance(ext, list):
            for item in ext:
                if isinstance(item, dict):
                    token = str(item.get("id") or item.get("value") or "").strip()
                    if token:
                        candidates.append(token)
        for token in candidates:
            if has_tracking_ref:
                picking = Picking.search([("carrier_tracking_ref", "=", token)], limit=1)
                if picking:
                    return picking
            picking = Picking.search(["|", ("name", "=", token), ("origin", "=", token)], limit=1, order="id desc")
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
            if picking:
                tracking_ref = picking.carrier_tracking_ref if "carrier_tracking_ref" in picking._fields else False
                if not rec.tracking_number:
                    vals["tracking_number"] = tracking_ref or picking.name
                if not rec.status:
                    vals["status"] = _state_from_picking(picking.state)
            if vals:
                rec.with_context(skip_tmf684_sync=True).write(vals)

    def _notify(self, action, rec):
        try:
            self.env["tmf.hub.subscription"]._notify_subscribers(
                api_name="shipmentTracking",
                event_type=action,
                resource_json=rec.to_tmf_json(),
            )
        except Exception:
            pass

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_odoo_links()
        for rec in recs:
            self._notify("create", rec)
        return recs

    def write(self, vals):
        state_changed = "status" in vals
        res = super().write(vals)
        if not self.env.context.get("skip_tmf684_sync"):
            self._sync_odoo_links()
        for rec in self:
            self._notify("update", rec)
            if state_changed:
                self._notify("state_change", rec)
        return res

    def unlink(self):
        payloads = [rec.to_tmf_json() for rec in self]
        res = super().unlink()
        for payload in payloads:
            try:
                self.env["tmf.hub.subscription"]._notify_subscribers(
                    api_name="shipmentTracking",
                    event_type="delete",
                    resource_json=payload,
                )
            except Exception:
                pass
        return res
