#!/usr/bin/env python3
"""
Config-driven TMF API smoke runner.

Usage:
  python OdooBSS/tools/tmf_api_smoke.py --config OdooBSS/tools/tmf_api_smoke.sample.json
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from typing import Any, Dict, List, Tuple


VAR_RE = re.compile(r"\{\{([a-zA-Z0-9_\-\.]+)\}\}")


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _interpolate(value: Any, vars_map: Dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {k: _interpolate(v, vars_map) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v, vars_map) for v in value]
    if isinstance(value, str):
        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            return str(vars_map.get(key, match.group(0)))

        return VAR_RE.sub(repl, value)
    return value


def _build_url(base_url: str, path: str, query: str | None = None) -> str:
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    if query:
        return f"{url}?{query}"
    return url


def _make_headers(default_headers: Dict[str, str], auth_cfg: Dict[str, Any]) -> Dict[str, str]:
    headers = dict(default_headers or {})
    auth_type = (auth_cfg or {}).get("type", "none")
    if auth_type == "basic":
        username = (auth_cfg or {}).get("username", "")
        password = (auth_cfg or {}).get("password", "")
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    elif auth_type == "bearer":
        token = (auth_cfg or {}).get("token", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    return headers


def _request(
    method: str,
    url: str,
    headers: Dict[str, str],
    payload: Any = None,
    timeout: int = 30,
) -> Tuple[int, Dict[str, str], Any]:
    body_bytes = None
    req_headers = dict(headers)
    if payload is not None:
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url=url, data=body_bytes, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            try:
                data = json.loads(raw) if raw else None
            except Exception:
                data = raw
            return resp.status, hdrs, data
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        hdrs = {k.lower(): v for k, v in e.headers.items()}
        try:
            data = json.loads(raw) if raw else None
        except Exception:
            data = raw
        return e.code, hdrs, data


def _extract_id_from_response(data: Any, headers: Dict[str, str]) -> str | None:
    if isinstance(data, dict):
        rid = data.get("id")
        if rid:
            return str(rid)
    location = headers.get("location")
    if location:
        return location.rstrip("/").split("/")[-1]
    return None


def _step(
    title: str,
    method: str,
    url: str,
    headers: Dict[str, str],
    expected_status: List[int],
    payload: Any = None,
    timeout: int = 30,
) -> Tuple[bool, int, Dict[str, str], Any]:
    started = time.time()
    status, resp_headers, data = _request(method, url, headers=headers, payload=payload, timeout=timeout)
    elapsed = int((time.time() - started) * 1000)
    ok = status in expected_status
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {title} :: {method} {url} -> {status} ({elapsed}ms)")
    if not ok:
        snippet = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        print(f"       expected={expected_status} body={snippet[:400]}")
    return ok, status, resp_headers, data


def run(config: Dict[str, Any]) -> int:
    base_url = config["base_url"]
    timeout = int(config.get("timeout_sec", 30))
    headers = _make_headers(config.get("default_headers", {}), config.get("auth", {}))
    tests = config.get("tests", [])
    vars_map: Dict[str, Any] = dict(config.get("vars", {}) or {})

    total_steps = 0
    failed_steps = 0

    for t in tests:
        t = deepcopy(t)
        name = t.get("name", "Unnamed Test")
        print(f"\n=== {name} ===")

        collection_path = _interpolate(t.get("collection_path", ""), vars_map)
        if not collection_path:
            print("[SKIP] missing collection_path")
            continue

        # 1) LIST
        list_cfg = t.get("list", {})
        list_query = _interpolate(list_cfg.get("query"), vars_map)
        list_expected = list_cfg.get("expected_status", [200])
        list_url = _build_url(base_url, collection_path, list_query)
        total_steps += 1
        ok, _, _, _ = _step(f"{name} list", "GET", list_url, headers, list_expected, timeout=timeout)
        if not ok:
            failed_steps += 1

        # 2) CREATE (optional)
        created_id = None
        create_cfg = t.get("create")
        if isinstance(create_cfg, dict):
            create_payload = _interpolate(create_cfg.get("payload", {}), vars_map)
            create_expected = create_cfg.get("expected_status", [200, 201, 202])
            create_url = _build_url(base_url, collection_path)
            total_steps += 1
            ok, _, h, d = _step(f"{name} create", "POST", create_url, headers, create_expected, payload=create_payload, timeout=timeout)
            if not ok:
                failed_steps += 1
            created_id = _extract_id_from_response(d, h)
            if created_id and create_cfg.get("save_as"):
                vars_map[str(create_cfg["save_as"])] = created_id

        # 3) GET by id (if id available)
        get_id_cfg = t.get("get_by_id", {})
        id_value = _interpolate(get_id_cfg.get("id"), vars_map) if get_id_cfg.get("id") else created_id
        id_path = _interpolate(t.get("id_path", ""), vars_map)
        if id_value and id_path:
            by_id_path = id_path.replace("{id}", str(id_value))
            by_id_query = _interpolate(get_id_cfg.get("query"), vars_map)
            by_id_expected = get_id_cfg.get("expected_status", [200])
            by_id_url = _build_url(base_url, by_id_path, by_id_query)
            total_steps += 1
            ok, _, _, _ = _step(f"{name} get-by-id", "GET", by_id_url, headers, by_id_expected, timeout=timeout)
            if not ok:
                failed_steps += 1

        # 4) PATCH (optional)
        patch_cfg = t.get("patch")
        if isinstance(patch_cfg, dict) and id_value and id_path:
            patch_payload = _interpolate(patch_cfg.get("payload", {}), vars_map)
            patch_expected = patch_cfg.get("expected_status", [200, 202])
            patch_url = _build_url(base_url, id_path.replace("{id}", str(id_value)))
            total_steps += 1
            ok, _, _, _ = _step(f"{name} patch", "PATCH", patch_url, headers, patch_expected, payload=patch_payload, timeout=timeout)
            if not ok:
                failed_steps += 1

        # 5) DELETE (optional)
        delete_cfg = t.get("delete")
        if isinstance(delete_cfg, dict) and delete_cfg.get("enabled", False) and id_value and id_path:
            delete_expected = delete_cfg.get("expected_status", [200, 202, 204])
            delete_url = _build_url(base_url, id_path.replace("{id}", str(id_value)))
            total_steps += 1
            ok, _, _, _ = _step(f"{name} delete", "DELETE", delete_url, headers, delete_expected, timeout=timeout)
            if not ok:
                failed_steps += 1

    print("\n=== Summary ===")
    print(f"steps={total_steps} failed={failed_steps} passed={total_steps - failed_steps}")
    return 1 if failed_steps else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TMF API smoke test runner")
    parser.add_argument("--config", required=True, help="Path to JSON config")
    args = parser.parse_args()
    config = _load_json(args.config)
    return run(config)


if __name__ == "__main__":
    sys.exit(main())
