#!/usr/bin/env python3
"""
Register/update TMF Hub subscriptions in Odoo so callbacks are visible in UI.

Example:
  python OdooTMFOpenAPI/tools/register_tmf_hubs.py ^
    --url http://localhost:8069 ^
    --db TMF_Odoo_DB ^
    --user admin ^
    --password admin ^
    --callback https://testproj.free.beeceptor.com
"""

from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import sys
import xmlrpc.client
from typing import Any


def parse_event_map(repo_root: Path) -> dict[str, dict[str, str]]:
    src = repo_root / "tmf_base" / "models" / "tmf_hub_subscription.py"
    text = src.read_text(encoding="utf-8")
    marker = "TMF_EVENT_NAME_MAP = "
    idx = text.find(marker)
    if idx < 0:
        raise RuntimeError("TMF_EVENT_NAME_MAP not found")
    start = text.find("{", idx)
    if start < 0:
        raise RuntimeError("Could not parse map start")

    depth = 0
    end = -1
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        raise RuntimeError("Could not parse map end")

    mapping_literal = text[start:end]
    mapping = ast.literal_eval(mapping_literal)
    normalized: dict[str, dict[str, str]] = {}
    for api_name, actions in mapping.items():
        if isinstance(api_name, str) and isinstance(actions, dict):
            normalized[api_name] = {str(k): str(v) for k, v in actions.items()}
    return normalized


def odoo_login(url: str, db: str, user: str, password: str) -> tuple[int, xmlrpc.client.ServerProxy]:
    common = xmlrpc.client.ServerProxy(f"{url.rstrip('/')}/xmlrpc/2/common")
    uid = common.authenticate(db, user, password, {})
    if isinstance(uid, bool) or not isinstance(uid, int) or uid <= 0:
        raise RuntimeError("Authentication failed")
    models = xmlrpc.client.ServerProxy(f"{url.rstrip('/')}/xmlrpc/2/object")
    return int(uid), models


def execute(
    models: xmlrpc.client.ServerProxy,
    db: str,
    uid: int,
    password: str,
    model: str,
    method: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    return models.execute_kw(db, uid, password, model, method, list(args), kwargs)


def upsert_subscription(
    url: str,
    db: str,
    user: str,
    password: str,
    api_name: str,
    event_type: str,
    callback: str,
) -> str:
    uid, models = odoo_login(url, db, user, password)
    domain = [["api_name", "=", api_name], ["event_type", "=", event_type]]
    sub_ids = execute(
        models,
        db,
        uid,
        password,
        "tmf.hub.subscription",
        "search",
        domain,
        limit=1,
    )
    vals = {
        "name": f"Auto {api_name} ({event_type})",
        "api_name": api_name,
        "callback": callback,
        "event_type": event_type,
        "active": True,
        "content_type": "application/json",
    }
    if sub_ids:
        execute(models, db, uid, password, "tmf.hub.subscription", "write", sub_ids, vals)
        return "updated"

    execute(models, db, uid, password, "tmf.hub.subscription", "create", vals)
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser(description="Register/update TMF hub subscriptions")
    parser.add_argument("--url", required=True, help="Odoo base URL, e.g. http://localhost:8069")
    parser.add_argument("--db", required=True, help="Database name")
    parser.add_argument("--user", required=True, help="Login user")
    parser.add_argument("--password", required=True, help="Login password")
    parser.add_argument("--callback", required=True, help="Webhook callback URL")
    parser.add_argument(
        "--event-type",
        default="any",
        choices=["any", "create", "update", "state_change", "information_required", "delete"],
        help="Subscription event_type",
    )
    parser.add_argument(
        "--all-actions",
        action="store_true",
        help="Create one subscription per action present in TMF_EVENT_NAME_MAP for each api_name",
    )
    parser.add_argument("--only-existing", action="store_true", help="Only update existing subscriptions callback")
    parser.add_argument("--workers", type=int, default=max(4, min(32, (os.cpu_count() or 4) * 5)), help="Number of concurrent worker threads")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    event_map = parse_event_map(repo_root)
    api_names = [] if args.only_existing else sorted(event_map.keys())

    uid, models = odoo_login(args.url, args.db, args.user, args.password)

    # Keep this callback as default for future manual records.
    execute(
        models,
        args.db,
        uid,
        args.password,
        "ir.config_parameter",
        "set_param",
        "tmf.hub.default_callback",
        args.callback,
    )

    # 1) Update all existing subscriptions to callback.
    existing_ids = execute(
        models,
        args.db,
        uid,
        args.password,
        "tmf.hub.subscription",
        "search",
        [],
    )
    if existing_ids:
        execute(
            models,
            args.db,
            uid,
            args.password,
            "tmf.hub.subscription",
            "write",
            existing_ids,
            {"callback": args.callback},
        )

    created = 0
    updated = len(existing_ids)

    # 2) Ensure subscriptions using chosen event_type or all actions (parallel).
    if api_names:
        targets: list[tuple[str, str]] = []
        if args.all_actions:
            for api_name in api_names:
                actions = sorted(event_map.get(api_name, {}).keys()) or [args.event_type]
                for action in actions:
                    targets.append((api_name, action))
        else:
            targets = [(api_name, args.event_type) for api_name in api_names]

        workers = max(1, int(args.workers))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    upsert_subscription,
                    args.url,
                    args.db,
                    args.user,
                    args.password,
                    api_name,
                    event_type,
                    args.callback,
                ): (api_name, event_type)
                for api_name, event_type in targets
            }
            for fut in as_completed(futures):
                api_name, event_type = futures[fut]
                try:
                    result = fut.result()
                    if result == "updated":
                        updated += 1
                    else:
                        created += 1
                except Exception as exc:
                    print(f"[WARN] failed api_name={api_name} event_type={event_type}: {exc}")

    total = execute(
        models,
        args.db,
        uid,
        args.password,
        "tmf.hub.subscription",
        "search_count",
        [],
    )

    print("TMF hub registration completed")
    print(f"callback={args.callback}")
    print(f"workers={args.workers}")
    print(f"updated={updated}")
    print(f"created={created}")
    print(f"total_subscriptions={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

