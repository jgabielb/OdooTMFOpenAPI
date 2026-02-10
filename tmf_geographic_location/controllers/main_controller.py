from odoo import http
from odoo.http import request
import json

def _parse_fields(params):
    raw = (params.get("fields") or "").strip()
    if not raw:
        return None
    return [x.strip() for x in raw.split(",") if x.strip()]

def _json_response(payload, status=200):
    return request.make_response(
        json.dumps(payload),
        headers=[("Content-Type", "application/json")],
        status=status
    )

class TMF675GeographicLocationController(http.Controller):

    # --- TMF675 compliant paths (as per conformance profile)
    @http.route('/location/geographicLocation', type='http', auth='public', methods=['GET'], csrf=False)
    def list_geographic_location(self, **params):
        fields_filter = _parse_fields(params)

        domain = []
        if params.get("name"):
            domain.append(("name", "=", params["name"]))
        if params.get("type"):
            domain.append(("tmf_type", "=", params["type"]))

        # Although table mentions name/type, test scenario uses spatialRef=WGS84
        if params.get("spatialRef"):
            domain.append(("spatial_ref", "=", params["spatialRef"]))

        records = request.env['tmf.geographic.location'].sudo().search(domain)
        return _json_response([r.to_tmf_json(fields_filter=fields_filter) for r in records], status=200)

    @http.route('/location/geographicLocation/<string:location_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_geographic_location_by_id(self, location_id, **params):
        fields_filter = _parse_fields(params)

        rec = request.env['tmf.geographic.location'].sudo().search([("tmf_id", "=", location_id)], limit=1)
        if not rec:
            # TMF675 error scenario expects 404 for unknown id
            return _json_response({"error": "Not Found"}, status=404)

        return _json_response(rec.to_tmf_json(fields_filter=fields_filter), status=200)

    # --- Compatibility aliases (optional, but keeps your TMF API base)
    @http.route('/tmf-api/geographicLocationManagement/v4/geographicLocation', type='http', auth='public', methods=['GET'], csrf=False)
    def list_geographic_location_alias(self, **params):
        return self.list_geographic_location(**params)

    @http.route('/tmf-api/geographicLocationManagement/v4/geographicLocation/<string:location_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_geographic_location_by_id_alias(self, location_id, **params):
        return self.get_geographic_location_by_id(location_id, **params)
