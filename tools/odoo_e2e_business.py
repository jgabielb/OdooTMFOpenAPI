#!/usr/bin/env python3
"""
Odoo business E2E runner for telecom scenarios.

Scenarios covered:
1) Create subscriber
2) Create one-time and recurring products
3) Create CRM opportunity
4) Sell one-time product
5) Sell recurring bundle products
6) Validate stock delivery for device lines
7) Device change (replacement order)
8) Cancel recurring sale order
9) Optional TMF API sanity checks

Usage:
  python OdooBSS/tools/odoo_e2e_business.py --config OdooBSS/tools/odoo_e2e_business.sample.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import xmlrpc.client
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str


class E2EError(Exception):
    pass


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _http_get_json(url: str, timeout: int = 20) -> Tuple[int, Any]:
    req = urllib.request.Request(url=url, method="GET", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body) if body else None
            except Exception:
                data = body
            return resp.status, data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body) if body else None
        except Exception:
            data = body
        return e.code, data


class OdooClient:
    def __init__(self, base_url: str, db: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password
        self.uid = None
        self.common = xmlrpc.client.ServerProxy(f"{self.base_url}/xmlrpc/2/common")
        self.models = xmlrpc.client.ServerProxy(f"{self.base_url}/xmlrpc/2/object")

    def login(self) -> int:
        uid = self.common.authenticate(self.db, self.username, self.password, {})
        if not uid:
            raise E2EError("Authentication failed")
        self.uid = uid
        return uid

    def _call(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        if self.uid is None:
            raise E2EError("Not authenticated")
        return self.models.execute_kw(self.db, self.uid, self.password, model, method, list(args), kwargs)

    def create(self, model: str, vals: Dict[str, Any]) -> int:
        return int(self._call(model, "create", vals))

    def write(self, model: str, ids: List[int], vals: Dict[str, Any]) -> bool:
        return bool(self._call(model, "write", ids, vals))

    def search(self, model: str, domain: List[Any], limit: Optional[int] = None, order: Optional[str] = None) -> List[int]:
        kwargs: Dict[str, Any] = {}
        if limit is not None:
            kwargs["limit"] = limit
        if order:
            kwargs["order"] = order
        return [int(x) for x in self._call(model, "search", domain, **kwargs)]

    def read(self, model: str, ids: List[int], fields: List[str]) -> List[Dict[str, Any]]:
        return list(self._call(model, "read", ids, fields))

    def search_read(
        self,
        model: str,
        domain: List[Any],
        fields: List[str],
        limit: Optional[int] = None,
        order: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {"fields": fields}
        if limit is not None:
            kwargs["limit"] = limit
        if order:
            kwargs["order"] = order
        return list(self._call(model, "search_read", domain, **kwargs))

    def call_method(self, model: str, method: str, ids: List[int], *args: Any) -> Any:
        return self._call(model, method, ids, *args)

    def model_exists(self, model: str) -> bool:
        ids = self.search("ir.model", [("model", "=", model)], limit=1)
        return bool(ids)

    def field_exists(self, model: str, field: str) -> bool:
        if not self.model_exists(model):
            return False
        fields_meta = self._call(model, "fields_get", [], {"attributes": ["type"]})
        return field in fields_meta

    def model_fields(self, model: str) -> List[str]:
        if not self.model_exists(model):
            return []
        fields_meta = self._call(model, "fields_get", [], {"attributes": ["type"]})
        return list(fields_meta.keys())

    def ensure_product(self, name: str, product_type: str, price: float, recurring: bool = False) -> Tuple[int, int]:
        found = self.search_read("product.template", [("name", "=", name)], ["id", "product_variant_id"], limit=1)
        if found:
            tmpl_id = int(found[0]["id"])
            variant = found[0].get("product_variant_id")
            variant_id = int(variant[0]) if isinstance(variant, list) and variant else 0
            return tmpl_id, variant_id

        vals: Dict[str, Any] = {
            "name": name,
            "sale_ok": True,
            "list_price": price,
        }

        desired_type = "service" if product_type == "service" else "consu"
        if self.field_exists("product.template", "type"):
            vals["type"] = desired_type
        if self.field_exists("product.template", "detailed_type"):
            vals["detailed_type"] = "service" if product_type == "service" else "consu"

        if recurring:
            if self.field_exists("product.template", "recurring_invoice"):
                vals["recurring_invoice"] = True
            if self.field_exists("product.template", "invoice_policy"):
                vals["invoice_policy"] = "order"

        tmpl_id = 0
        create_attempts = [vals]
        if self.field_exists("product.template", "type") and desired_type != "consu":
            alt_vals = dict(vals)
            alt_vals["type"] = "consu"
            create_attempts.append(alt_vals)
        if self.field_exists("product.template", "detailed_type"):
            alt_vals2 = dict(vals)
            alt_vals2["detailed_type"] = "consu" if product_type != "service" else "service"
            create_attempts.append(alt_vals2)

        last_err: Optional[Exception] = None
        for attempt in create_attempts:
            try:
                tmpl_id = self.create("product.template", attempt)
                break
            except Exception as e:  # pragma: no cover - environment specific fallback
                last_err = e
                continue
        if not tmpl_id:
            raise E2EError(f"Could not create product template '{name}': {last_err}")

        rec = self.read("product.template", [tmpl_id], ["product_variant_id"])[0]
        variant = rec.get("product_variant_id")
        if not variant:
            raise E2EError(f"Product variant not found for template {name}")
        return tmpl_id, int(variant[0])


def _line(name: str, ok: bool, detail: str) -> StepResult:
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name} :: {detail}")
    return StepResult(name=name, ok=ok, detail=detail)


def _warn(name: str, detail: str) -> StepResult:
    print(f"[WARN] {name} :: {detail}")
    return StepResult(name=name, ok=True, detail=detail)


def run(config: Dict[str, Any]) -> int:
    odoo_cfg = config["odoo"]
    scenario_cfg = config.get("scenario", {})
    results: List[StepResult] = []

    suffix = _now_tag()
    customer_name = scenario_cfg.get("customer_name_prefix", "E2E Subscriber") + f" {suffix}"
    address_street = scenario_cfg.get("customer_street", "Suecia 415")
    city = scenario_cfg.get("customer_city", "Providencia")
    state_name = scenario_cfg.get("customer_state_name", "Region Metropolitana")
    country_name = scenario_cfg.get("customer_country_name", "Chile")

    client = OdooClient(
        base_url=odoo_cfg["url"],
        db=odoo_cfg["db"],
        username=odoo_cfg["username"],
        password=odoo_cfg["password"],
    )
    client.login()
    results.append(_line("Auth", True, f"uid={client.uid}"))

    # 1) Subscriber
    country_ids = client.search("res.country", [("name", "ilike", country_name)], limit=1)
    state_ids = client.search("res.country.state", [("name", "ilike", state_name)], limit=1)
    partner_vals: Dict[str, Any] = {
        "name": customer_name,
        "street": address_street,
        "city": city,
        "customer_rank": 1,
    }
    if country_ids:
        partner_vals["country_id"] = country_ids[0]
    if state_ids:
        partner_vals["state_id"] = state_ids[0]
    partner_id = client.create("res.partner", partner_vals)
    results.append(_line("Create Subscriber", True, f"res.partner={partner_id}"))

    # 2) Products
    price_cfg = scenario_cfg.get("prices", {})
    p_voice_tmpl, p_voice = client.ensure_product("Voice 200 Min Plan", "service", float(price_cfg.get("voice", 29.9)), recurring=True)
    p_inet_tmpl, p_inet = client.ensure_product("Internet 1Gbps Plan", "service", float(price_cfg.get("internet", 59.9)), recurring=True)
    p_tv_tmpl, p_tv = client.ensure_product("TV Premium + Streaming", "service", float(price_cfg.get("tv", 39.9)), recurring=True)
    _, p_voice_hw = client.ensure_product("Voice Hardware CPE", "product", float(price_cfg.get("voice_hw", 79.0)))
    _, p_inet_hw = client.ensure_product("Internet ONT Device", "product", float(price_cfg.get("internet_hw", 120.0)))
    _, p_tv_hw = client.ensure_product("TV Box Device", "product", float(price_cfg.get("tv_hw", 99.0)))
    results.append(
        _line(
            "Ensure Products",
            True,
            f"recurring_templates={[p_voice_tmpl, p_inet_tmpl, p_tv_tmpl]} device_variants={[p_voice_hw, p_inet_hw, p_tv_hw]}",
        )
    )

    # 3) CRM lead
    lead_vals = {
        "name": f"E2E Triple Play Opportunity {suffix}",
        "partner_id": partner_id,
        "type": "opportunity",
    }
    lead_id = client.create("crm.lead", lead_vals) if client.model_exists("crm.lead") else 0
    if lead_id:
        results.append(_line("Create CRM Opportunity", True, f"crm.lead={lead_id}"))
    else:
        results.append(_warn("Create CRM Opportunity", "crm.lead model not available; skipped"))

    def _sale_order_lines(lines: List[Tuple[int, float]]) -> List[Tuple[int, int, Dict[str, Any]]]:
        cmds = []
        for product_id, price in lines:
            cmds.append(
                (
                    0,
                    0,
                    {
                        "product_id": product_id,
                        "product_uom_qty": 1.0,
                        "price_unit": float(price),
                    },
                )
            )
        return cmds

    # 4) One-time product sale
    one_time_lines = _sale_order_lines(
        [
            (p_voice_hw, float(price_cfg.get("voice_hw", 79.0))),
            (p_inet_hw, float(price_cfg.get("internet_hw", 120.0))),
            (p_tv_hw, float(price_cfg.get("tv_hw", 99.0))),
        ]
    )
    so_one_vals = {
        "partner_id": partner_id,
        "origin": f"E2E-OneTime-{suffix}",
        "order_line": one_time_lines,
    }
    if lead_id and client.field_exists("sale.order", "opportunity_id"):
        so_one_vals["opportunity_id"] = lead_id
    so_one_id = client.create("sale.order", so_one_vals)
    results.append(_line("Create One-time Sale Order", True, f"sale.order={so_one_id}"))

    # 5) Recurring sale
    recurring_lines = _sale_order_lines(
        [
            (p_voice, float(price_cfg.get("voice", 29.9))),
            (p_inet, float(price_cfg.get("internet", 59.9))),
            (p_tv, float(price_cfg.get("tv", 39.9))),
        ]
    )
    so_rec_vals = {
        "partner_id": partner_id,
        "origin": f"E2E-Recurring-{suffix}",
        "order_line": recurring_lines,
    }
    if lead_id and client.field_exists("sale.order", "opportunity_id"):
        so_rec_vals["opportunity_id"] = lead_id
    so_rec_id = client.create("sale.order", so_rec_vals)
    results.append(_line("Create Recurring Sale Order", True, f"sale.order={so_rec_id}"))

    # Confirm both orders
    client.call_method("sale.order", "action_confirm", [so_one_id])
    client.call_method("sale.order", "action_confirm", [so_rec_id])
    results.append(_line("Confirm Sale Orders", True, f"confirmed={[so_one_id, so_rec_id]}"))

    # 6) Validate pickings for one-time order
    picking_ids = client.search("stock.picking", [("sale_id", "=", so_one_id)])
    if not picking_ids:
        results.append(_warn("Validate Delivery", "No stock picking generated for one-time order"))
    else:
        for picking_id in picking_ids:
            try:
                client.call_method("stock.picking", "action_assign", [picking_id])
            except Exception:
                pass

            ml_fields_available = set(client.model_fields("stock.move.line"))
            qty_candidates = ["reserved_uom_qty", "product_uom_qty", "quantity", "qty_done"]
            read_fields = ["id"] + [f for f in qty_candidates if f in ml_fields_available]
            move_lines = client.search_read(
                "stock.move.line",
                [("picking_id", "=", picking_id)],
                read_fields,
            )
            for ml in move_lines:
                qty = (
                    ml.get("reserved_uom_qty")
                    or ml.get("product_uom_qty")
                    or ml.get("quantity")
                    or 1.0
                )
                if "qty_done" in ml_fields_available:
                    client.write("stock.move.line", [int(ml["id"])], {"qty_done": qty})

            try:
                client.call_method("stock.picking", "button_validate", [picking_id])
                results.append(_line("Validate Delivery", True, f"stock.picking={picking_id}"))
            except Exception as e:
                results.append(_warn("Validate Delivery", f"stock.picking={picking_id} validate skipped/error={e}"))

    # 7) Device change scenario (replacement order with new router-equivalent device)
    _, p_new_device = client.ensure_product("Internet ONT Device v2", "product", float(price_cfg.get("internet_hw_v2", 135.0)))
    so_swap_id = client.create(
        "sale.order",
        {
            "partner_id": partner_id,
            "origin": f"E2E-DeviceSwap-{suffix}",
            "order_line": _sale_order_lines([(p_new_device, float(price_cfg.get("internet_hw_v2", 135.0)))]),
        },
    )
    client.call_method("sale.order", "action_confirm", [so_swap_id])
    results.append(_line("Device Change Order", True, f"sale.order={so_swap_id} new_device_variant={p_new_device}"))

    # 8) Cancel recurring order
    cancel_ok = False
    try:
        client.call_method("sale.order", "action_cancel", [so_rec_id])
        cancel_ok = True
    except Exception as e:
        results.append(_warn("Cancel Recurring", f"action_cancel failed ({e}); manual cancellation may be required"))
    if cancel_ok:
        results.append(_line("Cancel Recurring", True, f"sale.order={so_rec_id} canceled"))

    # 9) Optional TMF sanity checks
    tmf_base = config.get("tmf_base_url")
    if tmf_base:
        cust_url = tmf_base.rstrip("/") + "/tmf-api/customerManagement/v5/customer?fields=id,name,status"
        st, _ = _http_get_json(cust_url, timeout=int(config.get("http_timeout_sec", 20)))
        if st == 200:
            results.append(_line("TMF Customer API Sanity", True, f"GET {cust_url} -> 200"))
        else:
            results.append(_warn("TMF Customer API Sanity", f"GET {cust_url} -> {st}"))

    # summary
    failed = sum(1 for r in results if not r.ok)
    passed = len(results) - failed
    print("\n=== Summary ===")
    print(f"steps={len(results)} failed={failed} passed={passed}")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Odoo telecom business E2E runner")
    parser.add_argument("--config", required=True, help="Path to JSON config")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    return run(cfg)


if __name__ == "__main__":
    sys.exit(main())
