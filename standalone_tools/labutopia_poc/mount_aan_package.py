#!/usr/bin/env python3
"""Mount an AAN-ready package into the LabUtopia EBench task asset root."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from standalone_tools.labutopia_poc.aan_consumer_check import _package_hash_summary


DEFAULT_EVIDENCE_DIR = Path("docs/labutopia_lab_poc/evidence_manifests")
TASK_CONFIG_SOURCE = "task/task_config.yaml"
REQUIRED_PRIMS_SOURCE = "task/required_prims.yaml"
EVALUATOR_SOURCE = "task/evaluator.yaml"
ROOT_USD_SOURCE = "asset.usd"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _default_json_out() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return DEFAULT_EVIDENCE_DIR / f"aan_dryingbox_task_mount_{stamp}.json"


def _namespace_parts(namespace: str) -> tuple[str, ...]:
    path = Path(namespace)
    if path.is_absolute() or not namespace or namespace.endswith("/"):
        raise ValueError(f"namespace must be a relative path: {namespace}")
    parts = path.parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"namespace must not contain traversal: {namespace}")
    return parts


def _relative_source(namespace: str, package_relative_path: str) -> str:
    return (Path(*_namespace_parts(namespace)) / package_relative_path).as_posix()


def _mount_path(composite_assets_root: Path, namespace: str) -> Path:
    return composite_assets_root / Path(*_namespace_parts(namespace))


def _same_source_symlink(path: Path, package_dir: Path) -> bool:
    return path.is_symlink() and path.resolve() == package_dir.resolve()


def _replace_existing(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)
        return
    if path.exists():
        raise ValueError(f"cannot replace unsupported path type: {path}")


def _ensure_symlink_mount(
    *,
    package_dir: Path,
    composite_assets_root: Path,
    namespace: str,
    replace: bool,
) -> tuple[Path, str, list[dict[str, Any]]]:
    target = _mount_path(composite_assets_root, namespace)
    blockers: list[dict[str, Any]] = []
    if target.exists() or target.is_symlink():
        if _same_source_symlink(target, package_dir):
            return target, "already_mounted_same_source", blockers
        if not replace:
            blockers.append(
                {
                    "code": "namespace_conflict",
                    "field": "namespace",
                    "path": str(target),
                    "existing_resolved_path": (
                        str(target.resolve()) if target.exists() or target.is_symlink() else None
                    ),
                    "expected_resolved_path": str(package_dir.resolve()),
                }
            )
            return target, "namespace_conflict", blockers
        _replace_existing(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(package_dir.resolve(), target_is_directory=True)
    return target, "mounted", blockers


def _load_required_prim_rows(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        rows = data.get("required_prims", [])
    else:
        rows = data
    if not isinstance(rows, list):
        raise ValueError("required_prims.yaml must contain a list or required_prims list")
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"required_prims[{index}] must be a mapping")
        normalized.append(
            {
                "role": row.get("role"),
                "path": row.get("path"),
                "required": row.get("required", True) is not False,
            }
        )
    return normalized


def _dry_run_composition(
    *,
    mounted_root_usd: Path,
    mounted_task_config: Path,
    mounted_required_prims: Path,
    mounted_evaluator: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    task_config_exists = mounted_task_config.is_file()
    required_prims_exists = mounted_required_prims.is_file()
    evaluator_exists = mounted_evaluator.is_file()
    if not task_config_exists:
        blockers.append(
            {
                "code": "missing_task_config",
                "field": "task_config_source",
                "path": str(mounted_task_config),
            }
        )
    if not required_prims_exists:
        blockers.append(
            {
                "code": "missing_required_prims_file",
                "field": "required_prims_source",
                "path": str(mounted_required_prims),
            }
        )
    if not evaluator_exists:
        blockers.append(
            {
                "code": "missing_evaluator",
                "field": "evaluator_source",
                "path": str(mounted_evaluator),
            }
        )

    stage = None
    stage_open_error = None
    try:
        from pxr import Usd  # type: ignore

        stage = Usd.Stage.Open(str(mounted_root_usd))
    except Exception as exc:  # pragma: no cover - depends on USD runtime details.
        stage_open_error = f"{type(exc).__name__}: {exc}"
    usd_stage_opened = stage is not None
    if not usd_stage_opened:
        blockers.append(
            {
                "code": "usd_stage_open_failed",
                "field": "root_usd_source",
                "path": str(mounted_root_usd),
                "error": stage_open_error,
            }
        )

    rows: list[dict[str, Any]] = []
    if required_prims_exists:
        for index, row in enumerate(_load_required_prim_rows(mounted_required_prims)):
            prim_path = row["path"]
            exists = bool(stage and isinstance(prim_path, str) and stage.GetPrimAtPath(prim_path))
            resolved_row = {
                "role": row["role"],
                "path": prim_path,
                "required": row["required"],
                "exists": exists,
            }
            rows.append(resolved_row)
            if row["required"] and not exists:
                blockers.append(
                    {
                        "code": "missing_required_prim",
                        "field": f"task.required_prims[{index}].path",
                        "path": prim_path,
                        "role": row["role"],
                    }
                )

    all_required_found = all(row["exists"] for row in rows if row["required"])
    dry_run = {
        "usd_stage_opened": usd_stage_opened,
        "usd_stage_open_error": stage_open_error,
        "task_config_exists": task_config_exists,
        "required_prims_exists": required_prims_exists,
        "evaluator_exists": evaluator_exists,
        "all_required_prims_found": all_required_found,
        "source_package_modified_during_check": False,
        "runtime_execution": "not_run",
    }
    return dry_run, rows, blockers


def build_mount_record(
    *,
    package_dir: Path,
    manifest_path: Path,
    consumer_check_path: Path,
    composite_assets_root: Path,
    namespace: str,
    replace: bool,
) -> dict[str, Any]:
    resolved_package = package_dir.resolve()
    resolved_manifest = manifest_path.resolve()
    resolved_consumer_check = consumer_check_path.resolve()
    resolved_composite_root = composite_assets_root.resolve()
    hash_before = _package_hash_summary(resolved_package)
    blockers: list[dict[str, Any]] = []
    path_resolution_status = "blocked"
    mount_target = _mount_path(composite_assets_root, namespace).absolute()

    consumer_check = _load_json(consumer_check_path)
    if consumer_check.get("aan_package_mount_allowed") is not True:
        blockers.append(
            {
                "code": "consumer_check_not_mount_allowed",
                "field": "aan_package_mount_allowed",
                "actual": consumer_check.get("aan_package_mount_allowed"),
                "expected": True,
            }
        )
    else:
        mount_target, path_resolution_status, mount_blockers = _ensure_symlink_mount(
            package_dir=resolved_package,
            composite_assets_root=composite_assets_root,
            namespace=namespace,
            replace=replace,
        )
        blockers.extend(mount_blockers)

    mounted_root_usd = mount_target / ROOT_USD_SOURCE
    mounted_task_config = mount_target / TASK_CONFIG_SOURCE
    mounted_required_prims = mount_target / REQUIRED_PRIMS_SOURCE
    mounted_evaluator = mount_target / EVALUATOR_SOURCE
    dry_run = {
        "usd_stage_opened": False,
        "usd_stage_open_error": None,
        "task_config_exists": mounted_task_config.is_file(),
        "required_prims_exists": mounted_required_prims.is_file(),
        "evaluator_exists": mounted_evaluator.is_file(),
        "all_required_prims_found": False,
        "source_package_modified_during_check": False,
        "runtime_execution": "not_run",
    }
    prim_rows: list[dict[str, Any]] = []
    if not blockers:
        dry_run, prim_rows, dry_run_blockers = _dry_run_composition(
            mounted_root_usd=mounted_root_usd,
            mounted_task_config=mounted_task_config,
            mounted_required_prims=mounted_required_prims,
            mounted_evaluator=mounted_evaluator,
        )
        blockers.extend(dry_run_blockers)

    hash_after = _package_hash_summary(resolved_package)
    source_changed = hash_before != hash_after
    dry_run["source_package_modified_during_check"] = source_changed
    if source_changed:
        blockers.append(
            {
                "code": "source_package_changed_during_mount",
                "field": "source_package_hash_after",
            }
        )

    status = "pass" if not blockers else "blocked"
    if blockers and path_resolution_status not in {"namespace_conflict"}:
        path_resolution_status = "blocked"
    return {
        "stage": "aan_task_root_mount_dry_run_composition",
        "status": status,
        "package_dir": str(resolved_package),
        "source_manifest": str(resolved_manifest),
        "consumer_check": str(resolved_consumer_check),
        "composite_assets_root": str(resolved_composite_root),
        "namespace": namespace,
        "mounted_namespace": str(mount_target.absolute()),
        "mounted_root_usd": str(mounted_root_usd.absolute()),
        "mounted_task_config": str(mounted_task_config.absolute()),
        "mounted_required_prims": str(mounted_required_prims.absolute()),
        "mounted_evaluator": str(mounted_evaluator.absolute()),
        "symlink_or_copy_mode": "symlink",
        "path_resolution_status": path_resolution_status,
        "task_config_source": _relative_source(namespace, TASK_CONFIG_SOURCE),
        "required_prims_source": _relative_source(namespace, REQUIRED_PRIMS_SOURCE),
        "evaluator_source": _relative_source(namespace, EVALUATOR_SOURCE),
        "root_usd_source": _relative_source(namespace, ROOT_USD_SOURCE),
        "dry_run_composition": dry_run,
        "required_prim_resolution_rows": prim_rows,
        "source_package_hash_before": hash_before,
        "source_package_hash_after": hash_after,
        "local_usd_repair_allowed": False,
        "runtime_execution_passed": False,
        "forbidden_claims": ["ebench_task_execution_passed"],
        "blockers": blockers,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Mount an AAN-ready package into a GenManip / EBench assets root "
            "and run a dry-run composition check."
        )
    )
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--consumer-check", required=True, type=Path)
    parser.add_argument("--composite-assets-root", required=True, type=Path)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace an existing namespace that points somewhere else.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.package_dir.is_dir():
        raise SystemExit(f"package directory does not exist: {args.package_dir}")
    if not args.manifest.is_file():
        raise SystemExit(f"manifest does not exist: {args.manifest}")
    if not args.consumer_check.is_file():
        raise SystemExit(f"consumer check does not exist: {args.consumer_check}")
    try:
        _namespace_parts(args.namespace)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    record = build_mount_record(
        package_dir=args.package_dir,
        manifest_path=args.manifest,
        consumer_check_path=args.consumer_check,
        composite_assets_root=args.composite_assets_root,
        namespace=args.namespace,
        replace=args.replace,
    )
    json_out = args.json_out or _default_json_out()
    _write_json(json_out, record)
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
