# Cold Runtime Sandbox Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic `pxr-compose` cold-runtime probe that copies the LabUtopia task package into a cold sandbox, isolates runtime cache/search paths, composes the copied USD scene, and reports runtime dependency leakage without upgrading official/policy/showcase/native claims.

**Architecture:** Implement one standalone tool, `standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py`, with pure helper functions for report construction, sandbox copying, environment construction, dependency classification, MDL expansion, child probing, and parent subprocess orchestration. Keep static package validation in `validate_task_package.py`; this tool calls it first by default and supports injected validation in tests so tiny USD fixtures stay hermetic.

**Tech Stack:** Python 3.10, pathlib, dataclasses, argparse, subprocess, tempfile, shutil, hashlib, json, pytest, pxr.Usd, pxr.Sdf, pxr.UsdUtils.

**2026-06-29 execution update:** The probe exposed one real packaging gap after the initial implementation: the wrapper `scene.usda` had local material overrides, but copied source `scene.usd` still contained remote MDL source assets and remote Sektion cabinet payloads. `build_asset_overlay.py` now sanitizes the copied source layer with USD APIs before writing the wrapper. The current verification command is:

```bash
python standalone_tools/labutopia_poc/build_asset_overlay.py --drying-box-strategy native_complex --physics-override-output-root saved/diagnostics/native_dryingbox_physics_override_20260629_aluminum_mirror
python standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py --output /tmp/labutopia_cold_runtime_probe_after_material_shim.json
```

The latest probe result is `status=PASS` with `remote_uri_count=0`, `missing_local_dependency_count=0`, `dependency_scan_error_count=0`, `unauthorized_outside_sandbox_runtime_path_count=0`, `user_cache_path_count=0`, and `missing_required_prim_paths=[]`. This evidence is only a cold runtime dependency-closure claim; it does not upgrade official leaderboard, policy success, PM showcase, native material closure, or full native material closure.

---

## File Map

| File | Responsibility |
| --- | --- |
| `standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py` | New CLI and helper module for sandbox layout, isolated child env, static-validation gate, `pxr-compose` child probe, runtime dependency classification, MDL import/texture expansion, report JSON, and optional heavy Isaac skip policy. |
| `tests/labutopia_poc/test_cold_runtime_sandbox_probe.py` | Focused unit and subprocess tests for claim boundaries, sandbox merge rules, search path isolation, dependency classification, MDL parsing, tiny USD composition PASS/FAIL/BLOCKED, and static-validation injection. |
| `docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md` | Add the cold runtime sandbox probe as the runtime isolation layer after static offline package validation and before heavier Lift2 contract claims. |
| `docs/labutopia_lab_poc/evidence_manifests/README.md` | Add report fields and PM wording for `cold_runtime_sandbox_probe_passed`, including the non-claim that v1 is not kernel network isolation. |

## Task 1: Report Model And Claim Boundary

**Files:**
- Create: `tests/labutopia_poc/test_cold_runtime_sandbox_probe.py`
- Create: `standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py`

- [ ] **Step 1: Write failing report tests**

Add these tests to `tests/labutopia_poc/test_cold_runtime_sandbox_probe.py`:

```python
from __future__ import annotations

from pathlib import Path

from standalone_tools.labutopia_poc import cold_runtime_sandbox_probe as probe


def test_claim_boundary_keeps_broader_claims_false():
    boundary = probe.build_claim_boundary("PASS")

    assert boundary == {
        "cold_runtime_sandbox_probe_passed": True,
        "official_leaderboard_claim_allowed": False,
        "policy_success_claim_allowed": False,
        "pm_showcase_ready": False,
        "native_material_closure_claim_allowed": False,
        "full_native_material_closure_claim_allowed": False,
    }


def test_claim_boundary_is_false_when_probe_does_not_pass():
    assert probe.build_claim_boundary("FAIL")[
        "cold_runtime_sandbox_probe_passed"
    ] is False
    assert probe.build_claim_boundary("BLOCKED")[
        "cold_runtime_sandbox_probe_passed"
    ] is False


def test_status_derivation_blocks_static_validation_failure():
    status = probe.derive_parent_status(
        static_validation_status="FAIL",
        child_status="PASS",
        runtime_counts={
            "remote_uri_count": 0,
            "user_cache_path_count": 0,
            "unauthorized_outside_sandbox_runtime_path_count": 0,
            "non_allowlisted_search_path_count": 0,
            "missing_required_prim_count": 0,
        },
    )

    assert status == "FAIL"


def test_status_derivation_rejects_runtime_leakage():
    status = probe.derive_parent_status(
        static_validation_status="PASS",
        child_status="PASS",
        runtime_counts={
            "remote_uri_count": 1,
            "user_cache_path_count": 0,
            "unauthorized_outside_sandbox_runtime_path_count": 0,
            "non_allowlisted_search_path_count": 0,
            "missing_required_prim_count": 0,
        },
    )

    assert status == "FAIL"


def test_status_derivation_passes_only_clean_child_pass():
    status = probe.derive_parent_status(
        static_validation_status="PASS",
        child_status="PASS",
        runtime_counts={
            "remote_uri_count": 0,
            "user_cache_path_count": 0,
            "unauthorized_outside_sandbox_runtime_path_count": 0,
            "non_allowlisted_search_path_count": 0,
            "missing_required_prim_count": 0,
        },
    )

    assert status == "PASS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
```

Expected: FAIL because `cold_runtime_sandbox_probe.py` does not exist or does not expose the tested functions.

- [ ] **Step 3: Implement the minimal report helpers**

Create `standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py` with:

```python
#!/usr/bin/env python3
"""Cold-runtime sandbox probe for LabUtopia EBench task packages."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any


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
REMOTE_URI_PREFIXES = ("http://", "https://", "omniverse://", "s3://")
CACHE_MARKERS = ("/.cache/", "/ov/pkg/", "/kit/cache/")
DEFAULT_CHILD_TIMEOUT_SECONDS = 120
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
```

- [ ] **Step 4: Run tests to verify Task 1 passes**

Run:

```bash
python -m pytest tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
```

Expected: PASS for the Task 1 tests.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py tests/labutopia_poc/test_cold_runtime_sandbox_probe.py
git commit -m "feat: add cold runtime probe report boundary"
```

## Task 2: Sandbox Layout And Environment Isolation

**Files:**
- Modify: `tests/labutopia_poc/test_cold_runtime_sandbox_probe.py`
- Modify: `standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py`

- [ ] **Step 1: Add failing sandbox layout tests**

Append these tests:

```python
def _write(path: Path, content: bytes = b"data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_build_sandbox_merges_common_runtime_files_at_assets_root(tmp_path):
    package_root = tmp_path / "package"
    overlay_root = tmp_path / "overlay"
    _write(package_root / "common/miscs/mdl/test.mdl", b"mdl")
    _write(package_root / "common/assets_manifest.json", b"{}")
    _write(overlay_root / "scene_usds/labutopia/level1_poc/lab_001/scene.usda", b"#usda 1.0\n")

    layout = probe.build_sandbox_layout(
        sandbox_root=tmp_path / "sandbox",
        package_root=package_root,
        overlay_root=overlay_root,
    )

    assert (layout.assets_dir / "miscs/mdl/test.mdl").read_bytes() == b"mdl"
    assert (layout.assets_dir / "scene_usds/labutopia/level1_poc/lab_001/scene.usda").exists()
    assert not (layout.assets_dir / "common/miscs/mdl/test.mdl").exists()


def test_build_sandbox_rejects_nonidentical_common_overlay_collision(tmp_path):
    package_root = tmp_path / "package"
    overlay_root = tmp_path / "overlay"
    _write(package_root / "common/miscs/mdl/test.mdl", b"from-common")
    _write(overlay_root / "miscs/mdl/test.mdl", b"from-overlay")

    try:
        probe.build_sandbox_layout(
            sandbox_root=tmp_path / "sandbox",
            package_root=package_root,
            overlay_root=overlay_root,
        )
    except probe.SandboxBuildError as exc:
        assert "collision differs" in str(exc)
    else:
        raise AssertionError("expected SandboxBuildError")


def test_build_child_environment_rewrites_assets_and_cache_paths(tmp_path, monkeypatch):
    sandbox = tmp_path / "sandbox"
    layout = probe.SandboxLayout(
        sandbox_root=sandbox,
        package_config_root=sandbox / "package_config",
        assets_dir=sandbox / "assets",
        home=sandbox / "home",
        cache=sandbox / "cache",
        reports=sandbox / "reports",
    )
    monkeypatch.setenv("MDL_SYSTEM_PATH", "/source/miscs/mdl")
    monkeypatch.setenv("PXR_AR_DEFAULT_SEARCH_PATH", "{ASSETS_DIR}/scene_usds:/tmp/source")

    env, report = probe.build_child_environment(
        layout,
        base_env=os.environ,
        task_env_vars={"MDL_SYSTEM_PATH": "{ASSETS_DIR}/miscs/mdl"},
        builtin_allowlist_roots=(Path("/isaac-sim/materials"),),
    )

    assert env["HOME"] == str(layout.home)
    assert env["XDG_CACHE_HOME"] == str(layout.cache)
    assert str(layout.assets_dir) in env["PXR_AR_DEFAULT_SEARCH_PATH"]
    assert env["MDL_SYSTEM_PATH"] == str(layout.assets_dir / "miscs/mdl")
    assert report["non_allowlisted_search_path_count"] == 1
    assert report["original_overlay_search_path_count"] == 0
    assert report["user_cache_env_count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
```

Expected: FAIL for missing `SandboxLayout`, `SandboxBuildError`, `build_sandbox_layout`, and `build_child_environment`.

- [ ] **Step 3: Implement sandbox and env helpers**

Add to `cold_runtime_sandbox_probe.py`:

```python
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
    cache: Path,
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
            if not any(_is_relative_to(candidate, root) for root in builtin_allowlist_roots):
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
        cache=layout.cache,
        builtin_allowlist_roots=builtin_allowlist_roots,
    )
    effective_mdl_system, mdl_bad, mdl_original, mdl_cache = _search_path_report(
        mdl_system_entries,
        assets_dir=layout.assets_dir,
        cache=layout.cache,
        builtin_allowlist_roots=builtin_allowlist_roots,
    )
    effective_mdl_user, user_bad, user_original, user_cache = _search_path_report(
        mdl_user_entries,
        assets_dir=layout.assets_dir,
        cache=layout.cache,
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
        "original_overlay_search_path_count": pxr_original + mdl_original + user_original,
        "user_cache_env_count": pxr_cache + mdl_cache + user_cache,
    }
    return env, report
```

- [ ] **Step 4: Run tests to verify Task 2 passes**

Run:

```bash
python -m pytest tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
```

Expected: PASS for Task 1 and Task 2 tests.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py tests/labutopia_poc/test_cold_runtime_sandbox_probe.py
git commit -m "feat: build cold runtime sandbox layout"
```

## Task 3: Runtime Dependency Classification And MDL Expansion

**Files:**
- Modify: `tests/labutopia_poc/test_cold_runtime_sandbox_probe.py`
- Modify: `standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py`

- [ ] **Step 1: Add failing dependency tests**

Append these tests:

```python
def test_classify_runtime_dependency_counts_remote_cache_outside_and_builtin(tmp_path):
    sandbox_assets = tmp_path / "sandbox/assets"
    sandbox_assets.mkdir(parents=True)

    records = [
        probe.classify_runtime_dependency(
            authored_value="HTTPS://example.invalid/material.mdl",
            resolved_path=None,
            dependency_type="mdl",
            assets_dir=sandbox_assets,
            builtin_allowlist_roots=(Path("/isaac-sim/materials"),),
        ),
        probe.classify_runtime_dependency(
            authored_value=str(tmp_path / ".cache/texture.png"),
            resolved_path=tmp_path / ".cache/texture.png",
            dependency_type="texture",
            assets_dir=sandbox_assets,
            builtin_allowlist_roots=(Path("/isaac-sim/materials"),),
        ),
        probe.classify_runtime_dependency(
            authored_value="/cpfs/source/scene.usd",
            resolved_path=Path("/cpfs/source/scene.usd"),
            dependency_type="usd",
            assets_dir=sandbox_assets,
            builtin_allowlist_roots=(Path("/isaac-sim/materials"),),
        ),
        probe.classify_runtime_dependency(
            authored_value="/isaac-sim/materials/Base.mdl",
            resolved_path=Path("/isaac-sim/materials/Base.mdl"),
            dependency_type="mdl",
            assets_dir=sandbox_assets,
            builtin_allowlist_roots=(Path("/isaac-sim/materials"),),
        ),
    ]

    counts = probe.summarize_dependency_records(records)

    assert counts["remote_uri_count"] == 1
    assert counts["user_cache_path_count"] == 1
    assert counts["unauthorized_outside_sandbox_runtime_path_count"] == 1
    assert counts["allowlisted_builtin_runtime_path_count"] == 1


def test_parse_mdl_dependencies_supports_quoted_module_and_textures(tmp_path):
    mdl = tmp_path / "materials/root.mdl"
    _write(
        mdl,
        b'''
import "helper.mdl";
import helper_module;
import ::pkg::other_helper;
export material Root() = material(
    surface: material_surface(scattering: df::diffuse_reflection_bsdf(
        tint: texture_2d("textures/base.png").mono))
);
''',
    )

    deps = probe.parse_mdl_dependency_values(mdl.read_text(encoding="utf-8"))

    assert deps == [
        ("mdl_import", "helper.mdl"),
        ("mdl_import", "helper_module"),
        ("mdl_import", "::pkg::other_helper"),
        ("texture", "textures/base.png"),
    ]


def test_expand_local_mdl_dependencies_rejects_nested_remote_texture(tmp_path):
    assets_dir = tmp_path / "assets"
    _write(assets_dir / "root.mdl", b'import "helper.mdl";')
    _write(assets_dir / "helper.mdl", b'texture_2d("https://example.invalid/t.png")')

    records = probe.expand_local_mdl_dependencies(
        mdl_path=assets_dir / "root.mdl",
        assets_dir=assets_dir,
        mdl_search_paths=[assets_dir],
        builtin_allowlist_roots=(Path("/isaac-sim/materials"),),
    )

    counts = probe.summarize_dependency_records(records)
    assert counts["remote_uri_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
```

Expected: FAIL for missing dependency classifier and MDL parsing helpers.

- [ ] **Step 3: Implement dependency helpers**

Add these helpers:

```python
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
    under_assets = bool(path and path.is_absolute() and _is_relative_to(path, assets_dir))
    builtin = bool(
        path
        and path.is_absolute()
        and any(_is_relative_to(path, root) for root in builtin_allowlist_roots)
    )
    remote = _is_remote_uri(authored_value) or bool(resolved_text and _is_remote_uri(resolved_text))
    cache = _is_cache_path(authored_value) or bool(resolved_text and _is_cache_path(resolved_text))
    outside = bool(path and path.is_absolute() and not under_assets and not builtin)
    return RuntimeDependencyRecord(
        dependency_type=dependency_type,
        authored_value=authored_value,
        resolved_path=resolved_text,
        is_remote_uri=remote,
        is_user_cache_path=cache,
        is_under_assets_dir=under_assets,
        is_allowlisted_builtin=builtin,
        is_unauthorized_outside_sandbox=outside and not remote,
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
```

Also add regex-based MDL helpers:

```python
import re

QUOTED_MDL_IMPORT_RE = re.compile(r'import\\s+"([^"]+\\.mdl)"\\s*;')
MODULE_MDL_IMPORT_RE = re.compile(r'import\\s+((?:::)?[A-Za-z_][A-Za-z0-9_:]*)\\s*;')
TEXTURE_2D_RE = re.compile(r'texture_2d\\s*\\(\\s*"([^"]+)"')


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


def _resolve_mdl_reference(value: str, *, current_dir: Path, search_paths: list[Path]) -> Path | None:
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
        else:
            if not _is_remote_uri(value):
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
```

- [ ] **Step 4: Run tests to verify Task 3 passes**

Run:

```bash
python -m pytest tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
```

Expected: PASS for Task 1 through Task 3 tests.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py tests/labutopia_poc/test_cold_runtime_sandbox_probe.py
git commit -m "feat: classify cold runtime dependencies"
```

## Task 4: Required Prim Derivation And Child `pxr-compose`

**Files:**
- Modify: `tests/labutopia_poc/test_cold_runtime_sandbox_probe.py`
- Modify: `standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py`

- [ ] **Step 1: Add failing required prim and tiny USD tests**

Append:

```python
def test_derive_required_prims_uses_wrapper_fallback_order():
    manifest = {
        "drying_box_runtime_asset": {
            "wrapper_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01"
        },
        "articulation_part_paths": {
            "obj_DryingBox_01_handle": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle"
        },
    }
    task_config = {"metric_joint_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/RevoluteJoint"}

    records = probe.derive_required_prim_paths(manifest, task_config)

    assert "/World/labutopia_level1_poc/obj_obj_DryingBox_01" in records
    assert "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle" in records
    assert "/World/labutopia_level1_poc/obj_obj_DryingBox_01/RevoluteJoint" in records
    assert "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks" in records


def test_child_pxr_compose_passes_tiny_usd(tmp_path):
    scene = tmp_path / "assets/scene.usda"
    _write(
        scene,
        b'''#usda 1.0
def Xform "World"
{
    def Xform "labutopia_level1_poc"
    {
        def Xform "obj_obj_DryingBox_01"
        {
            def Xform "handle" {}
            def Scope "Looks" {}
            def PhysicsRevoluteJoint "RevoluteJoint" {}
        }
    }
}
''',
    )

    report = probe.run_child_pxr_compose(
        runtime_scene=scene,
        assets_dir=tmp_path / "assets",
        required_prim_paths=[
            "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
            "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle",
            "/World/labutopia_level1_poc/obj_obj_DryingBox_01/RevoluteJoint",
            "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks",
        ],
        environment_report={
            "non_allowlisted_search_path_count": 0,
            "effective_mdl_system_path_entries": [str(tmp_path / "assets")],
        },
    )

    assert report["status"] == "PASS"
    assert report["runtime"]["composition_ok"] is True
    assert report["runtime"]["missing_required_prim_paths"] == []


def test_child_pxr_compose_fails_missing_required_prim(tmp_path):
    scene = tmp_path / "assets/scene.usda"
    _write(scene, b'#usda 1.0\ndef Xform "World" {}\n')

    report = probe.run_child_pxr_compose(
        runtime_scene=scene,
        assets_dir=tmp_path / "assets",
        required_prim_paths=["/World/missing"],
        environment_report={
            "non_allowlisted_search_path_count": 0,
            "effective_mdl_system_path_entries": [str(tmp_path / "assets")],
        },
    )

    assert report["status"] == "FAIL"
    assert report["runtime"]["missing_required_prim_paths"] == ["/World/missing"]


def test_child_pxr_compose_resolves_relative_mdl_source_asset(tmp_path):
    assets = tmp_path / "assets"
    scene = assets / "scene.usda"
    _write(assets / "miscs/mdl/Aluminum_Anodized_Charcoal.mdl", b"export material M() = material();")
    _write(
        scene,
        b'''#usda 1.0
def Xform "World"
{
    def Material "Looks"
    {
        def Shader "Shader"
        {
            uniform token info:implementationSource = "sourceAsset"
            asset info:mdl:sourceAsset = @Aluminum_Anodized_Charcoal.mdl@
        }
    }
}
''',
    )

    report = probe.run_child_pxr_compose(
        runtime_scene=scene,
        assets_dir=assets,
        required_prim_paths=["/World"],
        environment_report={
            "non_allowlisted_search_path_count": 0,
            "effective_mdl_system_path_entries": [str(assets / "miscs/mdl")],
        },
    )

    assert report["status"] == "PASS"
    assert any(
        record["authored_value"] == "Aluminum_Anodized_Charcoal.mdl"
        and record["resolved_path"].endswith("Aluminum_Anodized_Charcoal.mdl")
        for record in report["runtime"]["resolved_runtime_dependency_records"]
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
```

Expected: FAIL for missing required prim and child probe helpers.

- [ ] **Step 3: Implement required prim and child probe helpers**

Add:

```python
def derive_required_prim_paths(
    manifest: dict[str, Any],
    task_config: dict[str, Any],
) -> list[str]:
    paths: list[str] = []
    runtime_asset = manifest.get("drying_box_runtime_asset") or {}
    wrapper = runtime_asset.get("wrapper_prim_path")
    if not wrapper:
        for stage in (manifest.get("asset_acceptance") or {}).get("acceptance_stages", []):
            evidence = stage.get("evidence") or {}
            wrapper = evidence.get("wrapper_prim_path")
            if wrapper:
                break
    if not wrapper:
        wrapper = (manifest.get("wrapper_prim_paths") or {}).get("obj_DryingBox_01")
    if wrapper:
        paths.extend([wrapper, f"{wrapper}/Looks"])
    handle = (manifest.get("articulation_part_paths") or {}).get("obj_DryingBox_01_handle")
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
    if isinstance(value, (list, tuple)):
        values: list[Any] = []
        for item in value:
            values.extend(_asset_path_values(item, Sdf))
        return values
    return []


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
            for target in rel.GetTargets():
                target_text = str(target)
                if target_text.startswith(("http://", "https://", "omniverse://", "s3://")):
                    records.append((f"{rel.GetPath()}:target", Sdf.AssetPath(target_text)))
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
    resolved = Path(candidate)
    if not resolved.is_absolute():
        resolved = _resolve_mdl_reference(
            candidate,
            current_dir=assets_dir,
            search_paths=mdl_search_paths,
        )
    if not resolved or not resolved.exists():
        return []
    return expand_local_mdl_dependencies(
        mdl_path=resolved,
        assets_dir=assets_dir,
        mdl_search_paths=mdl_search_paths,
        builtin_allowlist_roots=builtin_allowlist_roots,
    )


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
            "runtime": {"composition_ok": False, "error": f"{type(import_error).__name__}: {import_error}"},
        }
    try:
        stage = Usd.Stage.Open(str(runtime_scene))
        if stage is None:
            raise RuntimeError(f"Usd.Stage.Open returned None for {runtime_scene}")
        stage.Load()
    except Exception as exc:
        return {
            "status": FAIL,
            "runtime": {"composition_ok": False, "error": f"{type(exc).__name__}: {exc}"},
        }

    missing = [path for path in required_prim_paths if not stage.GetPrimAtPath(path)]
    records: list[RuntimeDependencyRecord] = []
    mdl_search_paths = [
        Path(path)
        for path in environment_report.get("effective_mdl_system_path_entries", [])
    ]
    try:
        layers, assets, unresolved = UsdUtils.ComputeAllDependencies(str(runtime_scene))
    except Exception:
        layers, assets, unresolved = [], [], []
    for item in list(layers) + list(assets) + list(unresolved):
        authored = str(item)
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
        if record is not None:
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
    status = FAIL if missing or any(
        counts.get(key, 0)
        for key in (
            "remote_uri_count",
            "user_cache_path_count",
            "unauthorized_outside_sandbox_runtime_path_count",
        )
    ) or environment_report.get("non_allowlisted_search_path_count", 0) else PASS
    return {
        "status": status,
        "runtime": {
            "runtime_scene": str(runtime_scene),
            "composition_ok": True,
            "required_prim_records": [{"prim_path": path, "exists": path not in missing} for path in required_prim_paths],
            "missing_required_prim_paths": missing,
            "resolved_runtime_dependency_records": [record.__dict__ for record in records],
            **counts,
        },
    }
```

- [ ] **Step 4: Run tests to verify Task 4 passes**

Run:

```bash
python -m pytest tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
```

Expected: PASS for Task 1 through Task 4 tests.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py tests/labutopia_poc/test_cold_runtime_sandbox_probe.py
git commit -m "feat: compose cold runtime USD in child probe"
```

## Task 5: Parent Runner, CLI, And Artifact Report

**Files:**
- Modify: `tests/labutopia_poc/test_cold_runtime_sandbox_probe.py`
- Modify: `standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py`

- [ ] **Step 1: Add failing parent runner and CLI tests**

Append:

```python
def test_parent_runner_uses_injected_static_validation_for_tiny_fixture(tmp_path):
    package_root = tmp_path / "package"
    overlay_root = tmp_path / "overlay"
    _write(package_root / "common/assets_manifest.json", b'{"asset_id":"Tiny"}')
    _write(
        overlay_root / "scene.usda",
        b'''#usda 1.0
def Xform "World"
{
    def Xform "object" {}
}
''',
    )

    report = probe.run_parent_probe(
        manifest_path=package_root / "common/assets_manifest.json",
        package_root=package_root,
        overlay_root=overlay_root,
        runtime_scene_relative=Path("scene.usda"),
        required_prim_paths=["/World/object"],
        static_validation_runner=lambda: {"status": "PASS", "command": "stub"},
        mode="pxr-compose",
        sandbox_root=tmp_path / "sandbox",
    )

    assert report["status"] == "PASS"
    assert report["static_validation"]["command"] == "stub"
    assert Path(report["artifacts"]["stdout_path"]).exists()
    assert Path(report["artifacts"]["stderr_path"]).exists()
    assert Path(report["artifacts"]["child_report_path"]).exists()
    assert report["artifacts"]["sha256"]["child_report_path"]
    assert report["claim_boundary"]["cold_runtime_sandbox_probe_passed"] is True
    assert report["claim_boundary"]["official_leaderboard_claim_allowed"] is False


def test_parent_runner_static_validation_fail_prevents_pass(tmp_path):
    package_root = tmp_path / "package"
    overlay_root = tmp_path / "overlay"
    _write(package_root / "common/assets_manifest.json", b'{"asset_id":"Tiny"}')

    report = probe.run_parent_probe(
        manifest_path=package_root / "common/assets_manifest.json",
        package_root=package_root,
        overlay_root=overlay_root,
        runtime_scene_relative=Path("missing.usda"),
        required_prim_paths=[],
        static_validation_runner=lambda: {"status": "FAIL", "command": "stub"},
        mode="pxr-compose",
        sandbox_root=tmp_path / "sandbox",
    )

    assert report["status"] == "FAIL"
    assert report["claim_boundary"]["cold_runtime_sandbox_probe_passed"] is False


def test_parse_args_defaults_to_pxr_compose():
    args = probe.parse_args([])

    assert args.mode == "pxr-compose"
    assert args.child_timeout_seconds == 120


def test_child_cli_writes_report_for_tiny_fixture(tmp_path):
    scene = tmp_path / "assets/scene.usda"
    output = tmp_path / "child_report.json"
    env_report = tmp_path / "environment.json"
    required = tmp_path / "required_prims.json"
    _write(scene, b'#usda 1.0\ndef Xform "World" {}\n')
    env_report.write_text(
        '{"non_allowlisted_search_path_count":0,"effective_mdl_system_path_entries":[]}',
        encoding="utf-8",
    )
    required.write_text('["/World"]', encoding="utf-8")

    exit_code = probe.main(
        [
            "--child-pxr-compose",
            "--runtime-scene",
            str(scene),
            "--assets-dir",
            str(tmp_path / "assets"),
            "--required-prims-json",
            str(required),
            "--environment-report-json",
            str(env_report),
            "--child-report-output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert '"status": "PASS"' in output.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
```

Expected: FAIL for missing parent runner and CLI helpers.

- [ ] **Step 3: Implement parent runner and CLI**

Add:

```python
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
            "non_allowlisted_search_path_count": int(
                environment_report.get("non_allowlisted_search_path_count") or 0
            ),
            "missing_required_prim_count": len(runtime.get("missing_required_prim_paths") or []),
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
                "network_isolation_mode": "best_effort_env_and_resolved_dependency_probe",
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


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_hashes(paths: dict[str, Path]) -> dict[str, str]:
    return {key: _sha256(path) for key, path in paths.items() if path.exists()}


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
        stdout_path.write_text(exc.stdout or "", encoding="utf-8")
        stderr_path.write_text(exc.stderr or "child process timed out", encoding="utf-8")
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


try:
    import yaml
except Exception:
    yaml = None


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
    parser.add_argument("--mode", default="pxr-compose", choices=["pxr-compose", "isaac-python-smoke", "lift2-contract"])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--package-root", type=Path, default=PACKAGE_ROOT)
    parser.add_argument("--overlay-root", type=Path, required=False)
    parser.add_argument("--runtime-scene-relative", type=Path, default=Path("scene_usds/labutopia/level1_poc/lab_001/scene.usda"))
    parser.add_argument("--required-prim", action="append", default=[])
    parser.add_argument("--runtime-scene", type=Path)
    parser.add_argument("--assets-dir", type=Path)
    parser.add_argument("--required-prims-json", type=Path)
    parser.add_argument("--environment-report-json", type=Path)
    parser.add_argument("--child-report-output", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child-timeout-seconds", type=int, default=DEFAULT_CHILD_TIMEOUT_SECONDS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.child_pxr_compose:
        required_prims = json.loads(args.required_prims_json.read_text(encoding="utf-8"))
        environment_report = json.loads(args.environment_report_json.read_text(encoding="utf-8"))
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
            report = {"schema_version": 1, "status": BLOCKED, "mode": args.mode, "reason": "heavy Isaac mode not enabled"}
            print(json.dumps(report, indent=2, sort_keys=True))
            return 2
        report = {"schema_version": 1, "status": BLOCKED, "mode": args.mode, "reason": "mode not implemented in v1"}
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2
    overlay_root = args.overlay_root
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    task_config = default_open_door_task_config(args.package_root)
    required_prims = args.required_prim or derive_required_prim_paths(
        manifest,
        task_config,
    )
    task_env_vars = extract_task_env_vars(task_config)
    if overlay_root is None:
        overlay_root = Path(manifest.get("overlay_root", ""))
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
```

- [ ] **Step 4: Run tests to verify Task 5 passes**

Run:

```bash
python -m pytest tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
```

Expected: PASS for Task 1 through Task 5 tests.

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py tests/labutopia_poc/test_cold_runtime_sandbox_probe.py
git commit -m "feat: add cold runtime probe cli"
```

## Task 6: DryingBox Defaults And Documentation

**Files:**
- Modify: `tests/labutopia_poc/test_cold_runtime_sandbox_probe.py`
- Modify: `standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py`
- Modify: `docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md`
- Modify: `docs/labutopia_lab_poc/evidence_manifests/README.md`

- [ ] **Step 1: Add failing DryingBox default tests**

Append:

```python
def test_default_required_prims_include_dryingbox_contract_paths():
    manifest = {
        "drying_box_runtime_asset": {
            "wrapper_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01"
        },
        "articulation_part_paths": {
            "obj_DryingBox_01_handle": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle"
        },
    }
    task_config = {}

    paths = probe.derive_required_prim_paths(manifest, task_config)

    assert "/World/labutopia_level1_poc/obj_obj_DryingBox_01" in paths
    assert "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle" in paths
    assert "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks" in paths


def test_isaac_mode_requires_explicit_heavy_flag(monkeypatch):
    monkeypatch.delenv("LABUTOPIA_RUN_HEAVY_ISAAC_TESTS", raising=False)

    exit_code = probe.main(["--mode", "isaac-python-smoke"])

    assert exit_code == 2


def test_extract_task_env_vars_reads_first_evaluation_config():
    task_config = {
        "evaluation_configs": [
            {
                "env_vars": {
                    "MDL_SYSTEM_PATH": "/isaac-sim/materials:{ASSETS_DIR}/miscs/mdl"
                }
            }
        ]
    }

    assert probe.extract_task_env_vars(task_config) == {
        "MDL_SYSTEM_PATH": "/isaac-sim/materials:{ASSETS_DIR}/miscs/mdl"
    }
```

- [ ] **Step 2: Run tests to verify they fail or expose missing default behavior**

Run:

```bash
python -m pytest tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
```

Expected: PASS if Task 5 already wired DryingBox defaults and nested `evaluation_configs[0].env_vars`; otherwise FAIL and fix Step 3 before editing docs.

- [ ] **Step 3: Verify default task config loading**

Task 5 should already include these helpers. If the implementation still has a top-level-only `env_vars` reader, replace it with this exact version so real LabUtopia task YAML is supported:

```python
try:
    import yaml
except Exception:
    yaml = None


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
```

Confirm `main()` uses `required_prims = args.required_prim or derive_required_prim_paths(manifest, task_config)` and passes `task_env_vars=extract_task_env_vars(task_config)` into `run_parent_probe()`.

- [ ] **Step 4: Update docs**

In `docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md`, add this paragraph under the offline dependency rule section:

```markdown
Cold runtime sandbox probe 是 static offline validation 后的下一层。它会把 package config、`common/` runtime files 和 overlay copy 到临时 `sandbox_root`，把 `{ASSETS_DIR}`、`MDL_SYSTEM_PATH`、`PXR_AR_DEFAULT_SEARCH_PATH` 指向 sandbox copy，再用 `pxr.Usd.Stage.Open` compose runtime scene。通过后只能说 `cold_runtime_sandbox_probe_passed=true`；它仍不等于 kernel-level network block、official leaderboard、policy success 或 PM showcase-ready。
```

In `docs/labutopia_lab_poc/evidence_manifests/README.md`, add this field guide section after the offline dependency checklist:

````markdown
## Cold Runtime Sandbox Probe 字段

`cold_runtime_sandbox_probe` 记录 copied package 在冷目录里的最小 runtime compose 结果：

```json
{
  "status": "PASS",
  "mode": "pxr-compose",
  "sandbox": {
    "network_isolation_mode": "best_effort_env_and_resolved_dependency_probe"
  },
  "environment": {
    "non_allowlisted_search_path_count": 0
  },
  "runtime": {
    "remote_uri_count": 0,
    "user_cache_path_count": 0,
    "unauthorized_outside_sandbox_runtime_path_count": 0,
    "allowlisted_builtin_runtime_path_count": 0,
    "missing_required_prim_paths": []
  },
  "claim_boundary": {
    "cold_runtime_sandbox_probe_passed": true,
    "official_leaderboard_claim_allowed": false,
    "policy_success_claim_allowed": false,
    "pm_showcase_ready": false,
    "native_material_closure_claim_allowed": false,
    "full_native_material_closure_claim_allowed": false
  }
}
```

PM 可以说：复制到冷目录后，解析到的 runtime dependency 没有回源到原始 `/cpfs`、公网 URI 或用户 cache。PM 不能说：这已经是系统级断网证明，或 official/policy/render showcase 已完成。
````

- [ ] **Step 5: Run focused docs and tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
python standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py --mode isaac-python-smoke
```

Expected: pytest PASS; Isaac command exits `2` with a `BLOCKED` report unless the heavy env flag and `/isaac-sim/python.sh` are both available.

- [ ] **Step 6: Commit Task 6**

Run:

```bash
git add standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py tests/labutopia_poc/test_cold_runtime_sandbox_probe.py docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md docs/labutopia_lab_poc/evidence_manifests/README.md
git commit -m "docs: document cold runtime sandbox probe"
```

## Task 7: Full Verification, Review, And Push

**Files:**
- Verify: all changed files

- [ ] **Step 1: Run focused verification**

Run:

```bash
python -m pytest tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
python standalone_tools/labutopia_poc/validate_task_package.py
python -m pytest tests/labutopia_poc/test_offline_package_validation.py tests/labutopia_poc/test_validate_task_package.py tests/labutopia_poc/test_cold_runtime_sandbox_probe.py -q
```

Expected: new tests PASS; package validator reports `LabUtopia task package validation OK`; focused package tests PASS.

- [ ] **Step 2: Run full LabUtopia POC tests**

Run:

```bash
python -m pytest tests/labutopia_poc -q
```

Expected: existing suite remains green with the same skip policy for environment-heavy tests.

- [ ] **Step 3: Run formatting and worktree checks**

Run:

```bash
git diff --check
git status -sb
```

Expected: no whitespace errors; status shows only intentional committed branch changes.

- [ ] **Step 4: Request multi-agent review**

Ask one reviewer to check spec compliance against `docs/superpowers/specs/2026-06-29-cold-runtime-sandbox-probe-design.md`, and another reviewer to check testability and code quality for `standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py` and `tests/labutopia_poc/test_cold_runtime_sandbox_probe.py`.

Expected: no Critical or Important findings. If findings exist, fix them with a new commit and rerun Step 1 through Step 3.

- [ ] **Step 5: Push branch**

Run:

```bash
git push -u fork labutopia-cold-runtime-sandbox
```

Expected: branch is pushed. If HTTPS push hits `Proxy CONNECT aborted`, use the existing GitHub proxy skill with a one-shot command and do not write proxy credentials into git config.
