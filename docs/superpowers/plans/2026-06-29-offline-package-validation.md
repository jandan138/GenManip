# Offline Package Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable static offline dependency validator for package-local MDL/texture records and integrate it into the DryingBox validator without changing manifest schema.

**Architecture:** Create `standalone_tools/labutopia_poc/offline_package_validation.py` with dataclass expectations and pure assertion helpers. Keep DryingBox constants and exact Aluminum checks in `validate_task_package.py`; use the helper only for records that already claim package-local/local-mirror dependency closure.

**Tech Stack:** Python 3.10, dataclasses, pathlib, hashlib, pytest, existing LabUtopia POC validator.

---

## File Map

| File | Responsibility |
| --- | --- |
| `standalone_tools/labutopia_poc/offline_package_validation.py` | New reusable offline dependency assertions for local paths, SHA256, byte counts, remote runtime URI rejection, and waiver claim boundaries. |
| `tests/labutopia_poc/test_offline_package_validation.py` | Focused unit tests for valid local mirror, remote runtime URI, missing file, SHA mismatch, byte mismatch, outside-root path, source URL provenance, and waiver overclaim. |
| `standalone_tools/labutopia_poc/validate_task_package.py` | DryingBox integration point; flatten only package-local Aluminum MDL/texture records into the reusable helper while preserving exact DryingBox checks. |
| `tests/labutopia_poc/test_validate_task_package.py` | Add one regression proving corrupted Aluminum texture dependency evidence is rejected through the package validator. |
| `docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md` | Document that cold/offline validation currently means static local-file/hash closure, not a network-blocking runtime sandbox. |
| `docs/labutopia_lab_poc/evidence_manifests/README.md` | Add a PM/intern-readable checklist for offline dependency records and claim boundaries. |

## Task 1: Add Offline Helper Unit Tests

**Files:**
- Create: `tests/labutopia_poc/test_offline_package_validation.py`

- [ ] **Step 1: Create failing tests**

Create `tests/labutopia_poc/test_offline_package_validation.py` with these tests:

```python
from __future__ import annotations

import hashlib

import pytest

from standalone_tools.labutopia_poc.offline_package_validation import (
    OfflineDependencyExpectation,
    OfflineDependencyRoots,
    assert_offline_dependency_records,
)


def _write(path, content: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _expectation() -> OfflineDependencyExpectation:
    return OfflineDependencyExpectation(
        allowed_location_statuses={
            "local_mirror_copied_with_package",
            "local_file_copied_with_source_scene",
        },
        local_path_fields={"local_mirror_path", "relative_path"},
        remote_checked_fields={"local_mirror_path", "relative_path", "worker_resolved_path"},
        informational_uri_fields={"source_url"},
    )


def test_offline_dependency_records_accept_local_mdl_and_texture(tmp_path):
    package_root = tmp_path / "package/common"
    mdl_hash = _write(package_root / "miscs/mdl/test.mdl", b"mdl")
    texture_hash = _write(package_root / "textures/test.png", b"texture")
    records = [
        {
            "material_name": "TestMaterial",
            "dependency_location_status": "local_mirror_copied_with_package",
            "local_mirror_path": "miscs/mdl/test.mdl",
            "sha256": mdl_hash,
            "bytes": 3,
            "source_url": "https://example.invalid/source.mdl",
            "worker_resolved_path": "{ASSETS_DIR}/miscs/mdl/test.mdl",
            "texture_dependency_records": [
                {
                    "relative_path": "textures/test.png",
                    "dependency_location_status": "local_mirror_copied_with_package",
                    "sha256": texture_hash,
                    "bytes": 7,
                    "source_url": "https://example.invalid/texture.png",
                    "worker_resolved_path": "{ASSETS_DIR}/textures/test.png",
                }
            ],
        }
    ]

    assert_offline_dependency_records(
        "assets_manifest.json",
        records,
        OfflineDependencyRoots(package_root=package_root),
        _expectation(),
    )


def test_offline_dependency_records_reject_remote_runtime_uri(tmp_path):
    package_root = tmp_path / "package/common"
    digest = _write(package_root / "test.mdl", b"mdl")
    records = [
        {
            "material_name": "RemoteRuntime",
            "dependency_location_status": "local_mirror_copied_with_package",
            "local_mirror_path": "test.mdl",
            "sha256": digest,
            "bytes": 3,
            "worker_resolved_path": "https://example.invalid/test.mdl",
        }
    ]

    with pytest.raises(AssertionError, match="worker_resolved_path must not point to a remote URI"):
        assert_offline_dependency_records(
            "assets_manifest.json",
            records,
            OfflineDependencyRoots(package_root=package_root),
            _expectation(),
        )


def test_offline_dependency_records_reject_missing_file(tmp_path):
    records = [
        {
            "material_name": "Missing",
            "dependency_location_status": "local_mirror_copied_with_package",
            "local_mirror_path": "missing.mdl",
            "sha256": "0" * 64,
            "bytes": 3,
        }
    ]

    with pytest.raises(AssertionError, match="local_mirror_path file does not exist"):
        assert_offline_dependency_records(
            "assets_manifest.json",
            records,
            OfflineDependencyRoots(package_root=tmp_path),
            _expectation(),
        )


def test_offline_dependency_records_reject_hash_mismatch(tmp_path):
    package_root = tmp_path / "package/common"
    _write(package_root / "test.mdl", b"mdl")
    records = [
        {
            "material_name": "HashMismatch",
            "dependency_location_status": "local_mirror_copied_with_package",
            "local_mirror_path": "test.mdl",
            "sha256": "0" * 64,
            "bytes": 3,
        }
    ]

    with pytest.raises(AssertionError, match="local_mirror_path hash mismatch"):
        assert_offline_dependency_records(
            "assets_manifest.json",
            records,
            OfflineDependencyRoots(package_root=package_root),
            _expectation(),
        )


def test_offline_dependency_records_reject_byte_mismatch(tmp_path):
    package_root = tmp_path / "package/common"
    digest = _write(package_root / "test.mdl", b"mdl")
    records = [
        {
            "material_name": "ByteMismatch",
            "dependency_location_status": "local_mirror_copied_with_package",
            "local_mirror_path": "test.mdl",
            "sha256": digest,
            "bytes": 99,
        }
    ]

    with pytest.raises(AssertionError, match="local_mirror_path byte count mismatch"):
        assert_offline_dependency_records(
            "assets_manifest.json",
            records,
            OfflineDependencyRoots(package_root=package_root),
            _expectation(),
        )


def test_offline_dependency_records_reject_absolute_outside_root(tmp_path):
    outside_file = tmp_path / "outside/test.mdl"
    digest = _write(outside_file, b"mdl")
    records = [
        {
            "material_name": "Outside",
            "dependency_location_status": "local_mirror_copied_with_package",
            "local_mirror_path": str(outside_file),
            "sha256": digest,
            "bytes": 3,
        }
    ]

    with pytest.raises(AssertionError, match="local_mirror_path must stay under an allowed root"):
        assert_offline_dependency_records(
            "assets_manifest.json",
            records,
            OfflineDependencyRoots(package_root=tmp_path / "package/common"),
            _expectation(),
        )


def test_offline_dependency_records_reject_waiver_overclaim(tmp_path):
    records = [
        {
            "material_name": "Waived",
            "resolution_mode": "explicit_waiver",
            "waiver_id": "REMOTE_001",
            "closure_claim_allowed": True,
        }
    ]

    with pytest.raises(AssertionError, match="explicit waiver must not allow closure claims"):
        assert_offline_dependency_records(
            "assets_manifest.json",
            records,
            OfflineDependencyRoots(package_root=tmp_path),
            _expectation(),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/labutopia_poc/test_offline_package_validation.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'standalone_tools.labutopia_poc.offline_package_validation'`.

## Task 2: Implement Offline Dependency Helper

**Files:**
- Create: `standalone_tools/labutopia_poc/offline_package_validation.py`

- [ ] **Step 1: Add helper implementation**

Create `standalone_tools/labutopia_poc/offline_package_validation.py` implementing:

```python
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any


REMOTE_URI_PREFIXES = ("http://", "https://", "omniverse://", "s3://")
CACHE_PATH_MARKERS = ("/.cache/", "/ov/pkg/", "/kit/cache/")


@dataclass(frozen=True)
class OfflineDependencyRoots:
    package_root: Path
    overlay_root: Path | None = None


@dataclass(frozen=True)
class OfflineDependencyExpectation:
    allowed_location_statuses: set[str]
    local_path_fields: set[str]
    remote_checked_fields: set[str]
    informational_uri_fields: set[str]


def assert_offline_dependency_records(
    manifest_path: object,
    records: object,
    roots: OfflineDependencyRoots,
    expectation: OfflineDependencyExpectation,
) -> None:
    prefix = str(manifest_path)
    if not isinstance(records, list):
        raise AssertionError(f"{prefix}: offline dependency records must be a list")
    for index, record in enumerate(records):
        _assert_record(prefix, record, index, roots, expectation)


def _assert_record(
    prefix: str,
    record: object,
    index: int,
    roots: OfflineDependencyRoots,
    expectation: OfflineDependencyExpectation,
) -> None:
    if not isinstance(record, dict):
        raise AssertionError(f"{prefix}: offline dependency record {index} must be a mapping")
    identity = _record_identity(record, index)
    _assert_remote_fields(prefix, identity, record, expectation)
    _assert_waiver_boundary(prefix, identity, record)
    status = record.get("dependency_location_status")
    resolution_mode = record.get("resolution_mode")
    requires_local = (
        status in expectation.allowed_location_statuses
        or resolution_mode == "local_mirror"
    )
    if requires_local:
        _assert_local_evidence(prefix, identity, record)
        for field in expectation.local_path_fields:
            if field in record:
                _assert_local_path_field(prefix, identity, record, field, roots)
    for nested in record.get("texture_dependency_records", []) or []:
        _assert_record(prefix, nested, index, roots, expectation)


def _assert_remote_fields(
    prefix: str,
    identity: str,
    record: dict[str, Any],
    expectation: OfflineDependencyExpectation,
) -> None:
    for field in expectation.remote_checked_fields:
        value = record.get(field)
        if isinstance(value, str) and _is_remote_or_cache_path(value):
            raise AssertionError(
                f"{prefix}: {identity} {field} must not point to a remote URI"
            )
    for field, value in record.items():
        if field in expectation.informational_uri_fields:
            continue
        if isinstance(value, str) and _is_cache_path(value):
            raise AssertionError(
                f"{prefix}: {identity} {field} must not point to user cache"
            )


def _assert_waiver_boundary(prefix: str, identity: str, record: dict[str, Any]) -> None:
    if record.get("resolution_mode") != "explicit_waiver":
        return
    if any(
        record.get(field) is True
        for field in (
            "closure_claim_allowed",
            "full_material_closure_claim_allowed",
            "native_material_closure_claim_allowed",
            "full_native_material_closure_claim_allowed",
        )
    ):
        raise AssertionError(
            f"{prefix}: {identity} explicit waiver must not allow closure claims"
        )


def _assert_local_evidence(prefix: str, identity: str, record: dict[str, Any]) -> None:
    digest = record.get("sha256") or record.get("local_mirror_sha256")
    byte_count = record.get("bytes") or record.get("local_mirror_bytes")
    if not (isinstance(digest, str) and len(digest) == 64):
        raise AssertionError(f"{prefix}: {identity} must record sha256")
    if not (isinstance(byte_count, int) and byte_count > 0):
        raise AssertionError(f"{prefix}: {identity} must record positive byte count")


def _assert_local_path_field(
    prefix: str,
    identity: str,
    record: dict[str, Any],
    field: str,
    roots: OfflineDependencyRoots,
) -> None:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise AssertionError(f"{prefix}: {identity} {field} is missing")
    path = _resolve_allowed_path(value, roots)
    if path is None:
        raise AssertionError(
            f"{prefix}: {identity} {field} must stay under an allowed root"
        )
    if not path.exists():
        raise AssertionError(f"{prefix}: {identity} {field} file does not exist")
    digest = record.get("sha256") or record.get("local_mirror_sha256")
    byte_count = record.get("bytes") or record.get("local_mirror_bytes")
    if _sha256(path) != digest:
        raise AssertionError(f"{prefix}: {identity} {field} hash mismatch")
    if path.stat().st_size != byte_count:
        raise AssertionError(f"{prefix}: {identity} {field} byte count mismatch")


def _resolve_allowed_path(value: str, roots: OfflineDependencyRoots) -> Path | None:
    raw = value.replace("{ASSETS_DIR}/", "")
    candidate = Path(raw)
    allowed_roots = [roots.package_root.resolve()]
    if roots.overlay_root is not None:
        allowed_roots.append(roots.overlay_root.resolve())
    candidates = [candidate] if candidate.is_absolute() else [
        roots.package_root / raw,
        *( [roots.overlay_root / raw] if roots.overlay_root is not None else [] ),
    ]
    for item in candidates:
        resolved = item.resolve()
        if any(_is_relative_to(resolved, root) for root in allowed_roots):
            return resolved
    return None


def _is_remote_or_cache_path(value: str) -> bool:
    return value.startswith(REMOTE_URI_PREFIXES) or _is_cache_path(value)


def _is_cache_path(value: str) -> bool:
    return any(marker in value for marker in CACHE_PATH_MARKERS)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _record_identity(record: dict[str, Any], index: int) -> str:
    return str(
        record.get("material_name")
        or record.get("relative_path")
        or record.get("local_mirror_path")
        or f"record[{index}]"
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
```

- [ ] **Step 2: Run helper tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_offline_package_validation.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit**

Run:

```bash
git add standalone_tools/labutopia_poc/offline_package_validation.py tests/labutopia_poc/test_offline_package_validation.py
git commit -m "feat: add offline package dependency validator"
```

## Task 3: Integrate DryingBox Package-Local Records

**Files:**
- Modify: `standalone_tools/labutopia_poc/validate_task_package.py`
- Modify: `tests/labutopia_poc/test_validate_task_package.py`

- [ ] **Step 1: Import helper**

Add imports:

```python
from standalone_tools.labutopia_poc.offline_package_validation import (
    OfflineDependencyExpectation,
    OfflineDependencyRoots,
    assert_offline_dependency_records,
)
```

- [ ] **Step 2: Add expectation factory**

Add near DryingBox constants:

```python
def _drying_box_offline_dependency_expectation() -> OfflineDependencyExpectation:
    return OfflineDependencyExpectation(
        allowed_location_statuses={"local_mirror_copied_with_package"},
        local_path_fields={"local_mirror_path"},
        remote_checked_fields={
            "local_mirror_path",
            "relative_path",
            "worker_resolved_path",
        },
        informational_uri_fields={"source_url"},
    )
```

- [ ] **Step 3: Add helper to collect package-local records**

Add:

```python
def _drying_box_package_local_dependency_records(
    dependency_report: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for record in dependency_report:
        if record.get("dependency_location_status") == "local_mirror_copied_with_package":
            records.append(record)
        for texture_record in record.get("texture_dependency_records", []) or []:
            if (
                isinstance(texture_record, dict)
                and texture_record.get("dependency_location_status")
                == "local_mirror_copied_with_package"
            ):
                records.append(texture_record)
    return records
```

- [ ] **Step 4: Call helper in `_validate_drying_box_wrapper_composition()`**

After `dependency_report` is verified as a list and `overlay_root` is computed, call:

```python
    assert_offline_dependency_records(
        manifest_path,
        _drying_box_package_local_dependency_records(dependency_report),
        OfflineDependencyRoots(
            package_root=PACKAGE_ROOT / "common",
            overlay_root=overlay_root,
        ),
        _drying_box_offline_dependency_expectation(),
    )
```

Keep all existing exact Aluminum mirror and texture hash checks.

- [ ] **Step 5: Add regression test**

Add a test in `tests/labutopia_poc/test_validate_task_package.py` that copies the manifest, corrupts the first Aluminum texture `sha256`, monkeypatches `PACKAGE_ROOT`, writes required temp files, and expects `_validate_drying_box_wrapper_composition()` to raise `hash mismatch`.

- [ ] **Step 6: Run package tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_validate_task_package.py -q
python standalone_tools/labutopia_poc/validate_task_package.py
```

Expected: PASS and `LabUtopia task package validation OK`.

- [ ] **Step 7: Commit**

Run:

```bash
git add standalone_tools/labutopia_poc/validate_task_package.py tests/labutopia_poc/test_validate_task_package.py
git commit -m "feat: validate DryingBox offline package dependencies"
```

## Task 4: Document Offline Validation Boundary

**Files:**
- Modify: `docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md`
- Modify: `docs/labutopia_lab_poc/evidence_manifests/README.md`

- [ ] **Step 1: Update pipeline docs**

Add under Gate 1 or Gate 3:

```markdown
Cold/offline package validation currently means static dependency closure: known runtime MDL/texture/package-local records must resolve under package root or staged overlay root, match SHA256/bytes, and avoid remote/cache runtime paths. It is not yet a network-blocked Isaac sandbox run.
```

- [ ] **Step 2: Update manifest field guide**

Add:

```markdown
Offline dependency record checklist:

- runtime path fields must be package-relative, `{ASSETS_DIR}`-relative, or under an explicit staged overlay root.
- `source_url` is provenance only; it cannot be the runtime dependency path.
- package-local files must record SHA256 and byte count.
- offline dependency pass does not upgrade native material closure, official leaderboard, policy success, or PM showcase claims.
```

- [ ] **Step 3: Run docs check**

Run:

```bash
rg -n "offline|Cold/offline|offline dependency|source_url" docs/labutopia_lab_poc
```

Expected: docs explain the boundary and claim limits.

- [ ] **Step 4: Commit**

Run:

```bash
git add docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md docs/labutopia_lab_poc/evidence_manifests/README.md
git commit -m "docs: explain offline package validation boundary"
```

## Task 5: Final Verification and Push

**Files:**
- Verify all LabUtopia POC checks.

- [ ] **Step 1: Run static validator**

Run:

```bash
python standalone_tools/labutopia_poc/validate_task_package.py
```

Expected: `LabUtopia task package validation OK`.

- [ ] **Step 2: Run focused tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_offline_package_validation.py tests/labutopia_poc/test_asset_acceptance_validation.py tests/labutopia_poc/test_validate_task_package.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full LabUtopia POC tests**

Run:

```bash
python -m pytest tests/labutopia_poc -q
```

Expected: PASS.

- [ ] **Step 4: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 5: Push and confirm clean**

Run:

```bash
git status -sb
git push -u fork labutopia-offline-package-validation
git status -sb
```

Expected: branch has upstream, no ahead/behind markers, worktree clean.
