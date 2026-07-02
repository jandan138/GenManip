#!/usr/bin/env python3
"""Create and preflight the AAN runtime adapter for LabUtopia Lift2 smoke."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_EVIDENCE_DIR = Path("docs/labutopia_lab_poc/evidence_manifests")
DEFAULT_AAN_GROUP = "ebench/labutopia_lab_poc/aan_lift2_candidate"
DEFAULT_AAN_TASK = "level1_open_door"
DEFAULT_WRAPPER_USD_NAME = "scene_usds/labutopia/aan/dryingbox_01_overlay_scene"
LEGACY_USD_NAME = "scene_usds/labutopia/level1_poc/lab_001/scene"
DEFAULT_SOURCE_TASK_CONFIG = Path(
    "configs/tasks/ebench/labutopia_lab_poc/lift2_candidate/level1_open_door.yml"
)


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _default_json_out() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return DEFAULT_EVIDENCE_DIR / f"aan_dryingbox_runtime_adapter_{stamp}.json"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_hash_summary(package_dir: Path) -> dict[str, Any]:
    files = sorted(path for path in package_dir.rglob("*") if path.is_file())
    tree_digest = hashlib.sha256()
    file_hashes: list[dict[str, str]] = []
    for path in files:
        relative = path.relative_to(package_dir).as_posix()
        file_sha = _sha256_file(path)
        tree_digest.update(relative.encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(file_sha.encode("ascii"))
        tree_digest.update(b"\n")
        file_hashes.append({"path": relative, "sha256": file_sha})
    return {
        "algorithm": "sha256(sorted_relative_path_nul_file_sha256)",
        "digest": tree_digest.hexdigest(),
        "files": file_hashes,
    }


def _task_group_dir(repo_root: Path, task_group: str = DEFAULT_AAN_GROUP) -> Path:
    return repo_root / "configs/tasks" / task_group


def _task_config_path(
    repo_root: Path,
    task_group: str = DEFAULT_AAN_GROUP,
    task_name: str = DEFAULT_AAN_TASK,
) -> Path:
    return _task_group_dir(repo_root, task_group) / f"{task_name}.yml"


def _task_index_path(repo_root: Path, task_group: str = DEFAULT_AAN_GROUP) -> Path:
    return _task_group_dir(repo_root, task_group) / f"{Path(task_group).name}.json"


def _task_assets_manifest_path(
    repo_root: Path, task_group: str = DEFAULT_AAN_GROUP
) -> Path:
    return _task_group_dir(repo_root, task_group) / "assets_manifest.json"


def _task_config_ref(repo_root: Path, task_config_path: Path) -> str:
    tasks_root = repo_root / "configs/tasks"
    return task_config_path.resolve().relative_to(tasks_root.resolve()).as_posix()


def _wrapper_path(composite_assets_root: Path, runtime_usd_name: str) -> Path:
    runtime_path = Path(runtime_usd_name)
    if runtime_path.suffix not in {".usd", ".usda", ".usdc"}:
        runtime_path = Path(f"{runtime_usd_name}.usda")
    return composite_assets_root / runtime_path


def _expected_mounted_root_usd(composite_assets_root: Path, namespace: str) -> Path:
    return (composite_assets_root / namespace / "asset.usd").absolute()


def _relative_reference(from_wrapper: Path, mounted_root_usd: Path) -> str:
    return Path(
        os.path.relpath(mounted_root_usd.absolute(), from_wrapper.parent.absolute())
    ).as_posix()


def _write_wrapper(
    wrapper_path: Path,
    mounted_root_usd: Path,
    *,
    runtime_scene_uid: str | None = None,
    runtime_object_uid: str | None = None,
) -> str:
    wrapper_reference = _relative_reference(wrapper_path, mounted_root_usd)
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    if runtime_scene_uid and runtime_object_uid:
        lines = [
            "#usda 1.0",
            "(",
            '    defaultPrim = "World"',
            ")",
            "",
            'def Xform "World"',
            "{",
            f'    def Xform "{runtime_scene_uid}"',
            "    {",
            f'        def Xform "obj_{runtime_object_uid}" (',
            f"            references = @{wrapper_reference}@",
            "        )",
            "        {",
            "        }",
            "    }",
            "}",
            "",
        ]
    else:
        lines = [
            "#usda 1.0",
            "(",
            '    defaultPrim = "World"',
            ")",
            "",
            'def Xform "World" (',
            f"    references = @{wrapper_reference}@</World>",
            ")",
            "{",
            "}",
            "",
        ]
    wrapper_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    return wrapper_reference


def _wrapper_reference_asset_paths(
    wrapper_path: Path, blockers: list[dict[str, Any]]
) -> list[str]:
    if not wrapper_path.is_file():
        return []
    try:
        from pxr import Sdf  # type: ignore

        layer = Sdf.Layer.FindOrOpen(str(wrapper_path))
        if layer is None:
            blockers.append(
                {
                    "code": "runtime_wrapper_reference_parse_failed",
                    "field": "wrapper_references",
                    "path": str(wrapper_path),
                    "error": "Sdf.Layer.FindOrOpen returned None",
                }
            )
            return []
        world_prim = layer.GetPrimAtPath("/World")
        if world_prim is None:
            blockers.append(
                {
                    "code": "runtime_wrapper_world_prim_missing",
                    "field": "wrapper_references",
                    "path": str(wrapper_path),
                }
            )
            return []
        references: list[str] = []
        prims = [world_prim]
        while prims:
            prim = prims.pop(0)
            for items in (
                prim.referenceList.explicitItems,
                prim.referenceList.prependedItems,
                prim.referenceList.appendedItems,
                prim.referenceList.addedItems,
            ):
                for reference in items:
                    asset_path = getattr(reference, "assetPath", "")
                    if asset_path and asset_path not in references:
                        references.append(asset_path)
            prims.extend(list(prim.nameChildren))
        return references
    except Exception as exc:  # pragma: no cover - depends on USD runtime.
        blockers.append(
            {
                "code": "runtime_wrapper_reference_parse_failed",
                "field": "wrapper_references",
                "path": str(wrapper_path),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        return []


def _make_task_config(
    source: dict[str, Any],
    namespace: str,
    *,
    task_group: str = DEFAULT_AAN_GROUP,
    task_name: str = DEFAULT_AAN_TASK,
    runtime_usd_name: str = DEFAULT_WRAPPER_USD_NAME,
    generic_smoke: bool = False,
) -> dict[str, Any]:
    config = copy.deepcopy(source)
    evaluation_configs = config.get("evaluation_configs")
    if not isinstance(evaluation_configs, list) or not evaluation_configs:
        raise ValueError("source task config must contain evaluation_configs")
    evaluation = evaluation_configs[0]
    if not isinstance(evaluation, dict):
        raise ValueError("evaluation_configs[0] must be a mapping")

    evaluation["task_name"] = f"{task_group}/{task_name}"
    evaluation["usd_name"] = runtime_usd_name
    evaluation["labutopia_aan_consumer"] = {
        "schema_version": 1,
        "runtime_adapter": "aan_usda_wrapper",
        "namespace": namespace,
        "mounted_root_usd": f"{namespace}/asset.usd",
        "legacy_overlay_used": False,
        "generic_smoke": generic_smoke,
    }
    if generic_smoke:
        evaluation["instruction"] = "Run AAN package reset/step smoke."
        generation_config = evaluation.setdefault("generation_config", {})
        if isinstance(generation_config, dict):
            generation_config["goal"] = []
        evaluation["object_config"] = {}
    lift2_contract = evaluation.setdefault("labutopia_lift2_contract", {})
    if isinstance(lift2_contract, dict):
        lift2_contract["material_boundary"] = "aan_package_material_closure_from_manifest"

    env_vars = evaluation.setdefault("env_vars", {})
    if isinstance(env_vars, dict):
        mdl_path = f"{{ASSETS_DIR}}/{namespace}/deps/mdl"
        existing = str(env_vars.get("MDL_SYSTEM_PATH", "/isaac-sim/materials/"))
        parts = [part for part in existing.split(":") if part]
        if mdl_path not in parts:
            parts.append(mdl_path)
        env_vars["MDL_SYSTEM_PATH"] = ":".join(parts)
    return config


def _write_task_artifacts(
    *,
    repo_root: Path,
    source_task_config_path: Path,
    composite_assets_root: Path,
    namespace: str,
    mount_record_path: Path,
    mounted_root_usd: Path,
    task_group: str = DEFAULT_AAN_GROUP,
    task_name: str = DEFAULT_AAN_TASK,
    runtime_usd_name: str = DEFAULT_WRAPPER_USD_NAME,
    generic_smoke: bool = False,
) -> tuple[Path, Path, Path]:
    source = _read_yaml(source_task_config_path)
    task_config_path = _task_config_path(repo_root, task_group, task_name)
    index_path = _task_index_path(repo_root, task_group)
    assets_manifest_path = _task_assets_manifest_path(repo_root, task_group)

    _write_yaml(
        task_config_path,
        _make_task_config(
            source,
            namespace,
            task_group=task_group,
            task_name=task_name,
            runtime_usd_name=runtime_usd_name,
            generic_smoke=generic_smoke,
        ),
    )
    _write_json(index_path, [f"{task_group}/{task_name}.yml"])
    _write_json(
        assets_manifest_path,
        {
            "schema_version": 1,
            "overlay_root": str(composite_assets_root.resolve()),
            "runtime_usd_name": runtime_usd_name,
            "usd_name": runtime_usd_name,
            "namespace": namespace,
            "mounted_root_usd": str(mounted_root_usd.absolute()),
            "mount_record": str(mount_record_path.resolve()),
            "legacy_overlay_used": False,
            "generic_smoke": generic_smoke,
        },
    )
    return task_config_path, index_path, assets_manifest_path


def _load_first_evaluation(task_config_path: Path) -> dict[str, Any]:
    task_config = _read_yaml(task_config_path)
    evaluation_configs = task_config.get("evaluation_configs")
    if not isinstance(evaluation_configs, list) or not evaluation_configs:
        raise ValueError(f"{task_config_path}: missing evaluation_configs")
    evaluation = evaluation_configs[0]
    if not isinstance(evaluation, dict):
        raise ValueError(f"{task_config_path}: evaluation_configs[0] must be a mapping")
    return evaluation


def _required_rows_from_runtime_wrapper(
    wrapper_path: Path,
    rows: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    *,
    runtime_scene_uid: str | None = None,
    runtime_object_uid: str | None = None,
) -> list[dict[str, Any]]:
    runtime_rows: list[dict[str, Any]] = []
    stage = None
    stage_open_error = None
    try:
        from pxr import Usd  # type: ignore

        stage = Usd.Stage.Open(str(wrapper_path))
    except Exception as exc:  # pragma: no cover - depends on USD runtime.
        stage_open_error = f"{type(exc).__name__}: {exc}"

    if stage is None:
        blockers.append(
            {
                "code": "runtime_wrapper_open_failed",
                "field": "resolved_runtime_scene",
                "path": str(wrapper_path),
                "error": stage_open_error,
            }
        )

    for index, row in enumerate(rows):
        prim_path = row.get("path")
        runtime_path = _runtime_required_prim_path(
            prim_path,
            runtime_scene_uid=runtime_scene_uid,
            runtime_object_uid=runtime_object_uid,
        )
        is_not_applicable = (
            row.get("status") == "not_applicable"
            or prim_path == "N/A"
            or row.get("required", True) is False and prim_path == "N/A"
        )
        exists = (
            None
            if is_not_applicable
            else bool(
                stage
                and isinstance(runtime_path, str)
                and stage.GetPrimAtPath(runtime_path)
            )
        )
        runtime_row = dict(row)
        if runtime_scene_uid and runtime_object_uid:
            runtime_row["runtime_path"] = runtime_path
        runtime_row["exists_in_runtime_wrapper"] = exists
        runtime_rows.append(runtime_row)
        if not is_not_applicable and row.get("required", True) is not False and not exists:
            blockers.append(
                {
                    "code": "required_prim_missing_in_runtime_wrapper",
                    "field": f"required_prim_resolution_rows[{index}].path",
                    "path": prim_path,
                    "runtime_path": runtime_path,
                    "role": row.get("role"),
                }
            )
    return runtime_rows


def _runtime_required_prim_path(
    prim_path: Any,
    *,
    runtime_scene_uid: str | None,
    runtime_object_uid: str | None,
) -> Any:
    if not isinstance(prim_path, str):
        return prim_path
    if prim_path == "N/A":
        return "N/A"
    if not runtime_scene_uid or not runtime_object_uid:
        return prim_path
    normalized = prim_path if prim_path.startswith("/") else f"/{prim_path}"
    parts = [part for part in normalized.split("/") if part]
    suffix = "/" + "/".join(parts[1:]) if len(parts) > 1 else ""
    return f"/World/{runtime_scene_uid}/obj_{runtime_object_uid}{suffix}"


def preflight_runtime_adapter(
    *,
    repo_root: Path,
    mount_record_path: Path,
    task_config_path: Path,
    json_out: Path | None = None,
    task_group: str = DEFAULT_AAN_GROUP,
    expected_runtime_usd_name: str = DEFAULT_WRAPPER_USD_NAME,
    runtime_scene_uid: str | None = None,
    runtime_object_uid: str | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    mount_record_path = mount_record_path.resolve()
    task_config_path = task_config_path.resolve()
    mount_record = _read_json(mount_record_path)
    blockers: list[dict[str, Any]] = []

    composite_assets_root = Path(str(mount_record.get("composite_assets_root", ""))).resolve()
    namespace = str(mount_record.get("namespace", ""))
    recorded_mounted_root_usd = Path(
        str(mount_record.get("mounted_root_usd", ""))
    ).absolute()
    expected_mounted_root_usd = _expected_mounted_root_usd(
        composite_assets_root, namespace
    )
    mounted_namespace = expected_mounted_root_usd.parent
    mounted_root_usd = expected_mounted_root_usd
    evaluation = _load_first_evaluation(task_config_path)
    runtime_usd_name = evaluation.get("usd_name")
    config_ref = _task_config_ref(repo_root, task_config_path)
    wrapper_path = (
        _wrapper_path(composite_assets_root, runtime_usd_name)
        if isinstance(runtime_usd_name, str)
        else composite_assets_root / "invalid.usda"
    )

    if mount_record.get("status") != "pass":
        blockers.append(
            {
                "code": "mount_record_not_pass",
                "field": "mount_record.status",
                "actual": mount_record.get("status"),
                "expected": "pass",
            }
        )
    if not config_ref.startswith(f"{task_group}/"):
        blockers.append(
            {
                "code": "non_aan_config_path",
                "field": "config_path",
                "actual": config_ref,
                "expected_prefix": f"{task_group}/",
            }
        )
    if runtime_usd_name != expected_runtime_usd_name:
        blockers.append(
            {
                "code": "legacy_usd_name_used"
                if runtime_usd_name == LEGACY_USD_NAME
                else "unexpected_usd_name",
                "field": "evaluation_configs[0].usd_name",
                "actual": runtime_usd_name,
                "expected": expected_runtime_usd_name,
            }
        )
    if not wrapper_path.is_file():
        blockers.append(
            {
                "code": "runtime_wrapper_missing",
                "field": "resolved_runtime_scene",
                "path": str(wrapper_path),
            }
        )
    if recorded_mounted_root_usd != expected_mounted_root_usd:
        blockers.append(
            {
                "code": "mounted_root_usd_not_in_composite_namespace",
                "field": "mounted_root_usd",
                "actual": str(recorded_mounted_root_usd),
                "expected": str(expected_mounted_root_usd),
            }
        )

    expected_reference = (
        _relative_reference(wrapper_path, mounted_root_usd)
        if wrapper_path.parent.exists()
        else ""
    )
    wrapper_references = _wrapper_reference_asset_paths(wrapper_path, blockers)
    if expected_reference and expected_reference not in wrapper_references:
        blockers.append(
            {
                "code": "runtime_wrapper_missing_aan_reference",
                "field": "wrapper_references",
                "actual": wrapper_references,
                "expected": expected_reference,
                "path": str(wrapper_path),
            }
        )

    required_rows = mount_record.get("required_prim_resolution_rows", [])
    if not isinstance(required_rows, list):
        required_rows = []
        blockers.append(
            {
                "code": "required_rows_missing",
                "field": "required_prim_resolution_rows",
            }
        )
    runtime_rows = _required_rows_from_runtime_wrapper(
        wrapper_path,
        required_rows,
        blockers,
        runtime_scene_uid=runtime_scene_uid,
        runtime_object_uid=runtime_object_uid,
    )

    digest = mount_record.get("source_package_hash_after", {})
    package_tree_digest = digest.get("digest") if isinstance(digest, dict) else None
    mounted_package_hash = None
    if mounted_namespace.is_dir():
        mounted_package_hash = _package_hash_summary(mounted_namespace)
    else:
        blockers.append(
            {
                "code": "mounted_namespace_missing",
                "field": "mounted_namespace",
                "path": str(mounted_namespace),
            }
        )
    mounted_package_tree_digest = (
        mounted_package_hash.get("digest") if mounted_package_hash else None
    )
    if package_tree_digest != mounted_package_tree_digest:
        blockers.append(
            {
                "code": "mounted_package_tree_digest_mismatch",
                "field": "source_package_hash_after.digest",
                "actual": mounted_package_tree_digest,
                "expected": package_tree_digest,
            }
        )
    legacy_overlay_used = runtime_usd_name == LEGACY_USD_NAME
    status = "pass" if not blockers else "blocked"
    record = {
        "stage": "aan_runtime_adapter_preflight",
        "status": status,
        "run_id": None,
        "command": None,
        "config_path": config_ref,
        "task_name": evaluation.get("task_name"),
        "composite_assets_root": str(composite_assets_root),
        "namespace": namespace,
        "runtime_scene_uid": runtime_scene_uid,
        "runtime_object_uid": runtime_object_uid,
        "mount_record_mounted_root_usd": str(recorded_mounted_root_usd),
        "mounted_root_usd": str(mounted_root_usd),
        "mounted_root_usd_sha256": _sha256_file(mounted_root_usd)
        if mounted_root_usd.is_file()
        else None,
        "package_tree_digest": package_tree_digest,
        "mounted_package_tree_digest": mounted_package_tree_digest,
        "mounted_package_hash": mounted_package_hash,
        "runtime_usd_name": runtime_usd_name,
        "resolved_runtime_scene": str(wrapper_path),
        "runtime_scene_sha256": _sha256_file(wrapper_path) if wrapper_path.is_file() else None,
        "wrapper_references": wrapper_references,
        "legacy_overlay_used": legacy_overlay_used,
        "reset_passed": False,
        "step_passed": False,
        "required_prim_resolution_rows": runtime_rows,
        "result_info_path": None,
        "stdout_path": None,
        "stderr_path": None,
        "runtime_execution_passed": False,
        "allowed_claims": {
            "aan_runtime_adapter_preflight_passed": status == "pass",
            "aan_live_eval_smoke_passed": False,
        },
        "forbidden_claims": [
            "ebench_task_execution_passed",
            "official_leaderboard_score_complete",
            "policy_success_proven",
        ],
        "blockers": blockers,
    }
    if json_out is not None:
        _write_json(json_out, record)
    return record


def build_runtime_adapter_record(
    *,
    repo_root: Path,
    mount_record_path: Path,
    source_task_config_path: Path,
    json_out: Path | None = None,
    task_group: str = DEFAULT_AAN_GROUP,
    task_name: str = DEFAULT_AAN_TASK,
    runtime_usd_name: str = DEFAULT_WRAPPER_USD_NAME,
    runtime_scene_uid: str | None = None,
    runtime_object_uid: str | None = None,
    generic_smoke: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    mount_record_path = mount_record_path.resolve()
    source_task_config_path = source_task_config_path.resolve()
    mount_record = _read_json(mount_record_path)
    composite_assets_root = Path(str(mount_record["composite_assets_root"])).resolve()
    namespace = str(mount_record["namespace"])
    mounted_root_usd = _expected_mounted_root_usd(composite_assets_root, namespace)
    wrapper_path = _wrapper_path(composite_assets_root, runtime_usd_name)

    _write_wrapper(
        wrapper_path,
        mounted_root_usd,
        runtime_scene_uid=runtime_scene_uid,
        runtime_object_uid=runtime_object_uid,
    )
    task_config_path, _index_path, _assets_manifest_path = _write_task_artifacts(
        repo_root=repo_root,
        source_task_config_path=source_task_config_path,
        composite_assets_root=composite_assets_root,
        namespace=namespace,
        mount_record_path=mount_record_path,
        mounted_root_usd=mounted_root_usd,
        task_group=task_group,
        task_name=task_name,
        runtime_usd_name=runtime_usd_name,
        generic_smoke=generic_smoke,
    )
    return preflight_runtime_adapter(
        repo_root=repo_root,
        mount_record_path=mount_record_path,
        task_config_path=task_config_path,
        json_out=json_out,
        task_group=task_group,
        expected_runtime_usd_name=runtime_usd_name,
        runtime_scene_uid=runtime_scene_uid,
        runtime_object_uid=runtime_object_uid,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and preflight the LabUtopia AAN runtime adapter."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--mount-record", type=Path, required=True)
    parser.add_argument("--source-task-config", type=Path, default=DEFAULT_SOURCE_TASK_CONFIG)
    parser.add_argument("--task-group", default=DEFAULT_AAN_GROUP)
    parser.add_argument("--task-name", default=DEFAULT_AAN_TASK)
    parser.add_argument("--runtime-usd-name", default=DEFAULT_WRAPPER_USD_NAME)
    parser.add_argument("--runtime-scene-uid", default=None)
    parser.add_argument("--runtime-object-uid", default=None)
    parser.add_argument("--generic-smoke", action="store_true")
    parser.add_argument("--json-out", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(raw_argv)
    repo_root = args.repo_root.resolve()
    source_task_config = args.source_task_config
    if not source_task_config.is_absolute():
        source_task_config = repo_root / source_task_config
    json_out = args.json_out or repo_root / _default_json_out()
    record = build_runtime_adapter_record(
        repo_root=repo_root,
        mount_record_path=args.mount_record,
        source_task_config_path=source_task_config,
        task_group=args.task_group,
        task_name=args.task_name,
        runtime_usd_name=args.runtime_usd_name,
        runtime_scene_uid=args.runtime_scene_uid,
        runtime_object_uid=args.runtime_object_uid,
        generic_smoke=args.generic_smoke,
        json_out=None,
    )
    record["command"] = (
        "python standalone_tools/labutopia_poc/aan_runtime_adapter.py "
        + shlex.join(raw_argv)
    )
    _write_json(json_out, record)
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record["status"] == "pass" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
