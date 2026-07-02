#!/usr/bin/env python3
"""Build AAN live runtime-smoke evidence from adapter and live probe records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _row_by_name(rows: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("name")): row
        for row in rows
        if isinstance(row, dict) and row.get("name") is not None
    }


def _row_passed(rows: dict[str, dict[str, Any]], name: str) -> bool:
    return rows.get(name, {}).get("status") == "PASS"


def _path_exists(path_value: Any) -> bool:
    return isinstance(path_value, str) and Path(path_value).exists()


def _load_result_info(path_value: Any) -> dict[str, Any] | None:
    if not isinstance(path_value, str) or not Path(path_value).is_file():
        return None
    data = _read_json(Path(path_value))
    return data if isinstance(data, dict) else None


def _commands_from_items(items: list[str] | None) -> dict[str, str]:
    commands: dict[str, str] = {}
    for item in items or []:
        key, separator, value = item.partition("=")
        if not separator or not key.strip() or not value.strip():
            raise ValueError("--command must use key=value")
        commands[key.strip()] = value.strip()
    return commands


def _command_contains_run_id(commands: dict[str, str], keys: tuple[str, ...], run_id: str) -> bool:
    return any(run_id in commands.get(key, "") for key in keys)


def _is_fresh_aan_run_id(run_id: Any) -> bool:
    if not isinstance(run_id, str) or not run_id:
        return False
    stale_prefixes = (
        "labutopia_lift2_composite_",
        "labutopia_lift2_contract_probe_",
        "native_dryingbox_",
    )
    return not run_id.startswith(stale_prefixes)


def _phase_owner_for_blocker(blocker: dict[str, Any]) -> tuple[str, str, str]:
    code = str(blocker.get("code", ""))
    field = str(blocker.get("field", ""))
    if code == "submit_failed":
        return "submit", "GenManip/EBench runtime", "Fix submit command, task path, run_id, or server queue state."
    if code == "probe_or_eval_failed":
        return "client_probe", "GenManip/EBench runtime", "Fix the probe/eval client command and rerun Stage 4b."
    if code in {
        "run_id_missing",
        "run_id_not_fresh",
        "run_id_mismatch",
        "run_id_missing_from_submit_command",
        "run_id_missing_from_probe_or_eval_command",
        "run_id_missing_from_result_info_path",
    }:
        return "client_probe", "LabUtopia consumer", "Rerun with one fresh AAN run_id across submit, probe/eval, artifacts, and manifest."
    if code in {"adapter_preflight_not_pass", "legacy_overlay_used"}:
        return "asset_package", "LabUtopia consumer", "Fix the AAN runtime adapter before running live smoke."
    if code == "result_info_missing" or "logging" in code or "stdout" in code or "stderr" in code:
        return "logging", "GenManip/EBench runtime", "Produce and retain result_info, stdout, and stderr artifacts."
    if "camera" in field:
        return "render", "GenManip/EBench runtime", "Fix camera/render contract or task camera config."
    if "reward/success" in field:
        return "metric", "GenManip/EBench runtime", "Fix reward, success, or metric readback."
    if "action" in field:
        return "step", "GenManip/EBench runtime", "Use the Lift2/R5a action dialect and fix step handling."
    if "observation" in field:
        return "reset", "GenManip/EBench runtime", "Fix reset observation schema or task reset."
    return "client_probe", "GenManip/EBench runtime", "Inspect blocker details and rerun Stage 4b."


def _first_failure(blockers: list[dict[str, Any]]) -> tuple[str | None, str | None, str | None]:
    if not blockers:
        return None, None, None
    phase, owner, action = _phase_owner_for_blocker(blockers[0])
    return phase, owner, action


def _summarize_runtime_warnings(paths: list[Path] | None) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    mdl_compiler_error_count = 0
    for path in paths or []:
        exists = path.exists()
        text = path.read_text(encoding="utf-8", errors="replace") if exists else ""
        count = text.count("[MDLC:COMPILER]")
        mdl_compiler_error_count += count
        records.append(
            {
                "path": str(path),
                "exists": exists,
                "mdl_compiler_error_count": count,
            }
        )
    return {
        "warning_log_count": len(records),
        "mdl_compiler_error_count": mdl_compiler_error_count,
        "records": records,
        "material_warning_claim_boundary": (
            "Stage 4b PASS proves runtime reset/step/render/metric/logging, not full visual material parity."
        ),
    }


def build_runtime_smoke_record(
    *,
    adapter_record_path: Path,
    probe_json_path: Path,
    json_out: Path | None = None,
    commands: dict[str, str] | None = None,
    expected_run_id: str | None = None,
    submit_exit_code: int | None = None,
    probe_or_eval_exit_code: int | None = None,
    runtime_warning_logs: list[Path] | None = None,
) -> dict[str, Any]:
    adapter = _read_json(adapter_record_path)
    probe = _read_json(probe_json_path)
    if not isinstance(adapter, dict):
        raise ValueError(f"{adapter_record_path}: expected JSON object")
    if not isinstance(probe, dict):
        raise ValueError(f"{probe_json_path}: expected JSON object")

    rows = _row_by_name(probe.get("schema_rows"))
    logging = probe.get("logging") if isinstance(probe.get("logging"), dict) else {}
    live_probe = (
        probe.get("live_probe") if isinstance(probe.get("live_probe"), dict) else {}
    )
    result_info_path = logging.get("result_path")
    stdout_path = logging.get("stdout_path")
    stderr_path = logging.get("stderr_path")
    result_info = _load_result_info(result_info_path)
    commands = commands or {}
    run_id = logging.get("run_id")
    run_id_is_fresh = _is_fresh_aan_run_id(run_id)
    expected_run_id_matches = expected_run_id is None or run_id == expected_run_id
    run_id_for_checks = run_id if isinstance(run_id, str) else ""
    run_id_matches_submit = bool(run_id_for_checks) and _command_contains_run_id(
        commands, ("submit",), run_id_for_checks
    )
    run_id_matches_probe_or_eval = bool(run_id_for_checks) and _command_contains_run_id(
        commands, ("probe", "eval", "eval_or_smoke_client", "smoke_client"), run_id_for_checks
    )
    run_id_matches_result_info_path = (
        bool(run_id_for_checks)
        and isinstance(result_info_path, str)
        and run_id_for_checks in result_info_path
    )

    step_results = live_probe.get("step_results")
    step_response_present = any(
        isinstance(row, dict) and row.get("response_present") is True
        for row in (step_results if isinstance(step_results, list) else [])
    )
    reset_passed = (
        live_probe.get("reset_observation_present") is True
        and _row_passed(rows, "observation keys")
    )
    step_passed = (
        step_response_present
        and _row_passed(rows, "action dialects")
        and _row_passed(rows, "reward/success fields")
    )
    render_passed = _row_passed(rows, "camera input keys")
    metric_passed = _row_passed(rows, "reward/success fields") and result_info is not None
    logging_passed = (
        _row_passed(rows, "logging fields")
        and _path_exists(result_info_path)
        and _path_exists(stdout_path)
        and _path_exists(stderr_path)
    )
    stdout_exists = _path_exists(stdout_path)
    stderr_exists = _path_exists(stderr_path)
    no_fail_or_blocked_rows = all(
        row.get("status") == "PASS" for row in rows.values()
    )

    blockers: list[dict[str, Any]] = []
    if not run_id_for_checks:
        blockers.append({"code": "run_id_missing", "field": "logging.run_id"})
    elif not run_id_is_fresh:
        blockers.append(
            {"code": "run_id_not_fresh", "field": "logging.run_id", "actual": run_id}
        )
    if not expected_run_id_matches:
        blockers.append(
            {
                "code": "run_id_mismatch",
                "field": "logging.run_id",
                "actual": run_id,
                "expected": expected_run_id,
            }
        )
    if not run_id_matches_submit:
        blockers.append(
            {
                "code": "run_id_missing_from_submit_command",
                "field": "commands.submit",
                "run_id": run_id,
            }
        )
    if not run_id_matches_probe_or_eval:
        blockers.append(
            {
                "code": "run_id_missing_from_probe_or_eval_command",
                "field": "commands.probe|commands.eval_or_smoke_client",
                "run_id": run_id,
            }
        )
    if not run_id_matches_result_info_path:
        blockers.append(
            {
                "code": "run_id_missing_from_result_info_path",
                "field": "result_info_path",
                "run_id": run_id,
                "path": result_info_path,
            }
        )
    if submit_exit_code != 0:
        blockers.append(
            {
                "code": "submit_failed",
                "field": "submit_exit_code",
                "actual": submit_exit_code,
                "expected": 0,
            }
        )
    if probe_or_eval_exit_code != 0:
        blockers.append(
            {
                "code": "probe_or_eval_failed",
                "field": "probe_or_eval_exit_code",
                "actual": probe_or_eval_exit_code,
                "expected": 0,
            }
        )
    if adapter.get("status") != "pass":
        blockers.append(
            {
                "code": "adapter_preflight_not_pass",
                "field": "adapter_record.status",
                "actual": adapter.get("status"),
                "expected": "pass",
            }
        )
    if adapter.get("legacy_overlay_used") is not False:
        blockers.append(
            {
                "code": "legacy_overlay_used",
                "field": "adapter_record.legacy_overlay_used",
                "actual": adapter.get("legacy_overlay_used"),
                "expected": False,
            }
        )
    for name, row in rows.items():
        status = row.get("status")
        if status != "PASS":
            blockers.append(
                {
                    "code": "probe_row_blocked",
                    "field": f"schema_rows.{name}",
                    "status": status,
                    "finding": row.get("finding"),
                }
            )
    if result_info is None:
        blockers.append(
            {
                "code": "result_info_missing",
                "field": "result_info_path",
                "path": result_info_path,
            }
        )
    if not logging_passed:
        blockers.append(
            {
                "code": "runtime_logging_incomplete",
                "field": "logging",
                "result_info_exists": _path_exists(result_info_path),
                "stdout_exists": _path_exists(stdout_path),
                "stderr_exists": _path_exists(stderr_path),
            }
        )

    status = "PASS" if not blockers else "BLOCKED"
    failure_phase, failure_owner, blocker_or_next_action = _first_failure(blockers)
    record = {
        "stage": "aan_stage4b_live_smoke",
        "status": status,
        "run_id": run_id,
        "run_id_is_fresh": run_id_is_fresh,
        "run_id_matches_submit": run_id_matches_submit,
        "run_id_matches_probe_or_eval": run_id_matches_probe_or_eval,
        "run_id_matches_result_info_path": run_id_matches_result_info_path,
        "commands": commands,
        "adapter_record": str(adapter_record_path),
        "probe_json": str(probe_json_path),
        "config_path": adapter.get("config_path"),
        "task_name": adapter.get("task_name"),
        "composite_assets_root": adapter.get("composite_assets_root"),
        "namespace": adapter.get("namespace"),
        "mounted_root_usd": adapter.get("mounted_root_usd"),
        "mounted_root_usd_sha256": adapter.get("mounted_root_usd_sha256"),
        "package_tree_digest": adapter.get("package_tree_digest"),
        "mounted_package_tree_digest": adapter.get("mounted_package_tree_digest"),
        "runtime_usd_name": adapter.get("runtime_usd_name"),
        "resolved_runtime_scene": adapter.get("resolved_runtime_scene"),
        "runtime_scene_sha256": adapter.get("runtime_scene_sha256"),
        "wrapper_references": adapter.get("wrapper_references", []),
        "legacy_overlay_used": adapter.get("legacy_overlay_used"),
        "reset_passed": reset_passed,
        "step_passed": step_passed,
        "render_passed": render_passed,
        "metric_passed": metric_passed,
        "logging_passed": logging_passed,
        "submit_exit_code": submit_exit_code,
        "probe_or_eval_exit_code": probe_or_eval_exit_code,
        "stdout_exists": stdout_exists,
        "stderr_exists": stderr_exists,
        "no_fail_or_blocked_rows": no_fail_or_blocked_rows,
        "aan_live_eval_smoke_passed": status == "PASS",
        "failure_phase": failure_phase,
        "failure_owner": failure_owner,
        "blocker_or_next_action": blocker_or_next_action,
        "runtime_warning_summary": _summarize_runtime_warnings(runtime_warning_logs),
        "required_prim_resolution_rows": adapter.get("required_prim_resolution_rows", []),
        "schema_rows": probe.get("schema_rows", []),
        "live_probe": live_probe,
        "result_info_path": result_info_path,
        "result_info_exists": result_info is not None,
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
        "score": result_info.get("score") if result_info else None,
        "success_rate": result_info.get("success_rate") if result_info else None,
        "allowed_claims": {
            "aan_runtime_adapter_preflight_passed": adapter.get("status") == "pass",
            "aan_live_eval_smoke_passed": status == "PASS",
            "policy_success_proven": False,
        },
        "forbidden_claims": [
            "official_leaderboard_score_complete",
            "policy_success_proven",
            "full_visual_material_parity_proven",
        ],
        "blockers": blockers,
    }
    if json_out is not None:
        _write_json(json_out, record)
    return record


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build LabUtopia AAN runtime-smoke evidence."
    )
    parser.add_argument("--adapter-record", required=True, type=Path)
    parser.add_argument("--probe-json", required=True, type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("--expected-run-id", default=None)
    parser.add_argument("--submit-exit-code", type=int, required=True)
    parser.add_argument("--probe-or-eval-exit-code", type=int, required=True)
    parser.add_argument("--runtime-warning-log", action="append", default=[], type=Path)
    parser.add_argument(
        "--command",
        action="append",
        default=[],
        help="Record a command as key=value. Repeat for submit/eval/probe/status.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    record = build_runtime_smoke_record(
        adapter_record_path=args.adapter_record,
        probe_json_path=args.probe_json,
        json_out=args.json_out,
        commands=_commands_from_items(args.command),
        expected_run_id=args.expected_run_id,
        submit_exit_code=args.submit_exit_code,
        probe_or_eval_exit_code=args.probe_or_eval_exit_code,
        runtime_warning_logs=args.runtime_warning_log,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
