import json
from odoo import http, fields
from odoo.http import request, Response
from odoo.exceptions import ValidationError
import uuid
from datetime import timedelta

def _json_response(payload, status=200, headers=None):
    headers = headers or []
    body = json.dumps(payload, ensure_ascii=False)
    return Response(body, status=status, headers=headers + [("Content-Type", "application/json")])

def _read_json():
    raw = request.httprequest.data or b"{}"
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None

def _tmf_error(status, message):
    return _json_response({"error": message}, status=status)

def _normalize_service_state(state):
    if not state:
        return None

    s = str(state).strip()

    # accept variants CTK might send
    # TMF640 values are like: active, inactive, reserved, designed, terminated, feasabilityChecked :contentReference[oaicite:0]{index=0}
    mapping = {
        "Active": "active",
        "ACTIVE": "active",
        "Inactive": "inactive",
        "INACTIVE": "inactive",
        "Reserved": "reserved",
        "RESERVED": "reserved",
        "Designed": "designed",
        "DESIGNED": "designed",
        "Terminated": "terminated",
        "TERMINATED": "terminated",
        # tolerate spelling/case
        "feasibilityChecked": "feasabilityChecked",
        "FeasibilityChecked": "feasabilityChecked",
        "FeasabilityChecked": "feasabilityChecked",
    }
    if s in mapping:
        return mapping[s]

    # already correct?
    if s in {"active","inactive","reserved","designed","terminated","feasabilityChecked"}:
        return s

    return s  # let validation raise, but we’ll catch and return JSON error


class TMF640Controller(http.Controller):
    base = "/tmf-api/ServiceActivationAndConfiguration/v4"

    # -------------------------
    # Service
    # -------------------------
    @http.route(f"{base}/service", type="http", auth="public", methods=["GET"], csrf=False)
    def list_service(self, **query):
        domain = []

        if "id" in query:
            domain = ["|", ("tmf640_id", "=", query["id"]), ("tmf_id", "=", query["id"])]

        if "serviceDate" in query and query["serviceDate"]:
            try:
                # CTK sends like 2026-01-27T12:47:25
                dt = fields.Datetime.from_string(query["serviceDate"].replace("Z", "").replace("T", " "))
                # tolerant match: +/- 2 seconds
                dt_from = dt - timedelta(seconds=2)
                dt_to = dt + timedelta(seconds=2)
                domain += [("service_date", ">=", dt_from), ("service_date", "<=", dt_to)]
            except Exception:
                # CTK wants 200, return empty list instead of 500
                return _json_response([], status=200)

        services = request.env["tmf640.service"].sudo().search(domain)
        return _json_response([s.to_tmf_json() for s in services], status=200)
    
    # ✅ CTK alias (uppercase)
    @http.route(f"{base}/Service", type="http", auth="public", methods=["GET"], csrf=False)
    def list_Service(self, **query):
        return self.list_service(**query)

    @http.route(f"{base}/service/<string:sid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_service(self, sid, **query):
        svc = request.env["tmf640.service"].sudo().search([("tmf640_id", "=", sid)], limit=1)
        if not svc:
            svc = request.env["tmf640.service"].sudo().browse(int(sid)) if sid.isdigit() else svc
        if not svc or not svc.exists():
            return _tmf_error(404, "Service not found")
        return _json_response(svc.to_tmf_json(), status=200)
    
    # ✅ CTK alias (uppercase)
    @http.route(f"{base}/Service/<string:sid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_Service(self, sid, **query):
        return self.get_service(sid, **query)

    @http.route(f"{base}/service", type="http", auth="public", methods=["POST"], csrf=False)
    def create_service(self, **kwargs):
        try:
            data = _read_json()
            if data is None:
                return _tmf_error(400, "Invalid JSON")

            spec = data.get("serviceSpecification") or {}
            spec_id = spec.get("id")
            if not spec_id:
                return _tmf_error(400, "Missing mandatory field: serviceSpecification.id")

            # normalize state (CTK may send 'Active' etc.)
            state = (data.get("state") or "").strip()
            state_map = {
                "Active": "active", "ACTIVE": "active",
                "Inactive": "inactive", "INACTIVE": "inactive",
                "Reserved": "reserved", "RESERVED": "reserved",
                "Designed": "designed", "DESIGNED": "designed",
                "Terminated": "terminated", "TERMINATED": "terminated",
                "feasibilityChecked": "feasabilityChecked",
                "FeasibilityChecked": "feasabilityChecked",
            }
            state = state_map.get(state, state)
            if not state:
                return _tmf_error(400, "Missing mandatory field: state")

            new_id = data.get("id") or str(uuid.uuid4())

            vals = {
                "tmf640_id": new_id,
                "service_spec_id": spec_id,
                "state": state,
                "service_date": fields.Datetime.now(),  # ensure serviceDate exists
                "name": data.get("name"),
                "description": data.get("description"),
                "category": data.get("category"),
                "service_type": data.get("serviceType"),
            }

            svc = request.env["tmf640.service"].sudo().create(vals)

            href = f"/tmf-api/ServiceActivationAndConfiguration/v4/service/{svc.tmf640_id}"
            svc.sudo().write({"href": href})

            return _json_response(svc.to_tmf_json(), status=201)

        except ValidationError as e:
            return _tmf_error(400, str(e))
        except Exception as e:
            return _tmf_error(500, f"Internal error: {e}")
    
    # ✅ CTK alias (uppercase)
    @http.route(f"{base}/Service", type="http", auth="public", methods=["POST"], csrf=False)
    def create_Service(self, **kwargs):
        return self.create_service(**kwargs)

    @http.route(f"{base}/service/<string:sid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_service(self, sid, **kwargs):
        svc = request.env["tmf640.service"].sudo().search([("tmf640_id", "=", sid)], limit=1)
        if not svc:
            svc = request.env["tmf640.service"].sudo().browse(int(sid)) if sid.isdigit() else svc
        if not svc or not svc.exists():
            return _tmf_error(404, "Service not found")

        data = _read_json()
        if data is None:
            return _tmf_error(400, "Invalid JSON")

        # TMF640: merge patch is mandatory, json-patch optional :contentReference[oaicite:12]{index=12}
        # We'll treat body as merge patch: only update provided keys.
        mapping = {
            "name": "name",
            "description": "description",
            "category": "category",
            "serviceType": "service_type",
            "state": "state",
            "hasStarted": "has_started",
            "isBundle": "is_bundle",
            "isServiceEnabled": "is_service_enabled",
            "isStateful": "is_stateful",
            "@type": "tmf_type",
            "@schemaLocation": "schema_location",
            "@baseType": "base_type",
        }

        vals = {}
        for k, field_name in mapping.items():
            if k in data:
                vals[field_name] = data[k]

        if "serviceSpecification" in data and isinstance(data["serviceSpecification"], dict):
            spec = data["serviceSpecification"]
            if "id" in spec:
                vals["service_spec_id"] = spec["id"]
            if "name" in spec:
                vals["service_spec_name"] = spec["name"]
            if "href" in spec:
                vals["service_spec_href"] = spec["href"]
            if "version" in spec:
                vals["service_spec_version"] = spec["version"]

        for k, field_name in [
            ("serviceCharacteristic", "service_characteristic_json"),
            ("feature", "feature_json"),
            ("relatedParty", "related_party_json"),
            ("supportingService", "supporting_service_json"),
            ("supportingResource", "supporting_resource_json"),
        ]:
            if k in data:
                vals[field_name] = json.dumps(data[k], ensure_ascii=False)

        svc.write(vals)
        return _json_response(svc.to_tmf_json(), status=200)
    
    # ✅ CTK alias (uppercase)
    @http.route(f"{base}/Service/<string:sid>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def patch_Service(self, sid, **kwargs):
        return self.patch_service(sid, **kwargs)

    @http.route(f"{base}/service/<string:sid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_service(self, sid, **kwargs):
        svc = request.env["tmf640.service"].sudo().search([("tmf640_id", "=", sid)], limit=1)
        if not svc:
            svc = request.env["tmf640.service"].sudo().browse(int(sid)) if sid.isdigit() else svc
        if not svc or not svc.exists():
            return _tmf_error(404, "Service not found")

        svc.unlink()
        # Spec uses 204 :contentReference[oaicite:13]{index=13}
        return Response(status=204)
    
    # ✅ CTK alias (uppercase)
    @http.route(f"{base}/Service/<string:sid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def delete_Service(self, sid, **kwargs):
        return self.delete_service(sid, **kwargs)

    # -------------------------
    # Monitor
    # -------------------------
    @http.route(f"{base}/monitor", type="http", auth="public", methods=["GET"], csrf=False)
    def list_monitor(self, **query):
        mons = request.env["tmf640.monitor"].sudo().search([])
        return _json_response([m.to_tmf_json() for m in mons], status=200)

    @http.route(f"{base}/monitor/<string:mid>", type="http", auth="public", methods=["GET"], csrf=False)
    def get_monitor(self, mid, **query):
        mon = request.env["tmf640.monitor"].sudo().search([("tmf640_id", "=", mid)], limit=1)
        if not mon:
            mon = request.env["tmf640.monitor"].sudo().browse(int(mid)) if mid.isdigit() else mon
        if not mon or not mon.exists():
            return _tmf_error(404, "Monitor not found")
        return _json_response(mon.to_tmf_json(), status=200)

    # -------------------------
    # Hub (listener registry)
    # -------------------------
    @http.route(f"{base}/hub", type="http", auth="public", methods=["POST"], csrf=False)
    def register_hub(self, **kwargs):
        data = _read_json()
        if data is None or not data.get("callback"):
            return _tmf_error(400, "Missing callback")

        hub = request.env["tmf640.hub"].sudo().create({
            "callback": data.get("callback"),
            "query": data.get("query"),
        })

        # Spec sample returns 201 + Location header :contentReference[oaicite:14]{index=14}
        headers = [("Location", f"{self.base}/hub/{hub.id}")]
        return _json_response({"id": str(hub.id), "callback": hub.callback, "query": hub.query}, status=201, headers=headers)

    @http.route(f"{base}/hub/<int:hid>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def unregister_hub(self, hid, **kwargs):
        hub = request.env["tmf640.hub"].sudo().browse(hid)
        if not hub.exists():
            return _tmf_error(404, "Hub not found")
        hub.unlink()
        return Response(status=204)
