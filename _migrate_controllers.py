#!/usr/bin/env python3
"""
Migrate non-CTK TMF module controllers to use TMFBaseController.

For each module:
1. Rewrite controller to subclass TMFBaseController
2. Remove inline helpers (_json_response, _error, _parse_json, _find_record, _fields_filter)
3. Use BaseController methods (self._json, self._error, self._parse_json_body, etc.)
4. Add tmf_base to manifest depends
5. Fill missing CRUD routes on bare modules
"""
import ast
import os
import re
import json

ROOT = os.path.dirname(os.path.abspath(__file__))

# Modules to migrate and their TMF metadata
MODULES = {
    "tmf_5gslice_service_activation": {"tmf": "TMF924", "api_base": "/tmf-api/5gSliceServiceActivation/v4"},
    "tmf_ai_contract_specification": {"tmf": "TMF917", "api_base": "/tmf-api/aiContractSpecification/v4"},
    "tmf_cost_management": {"tmf": "TMF764", "api_base": "/tmf-api/costManagement/v5"},
    "tmf_customer360": {"tmf": "TMF717", "api_base": "/tmf-api/customer360Management/v4"},
    "tmf_device": {"tmf": "TMF908", "api_base": "/tmf-api/deviceManagement/v4"},
    "tmf_dunning_case_management": {"tmf": "TMF728", "api_base": "/tmf-api/dunningCaseManagement/v4"},
    "tmf_entity": {"tmf": "TMF703", "api_base": "/tmf-api/entityCatalogManagement/v4"},
    "tmf_event": {"tmf": "TMF688", "api_base": "/tmf-api/eventManagement/v4"},
    "tmf_iot_agent_device_management": {"tmf": "TMF908b", "api_base": "/tmf-api/iotAgentDeviceManagement/v4"},
    "tmf_iot_service_management": {"tmf": "TMF914", "api_base": "/tmf-api/iotServiceManagement/v4"},
    "tmf_managed_entity": {"tmf": "TMF703b", "api_base": "/tmf-api/managedEntityManagement/v4"},
    "tmf_metadata_catalog_management": {"tmf": "TMF725", "api_base": "/tmf-api/metadataCatalogManagement/v4"},
    "tmf_network_as_a_service_management": {"tmf": "TMF909", "api_base": "/tmf-api/networkAsAServiceManagement/v4"},
    "tmf_outage_management": {"tmf": "TMF777", "api_base": "/tmf-api/outageManagement/v4"},
    "tmf_performance_management": {"tmf": "TMF628", "api_base": "/tmf-api/performance/v5"},
    "tmf_private_optimized_binding": {"tmf": "TMF759", "api_base": "/tmf-api/privateOptimizedBinding/v4"},
    "tmf_process_flow": {"tmf": "TMF701", "api_base": "/tmf-api/processFlowManagement/v4"},
    "tmf_product_usage_catalog_management": {"tmf": "TMF767", "api_base": "/tmf-api/productUsageCatalogManagement/v4"},
    "tmf_resource_pool_management": {"tmf": "TMF685", "api_base": "/tmf-api/resourcePoolManagement/v5"},
    "tmf_resource_role_management": {"tmf": "TMF768", "api_base": "/tmf-api/resourceRoleManagement/v4"},
    "tmf_self_care_management": {"tmf": "TMF910", "api_base": "/tmf-api/selfCareManagement/v4"},
    "tmf_service_level_objective": {"tmf": "TMF623", "api_base": "/tmf-api/serviceLevelObjective/v4"},
    "tmf_service_usage_management": {"tmf": "TMF727", "api_base": "/tmf-api/serviceUsageManagement/v4"},
    "tmf_shipment_management": {"tmf": "TMF711", "api_base": "/tmf-api/shipmentManagement/v4"},
    "tmf_shipment_tracking_management": {"tmf": "TMF684", "api_base": "/tmf-api/shipmentTrackingManagement/v4"},
    "tmf_shipping_order": {"tmf": "TMF700", "api_base": "/tmf-api/shippingOrder/v4"},
    "tmf_userinfo": {"tmf": "TMF691", "api_base": "/tmf-api/userInfoManagement/v4"},
    "tmf_warranty_management": {"tmf": "TMF715", "api_base": "/tmf-api/warrantyManagement/v4"},
    "tmf_work_management": {"tmf": "TMF713", "api_base": "/tmf-api/workManagement/v4"},
    "tmf_work_qualification": {"tmf": "TMF714", "api_base": "/tmf-api/workQualification/v4"},
}


def add_tmf_base_dep(module_dir):
    """Add tmf_base to manifest depends if not already there."""
    manifest_path = os.path.join(module_dir, "__manifest__.py")
    if not os.path.exists(manifest_path):
        return
    content = open(manifest_path, "r", encoding="utf-8").read()
    if "tmf_base" in content:
        return
    # Insert tmf_base as first dep
    content = content.replace('"depends": [', '"depends": [\n        "tmf_base",')
    content = content.replace("'depends': [", "'depends': [\n        'tmf_base',")
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print(f"  + tmf_base dep added to manifest")


def extract_routes_and_resources(content):
    """Parse existing controller to extract route paths and RESOURCES dict."""
    routes = []
    # Find all @http.route decorators
    for m in re.finditer(r'@http\.route\([\'"]([^\'"]+)[\'"]', content):
        routes.append(m.group(1))
    for m in re.finditer(r'@http\.route\(\[([^\]]+)\]', content):
        paths = re.findall(r'[\'"]([^\'"]+)[\'"]', m.group(1))
        routes.extend(paths)

    # Try to extract RESOURCES dict
    resources = {}
    res_match = re.search(r'RESOURCES\s*=\s*\{', content)
    if res_match:
        # Try to parse from the match
        brace_count = 0
        start = res_match.start()
        for i, c in enumerate(content[start:], start):
            if c == '{':
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0:
                    try:
                        # Replace f-strings with placeholders for eval
                        block = content[start:i+1]
                        block = re.sub(r'RESOURCES\s*=\s*', '', block)
                        # This won't work with f-strings, fall back to regex
                    except:
                        pass
                    break

    return routes


def extract_models_from_controller(content):
    """Find all Odoo model names referenced in the controller."""
    models = set()
    for m in re.finditer(r'''request\.env\[['"]([^'"]+)['"]\]''', content):
        models.add(m.group(1))
    for m in re.finditer(r'''"model"\s*:\s*['"]([^'"]+)['"]''', content):
        models.add(m.group(1))
    return models


def extract_api_paths(content):
    """Extract all unique API base paths from routes."""
    paths = set()
    for m in re.finditer(r'[\'"](/[^<\'"]+?)/[^/<\'"]+[\'"]', content):
        paths.add(m.group(1))
    # Also check API_BASE
    for m in re.finditer(r'API_BASE\s*=\s*[\'"]([^\'"]+)[\'"]', content):
        paths.add(m.group(1))
    return paths


def get_resource_info(content):
    """Extract resource names, models, paths from RESOURCES dict or routes."""
    resources = []

    # Try RESOURCES dict pattern
    for m in re.finditer(
        r'''['"]([\w]+)['"]\s*:\s*\{[^}]*?['"]model['"]\s*:\s*['"]([^'"]+)['"][^}]*?['"]path['"]\s*:\s*['"]([^'"]+)['"]''',
        content, re.DOTALL
    ):
        name, model, path = m.group(1), m.group(2), m.group(3)
        # Check for required fields
        req_match = re.search(
            rf'''['"]{re.escape(name)}['"]\s*:\s*\{{[^}}]*?['"]required['"]\s*:\s*\[([^\]]*)\]''',
            content, re.DOTALL
        )
        required = []
        if req_match:
            required = re.findall(r'[\'"]([^\'"]+)[\'"]', req_match.group(1))
        resources.append({"name": name, "model": model, "path": path, "required": required})

    # Try f-string RESOURCES pattern
    if not resources:
        for m in re.finditer(
            r'''['"]([\w]+)['"]\s*:\s*\{[^}]*?['"]model['"]\s*:\s*['"]([^'"]+)['"][^}]*?['"]path['"]\s*:\s*f['"]([^'"]+)['"]''',
            content, re.DOTALL
        ):
            name, model, path_template = m.group(1), m.group(2), m.group(3)
            # Resolve f-string {API_BASE}
            api_base_match = re.search(r'API_BASE\s*=\s*[\'"]([^\'"]+)[\'"]', content)
            if api_base_match:
                path = path_template.replace("{API_BASE}", api_base_match.group(1))
            else:
                path = path_template
            req_match = re.search(
                rf'''['"]{re.escape(name)}['"]\s*:\s*\{{[^}}]*?['"]required['"]\s*:\s*\[([^\]]*)\]''',
                content, re.DOTALL
            )
            required = []
            if req_match:
                required = re.findall(r'[\'"]([^\'"]+)[\'"]', req_match.group(1))
            resources.append({"name": name, "model": model, "path": path, "required": required})

    return resources


def generate_controller(module_name, ctrl_content):
    """Generate a new controller using TMFBaseController pattern."""
    # Extract API_BASE
    api_base_match = re.search(r'API_BASE\s*=\s*[\'"]([^\'"]+)[\'"]', ctrl_content)
    if not api_base_match:
        # Try API_ROOT
        api_base_match = re.search(r'API_ROOT\s*=\s*[\'"]([^\'"]+)[\'"]', ctrl_content)
    api_base = api_base_match.group(1) if api_base_match else f"/tmf-api/{module_name.replace('tmf_', '')}/v4"

    # Get resources
    resources = get_resource_info(ctrl_content)

    # If no RESOURCES found, try to extract from routes
    if not resources:
        models = extract_models_from_controller(ctrl_content)
        # Filter out hub subscription model
        models = [m for m in models if m != "tmf.hub.subscription"]

        # Try to find paths from routes
        route_paths = []
        for m in re.finditer(r'''@http\.route\(['"](/[^'"<]+)['"]\s*,''', ctrl_content):
            p = m.group(1)
            if '/hub' not in p and '/listener' not in p:
                route_paths.append(p)
        for m in re.finditer(r'''@http\.route\(\[[^\]]*?['"](/[^'"<]+)['"]\s*[\],]''', ctrl_content):
            p = m.group(1)
            if '/hub' not in p and '/listener' not in p:
                route_paths.append(p)

        # Deduplicate paths and extract resource name from path
        seen_paths = set()
        for p in route_paths:
            if p not in seen_paths:
                seen_paths.add(p)
                res_name = p.rstrip("/").split("/")[-1]
                # Find matching model
                model = None
                for mdl in models:
                    if res_name.lower().replace("_", "") in mdl.lower().replace(".", "").replace("_", ""):
                        model = mdl
                        break
                if not model and models:
                    model = list(models)[0]
                if model:
                    resources.append({"name": res_name, "model": model, "path": p, "required": []})

    if not resources:
        return None  # Can't determine structure

    # Extract hub api_name pattern
    hub_api_match = re.search(r'''api_name.*?['"]([\w]+)['"]''', ctrl_content)
    default_api = hub_api_match.group(1) if hub_api_match else resources[0]["name"]

    # Extract listener event routes
    listener_events = []
    for m in re.finditer(r'''listener/([\w]+)Event''', ctrl_content):
        listener_events.append(m.group(1) + "Event")

    # Detect NON_PATCHABLE
    non_patch_match = re.search(r'NON_PATCHABLE\s*=\s*\{([^}]+)\}', ctrl_content)
    non_patchable = '{"id", "href"}' if non_patch_match else '{"id", "href"}'

    # Detect _guess_api_name logic
    guess_fn_match = re.search(r'def _guess_api_name\(.*?\):\s*\n(.*?)(?=\ndef |\nclass |\Z)', ctrl_content, re.DOTALL)

    # Build class name
    class_name = "".join(word.capitalize() for word in module_name.split("_")) + "Controller"
    class_name = class_name.replace("Tmf", "TMF")

    # Generate RESOURCES dict
    res_dict_lines = []
    for r in resources:
        req_str = ", ".join(f'"{rq}"' for rq in r["required"])
        res_dict_lines.append(f'''    "{r['name']}": {{
        "model": "{r['model']}",
        "path": f"{{API_BASE}}/{r['name']}",
        "required": [{req_str}],
    }},''')
    res_dict = "\n".join(res_dict_lines)

    # Generate route methods
    route_methods = []
    for r in resources:
        rname = r["name"]
        rname_cap = rname[0].upper() + rname[1:]
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', rname)

        route_methods.append(f'''
    @http.route(
        [RESOURCES["{rname}"]["path"], RESOURCES["{rname}"]["path"].replace("{rname}", "{rname_cap}")],
        type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def {safe_name}_collection(self, **kw):
        if request.httprequest.method == "POST":
            return self._tmf_create("{rname}")
        return self._tmf_list("{rname}", **kw)

    @http.route(
        [RESOURCES["{rname}"]["path"] + "/<string:rid>",
         RESOURCES["{rname}"]["path"].replace("{rname}", "{rname_cap}") + "/<string:rid>"],
        type="http", auth="public", methods=["GET", "PATCH", "DELETE"], csrf=False)
    def {safe_name}_individual(self, rid, **kw):
        return self._tmf_individual("{rname}", rid, **kw)''')

    # Generate listener routes
    listener_routes = []
    event_prefixes = set()
    for r in resources:
        rname = r["name"]
        rname_cap = rname[0].upper() + rname[1:]
        event_prefixes.add(rname_cap)

    for prefix in sorted(event_prefixes):
        for suffix in ["CreateEvent", "AttributeValueChangeEvent", "StateChangeEvent", "DeleteEvent"]:
            evt = f"{prefix}{suffix}"
            safe = re.sub(r'[^a-zA-Z0-9]', '_', evt)
            listener_routes.append(f'''
    @http.route(f"{{API_BASE}}/listener/{evt}", type="http", auth="public", methods=["POST"], csrf=False)
    def listener_{safe}(self, **_kw):
        return self._listener_ack()''')

    # Build the new controller
    new_content = f'''# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tmf_base.controllers.base_controller import TMFBaseController

_logger = logging.getLogger(__name__)

API_BASE = "{api_base}"
NON_PATCHABLE = {non_patchable}

RESOURCES = {{
{res_dict}
}}


class {class_name}(TMFBaseController):

    # ------------------------------------------------------------------
    # Generic CRUD using TMFBaseController helpers
    # ------------------------------------------------------------------

    def _tmf_list(self, res_key, **kw):
        cfg = RESOURCES[res_key]
        model = cfg["model"]
        domain = []
        for key, val in kw.items():
            if key in ("fields", "offset", "limit", "sort"):
                continue
            if val and hasattr(request.env[model], key):
                domain.append((key, "=", val))
        return self._list_response(model, domain, lambda r: r.to_tmf_json(), kw)

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

    # ------------------------------------------------------------------
    # Hub
    # ------------------------------------------------------------------

    @http.route(f"{{API_BASE}}/hub", type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def hub(self, **_kw):
        if request.httprequest.method == "GET":
            subs = request.env["tmf.hub.subscription"].sudo().search(
                [("callback", "!=", False)])
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

    # ------------------------------------------------------------------
    # Listener (acknowledge only)
    # ------------------------------------------------------------------

    def _listener_ack(self):
        data = self._parse_json_body()
        if not isinstance(data, dict):
            return self._error(400, "Bad Request", "Invalid event payload")
        return request.make_response("", status=201)

    # ------------------------------------------------------------------
    # Resource routes
    # ------------------------------------------------------------------
{"".join(route_methods)}

    # ------------------------------------------------------------------
    # Listener routes
    # ------------------------------------------------------------------
{"".join(listener_routes)}
'''
    return new_content


def process_module(module_name):
    module_dir = os.path.join(ROOT, module_name)
    if not os.path.isdir(module_dir):
        print(f"SKIP {module_name}: directory not found")
        return False

    # Find controller file
    ctrl_dir = os.path.join(module_dir, "controllers")
    ctrl_files = [f for f in os.listdir(ctrl_dir) if f.endswith(".py") and f != "__init__.py"] if os.path.isdir(ctrl_dir) else []

    if not ctrl_files:
        print(f"SKIP {module_name}: no controller files")
        return False

    ctrl_path = os.path.join(ctrl_dir, ctrl_files[0])
    ctrl_content = open(ctrl_path, "r", encoding="utf-8").read()

    # Skip if already migrated
    if "TMFBaseController" in ctrl_content:
        print(f"SKIP {module_name}: already uses TMFBaseController")
        return False

    new_content = generate_controller(module_name, ctrl_content)
    if not new_content:
        print(f"FAIL {module_name}: could not parse controller structure")
        return False

    # Validate syntax
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        print(f"FAIL {module_name}: generated code has syntax error: {e}")
        # Write anyway for manual fixing
        with open(ctrl_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)
        return False

    # Write
    with open(ctrl_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)

    # Add tmf_base dep
    add_tmf_base_dep(module_dir)

    print(f"  OK {module_name} -> {ctrl_files[0]}")
    return True


if __name__ == "__main__":
    ok = 0
    fail = 0
    for mod in sorted(MODULES):
        print(f"\n--- {mod} ---")
        if process_module(mod):
            ok += 1
        else:
            fail += 1
    print(f"\n=== Done: {ok} migrated, {fail} skipped/failed ===")
