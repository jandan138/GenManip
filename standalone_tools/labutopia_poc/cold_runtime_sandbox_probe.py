#!/usr/bin/env python3
"""Cold-runtime sandbox probe for LabUtopia EBench task packages."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
from typing import Any


PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED"
CACHE_MARKERS = ("/.cache/", "/ov/pkg/", "/kit/cache/")
REMOTE_URI_PREFIXES = ("http://", "https://", "omniverse://", "s3://")
BUILTIN_ALLOWLIST_ROOTS = (Path("/isaac-sim/materials"),)


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
        "non_allowlisted_search_path_count",
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


def _is_remote_uri(value: str) -> bool:
    return value.lower().startswith(REMOTE_URI_PREFIXES)


def _is_cache_path(value: str) -> bool:
    return any(marker in value.lower() for marker in CACHE_MARKERS)


def classify_runtime_dependency(
    *,
    authored_value: str,
    resolved_path: Path | None,
    dependency_type: str,
    assets_dir: Path,
    builtin_allowlist_roots: tuple[Path, ...] = BUILTIN_ALLOWLIST_ROOTS,
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
    return RuntimeDependencyRecord(
        dependency_type=dependency_type,
        authored_value=authored_value,
        resolved_path=resolved_text,
        is_remote_uri=remote,
        is_user_cache_path=cache,
        is_under_assets_dir=under_assets,
        is_allowlisted_builtin=builtin,
        is_unauthorized_outside_sandbox=outside and not remote and not cache,
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
    }


QUOTED_MDL_IMPORT_RE = re.compile(r'import\s+"([^"]+\.mdl)"\s*;')
MODULE_MDL_IMPORT_RE = re.compile(
    r"import\s+((?:::)?[A-Za-z_][A-Za-z0-9_:]*)\s*;"
)
TEXTURE_2D_RE = re.compile(r'texture_2d\s*\(\s*"([^"]+)"')


def parse_mdl_dependency_values(text: str) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    for value in QUOTED_MDL_IMPORT_RE.findall(text):
        records.append(("mdl_import", value))
    for value in MODULE_MDL_IMPORT_RE.findall(text):
        if not value.endswith(".mdl"):
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
    if value.startswith("::"):
        candidate_values.append(value.strip(":").replace("::", "/") + ".mdl")
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
        records.append(
            classify_runtime_dependency(
                authored_value=value,
                resolved_path=resolved,
                dependency_type=dependency_type,
                assets_dir=assets_dir,
                builtin_allowlist_roots=builtin_allowlist_roots,
            )
        )
        if dependency_type == "mdl_import" and resolved and resolved.exists():
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
    handle = (manifest.get("articulation_part_paths") or {}).get(
        "obj_DryingBox_01_handle"
    )
    if handle:
        paths.append(handle)
    joint = task_config.get("metric_joint_path") or task_config.get("joint_path")
    if joint:
        paths.append(joint)
    return list(dict.fromkeys(paths))


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
    try:
        layers, assets, unresolved = UsdUtils.ComputeAllDependencies(
            str(runtime_scene)
        )
    except Exception:
        layers, assets, unresolved = [], [], []
    for item in list(layers) + list(assets) + list(unresolved):
        authored = _dependency_item_to_path(item)
        record = classify_runtime_dependency(
            authored_value=authored,
            resolved_path=Path(authored) if Path(authored).is_absolute() else None,
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
            )
        )
        or environment_report.get("non_allowlisted_search_path_count", 0)
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
            "resolved_runtime_dependency_records": [
                record.__dict__ for record in records
            ],
            **counts,
        },
    }
