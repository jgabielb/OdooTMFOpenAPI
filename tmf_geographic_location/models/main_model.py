from odoo import models, fields, api
import json

class TmfGeographicLocation(models.Model):
    _name = 'tmf.geographic.location'
    _description = 'GeographicLocation'
    _inherit = ['tmf.model.mixin']

    # TMF675 mandatory attributes (response)
    name = fields.Char(required=True)
    geometry_type = fields.Char(required=True, string="geometryType")  # e.g. point, line
    accuracy = fields.Char(required=True)
    spatial_ref = fields.Char(required=True, string="spatialRef")      # e.g. WGS84

    # geometry: Array of geographicPoints (store as JSON string)
    # Example:
    # [{"x":"1.430937","y":"43.597208","z":""}]
    geometry = fields.Text(required=True, help="JSON array of geographic points")

    # TMF675 filtering mentions 'type' (and test scenarios use it)
    tmf_type = fields.Char(string="type")

    # Optional / legacy field you already had (not required by TMF675)
    bbox = fields.Char(string="bbox")
    stock_location_id = fields.Many2one("stock.location", string="Stock Location", ondelete="set null")

    def _get_tmf_api_path(self):
        # TMF675 defines {apiRoot}={serverRoot}/location and resource /geographicLocation
        return "/location/geographicLocation"

    def _safe_json_load(self, s, default):
        try:
            if not s:
                return default
            if isinstance(s, (dict, list)):
                return s
            return json.loads(s)
        except Exception:
            return default

    def _resolve_stock_location(self):
        self.ensure_one()
        Location = self.env["stock.location"].sudo()
        if self.stock_location_id and self.stock_location_id.exists():
            return self.stock_location_id
        if self.name:
            location = Location.search([("name", "=", self.name)], limit=1)
            if location:
                return location
        return Location.browse([])

    def _sync_stock_location_link(self):
        for rec in self:
            location = rec._resolve_stock_location()
            if location and location.exists() and rec.stock_location_id != location:
                rec.stock_location_id = location.id

    def to_tmf_json(self, fields_filter=None):
        """
        fields_filter: iterable of top-level keys to include (TMF ?fields= behavior)
        """
        self.ensure_one()

        payload = {
            "id": self.tmf_id,
            "href": self.href,
            "name": self.name,
            "geometryType": self.geometry_type,
            "accuracy": self.accuracy,
            "spatialRef": self.spatial_ref,
            "geometry": self._safe_json_load(self.geometry, []),
        }

        # Optional, but allowed
        if self.tmf_type:
            payload["type"] = self.tmf_type

        # Keep @type optional (allowed by conformance profile)
        payload["@type"] = "GeographicLocation"

        # Apply TMF fields projection:
        # If ?fields=name,type -> only include those keys (do NOT force id/href)
        if fields_filter:
            allowed = set([f.strip() for f in fields_filter if f and f.strip()])
            payload = {k: v for k, v in payload.items() if k in allowed}

        return self._tmf_normalize_payload(payload)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_stock_location_link()
        for rec in recs:
            rec._notify('geographicLocation', 'create', rec)
        return recs

    def write(self, vals):
        res = super().write(vals)
        if "name" in vals or "stock_location_id" in vals:
            self._sync_stock_location_link()
        for rec in self:
            rec._notify('geographicLocation', 'update', rec)
        return res

    def unlink(self):
        payloads = [r.to_tmf_json() for r in self]
        res = super().unlink()
        for resource in payloads:
            try:
                self.env['tmf.hub.subscription']._notify_subscribers(
                    api_name='geographicLocation',
                    event_type='delete',
                    resource_json=resource,
                )
            except Exception:
                pass
        return res

    def _notify(self, api_name, action, record):
        try:
            self.env['tmf.hub.subscription']._notify_subscribers(
                api_name=api_name,
                event_type=action,
                resource_json=record.to_tmf_json(),
            )
        except Exception:
            pass
