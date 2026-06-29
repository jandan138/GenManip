#!/usr/bin/env python3
"""Cold-runtime sandbox probe for LabUtopia EBench task packages."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
from typing import Any


PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED"
CACHE_MARKERS = ("/.cache/", "/ov/pkg/", "/kit/cache/")
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
