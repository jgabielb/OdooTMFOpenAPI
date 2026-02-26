from odoo import http
from odoo.http import request
import json

class TMFController(http.Controller):
    API_BASE = "/tmf-api/serviceLevelObjectiveManagement/v4/ServiceLevelObjective"

    @staticmethod
    def _json_response(payload, status=200, headers=None):
        hdrs = [("Content-Type", "application/json")]
        if headers:
            hdrs.extend(headers)
        return request.make_response(json.dumps(payload), headers=hdrs, status=status)

    @staticmethod
    def _get_json_body():
        raw = request.httprequest.data or b""
        if not raw:
            return {}
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    @staticmethod
    def _map_payload_to_vals(data):
        mapping = {
            "conformanceComparator": "conformance_comparator",
            "conformanceTarget": "conformance_target",
            "graceTimes": "grace_times",
            "name": "name",
            "thresholdTarget": "threshold_target",
            "toleranceTarget": "tolerance_target",
            "conformancePeriod": "conformance_period",
            "serviceLevelObjectiveConsequence": "service_level_objective_consequence",
            "serviceLevelObjectiveParameter": "service_level_objective_parameter",
            "tolerancePeriod": "tolerance_period",
            "validFor": "valid_for",
        }
        vals = {}
        for src, dst in mapping.items():
            if src in data:
                vals[dst] = data[src]
        return vals

    @http.route(API_BASE, type='http', auth='public', methods=['GET'], csrf=False)
    def get_resources(self, **params):
        records = request.env['tmf.service.level.objective'].sudo().search([])
        return self._json_response([r.to_tmf_json() for r in records], status=200)

    @http.route(f"{API_BASE}/<string:tmf_id>", type='http', auth='public', methods=['GET'], csrf=False)
    def get_resource(self, tmf_id, **params):
        rec = request.env['tmf.service.level.objective'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if not rec:
            return self._json_response({"error": "NotFound", "message": "ServiceLevelObjective not found"}, status=404)
        return self._json_response(rec.to_tmf_json(), status=200)

    @http.route(API_BASE, type='http', auth='public', methods=['POST'], csrf=False)
    def create_resource(self, **params):
        try:
            data = self._get_json_body()
            vals = self._map_payload_to_vals(data)
            new_rec = request.env['tmf.service.level.objective'].sudo().create(vals)
            return self._json_response(
                new_rec.to_tmf_json(),
                status=201,
                headers=[("Location", f"{self.API_BASE}/{new_rec.tmf_id}")],
            )
        except Exception as e:
            return self._json_response({'error': str(e)}, status=400)

    @http.route(f"{API_BASE}/<string:tmf_id>", type='http', auth='public', methods=['PATCH'], csrf=False)
    def patch_resource(self, tmf_id, **params):
        rec = request.env['tmf.service.level.objective'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if not rec:
            return self._json_response({"error": "NotFound", "message": "ServiceLevelObjective not found"}, status=404)
        try:
            data = self._get_json_body()
            vals = self._map_payload_to_vals(data)
            if vals:
                rec.write(vals)
            return self._json_response(rec.to_tmf_json(), status=200)
        except Exception as e:
            return self._json_response({'error': str(e)}, status=400)

    @http.route(f"{API_BASE}/<string:tmf_id>", type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_resource(self, tmf_id, **params):
        rec = request.env['tmf.service.level.objective'].sudo().search([('tmf_id', '=', tmf_id)], limit=1)
        if rec:
            rec.unlink()
        return request.make_response("", status=204)
