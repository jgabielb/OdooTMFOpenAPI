#!/usr/bin/env python3
"""
Config-driven TMF API smoke runner.

Usage:
  python OdooBSS/tools/tmf_api_smoke.py --config OdooBSS/tools/tmf_api_smoke.sample.json
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from copy import deepcopy
from typing import Any, Dict, List, Set, Tuple


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
    logs: List[str] | None = None,
) -> Tuple[bool, int, Dict[str, str], Any]:
    started = time.time()
    status, resp_headers, data = _request(method, url, headers=headers, payload=payload, timeout=timeout)
    elapsed = int((time.time() - started) * 1000)
    ok = status in expected_status
    tag = "PASS" if ok else "FAIL"
    line = f"[{tag}] {title} :: {method} {url} -> {status} ({elapsed}ms)"
    if logs is not None:
        logs.append(line)
    else:
        print(line)
    if not ok:
        snippet = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        line = f"       expected={expected_status} body={snippet[:400]}"
        if logs is not None:
            logs.append(line)
        else:
            print(line)
    return ok, status, resp_headers, data


def _collect_placeholders(value: Any) -> Set[str]:
    found: Set[str] = set()
    if isinstance(value, dict):
        for v in value.values():
            found.update(_collect_placeholders(v))
    elif isinstance(value, list):
        for v in value:
            found.update(_collect_placeholders(v))
    elif isinstance(value, str):
        for match in VAR_RE.finditer(value):
            found.add(match.group(1))
    return found


@dataclass
class _TestResult:
    index: int
    name: str
    logs: List[str]
    total_steps: int
    failed_steps: int
    saved_vars: Dict[str, str]


def _run_one_test(
    index: int,
    test_cfg: Dict[str, Any],
    base_url: str,
    headers: Dict[str, str],
    timeout: int,
    vars_map: Dict[str, Any],
) -> _TestResult:
    t = deepcopy(test_cfg)
    name = t.get("name", "Unnamed Test")
    logs: List[str] = [f"\n=== {name} ==="]
    total_steps = 0
    failed_steps = 0
    saved_vars: Dict[str, str] = {}

    collection_path = _interpolate(t.get("collection_path", ""), vars_map)
    if not collection_path:
        logs.append("[SKIP] missing collection_path")
        return _TestResult(index, name, logs, total_steps, failed_steps, saved_vars)

    # 1) LIST
    list_cfg = t.get("list", {})
    list_query = _interpolate(list_cfg.get("query"), vars_map)
    list_expected = list_cfg.get("expected_status", [200])
    list_url = _build_url(base_url, collection_path, list_query)
    total_steps += 1
    ok, _, _, _ = _step(f"{name} list", "GET", list_url, headers, list_expected, timeout=timeout, logs=logs)
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
        ok, _, h, d = _step(
            f"{name} create",
            "POST",
            create_url,
            headers,
            create_expected,
            payload=create_payload,
            timeout=timeout,
            logs=logs,
        )
        if not ok:
            failed_steps += 1
        created_id = _extract_id_from_response(d, h)
        if created_id and create_cfg.get("save_as"):
            saved_vars[str(create_cfg["save_as"])] = created_id

    # Include vars created during this test for interpolation of remaining steps.
    step_vars = dict(vars_map)
    step_vars.update(saved_vars)

    # 3) GET by id (if id available)
    get_id_cfg = t.get("get_by_id", {})
    id_value = _interpolate(get_id_cfg.get("id"), step_vars) if get_id_cfg.get("id") else created_id
    id_path = _interpolate(t.get("id_path", ""), step_vars)
    if id_value and id_path:
        by_id_path = id_path.replace("{id}", str(id_value))
        by_id_query = _interpolate(get_id_cfg.get("query"), step_vars)
        by_id_expected = get_id_cfg.get("expected_status", [200])
        by_id_url = _build_url(base_url, by_id_path, by_id_query)
        total_steps += 1
        ok, _, _, _ = _step(f"{name} get-by-id", "GET", by_id_url, headers, by_id_expected, timeout=timeout, logs=logs)
        if not ok:
            failed_steps += 1

    # 3b) Extended read scenarios (optional)
    scenarios_cfg = t.get("scenarios", {}) if isinstance(t.get("scenarios"), dict) else {}
    scenario_defaults = vars_map.get("__scenario_defaults__", {}) if isinstance(vars_map.get("__scenario_defaults__"), dict) else {}

    def _scenario_bool(key: str, default: bool = False) -> bool:
        if key in scenarios_cfg:
            return bool(scenarios_cfg.get(key))
        return bool(scenario_defaults.get(key, default))

    def _scenario_value(key: str, default: Any = None) -> Any:
        if key in scenarios_cfg:
            return scenarios_cfg.get(key)
        return scenario_defaults.get(key, default)

    if _scenario_bool("list_fields_enabled", False):
        fields_query = _interpolate(_scenario_value("list_fields_query", "fields=id"), step_vars)
        fields_expected = _scenario_value("list_fields_expected_status", [200])
        fields_url = _build_url(base_url, collection_path, fields_query)
        total_steps += 1
        ok, _, _, _ = _step(f"{name} list-fields", "GET", fields_url, headers, fields_expected, timeout=timeout, logs=logs)
        if not ok:
            failed_steps += 1

    if id_value and id_path and _scenario_bool("get_by_id_fields_enabled", False):
        id_fields_query = _interpolate(_scenario_value("get_by_id_fields_query", "fields=id"), step_vars)
        id_fields_expected = _scenario_value("get_by_id_fields_expected_status", [200])
        id_fields_url = _build_url(base_url, id_path.replace("{id}", str(id_value)), id_fields_query)
        total_steps += 1
        ok, _, _, _ = _step(
            f"{name} get-by-id-fields",
            "GET",
            id_fields_url,
            headers,
            id_fields_expected,
            timeout=timeout,
            logs=logs,
        )
        if not ok:
            failed_steps += 1

    if id_value and _scenario_bool("list_by_id_filter_enabled", False):
        id_param = str(_scenario_value("list_by_id_filter_param", "id"))
        id_filter_query = f"{urllib.parse.quote_plus(id_param)}={urllib.parse.quote_plus(str(id_value))}"
        id_filter_expected = _scenario_value("list_by_id_filter_expected_status", [200])
        id_filter_url = _build_url(base_url, collection_path, id_filter_query)
        total_steps += 1
        ok, _, _, _ = _step(
            f"{name} list-by-id-filter",
            "GET",
            id_filter_url,
            headers,
            id_filter_expected,
            timeout=timeout,
            logs=logs,
        )
        if not ok:
            failed_steps += 1

    if id_value and id_path and _scenario_bool("not_found_enabled", False):
        suffix = str(_scenario_value("not_found_suffix", "-not-found"))
        not_found_id = f"{id_value}{suffix}"
        not_found_expected = _scenario_value("not_found_expected_status", [404])
        not_found_url = _build_url(base_url, id_path.replace("{id}", not_found_id))
        total_steps += 1
        ok, _, _, _ = _step(
            f"{name} get-not-found",
            "GET",
            not_found_url,
            headers,
            not_found_expected,
            timeout=timeout,
            logs=logs,
        )
        if not ok:
            failed_steps += 1

    # 4) PATCH (optional)
    patch_cfg = t.get("patch")
    if isinstance(patch_cfg, dict) and id_value and id_path:
        patch_payload = _interpolate(patch_cfg.get("payload", {}), step_vars)
        patch_expected = patch_cfg.get("expected_status", [200, 202])
        patch_url = _build_url(base_url, id_path.replace("{id}", str(id_value)))
        total_steps += 1
        ok, _, _, _ = _step(
            f"{name} patch",
            "PATCH",
            patch_url,
            headers,
            patch_expected,
            payload=patch_payload,
            timeout=timeout,
            logs=logs,
        )
        if not ok:
            failed_steps += 1

    # 5) DELETE (optional)
    delete_cfg = t.get("delete")
    if isinstance(delete_cfg, dict) and delete_cfg.get("enabled", False) and id_value and id_path:
        delete_expected = delete_cfg.get("expected_status", [200, 202, 204])
        delete_url = _build_url(base_url, id_path.replace("{id}", str(id_value)))
        total_steps += 1
        ok, _, _, _ = _step(f"{name} delete", "DELETE", delete_url, headers, delete_expected, timeout=timeout, logs=logs)
        if not ok:
            failed_steps += 1
        if ok and _scenario_bool("verify_deleted_enabled", False):
            verify_deleted_expected = _scenario_value("verify_deleted_expected_status", [404])
            verify_deleted_url = _build_url(base_url, id_path.replace("{id}", str(id_value)))
            total_steps += 1
            ok2, _, _, _ = _step(
                f"{name} verify-deleted",
                "GET",
                verify_deleted_url,
                headers,
                verify_deleted_expected,
                timeout=timeout,
                logs=logs,
            )
            if not ok2:
                failed_steps += 1

    return _TestResult(index, name, logs, total_steps, failed_steps, saved_vars)


def _dependency_levels(tests: List[Dict[str, Any]], initial_vars: Dict[str, Any]) -> List[List[int]]:
    # Track first producer of each variable to emulate sequential behavior.
    first_producer: Dict[str, int] = {}
    for idx, t in enumerate(tests):
        save_as = ((t.get("create") or {}).get("save_as") if isinstance(t.get("create"), dict) else None)
        if save_as and save_as not in first_producer:
            first_producer[str(save_as)] = idx

    deps: Dict[int, Set[int]] = {i: set() for i in range(len(tests))}
    for idx, t in enumerate(tests):
        needed = _collect_placeholders(t)
        for var_name in needed:
            if var_name in initial_vars:
                continue
            prod_idx = first_producer.get(var_name)
            if prod_idx is not None and prod_idx < idx:
                deps[idx].add(prod_idx)

    indeg = {i: len(deps[i]) for i in deps}
    dependents: Dict[int, Set[int]] = {i: set() for i in deps}
    for node, parents in deps.items():
        for p in parents:
            dependents[p].add(node)

    levels: List[List[int]] = []
    ready = [i for i in range(len(tests)) if indeg[i] == 0]
    ready.sort()
    done = 0
    while ready:
        level = list(ready)
        levels.append(level)
        next_ready: List[int] = []
        for n in level:
            done += 1
            for child in sorted(dependents[n]):
                indeg[child] -= 1
                if indeg[child] == 0:
                    next_ready.append(child)
        ready = sorted(set(next_ready))

    # Fallback for cycles/unresolved graph: keep remaining in original order.
    if done < len(tests):
        remaining = [i for i in range(len(tests)) if indeg[i] > 0]
        levels.append(remaining)
    return levels


def run(config: Dict[str, Any], workers: int = 4) -> int:
    base_url = config["base_url"]
    timeout = int(config.get("timeout_sec", 30))
    headers = _make_headers(config.get("default_headers", {}), config.get("auth", {}))
    tests = config.get("tests", [])
    vars_map: Dict[str, Any] = dict(config.get("vars", {}) or {})
    vars_map["__scenario_defaults__"] = dict(config.get("scenario_defaults", {}) or {})

    total_steps = 0
    failed_steps = 0

    levels = _dependency_levels(tests, vars_map)
    for level in levels:
        if not level:
            continue
        future_by_idx: Dict[int, concurrent.futures.Future[_TestResult]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            for idx in level:
                test_vars = dict(vars_map)
                future_by_idx[idx] = executor.submit(
                    _run_one_test,
                    idx,
                    tests[idx],
                    base_url,
                    headers,
                    timeout,
                    test_vars,
                )

            # Print and aggregate in deterministic order.
            for idx in level:
                result = future_by_idx[idx].result()
                for line in result.logs:
                    print(line)
                total_steps += result.total_steps
                failed_steps += result.failed_steps
                vars_map.update(result.saved_vars)

    print("\n=== Summary ===")
    print(f"steps={total_steps} failed={failed_steps} passed={total_steps - failed_steps}")
    return 1 if failed_steps else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TMF API smoke test runner")
    parser.add_argument("--config", required=True, help="Path to JSON config")
    parser.add_argument("--workers", type=int, default=4, help="Max number of parallel test groups")
    args = parser.parse_args()
    config = _load_json(args.config)
    return run(config, workers=int(args.workers))


if __name__ == "__main__":
    sys.exit(main())
