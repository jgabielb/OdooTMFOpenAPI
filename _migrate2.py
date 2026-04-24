#!/usr/bin/env python3
"""Second-pass migration for modules the first script couldn't parse."""
import ast, os, re, textwrap

ROOT = os.path.dirname(os.path.abspath(__file__))

# Each entry: module_name -> (api_base, [(resource_name, model, path_suffix, required_fields), ...], listener_prefixes)
SPECS = {
    "tmf_5gslice_service_activation": (
        "/tmf-api/ServiceActivationAndConfiguration/v4",
        [("service", "tmf.5gslice.service.activation.resource", "service", []),
         ("monitor", "tmf.5gslice.service.activation.resource", "monitor", [])],
        ["Service", "Monitor"],
    ),
    "tmf_customer360": (
        "/tmf-api/customer360/v4",
        [("customer360", "tmf.customer360", "customer360", [])],
        ["Customer360"],
    ),
    "tmf_entity": (
        "/tmf-api/entityInventory/v4",
        [("entity", "tmf.entity", "entity", []),
         ("association", "tmf.entity.association", "association", [])],
        ["Entity", "Association"],
    ),
    "tmf_event": (
        "/tmf-api/event/v4",
        [("topic", "tmf.event.topic", "topic", ["name"]),
         ("event", "tmf.event", "event", [])],
        ["Topic", "Event"],
    ),
    "tmf_iot_agent_device_management": (
        "/tmf-api/iotdevicemanagement/v4",
        [("device", "tmf.iot.agent.device.resource", "device", []),
         ("agent", "tmf.iot.agent.device.resource", "agent", [])],
        ["Device", "Agent"],
    ),
    "tmf_iot_service_management": (
        "/tmf-api/iotservicemanagement/v4",
        [("iotService", "tmf.iot.service.resource", "iotService", []),
         ("iotServiceSpecification", "tmf.iot.service.resource", "iotServiceSpecification", [])],
        ["IotService", "IotServiceSpecification"],
    ),
    "tmf_network_as_a_service_management": (
        "/tmf-api/naas/v4",
        [("naasRequest", "tmf.naas.resource", "naasRequest", []),
         ("naasTemplate", "tmf.naas.resource", "naasTemplate", [])],
        ["NaasRequest", "NaasTemplate"],
    ),
    "tmf_outage_management": (
        "/tmf-api/outageManagement/v5",
        [("outage", "tmf.outage", "outage", [])],
        ["Outage"],
    ),
    "tmf_performance_management": (
        "/tmf-api/performance/v5",
        [("performanceMeasurementJob", "tmf.performance.management.resource", "performanceMeasurementJob", []),
         ("performanceMeasurementCollection", "tmf.performance.management.resource", "performanceMeasurementCollection", [])],
        ["PerformanceMeasurementJob", "PerformanceMeasurementCollection"],
    ),
    "tmf_process_flow": (
        "/tmf-api/processFlowManagement/v4",
        [("processFlow", "tmf.process.flow", "processFlow", []),
         ("taskFlow", "tmf.task.flow", "taskFlow", []),
         ("processFlowSpecification", "tmf.process.flow.specification", "processFlowSpecification", ["name"]),
         ("taskFlowSpecification", "tmf.task.flow.specification", "taskFlowSpecification", ["name"])],
        ["ProcessFlow", "TaskFlow", "ProcessFlowSpecification", "TaskFlowSpecification"],
    ),
    "tmf_product_usage_catalog_management": (
        "/tmf-api/productUsageCatalogManagement/v5",
        [("productUsageSpecification", "tmf.product.usage.specification", "productUsageSpecification", ["name"])],
        ["ProductUsageSpecification"],
    ),
    "tmf_resource_pool_management": (
        "/tmf-api/resourcePoolManagement/v5",
        [("resourcePool", "tmf.resource.pool", "resourcePool", []),
         ("resourcePoolSpecification", "tmf.resource.pool.specification", "resourcePoolSpecification", ["name"]),
         ("capacitySpecification", "tmf.capacity.specification", "capacitySpecification", ["name"]),
         ("availabilityCheck", "tmf.resource.pool.availability.check", "availabilityCheck", []),
         ("push", "tmf.resource.pool.push", "push", []),
         ("extract", "tmf.resource.pool.extract", "extract", [])],
        ["ResourcePool", "ResourcePoolSpecification", "CapacitySpecification"],
    ),
    "tmf_self_care_management": (
        "/tmf-api/tmf-componentsuite/selfcareapp/v1",
        [("selfCareApp", "tmf.self.care.resource", "selfCareApp", []),
         ("selfCareAppSpecification", "tmf.self.care.resource", "selfCareAppSpecification", [])],
        ["SelfCareApp", "SelfCareAppSpecification"],
    ),
    "tmf_service_level_objective": (
        "/tmf-api/serviceLevelObjectiveManagement/v4",
        [("serviceLevelObjective", "tmf.service.level.objective", "serviceLevelObjective", [])],
        ["ServiceLevelObjective"],
    ),
    "tmf_service_usage_management": (
        "/tmf-api/serviceUsage/v4",
        [("serviceUsage", "tmf.service.usage", "serviceUsage", [])],
        ["ServiceUsage"],
    ),
    "tmf_shipment_tracking_management": (
        "/tmf-api/shipmentTracking/v1",
        [("shipmentTracking", "tmf.shipment.tracking", "shipmentTracking", [])],
        ["ShipmentTracking"],
    ),
    "tmf_shipping_order": (
        "/tmf-api/shippingOrder/v4.0",
        [("shippingOrder", "tmf.shipping.order", "shippingOrder", [])],
        ["ShippingOrder"],
    ),
    "tmf_userinfo": (
        "/tmf-api/federatedIdentity/v5",
        [("userinfo", "tmf.userinfo", "userinfo", [])],
        ["Userinfo"],
    ),
}


def gen_controller(module_name, api_base, resources, listener_prefixes):
    class_name = "".join(w.capitalize() for w in module_name.split("_")).replace("Tmf", "TMF") + "Controller"

    res_dict_lines = []
    for rname, model, path_suffix, required in resources:
        req_str = ", ".join(f'"{r}"' for r in required)
        res_dict_lines.append(f'    "{rname}": {{"model": "{model}", "path": f"{{API_BASE}}/{path_suffix}", "required": [{req_str}]}},')
    res_dict = "\n".join(res_dict_lines)

    route_methods = []
    for rname, model, path_suffix, required in resources:
        safe = re.sub(r'[^a-zA-Z0-9]', '_', rname)
        cap = rname[0].upper() + rname[1:]
        route_methods.append(f'''
    @http.route(
        [RESOURCES["{rname}"]["path"]],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def {safe}_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("{rname}")
        return self._tmf_list("{rname}", **kw)

    @http.route(
        [RESOURCES["{rname}"]["path"] + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def {safe}_individual(self, rid, **kw):
        return self._tmf_individual("{rname}", rid, **kw)''')

    listener_routes = []
    for prefix in listener_prefixes:
        for suffix in ["CreateEvent", "AttributeValueChangeEvent", "StateChangeEvent", "DeleteEvent"]:
            evt = f"{prefix}{suffix}"
            safe = re.sub(r'[^a-zA-Z0-9]', '_', evt).lower()
            listener_routes.append(f'''
    @http.route(f"{{API_BASE}}/listener/{evt}", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_{safe}(self, **_kw):
        return self._listener_ack()''')

    default_api = resources[0][0]

    return f'''# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "{api_base}"
NON_PATCHABLE = {{"id", "href"}}

RESOURCES = {{
{res_dict}
}}


class {class_name}(TMFBaseController):

    def _tmf_list(self, res_key, **kw):
        cfg = RESOURCES[res_key]
        return self._list_response(cfg["model"], [], lambda r: r.to_tmf_json(), kw)

    def _tmf_create(self, res_key):
        cfg = RESOURCES[res_key]
        data = self._parse_json_body()
        if not isinstance(data, dict):
            return self._error(400, "Bad Request", "Invalid JSON body")
        for req in cfg.get("required", []):
            if req not in data:
                return self._error(400, "Bad Request", f"Missing mandatory attribute: {{req}}")
        Model = request.env[cfg["model"]].sudo()
        if hasattr(Model, "from_tmf_json"):
            vals = Model.from_tmf_json(data)
        else:
            vals = data
        rec = Model.create(vals)
        return self._json(rec.to_tmf_json(), status=201)

    def _tmf_individual(self, res_key, rid, **kw):
        cfg = RESOURCES[res_key]
        rid = self._normalize_tmf_id(rid)
        rec = self._find_record(cfg["model"], rid)
        if not rec:
            return self._error(404, "Not Found", f"{{res_key}} {{rid}} not found")
        method = request.httprequest.method
        if method == "GET":
            return self._json(self._select_fields(rec.to_tmf_json(), kw.get("fields")))
        elif method == "PATCH":
            data = self._parse_json_body()
            if not isinstance(data, dict):
                return self._error(400, "Bad Request", "Invalid JSON body")
            illegal = [k for k in data if k in NON_PATCHABLE]
            if illegal:
                return self._error(400, "Bad Request", f"Non-patchable attribute(s): {{', '.join(illegal)}}")
            Model = request.env[cfg["model"]].sudo()
            if hasattr(Model, "from_tmf_json"):
                vals = Model.from_tmf_json(data, partial=True)
            else:
                vals = data
            rec.write(vals)
            return self._json(rec.to_tmf_json())
        elif method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._error(405, "Method Not Allowed", f"{{method}} not supported")

    # Hub
    @http.route(f"{{API_BASE}}/hub", type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def hub(self, **_kw):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search([("callback", "!=", False)])
            return self._json([{{"id": str(s.id), "callback": s.callback, "query": s.query or ""}} for s in subs])
        data = self._parse_json_body()
        callback = (data or {{}}).get("callback")
        if not callback:
            return self._error(400, "Bad Request", "Missing mandatory attribute: callback")
        rec = request.env["tmf.hub.subscription"].sudo().create({{
            "name": f"{module_name}-{{callback}}",
            "api_name": "{default_api}",
            "callback": callback,
            "query": data.get("query", ""),
            "event_type": data.get("eventType") or "any",
            "content_type": "application/json",
        }})
        return self._json({{"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}}, status=201)

    @http.route(f"{{API_BASE}}/hub/<string:sid>", type="http", auth="public", methods=["GET", "DELETE"], csrf=False)
    def hub_detail(self, sid, **_kw):
        if not str(sid).isdigit():
            return self._error(404, "Not Found", f"Hub subscription {{sid}} not found")
        rec = request.env["tmf.hub.subscription"].sudo().browse(int(sid))
        if not rec.exists():
            return self._error(404, "Not Found", f"Hub subscription {{sid}} not found")
        if request.httprequest.method == "DELETE":
            rec.unlink()
            return request.make_response("", status=204)
        return self._json({{"id": str(rec.id), "callback": rec.callback, "query": rec.query or ""}})

    def _listener_ack(self):
        data = self._parse_json_body()
        if not isinstance(data, dict):
            return self._error(400, "Bad Request", "Invalid event payload")
        return request.make_response("", status=201)
{"".join(route_methods)}
{"".join(listener_routes)}
'''


def add_tmf_base_dep(module_dir):
    manifest_path = os.path.join(module_dir, "__manifest__.py")
    if not os.path.exists(manifest_path):
        return
    content = open(manifest_path, "r", encoding="utf-8").read()
    if "tmf_base" in content:
        return
    content = content.replace('"depends": [', '"depends": [\n        "tmf_base",')
    content = content.replace("'depends': [", "'depends': [\n        'tmf_base',")
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


if __name__ == "__main__":
    ok = fail = 0
    for mod, (api_base, resources, listeners) in sorted(SPECS.items()):
        print(f"--- {mod} ---")
        ctrl_dir = os.path.join(ROOT, mod, "controllers")
        ctrl_files = [f for f in os.listdir(ctrl_dir) if f.endswith(".py") and f != "__init__.py"]
        if not ctrl_files:
            print(f"  SKIP: no controller file")
            fail += 1
            continue
        ctrl_path = os.path.join(ctrl_dir, ctrl_files[0])
        content = gen_controller(mod, api_base, resources, listeners)
        try:
            ast.parse(content)
        except SyntaxError as e:
            print(f"  FAIL: syntax error: {e}")
            fail += 1
            continue
        with open(ctrl_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        add_tmf_base_dep(os.path.join(ROOT, mod))
        print(f"  OK -> {ctrl_files[0]}")
        ok += 1
    print(f"\n=== Done: {ok} migrated, {fail} failed ===")
