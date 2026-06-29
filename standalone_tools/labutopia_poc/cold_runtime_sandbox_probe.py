#!/usr/bin/env python3
"""Cold-runtime sandbox probe for LabUtopia EBench task packages."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - exercised by environments without PyYAML
    yaml = None


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = ROOT / "configs/tasks/ebench/labutopia_lab_poc"
DEFAULT_MANIFEST = PACKAGE_ROOT / "common/assets_manifest.json"
DEFAULT_VALIDATION_COMMAND = [
    sys.executable,
    "standalone_tools/labutopia_poc/validate_task_package.py",
]
PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED"
CACHE_MARKERS = ("/.cache/", "/ov/pkg/", "/kit/cache/")
REMOTE_URI_PREFIXES = (
    "http://",
    "https://",
    "omniverse://",
    "s3://",
    "http:/",
    "https:/",
    "omniverse:/",
    "s3:/",
)
DEFAULT_CHILD_TIMEOUT_SECONDS = 120
BUILTIN_ALLOWLIST_ROOTS = (
    Path("/isaac-sim/materials"),
    Path("/isaac-sim/kit/mdl"),
)
BUILTIN_MDL_SEARCH_ROOTS = (
    Path("/isaac-sim/kit/mdl/core/Base"),
    Path("/isaac-sim/kit/mdl/core/mdl"),
)
FILE_LIKE_ASSET_SUFFIXES = (
    ".usd",
    ".usda",
    ".usdc",
    ".mdl",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".exr",
)


def build_claim_boundary(status: str) -> dict[str, bool]:
    return {
        "cold_runtime_sandbox_probe_passed": status == PASS,
        "official_leaderboard_claim_allowed": False,
        "policy_success_claim_allowed": False,
        "pm_showcase_ready": False,
        "native_material_closure_claim_allowed": False,
        "full_native_material_closure_claim_allowed": False,
    }


def derive_parent_status(
    *,
    static_validation_status: str,
    child_status: str,
    runtime_counts: dict[str, int],
) -> str:
    if static_validation_status == BLOCKED or child_status == BLOCKED:
        return BLOCKED
    if static_validation_status != PASS or child_status != PASS:
        return FAIL
    blocking_keys = (
        "remote_uri_count",
        "user_cache_path_count",
        "unauthorized_outside_sandbox_runtime_path_count",
        "missing_local_dependency_count",
        "non_allowlisted_search_path_count",
        "user_cache_env_count",
        "original_overlay_search_path_count",
        "dependency_scan_error_count",
        "missing_required_prim_count",
    )
    if any(int(runtime_counts.get(key) or 0) for key in blocking_keys):
        return FAIL
    return PASS


class SandboxBuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class SandboxLayout:
    sandbox_root: Path
    package_config_root: Path
    assets_dir: Path
    home: Path
    cache: Path
    reports: Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_file_with_identical_collision(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if dst.is_dir():
            raise SandboxBuildError(f"collision targets directory: {dst}")
        if _sha256(src) != _sha256(dst):
            raise SandboxBuildError(f"collision differs: {src} -> {dst}")
        return
    shutil.copy2(src, dst)


def _copy_tree_contents(src_root: Path, dst_root: Path) -> None:
    if not src_root.exists():
        return
    for src in src_root.rglob("*"):
        if src.is_dir():
            continue
        relative = src.relative_to(src_root)
        _copy_file_with_identical_collision(src, dst_root / relative)


def build_sandbox_layout(
    *,
    sandbox_root: Path,
    package_root: Path,
    overlay_root: Path,
) -> SandboxLayout:
    layout = SandboxLayout(
        sandbox_root=sandbox_root,
        package_config_root=sandbox_root / "package_config",
        assets_dir=sandbox_root / "assets",
        home=sandbox_root / "home",
        cache=sandbox_root / "cache",
        reports=sandbox_root / "reports",
    )
    for path in (
        layout.package_config_root,
        layout.assets_dir,
        layout.home,
        layout.cache,
        layout.reports,
    ):
        path.mkdir(parents=True, exist_ok=True)
    config_dst = layout.package_config_root / "configs/tasks/ebench/labutopia_lab_poc"
    _copy_tree_contents(package_root, config_dst)
    _copy_tree_contents(package_root / "common", layout.assets_dir)
    _copy_tree_contents(overlay_root, layout.assets_dir)
    return layout


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _split_search_path(value: str) -> list[str]:
    return [part for part in value.split(os.pathsep) if part]


def _append_existing_paths(entries: list[str], paths: tuple[Path, ...]) -> list[str]:
    results = list(entries)
    existing = set(results)
    for path in paths:
        if path.exists():
            text = str(path)
            if text not in existing:
                results.append(text)
                existing.add(text)
    return results


def _search_path_report(
    entries: list[str],
    *,
    assets_dir: Path,
    builtin_allowlist_roots: tuple[Path, ...],
) -> tuple[list[str], int, int, int]:
    resolved_entries: list[str] = []
    non_allowlisted = 0
    original_overlay = 0
    user_cache = 0
    for entry in entries:
        resolved = entry.replace("{ASSETS_DIR}", str(assets_dir))
        resolved_entries.append(resolved)
        candidate = Path(resolved)
        normalized = resolved.lower()
        if any(marker in normalized for marker in CACHE_MARKERS):
            user_cache += 1
        if "/cpfs/" in normalized and not _is_relative_to(candidate, assets_dir):
            original_overlay += 1
        if candidate.is_absolute() and not _is_relative_to(candidate, assets_dir):
            if not any(
                _is_relative_to(candidate, root) for root in builtin_allowlist_roots
            ):
                non_allowlisted += 1
    return resolved_entries, non_allowlisted, original_overlay, user_cache


def build_child_environment(
    layout: SandboxLayout,
    *,
    base_env: os._Environ[str] | dict[str, str],
    task_env_vars: dict[str, str] | None = None,
    builtin_allowlist_roots: tuple[Path, ...] = BUILTIN_ALLOWLIST_ROOTS,
    builtin_mdl_search_roots: tuple[Path, ...] = BUILTIN_MDL_SEARCH_ROOTS,
) -> tuple[dict[str, str], dict[str, Any]]:
    env = dict(base_env)
    if task_env_vars:
        for key, value in task_env_vars.items():
            env[key] = value
    env["HOME"] = str(layout.home)
    env["XDG_CACHE_HOME"] = str(layout.cache)
    env["OV_USER_CACHE_DIR"] = str(layout.cache / "ov")
    env["PIP_CACHE_DIR"] = str(layout.cache / "pip")

    pxr_entries = _split_search_path(env.get("PXR_AR_DEFAULT_SEARCH_PATH", ""))
    mdl_system_entries = _split_search_path(env.get("MDL_SYSTEM_PATH", ""))
    mdl_user_entries = _split_search_path(env.get("MDL_USER_PATH", ""))
    if not pxr_entries:
        pxr_entries = [str(layout.assets_dir)]
    if not mdl_system_entries:
        mdl_system_entries = [str(layout.assets_dir)]
    mdl_system_entries = _append_existing_paths(
        mdl_system_entries, builtin_mdl_search_roots
    )

    effective_pxr, pxr_bad, pxr_original, pxr_cache = _search_path_report(
        pxr_entries,
        assets_dir=layout.assets_dir,
        builtin_allowlist_roots=builtin_allowlist_roots,
    )
    effective_mdl_system, mdl_bad, mdl_original, mdl_cache = _search_path_report(
        mdl_system_entries,
        assets_dir=layout.assets_dir,
        builtin_allowlist_roots=builtin_allowlist_roots,
    )
    effective_mdl_user, user_bad, user_original, user_cache = _search_path_report(
        mdl_user_entries,
        assets_dir=layout.assets_dir,
        builtin_allowlist_roots=builtin_allowlist_roots,
    )

    env["PXR_AR_DEFAULT_SEARCH_PATH"] = os.pathsep.join(effective_pxr)
    env["MDL_SYSTEM_PATH"] = os.pathsep.join(effective_mdl_system)
    env["MDL_USER_PATH"] = os.pathsep.join(effective_mdl_user)
    report = {
        "effective_mdl_system_path_entries": effective_mdl_system,
        "effective_mdl_user_path_entries": effective_mdl_user,
        "effective_pxr_search_path_entries": effective_pxr,
        "non_allowlisted_search_path_count": pxr_bad + mdl_bad + user_bad,
        "original_overlay_search_path_count": (
            pxr_original + mdl_original + user_original
        ),
        "user_cache_env_count": pxr_cache + mdl_cache + user_cache,
    }
    return env, report


@dataclass(frozen=True)
class RuntimeDependencyRecord:
    dependency_type: str
    authored_value: str
    resolved_path: str | None
    is_remote_uri: bool
    is_user_cache_path: bool
    is_under_assets_dir: bool
    is_allowlisted_builtin: bool
    is_unauthorized_outside_sandbox: bool
    is_missing_local_path: bool


def _is_remote_uri(value: str) -> bool:
    return value.lower().startswith(REMOTE_URI_PREFIXES)


def _is_cache_path(value: str) -> bool:
    return any(marker in value.lower() for marker in CACHE_MARKERS)


def _is_file_like_asset(value: str) -> bool:
    lowered = value.lower().split("?", 1)[0]
    return lowered.endswith(FILE_LIKE_ASSET_SUFFIXES)


def classify_runtime_dependency(
    *,
    authored_value: str,
    resolved_path: Path | None,
    dependency_type: str,
    assets_dir: Path,
    builtin_allowlist_roots: tuple[Path, ...] = BUILTIN_ALLOWLIST_ROOTS,
    treat_unresolved_as_missing: bool = False,
) -> RuntimeDependencyRecord:
    resolved_text = str(resolved_path) if resolved_path is not None else None
    path_text = resolved_text or authored_value
    path = Path(path_text) if path_text else None
    under_assets = bool(
        path and path.is_absolute() and _is_relative_to(path, assets_dir)
    )
    builtin = bool(
        path
        and path.is_absolute()
        and any(_is_relative_to(path, root) for root in builtin_allowlist_roots)
    )
    remote = _is_remote_uri(authored_value) or bool(
        resolved_text and _is_remote_uri(resolved_text)
    )
    cache = _is_cache_path(authored_value) or bool(
        resolved_text and _is_cache_path(resolved_text)
    )
    outside = bool(path and path.is_absolute() and not under_assets and not builtin)
    missing_local = False
    if not remote and not cache:
        if resolved_path is None:
            missing_local = treat_unresolved_as_missing or _is_file_like_asset(
                authored_value
            )
        elif (under_assets or builtin) and not resolved_path.exists():
            missing_local = True
    return RuntimeDependencyRecord(
        dependency_type=dependency_type,
        authored_value=authored_value,
        resolved_path=resolved_text,
        is_remote_uri=remote,
        is_user_cache_path=cache,
        is_under_assets_dir=under_assets,
        is_allowlisted_builtin=builtin,
        is_unauthorized_outside_sandbox=outside and not remote and not cache,
        is_missing_local_path=missing_local,
    )


def summarize_dependency_records(
    records: list[RuntimeDependencyRecord],
) -> dict[str, int]:
    return {
        "remote_uri_count": sum(record.is_remote_uri for record in records),
        "user_cache_path_count": sum(record.is_user_cache_path for record in records),
        "unauthorized_outside_sandbox_runtime_path_count": sum(
            record.is_unauthorized_outside_sandbox for record in records
        ),
        "allowlisted_builtin_runtime_path_count": sum(
            record.is_allowlisted_builtin for record in records
        ),
        "missing_local_dependency_count": sum(
            record.is_missing_local_path for record in records
        ),
    }


QUOTED_MDL_IMPORT_RE = re.compile(r'^\s*import\s+"([^"]+\.mdl)"\s*;', re.MULTILINE)
MODULE_MDL_IMPORT_RE = re.compile(
    r"^\s*import\s+((?:::)?[A-Za-z_][A-Za-z0-9_:]*)\s*;",
    re.MULTILINE,
)
USING_MDL_IMPORT_RE = re.compile(
    r"^\s*using\s+((?:::)?[A-Za-z_][A-Za-z0-9_:]*)\s+"
    r"import\s+(?:\*|[A-Za-z_][A-Za-z0-9_]*)\s*;",
    re.MULTILINE,
)
TEXTURE_2D_RE = re.compile(r'texture_2d\s*\(\s*"([^"]+)"')


def parse_mdl_dependency_values(text: str) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    for value in QUOTED_MDL_IMPORT_RE.findall(text):
        records.append(("mdl_import", value))
    for value in MODULE_MDL_IMPORT_RE.findall(text):
        if not value.endswith(".mdl"):
            records.append(("mdl_import", value))
    for value in USING_MDL_IMPORT_RE.findall(text):
        records.append(("mdl_import", value))
    for value in TEXTURE_2D_RE.findall(text):
        records.append(("texture", value))
    return records


def _resolve_mdl_reference(
    value: str,
    *,
    current_dir: Path,
    search_paths: list[Path],
) -> Path | None:
    if _is_remote_uri(value):
        return None
    candidate_values = [value]
    if "::" in value:
        parts = [part for part in value.strip(":").split("::") if part]
        for length in range(len(parts), 0, -1):
            candidate_values.append("/".join(parts[:length]) + ".mdl")
    elif not value.endswith(".mdl") and "/" not in value:
        candidate_values.append(value + ".mdl")
    for candidate_value in candidate_values:
        candidate = Path(candidate_value)
        if candidate.is_absolute() and candidate.exists():
            return candidate
        local = current_dir / candidate
        if local.exists():
            return local
        for root in search_paths:
            rooted = root / candidate
            if rooted.exists():
                return rooted
    return None


def expand_local_mdl_dependencies(
    *,
    mdl_path: Path,
    assets_dir: Path,
    mdl_search_paths: list[Path],
    builtin_allowlist_roots: tuple[Path, ...] = BUILTIN_ALLOWLIST_ROOTS,
    _seen: set[Path] | None = None,
) -> list[RuntimeDependencyRecord]:
    seen = set() if _seen is None else _seen
    resolved_mdl = mdl_path.resolve()
    if resolved_mdl in seen:
        return []
    seen.add(resolved_mdl)
    text = mdl_path.read_text(encoding="utf-8")
    records: list[RuntimeDependencyRecord] = []
    for dependency_type, value in parse_mdl_dependency_values(text):
        resolved = None
        if dependency_type == "mdl_import":
            resolved = _resolve_mdl_reference(
                value,
                current_dir=mdl_path.parent,
                search_paths=mdl_search_paths,
            )
        elif not _is_remote_uri(value):
            texture = Path(value)
            resolved = texture if texture.is_absolute() else mdl_path.parent / texture
        record = classify_runtime_dependency(
            authored_value=value,
            resolved_path=resolved,
            dependency_type=dependency_type,
            assets_dir=assets_dir,
            builtin_allowlist_roots=builtin_allowlist_roots,
            treat_unresolved_as_missing=dependency_type == "mdl_import",
        )
        records.append(record)
        if (
            dependency_type == "mdl_import"
            and resolved
            and resolved.exists()
            and not record.is_allowlisted_builtin
        ):
            records.extend(
                expand_local_mdl_dependencies(
                    mdl_path=resolved,
                    assets_dir=assets_dir,
                    mdl_search_paths=mdl_search_paths,
                    builtin_allowlist_roots=builtin_allowlist_roots,
                    _seen=seen,
                )
            )
    return records


def derive_required_prim_paths(
    manifest: dict[str, Any],
    task_config: dict[str, Any],
) -> list[str]:
    paths: list[str] = []
    runtime_asset = manifest.get("drying_box_runtime_asset") or {}
    wrapper = runtime_asset.get("wrapper_prim_path")
    if not wrapper:
        for stage in (manifest.get("asset_acceptance") or {}).get(
            "acceptance_stages", []
        ):
            evidence = stage.get("evidence") or {}
            wrapper = evidence.get("wrapper_prim_path")
            if wrapper:
                break
    if not wrapper:
        wrapper = (manifest.get("wrapper_prim_paths") or {}).get("obj_DryingBox_01")
    if wrapper:
        paths.extend([wrapper, f"{wrapper}/Looks"])
        scene_root = _scene_root_from_prim_path(wrapper)
        if scene_root:
            paths.append(scene_root)
    handle = (manifest.get("articulation_part_paths") or {}).get(
        "obj_DryingBox_01_handle"
    )
    if handle:
        paths.append(handle)
    joint = task_config.get("metric_joint_path") or task_config.get("joint_path")
    if joint:
        paths.append(joint)
    wrapper_prim_paths = manifest.get("wrapper_prim_paths") or {}
    object_config = task_config.get("object_config") or {}
    if isinstance(object_config, dict):
        for object_key, config in object_config.items():
            candidate_keys = [object_key]
            if isinstance(config, dict):
                candidate_keys.extend(str(item) for item in config.get("uid_list", []))
            for candidate_key in candidate_keys:
                object_path = wrapper_prim_paths.get(candidate_key)
                if object_path:
                    paths.append(object_path)
                    scene_root = _scene_root_from_prim_path(object_path)
                    if scene_root:
                        paths.append(scene_root)
    return list(dict.fromkeys(paths))


def _scene_root_from_prim_path(prim_path: str) -> str | None:
    parts = [part for part in prim_path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "World":
        return "/" + "/".join(parts[:2])
    if parts and parts[0] == "World":
        return "/World"
    return None


def _load_pxr_modules():
    try:
        from pxr import Sdf, Usd, UsdUtils  # type: ignore
    except Exception as exc:
        return None, None, None, exc
    return Sdf, Usd, UsdUtils, None


def _record_from_asset_value(
    value: Any,
    *,
    dependency_type: str,
    assets_dir: Path,
    mdl_search_paths: list[Path],
    builtin_allowlist_roots: tuple[Path, ...] = BUILTIN_ALLOWLIST_ROOTS,
) -> RuntimeDependencyRecord | None:
    if not hasattr(value, "path"):
        return None
    authored = str(value.path)
    resolved = getattr(value, "resolvedPath", None)
    resolved_path = Path(str(resolved)) if resolved else None
    if resolved_path is None and authored.endswith(".mdl"):
        resolved_path = _resolve_mdl_reference(
            authored,
            current_dir=assets_dir,
            search_paths=mdl_search_paths,
        )
    return classify_runtime_dependency(
        authored_value=authored,
        resolved_path=resolved_path,
        dependency_type=dependency_type,
        assets_dir=assets_dir,
        builtin_allowlist_roots=builtin_allowlist_roots,
    )


def _asset_path_values(value: Any, Sdf: Any) -> list[Any]:
    if isinstance(value, Sdf.AssetPath):
        return [value]
    if isinstance(value, (str, bytes)):
        return []
    try:
        iterator = iter(value)
    except TypeError:
        return []
    values: list[Any] = []
    for item in iterator:
        values.extend(_asset_path_values(item, Sdf))
    return values


def iter_stage_asset_path_values(stage: Any, Sdf: Any) -> list[tuple[str, Any]]:
    records: list[tuple[str, Any]] = []
    for prim in stage.Traverse():
        for key in prim.GetAllMetadata():
            for value in _asset_path_values(prim.GetMetadata(key), Sdf):
                records.append((f"{prim.GetPath()}:metadata:{key}", value))
        for attr in prim.GetAttributes():
            for value in _asset_path_values(attr.Get(), Sdf):
                records.append((f"{attr.GetPath()}:value", value))
            for key in attr.GetAllMetadata():
                for value in _asset_path_values(attr.GetMetadata(key), Sdf):
                    records.append((f"{attr.GetPath()}:metadata:{key}", value))
        for rel in prim.GetRelationships():
            for key in rel.GetAllMetadata():
                for value in _asset_path_values(rel.GetMetadata(key), Sdf):
                    records.append((f"{rel.GetPath()}:metadata:{key}", value))
    return records


def _expand_mdl_records_from_dependency(
    *,
    record: RuntimeDependencyRecord,
    assets_dir: Path,
    mdl_search_paths: list[Path],
    builtin_allowlist_roots: tuple[Path, ...],
) -> list[RuntimeDependencyRecord]:
    if record.is_allowlisted_builtin:
        return []
    candidate = record.resolved_path or record.authored_value
    if not candidate.endswith(".mdl"):
        return []
    resolved: Path | None = Path(candidate)
    if not resolved.is_absolute():
        resolved = _resolve_mdl_reference(
            candidate,
            current_dir=assets_dir,
            search_paths=mdl_search_paths,
        )
    if resolved is None or not resolved.exists():
        return []
    return expand_local_mdl_dependencies(
        mdl_path=resolved,
        assets_dir=assets_dir,
        mdl_search_paths=mdl_search_paths,
        builtin_allowlist_roots=builtin_allowlist_roots,
    )


def _dependency_item_to_path(item: Any) -> str:
    identifier = getattr(item, "identifier", None)
    if identifier:
        return str(identifier)
    path = getattr(item, "path", None)
    if path:
        return str(path)
    return str(item)


def _compute_all_dependencies(UsdUtils: Any, runtime_scene: Path):
    return UsdUtils.ComputeAllDependencies(str(runtime_scene))


def run_child_pxr_compose(
    *,
    runtime_scene: Path,
    assets_dir: Path,
    required_prim_paths: list[str],
    environment_report: dict[str, Any],
    builtin_allowlist_roots: tuple[Path, ...] = BUILTIN_ALLOWLIST_ROOTS,
) -> dict[str, Any]:
    Sdf, Usd, UsdUtils, import_error = _load_pxr_modules()
    if import_error is not None:
        return {
            "status": BLOCKED,
            "runtime": {
                "composition_ok": False,
                "error": f"{type(import_error).__name__}: {import_error}",
            },
        }
    try:
        stage = Usd.Stage.Open(str(runtime_scene))
        if stage is None:
            raise RuntimeError(f"Usd.Stage.Open returned None for {runtime_scene}")
        stage.Load()
    except Exception as exc:
        return {
            "status": FAIL,
            "runtime": {
                "composition_ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            },
        }

    missing = [path for path in required_prim_paths if not stage.GetPrimAtPath(path)]
    records: list[RuntimeDependencyRecord] = []
    mdl_search_paths = [
        Path(path)
        for path in environment_report.get("effective_mdl_system_path_entries", [])
    ]
    mdl_search_paths.extend(
        Path(path)
        for path in environment_report.get("effective_mdl_user_path_entries", [])
    )
    dependency_scan_error = None
    try:
        layers, assets, unresolved = _compute_all_dependencies(UsdUtils, runtime_scene)
    except Exception as exc:
        dependency_scan_error = f"{type(exc).__name__}: {exc}"
        layers, assets, unresolved = [], [], []
    for item in list(layers) + list(assets) + list(unresolved):
        authored = _dependency_item_to_path(item)
        resolved_path = Path(authored) if Path(authored).is_absolute() else None
        if resolved_path is None and authored.endswith(".mdl"):
            resolved_path = _resolve_mdl_reference(
                authored,
                current_dir=assets_dir,
                search_paths=mdl_search_paths,
            )
        record = classify_runtime_dependency(
            authored_value=authored,
            resolved_path=resolved_path,
            dependency_type="usd_dependency",
            assets_dir=assets_dir,
            builtin_allowlist_roots=builtin_allowlist_roots,
        )
        records.append(record)
        records.extend(
            _expand_mdl_records_from_dependency(
                record=record,
                assets_dir=assets_dir,
                mdl_search_paths=mdl_search_paths,
                builtin_allowlist_roots=builtin_allowlist_roots,
            )
        )
    for owner, asset_value in iter_stage_asset_path_values(stage, Sdf):
        record = _record_from_asset_value(
            asset_value,
            dependency_type=f"asset_path:{owner}",
            assets_dir=assets_dir,
            mdl_search_paths=mdl_search_paths,
            builtin_allowlist_roots=builtin_allowlist_roots,
        )
        if record is None:
            continue
        records.append(record)
        records.extend(
            _expand_mdl_records_from_dependency(
                record=record,
                assets_dir=assets_dir,
                mdl_search_paths=mdl_search_paths,
                builtin_allowlist_roots=builtin_allowlist_roots,
            )
        )
    counts = summarize_dependency_records(records)
    status = (
        FAIL
        if missing
        or any(
            counts.get(key, 0)
            for key in (
                "remote_uri_count",
                "user_cache_path_count",
                "unauthorized_outside_sandbox_runtime_path_count",
                "missing_local_dependency_count",
            )
        )
        or environment_report.get("non_allowlisted_search_path_count", 0)
        or environment_report.get("user_cache_env_count", 0)
        or environment_report.get("original_overlay_search_path_count", 0)
        or dependency_scan_error
        else PASS
    )
    return {
        "status": status,
        "runtime": {
            "runtime_scene": str(runtime_scene),
            "composition_ok": True,
            "required_prim_records": [
                {"prim_path": path, "exists": path not in missing}
                for path in required_prim_paths
            ],
            "missing_required_prim_paths": missing,
            "dependency_scan_error": dependency_scan_error,
            "dependency_scan_error_count": 1 if dependency_scan_error else 0,
            "resolved_runtime_dependency_records": [
                record.__dict__ for record in records
            ],
            **counts,
        },
    }


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_hashes(paths: dict[str, Path]) -> dict[str, str]:
    return {key: _sha256(path) for key, path in paths.items() if path.exists()}


def run_static_validation_command(command: list[str] | None = None) -> dict[str, Any]:
    actual = DEFAULT_VALIDATION_COMMAND if command is None else command
    completed = subprocess.run(
        actual,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    status = PASS if completed.returncode == 0 else FAIL
    return {
        "status": status,
        "command": " ".join(actual),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def run_child_probe_subprocess(
    *,
    layout: SandboxLayout,
    runtime_scene: Path,
    assets_dir: Path,
    required_prim_paths: list[str],
    environment_report: dict[str, Any],
    child_env: dict[str, str],
    child_timeout_seconds: int,
) -> dict[str, Any]:
    required_path = layout.reports / "required_prims.json"
    environment_path = layout.reports / "environment.json"
    child_report_path = layout.reports / "child_report.json"
    stdout_path = layout.reports / "child.stdout.txt"
    stderr_path = layout.reports / "child.stderr.txt"
    _write_json(required_path, required_prim_paths)
    _write_json(environment_path, environment_report)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child-pxr-compose",
        "--runtime-scene",
        str(runtime_scene),
        "--assets-dir",
        str(assets_dir),
        "--required-prims-json",
        str(required_path),
        "--environment-report-json",
        str(environment_path),
        "--child-report-output",
        str(child_report_path),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=child_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=child_timeout_seconds,
            check=False,
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        if child_report_path.exists():
            try:
                child_report = json.loads(child_report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                child_report = {
                    "status": FAIL,
                    "runtime": {
                        "composition_ok": False,
                        "error": f"child report malformed: {exc}",
                    },
                }
        else:
            child_report = {
                "status": FAIL,
                "runtime": {
                    "composition_ok": False,
                    "error": "child report missing",
                },
            }
        child_exit_code = completed.returncode
        if child_exit_code != 0 and child_report.get("status") == PASS:
            child_report["status"] = FAIL
            child_report.setdefault("runtime", {})["error"] = (
                f"child exited nonzero despite PASS report: {child_exit_code}"
            )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or "child process timed out"
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        child_report = {
            "status": BLOCKED,
            "runtime": {
                "composition_ok": False,
                "error": f"child process timed out after {child_timeout_seconds}s",
            },
        }
        _write_json(child_report_path, child_report)
        child_exit_code = -1
    artifact_paths = {
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
        "child_report_path": child_report_path,
    }
    return {
        "child_report": child_report,
        "artifacts": {
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "child_report_path": str(child_report_path),
            "child_exit_code": child_exit_code,
            "sha256": _artifact_hashes(artifact_paths),
        },
    }


def run_parent_probe(
    *,
    manifest_path: Path,
    package_root: Path,
    overlay_root: Path,
    runtime_scene_relative: Path,
    required_prim_paths: list[str],
    static_validation_runner,
    mode: str,
    sandbox_root: Path | None = None,
    child_timeout_seconds: int = DEFAULT_CHILD_TIMEOUT_SECONDS,
    task_env_vars: dict[str, str] | None = None,
) -> dict[str, Any]:
    started_at_utc = _utc_now()
    static_validation = static_validation_runner()
    if static_validation.get("status") != PASS:
        status = FAIL if static_validation.get("status") == FAIL else BLOCKED
        return {
            "schema_version": 1,
            "status": status,
            "mode": mode,
            "started_at_utc": started_at_utc,
            "ended_at_utc": _utc_now(),
            "child_timeout_seconds": child_timeout_seconds,
            "static_validation": static_validation,
            "artifacts": {
                "stdout_path": "",
                "stderr_path": "",
                "child_report_path": "",
                "sha256": {},
            },
            "claim_boundary": build_claim_boundary(status),
        }
    root = sandbox_root or Path(tempfile.mkdtemp(prefix="labutopia_cold_runtime_"))
    try:
        layout = build_sandbox_layout(
            sandbox_root=root,
            package_root=package_root,
            overlay_root=overlay_root,
        )
        child_env, environment_report = build_child_environment(
            layout,
            base_env=os.environ,
            task_env_vars=task_env_vars,
        )
        runtime_scene = layout.assets_dir / runtime_scene_relative
        child_result = run_child_probe_subprocess(
            layout=layout,
            runtime_scene=runtime_scene,
            assets_dir=layout.assets_dir,
            required_prim_paths=required_prim_paths,
            environment_report=environment_report,
            child_env=child_env,
            child_timeout_seconds=child_timeout_seconds,
        )
        child_report = child_result["child_report"]
        runtime = child_report.get("runtime") or {}
        runtime_counts = {
            "remote_uri_count": int(runtime.get("remote_uri_count") or 0),
            "user_cache_path_count": int(runtime.get("user_cache_path_count") or 0),
            "unauthorized_outside_sandbox_runtime_path_count": int(
                runtime.get("unauthorized_outside_sandbox_runtime_path_count") or 0
            ),
            "missing_local_dependency_count": int(
                runtime.get("missing_local_dependency_count") or 0
            ),
            "non_allowlisted_search_path_count": int(
                environment_report.get("non_allowlisted_search_path_count") or 0
            ),
            "user_cache_env_count": int(
                environment_report.get("user_cache_env_count") or 0
            ),
            "original_overlay_search_path_count": int(
                environment_report.get("original_overlay_search_path_count") or 0
            ),
            "dependency_scan_error_count": int(
                runtime.get("dependency_scan_error_count") or 0
            ),
            "missing_required_prim_count": len(
                runtime.get("missing_required_prim_paths") or []
            ),
        }
        status = derive_parent_status(
            static_validation_status=static_validation["status"],
            child_status=child_report["status"],
            runtime_counts=runtime_counts,
        )
        return {
            "schema_version": 1,
            "status": status,
            "mode": mode,
            "started_at_utc": started_at_utc,
            "ended_at_utc": _utc_now(),
            "command": sys.argv,
            "child_timeout_seconds": child_timeout_seconds,
            "static_validation": static_validation,
            "sandbox": {
                "sandbox_root": str(layout.sandbox_root),
                "package_config_root": str(layout.package_config_root),
                "assets_dir": str(layout.assets_dir),
                "home": str(layout.home),
                "xdg_cache_home": str(layout.cache),
                "network_isolation_mode": (
                    "best_effort_env_and_resolved_dependency_probe"
                ),
            },
            "environment": environment_report,
            "runtime": runtime,
            "artifacts": child_result["artifacts"],
            "claim_boundary": build_claim_boundary(status),
        }
    except SandboxBuildError as exc:
        return {
            "schema_version": 1,
            "status": FAIL,
            "mode": mode,
            "started_at_utc": started_at_utc,
            "ended_at_utc": _utc_now(),
            "static_validation": static_validation,
            "error": str(exc),
            "artifacts": {
                "stdout_path": "",
                "stderr_path": "",
                "child_report_path": "",
                "sha256": {},
            },
            "claim_boundary": build_claim_boundary(FAIL),
        }


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    if yaml is None or not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def first_evaluation_config(task_config: dict[str, Any]) -> dict[str, Any]:
    configs = task_config.get("evaluation_configs") or []
    if isinstance(configs, list) and configs and isinstance(configs[0], dict):
        return configs[0]
    return task_config


def default_open_door_task_config(package_root: Path) -> dict[str, Any]:
    task_path = package_root / "lift2_candidate/level1_open_door.yml"
    data = load_yaml_mapping(task_path)
    first = first_evaluation_config(data)
    root = "/World/labutopia_level1_poc/obj_obj_DryingBox_01"
    first.setdefault("metric_joint_path", f"{root}/RevoluteJoint")
    return first


def extract_task_env_vars(task_config: dict[str, Any]) -> dict[str, str]:
    first = first_evaluation_config(task_config)
    env_vars = first.get("env_vars") or {}
    return {
        str(key): str(value)
        for key, value in env_vars.items()
        if isinstance(key, str) and isinstance(value, (str, int, float))
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child-pxr-compose", action="store_true")
    parser.add_argument(
        "--mode",
        default="pxr-compose",
        choices=["pxr-compose", "isaac-python-smoke", "lift2-contract"],
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--package-root", type=Path, default=PACKAGE_ROOT)
    parser.add_argument("--overlay-root", type=Path)
    parser.add_argument(
        "--runtime-scene-relative",
        type=Path,
        default=Path("scene_usds/labutopia/level1_poc/lab_001/scene.usda"),
    )
    parser.add_argument("--required-prim", action="append", default=[])
    parser.add_argument("--runtime-scene", type=Path)
    parser.add_argument("--assets-dir", type=Path)
    parser.add_argument("--required-prims-json", type=Path)
    parser.add_argument("--environment-report-json", type=Path)
    parser.add_argument("--child-report-output", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--child-timeout-seconds",
        type=int,
        default=DEFAULT_CHILD_TIMEOUT_SECONDS,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.child_pxr_compose:
        required_prims = json.loads(args.required_prims_json.read_text(encoding="utf-8"))
        environment_report = json.loads(
            args.environment_report_json.read_text(encoding="utf-8")
        )
        report = run_child_pxr_compose(
            runtime_scene=args.runtime_scene,
            assets_dir=args.assets_dir,
            required_prim_paths=required_prims,
            environment_report=environment_report,
        )
        _write_json(args.child_report_output, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == PASS else 1
    if args.mode != "pxr-compose":
        if args.mode == "isaac-python-smoke" and (
            not Path("/isaac-sim/python.sh").is_file()
            or os.environ.get("LABUTOPIA_RUN_HEAVY_ISAAC_TESTS") != "1"
        ):
            report = {
                "schema_version": 1,
                "status": BLOCKED,
                "mode": args.mode,
                "reason": "heavy Isaac mode not enabled",
            }
            print(json.dumps(report, indent=2, sort_keys=True))
            return 2
        report = {
            "schema_version": 1,
            "status": BLOCKED,
            "mode": args.mode,
            "reason": "mode not implemented in v1",
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    task_config = default_open_door_task_config(args.package_root)
    required_prims = args.required_prim or derive_required_prim_paths(
        manifest,
        task_config,
    )
    task_env_vars = extract_task_env_vars(task_config)
    overlay_root = args.overlay_root or Path(manifest.get("overlay_root", ""))
    report = run_parent_probe(
        manifest_path=args.manifest,
        package_root=args.package_root,
        overlay_root=overlay_root,
        runtime_scene_relative=args.runtime_scene_relative,
        required_prim_paths=required_prims,
        static_validation_runner=run_static_validation_command,
        mode=args.mode,
        child_timeout_seconds=args.child_timeout_seconds,
        task_env_vars=task_env_vars,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
