#!/usr/bin/env python3
"""
Batch CTK runner for Windows run.bat-based TMF CTKs.

Examples:
  python OdooBSS/tools/run_ctk_batch.py
  python OdooBSS/tools/run_ctk_batch.py --include TMF620,TMF621,TMF702
  python OdooBSS/tools/run_ctk_batch.py --base-url http://host.docker.internal:8069
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


TMF_RE = re.compile(r"TMF(\d+)_", re.IGNORECASE)
LAUNCHER_NAMES = ("run.bat", "Windows-PowerShell-RUNCTK.ps1")
LOCALHOST_CTK_IDS = {"TMF654", "TMF674", "TMF676", "TMF709", "TMF730", "TMF915"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multiple TMF CTKs and aggregate results.")
    parser.add_argument(
        "--root",
        default="DOCUMENTATION/OpenApiTable",
        help="Root folder where TMF folders live (default: DOCUMENTATION/OpenApiTable).",
    )
    parser.add_argument(
        "--include",
        default="",
        help="Comma-separated TMF IDs to include, e.g. TMF620,621,TMF702.",
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="Comma-separated TMF IDs to exclude, e.g. TMF702,TMF639.",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="Optional base URL argument passed to each run.bat.",
    )
    parser.add_argument(
        "--stop-on-fail",
        action="store_true",
        help="Stop execution after first failing CTK.",
    )
    parser.add_argument(
        "--output-dir",
        default="DOCUMENTATION/ctk_batch_reports",
        help="Directory where summary files are written.",
    )
    parser.add_argument(
        "--no-auto-extract",
        action="store_true",
        help="Do not auto-extract CTK zip files before discovery.",
    )
    parser.add_argument(
        "--all-versions",
        action="store_true",
        help="Run all discovered versions per TMF. Default runs only latest version per TMF.",
    )
    return parser.parse_args()


def normalize_tmf_id(token: str) -> str:
    token = token.strip().upper()
    if not token:
        return ""
    if token.startswith("TMF"):
        return token
    return f"TMF{token}"


def parse_tmf_set(raw: str) -> set[str]:
    if not raw.strip():
        return set()
    return {normalize_tmf_id(x) for x in raw.split(",") if normalize_tmf_id(x)}


def tmf_from_path(path: Path) -> str:
    for part in path.parts:
        m = TMF_RE.match(part)
        if m:
            return f"TMF{m.group(1)}"
    return "UNKNOWN"


def _extract_version(path: Path) -> tuple[int, int, int]:
    for part in path.parts:
        if re.match(r"^\d+\.\d+\.\d+$", part):
            try:
                return tuple(int(x) for x in part.split("."))  # type: ignore[return-value]
            except Exception:
                pass
    return (0, 0, 0)


def discover_runs(root: Path, all_versions: bool = False) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for launcher_name in LAUNCHER_NAMES:
        for launcher in root.rglob(launcher_name):
            tmf_id = tmf_from_path(launcher)
            # Some legacy PS wrappers assume a nested ./ctk directory; skip broken extracts.
            if launcher.name.lower() == "windows-powershell-runctk.ps1":
                if not (launcher.parent / "ctk").exists():
                    continue
            runs.append(
                {
                    "tmf_id": tmf_id,
                    "launcher": launcher,
                    "ctk_dir": launcher.parent,
                    "version": _extract_version(launcher),
                }
            )
    runs.sort(key=lambda r: (r["tmf_id"], str(r["launcher"])))
    # Deduplicate same TMF+folder by preferring run.bat over ps1 wrapper.
    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for run in runs:
        key = (run["tmf_id"], run["ctk_dir"].as_posix())
        prev = dedup.get(key)
        if not prev:
            dedup[key] = run
            continue
        prev_name = prev["launcher"].name.lower()
        cur_name = run["launcher"].name.lower()
        if prev_name != "run.bat" and cur_name == "run.bat":
            dedup[key] = run
    dedup_list = sorted(dedup.values(), key=lambda r: (r["tmf_id"], str(r["launcher"])))
    if all_versions:
        return dedup_list

    # By default keep latest version per TMF ID.
    latest: dict[str, dict[str, Any]] = {}
    for run in dedup_list:
        tmf_id = run["tmf_id"]
        cur = latest.get(tmf_id)
        if not cur:
            latest[tmf_id] = run
            continue
        if run["version"] > cur["version"]:
            latest[tmf_id] = run
            continue
        if run["version"] == cur["version"]:
            # Prefer run.bat over PS wrapper at same version.
            cur_name = Path(cur["launcher"]).name.lower()
            run_name = Path(run["launcher"]).name.lower()
            if cur_name != "run.bat" and run_name == "run.bat":
                latest[tmf_id] = run
    return sorted(latest.values(), key=lambda r: (r["tmf_id"], str(r["launcher"])))


def find_json_report(ctk_dir: Path) -> Path | None:
    candidates = [
        ctk_dir / "reports" / "jsonResults.json",
        ctk_dir / "reports" / "index.json",
        ctk_dir / "jsonResults.json",
        ctk_dir / "RESULTS" / "assets" / "test_data.json",
        ctk_dir / "cypress" / "reports" / "index.json",
        ctk_dir / "DO_NOT_CHANGE" / "cypress" / "reports" / "index.json",
        ctk_dir / "DO_NOT_CHANGE" / "cypress" / "reports" / "json" / "mochawesome.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    for candidate in ctk_dir.rglob("jsonResults.json"):
        return candidate
    return None


def parse_report(report_path: Path | None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "assertions_total": 0,
        "assertions_failed": None,
        "tests_total": 0,
        "tests_failed": None,
        "scripts_failed": None,
        "pass_rate": None,
    }
    if not report_path:
        return data

    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return data

    if report_path.name == "test_data.json":
        total = 0
        failed = 0

        def walk(node: Any) -> None:
            nonlocal total, failed
            if isinstance(node, dict):
                if "testResult" in node:
                    total += 1
                    test_result = str(node.get("testResult") or "").strip().lower()
                    html_result = str(node.get("htmlResult") or "").strip().lower()
                    if test_result in {"failure", "failed", "error"} or html_result in {"failure", "failed", "error"}:
                        failed += 1
                    return
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload)
        data["tests_total"] = total
        data["tests_failed"] = failed
        data["assertions_total"] = total
        data["assertions_failed"] = failed
        data["scripts_failed"] = 0
        if total > 0:
            data["pass_rate"] = round(((total - failed) / total) * 100.0, 2)
        return data

    # Newman-style report
    run_stats = (payload.get("run") or {}).get("stats") or {}
    if run_stats:
        assertions = run_stats.get("assertions") or {}
        tests = run_stats.get("tests") or {}
        scripts = run_stats.get("scripts") or {}
        data["assertions_total"] = int(assertions.get("total") or 0)
        data["assertions_failed"] = int(assertions.get("failed") or 0)
        data["tests_total"] = int(tests.get("total") or 0)
        data["tests_failed"] = int(tests.get("failed") or 0)
        data["scripts_failed"] = int(scripts.get("failed") or 0)
    else:
        # Cypress/Mochawesome fallback report formats
        stats = payload.get("stats") or {}
        if isinstance(stats, dict):
            tests_total = (
                stats.get("tests")
                or stats.get("totalTests")
                or stats.get("testsRegistered")
                or 0
            )
            tests_failed = stats.get("failures")
            if tests_failed is None:
                total_failed = payload.get("totalFailed")
                tests_failed = total_failed if total_failed is not None else 0
            data["tests_total"] = int(tests_total or 0)
            data["tests_failed"] = int(tests_failed or 0)
            # No assertion granularity available: treat test failures as assertion failures
            data["assertions_total"] = data["tests_total"]
            data["assertions_failed"] = data["tests_failed"]
            data["scripts_failed"] = 0

    if data["assertions_total"] > 0 and data["assertions_failed"] is not None:
        passed = data["assertions_total"] - data["assertions_failed"]
        data["pass_rate"] = round((passed / data["assertions_total"]) * 100.0, 2)

    return data


def _contains_launcher(folder: Path) -> bool:
    for name in LAUNCHER_NAMES:
        if list(folder.rglob(name)):
            return True
    return False


def _extract_zip_once(zip_path: Path) -> None:
    target = zip_path.with_suffix("")
    # If target already has launcher scripts, don't touch.
    if target.exists() and _contains_launcher(target):
        return
    if not target.exists():
        target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target)


def auto_extract_ctk_zips(root: Path) -> None:
    for ctk_dir in root.rglob("ctk"):
        if not ctk_dir.is_dir():
            continue
        for zip_file in ctk_dir.glob("*.zip"):
            try:
                _extract_zip_once(zip_file)
            except Exception as exc:
                print(f"WARN: could not extract {zip_file}: {exc}")


def _build_cmd_for_launcher(launcher: Path, base_url: str) -> list[str]:
    name = launcher.name.lower()
    if name == "run.bat":
        cmd = ["cmd", "/c", launcher.name]
        if base_url:
            cmd.append(base_url)
        return cmd
    if name == "windows-powershell-runctk.ps1":
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", launcher.name]
        if base_url:
            cmd.append(base_url)
        return cmd
    raise ValueError(f"Unsupported launcher: {launcher}")


def _rewrite_url_host(value: str, base_url: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return value
    try:
        dst = urlparse(base_url.strip())
    except Exception:
        return value
    if not dst.scheme or not dst.netloc:
        return value

    candidate = raw
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", candidate):
        candidate = f"http://{candidate}"

    try:
        src = urlparse(candidate)
    except Exception:
        return value
    if not src.netloc:
        return value

    # Replace only scheme+host:port, keep path/query/fragment from original.
    out = f"{dst.scheme}://{dst.netloc}{src.path or ''}"
    if src.query:
        out += f"?{src.query}"
    if src.fragment:
        out += f"#{src.fragment}"
    return out


def _rewrite_obj_urls(node: Any, base_url: str) -> Any:
    if isinstance(node, dict):
        return {k: _rewrite_obj_urls(v, base_url) for k, v in node.items()}
    if isinstance(node, list):
        return [_rewrite_obj_urls(v, base_url) for v in node]
    if isinstance(node, str):
        text = node.strip()
        first = text.split("/", 1)[0]
        # Rewrite plain host:port strings too (legacy CTKs often use 192.168.x.x:8069)
        if text.startswith(("http://", "https://")):
            return _rewrite_url_host(node, base_url)
        if re.match(r"^[A-Za-z0-9_.-]+:\d+($|/)", text):
            return _rewrite_url_host(node, base_url)
        if "/" in text and ":" in first:
            return _rewrite_url_host(node, base_url)
    return node


def _apply_tmf_specific_url_fixes(node: Any, tmf_id: str) -> Any:
    if isinstance(node, dict):
        return {k: _apply_tmf_specific_url_fixes(v, tmf_id) for k, v in node.items()}
    if isinstance(node, list):
        return [_apply_tmf_specific_url_fixes(v, tmf_id) for v in node]
    if isinstance(node, str):
        text = node
        if tmf_id == "TMF632":
            # TMF632 CTK package uses partyRoleManagement path in some versions.
            text = text.replace("/partyRoleManagement/", "/partyManagement/")
        return text
    return node


def override_config_base_url(ctk_dir: Path, base_url: str, tmf_id: str = "UNKNOWN") -> int:
    if not base_url:
        return 0
    changed = 0
    for cfg in ctk_dir.rglob("config.json"):
        try:
            original = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            continue
        updated = _rewrite_obj_urls(original, base_url)
        updated = _apply_tmf_specific_url_fixes(updated, tmf_id)
        if updated != original:
            cfg.write_text(json.dumps(updated, indent=2), encoding="utf-8")
            changed += 1
    return changed


def wait_for_base_url(base_url: str, timeout_sec: int = 90) -> bool:
    if not base_url:
        return True
    deadline = dt.datetime.now() + dt.timedelta(seconds=timeout_sec)
    attempts = 0
    while dt.datetime.now() < deadline:
        attempts += 1
        try:
            req = Request(base_url, method="GET")
            with urlopen(req, timeout=5) as resp:  # nosec B310 - local CTK target
                if resp.status < 500:
                    if attempts > 1:
                        print(f"Base URL became reachable after {attempts} checks: {base_url}")
                    return True
        except Exception:
            pass
        # short sleep without importing time module globally
        subprocess.run(["cmd", "/c", "ping -n 2 127.0.0.1 >NUL"], check=False)
    print(f"WARN: base URL not reachable after {timeout_sec}s: {base_url}")
    return False


def effective_base_url_for_tmf(tmf_id: str, base_url: str) -> str:
    if tmf_id not in LOCALHOST_CTK_IDS:
        return base_url
    # These CTKs run locally (non-docker), so force loopback host.
    if not base_url:
        return "http://127.0.0.1:8069"
    try:
        parsed = urlparse(base_url.strip())
    except Exception:
        return "http://127.0.0.1:8069"
    scheme = parsed.scheme or "http"
    port = parsed.port or 8069
    return f"{scheme}://127.0.0.1:{port}"


def run_one(
    run_item: dict[str, Any],
    base_url: str,
    output_log: Path,
) -> dict[str, Any]:
    launcher = run_item["launcher"]
    ctk_dir = run_item["ctk_dir"]
    tmf_id = run_item["tmf_id"]
    effective_base_url = effective_base_url_for_tmf(tmf_id, base_url)

    cmd = _build_cmd_for_launcher(launcher, effective_base_url)

    started = dt.datetime.now()
    print(f"[{tmf_id}] START {ctk_dir} ({launcher.name})")
    if effective_base_url:
        changed = override_config_base_url(ctk_dir, effective_base_url, tmf_id=tmf_id)
        if changed:
            print(
                f"[{tmf_id}] config override applied in {changed} file(s) "
                f"with base-url={effective_base_url}"
            )
        wait_for_base_url(effective_base_url)

    with output_log.open("w", encoding="utf-8", errors="replace") as f:
        env = dict(os.environ)
        env.setdefault("platform", "linux/amd64")
        env.setdefault("DOCKER_DEFAULT_PLATFORM", "linux/amd64")
        process = subprocess.Popen(
            cmd,
            cwd=str(ctk_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            try:
                sys.stdout.write(line)
            except UnicodeEncodeError:
                safe = line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
                    sys.stdout.encoding or "utf-8", errors="replace"
                )
                sys.stdout.write(safe)
            f.write(line)
        exit_code = process.wait()

    finished = dt.datetime.now()
    duration_sec = int((finished - started).total_seconds())

    report_path = find_json_report(ctk_dir)
    metrics = parse_report(report_path)

    assertions_failed = metrics["assertions_failed"]
    passed = (exit_code == 0) and (assertions_failed == 0 if assertions_failed is not None else True)
    status = "PASS" if passed else "FAIL"

    print(
        f"[{tmf_id}] {status} exit={exit_code} "
        f"assertions_failed={assertions_failed} duration={duration_sec}s"
    )

    return {
        "tmf_id": tmf_id,
        "ctk_dir": str(ctk_dir),
        "launcher": str(launcher),
        "exit_code": exit_code,
        "duration_sec": duration_sec,
        "report_path": str(report_path) if report_path else "",
        "status": status,
        **metrics,
    }


def write_outputs(out_dir: Path, results: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "summary.json"
    csv_path = out_dir / "summary.csv"
    md_path = out_dir / "summary.md"

    totals = {
        "count": len(results),
        "pass": sum(1 for r in results if r["status"] == "PASS"),
        "fail": sum(1 for r in results if r["status"] == "FAIL"),
    }

    aggregate = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "totals": totals,
        "results": results,
    }
    json_path.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")

    fieldnames = [
        "tmf_id",
        "status",
        "exit_code",
        "assertions_total",
        "assertions_failed",
        "pass_rate",
        "tests_total",
        "tests_failed",
        "scripts_failed",
        "duration_sec",
        "ctk_dir",
        "launcher",
        "report_path",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    lines = [
        "# CTK Batch Summary",
        "",
        f"- Generated: {aggregate['generated_at']}",
        f"- Total: {totals['count']}",
        f"- Pass: {totals['pass']}",
        f"- Fail: {totals['fail']}",
        "",
        "| TMF | Status | Exit | Assertions Failed | Assertions Total | Pass % | Duration(s) | Launcher |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in results:
        lines.append(
            f"| {r['tmf_id']} | {r['status']} | {r['exit_code']} | "
            f"{'' if r['assertions_failed'] is None else r['assertions_failed']} | "
            f"{r.get('assertions_total', 0)} | "
            f"{'' if r['pass_rate'] is None else r['pass_rate']} | "
            f"{r['duration_sec']} | "
            f"{Path(r.get('launcher') or '').name} |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nSummary written to:")
    print(f"  {json_path}")
    print(f"  {csv_path}")
    print(f"  {md_path}")


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    output_root = Path(args.output_dir).resolve()

    include_ids = parse_tmf_set(args.include)
    exclude_ids = parse_tmf_set(args.exclude)

    if not root.exists():
        print(f"ERROR: root not found: {root}")
        return 2

    if not args.no_auto_extract:
        print(f"Auto-extracting CTK zips under {root} ...")
        auto_extract_ctk_zips(root)

    runs = discover_runs(root, all_versions=args.all_versions)
    if include_ids:
        runs = [r for r in runs if r["tmf_id"] in include_ids]
    if exclude_ids:
        runs = [r for r in runs if r["tmf_id"] not in exclude_ids]

    if not runs:
        print("No CTK launcher files matched filters.")
        return 2

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_out_dir = output_root / f"run_{timestamp}"
    logs_dir = run_out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    print(f"Discovered {len(runs)} CTK runners under {root}")
    if include_ids:
        print(f"Include filter: {sorted(include_ids)}")
    if exclude_ids:
        print(f"Exclude filter: {sorted(exclude_ids)}")
    if args.base_url:
        print(f"Base URL argument: {args.base_url}")
    print("")

    results: list[dict[str, Any]] = []
    for r in runs:
        launcher_name = Path(r["launcher"]).name
        log_file = logs_dir / f"{r['tmf_id']}_{Path(r['ctk_dir']).name}_{launcher_name}.log"
        result = run_one(r, args.base_url, log_file)
        results.append(result)
        if args.stop_on_fail and result["status"] == "FAIL":
            print("Stopping on first failure (--stop-on-fail).")
            break

    write_outputs(run_out_dir, results)

    failures = [r for r in results if r["status"] == "FAIL"]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
