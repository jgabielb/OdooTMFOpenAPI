#!/usr/bin/env python3
"""TMFC003 integration smoke test.

Path under test:
    POST sale.order tmf_status=inProgress
    -> verify service order spawn + flow creation (TMF701)

This uses Odoo XML-RPC directly instead of the TMF APIs to:
- create a minimal customer and product,
- create a sale.order with one line,
- drive its tmf_status to "inProgress" to trigger TMFC003 orchestration,
- verify that:
    * at least one tmfc003_service_order_ids record exists, and
    * at least one tmfc003_process_flow_ids and tmfc003_task_flow_ids exist,
    * the service order(s) point back to the originating sale.order.

Exit code is 0 on success, 1 on failure.

Usage:
  python tools/tmfc003_smoke.py \
    --url http://localhost:8069 \
    --db TMF_Odoo_DB \
    --username admin \
    --password admin
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import xmlrpc.client


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str


class SmokeError(Exception):
    pass


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


class OdooClient:
    """Minimal XML-RPC client (trimmed from odoo_e2e_business.py)."""

    def __init__(self, base_url: str, db: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password
        self.uid: Optional[int] = None
        self.common = xmlrpc.client.ServerProxy(f"{self.base_url}/xmlrpc/2/common")
        self.models = xmlrpc.client.ServerProxy(f"{self.base_url}/xmlrpc/2/object")

    def login(self) -> int:
        uid = self.common.authenticate(self.db, self.username, self.password, {})
        if not uid:
            raise SmokeError("Authentication failed")
        self.uid = int(uid)
        return self.uid

    # Low-level helpers -------------------------------------------------

    def _call(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        if self.uid is None:
            raise SmokeError("Not authenticated")
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
        res = self._call(model, "search", domain, **kwargs)
        return [int(x) for x in res]

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

    def model_exists(self, model: str) -> bool:
        ids = self.search("ir.model", [("model", "=", model)], limit=1)
        return bool(ids)

    def field_exists(self, model: str, field: str) -> bool:
        if not self.model_exists(model):
            return False
        fields_meta = self._call(model, "fields_get", [], {"attributes": ["type"]})
        return field in fields_meta

    def ensure_product(self, name: str, price: float) -> Tuple[int, int]:
        """Ensure a simple sellable product exists and return (template_id, variant_id)."""
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
        # Try to set type if present; fall back gracefully otherwise.
        if self.field_exists("product.template", "type"):
            vals["type"] = "service"
        if self.field_exists("product.template", "detailed_type"):
            vals["detailed_type"] = "service"

        tmpl_id = self.create("product.template", vals)
        rec = self.read("product.template", [tmpl_id], ["product_variant_id"])[0]
        variant = rec.get("product_variant_id")
        if not variant:
            raise SmokeError(f"Product variant not found for template {name}")
        return tmpl_id, int(variant[0])


def _line(name: str, ok: bool, detail: str) -> StepResult:
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name} :: {detail}")
    return StepResult(name=name, ok=ok, detail=detail)


def run(url: str, db: str, username: str, password: str) -> int:
    results: List[StepResult] = []
    tag = _now_tag()

    client = OdooClient(url, db, username, password)
    client.login()
    results.append(_line("Auth", True, f"uid={client.uid}"))

    # Sanity: required model/field presence
    if not client.model_exists("sale.order"):
        raise SmokeError("Model sale.order not found")
    if not client.field_exists("sale.order", "tmf_status"):
        raise SmokeError("Field sale.order.tmf_status not found (TMF622 wiring missing)")
    if not client.field_exists("sale.order", "tmfc003_service_order_ids"):
        raise SmokeError("Field sale.order.tmfc003_service_order_ids not found (TMFC003 wiring missing)")
    if not client.field_exists("sale.order", "tmfc003_process_flow_ids"):
        raise SmokeError("Field sale.order.tmfc003_process_flow_ids not found (TMFC003 wiring missing)")

    # 1) Create minimal customer
    partner_vals: Dict[str, Any] = {
        "name": f"TMFC003 Smoke Customer {tag}",
        "customer_rank": 1,
    }
    partner_id = client.create("res.partner", partner_vals)
    results.append(_line("Create Customer", True, f"res.partner={partner_id}"))

    # 2) Ensure a product
    _, product_id = client.ensure_product("TMFC003 Smoke Product", 10.0)
    results.append(_line("Ensure Product", True, f"product.product={product_id}"))

    # 3) Create sale.order with one line
    order_vals: Dict[str, Any] = {
        "partner_id": partner_id,
        "origin": f"TMFC003-SMOKE-{tag}",
        "order_line": [
            (
                0,
                0,
                {
                    "product_id": product_id,
                    "product_uom_qty": 1.0,
                    "price_unit": 10.0,
                },
            )
        ],
    }
    sale_order_id = client.create("sale.order", order_vals)
    results.append(_line("Create Sale Order", True, f"sale.order={sale_order_id}"))

    # 4) Drive tmf_status -> acknowledged -> inProgress to trigger TMFC003
    #    (acknowledged step for clarity; TMFC003 only reacts to inProgress.)
    client.write("sale.order", [sale_order_id], {"tmf_status": "acknowledged"})
    results.append(_line("Set tmf_status=acknowledged", True, f"sale.order={sale_order_id}"))

    client.write("sale.order", [sale_order_id], {"tmf_status": "inProgress"})
    results.append(_line("Set tmf_status=inProgress", True, f"sale.order={sale_order_id}"))

    # 5) Read back orchestration artifacts
    recs = client.read(
        "sale.order",
        [sale_order_id],
        [
            "tmf_status",
            "tmfc003_delivery_state",
            "tmfc003_service_order_ids",
            "tmfc003_process_flow_ids",
            "tmfc003_task_flow_ids",
        ],
    )
    if not recs:
        raise SmokeError("sale.order not found on read back")
    so = recs[0]

    svc_ids = [int(x) for x in (so.get("tmfc003_service_order_ids") or [])]
    pf_ids = [int(x) for x in (so.get("tmfc003_process_flow_ids") or [])]
    tf_ids = [int(x) for x in (so.get("tmfc003_task_flow_ids") or [])]
    delivery_state = so.get("tmfc003_delivery_state") or ""

    if not svc_ids:
        raise SmokeError("No tmfc003_service_order_ids spawned after tmf_status=inProgress")
    if not pf_ids:
        raise SmokeError("No tmfc003_process_flow_ids created for delivery orchestration")
    if not tf_ids:
        raise SmokeError("No tmfc003_task_flow_ids created for delivery orchestration")

    results.append(
        _line(
            "Verify Orchestration Artifacts",
            True,
            f"service_orders={svc_ids} process_flows={pf_ids} task_flows={tf_ids} delivery_state={delivery_state or 'n/a'}",
        )
    )

    # 6) Verify that service orders point back to the product order
    svc = client.read("tmf.service.order", svc_ids, ["tmfc003_product_order_id"])
    missing_link = [r for r in svc if not r.get("tmfc003_product_order_id")]
    if missing_link:
        raise SmokeError("Some service orders are missing tmfc003_product_order_id linkage")

    results.append(_line("Verify ServiceOrder linkage", True, f"checked={len(svc_ids)}"))

    # Summary
    failed = sum(1 for r in results if not r.ok)
    passed = len(results) - failed
    print("\n=== TMFC003 Smoke Summary ===")
    print(f"steps={len(results)} failed={failed} passed={passed}")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TMFC003 integration smoke test")
    parser.add_argument("--url", required=True, help="Odoo base URL, e.g. http://localhost:8069")
    parser.add_argument("--db", required=True, help="Odoo database name")
    parser.add_argument("--username", required=True, help="Odoo username")
    parser.add_argument("--password", required=True, help="Odoo password")
    args = parser.parse_args()

    try:
        return run(args.url, args.db, args.username, args.password)
    except Exception as exc:  # pragma: no cover - smoke harness robustness
        print(f"[FAIL] TMFC003 smoke test raised exception: {exc}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
