# EBench Asset Acceptance Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable evidence-gated acceptance pipeline so LabUtopia and future external asset packages can enter GenManip/EBench with explicit material, physics, articulation, runtime, render, and Lift2 contract claims.

**Architecture:** Keep Lift2 contract validation separate from full material closure. Add an asset-agnostic `asset_acceptance` schema and validator helpers, then make DryingBox the first reference asset by closing remaining fallback material surfaces and producing one final `asset_acceptance_record.json`.

**Tech Stack:** Python 3.10, USD Python APIs (`pxr.Usd`, `pxr.UsdShade`, `pxr.UsdPhysics`, `pxr.UsdGeom`), Isaac Sim 4.1 runtime, GenManip/EBench task configs, pytest, JSON manifests, static Markdown/HTML docs.

**Current Stage/Gate convention:** `Acceptance Stage` is execution order; `Gate` is claim status. `Stage 7` is the local Lift2 evaluator robot contract, while `Gate 7` remains render evidence. The two number systems do not map 1:1.

**2026-06-29 update:** Stage 0-7 now has a shared machine-readable registry:

- `standalone_tools/labutopia_poc/asset_acceptance.py` defines `ACCEPTANCE_STAGE_CONTRACT`, `acceptance_stage_entry()`, and `assert_acceptance_stages_are_ordered()`.
- `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json` records package-side Stage 0-4 in `asset_acceptance.acceptance_stages`.
- `docs/labutopia_lab_poc/evidence_manifests/dryingbox_asset_acceptance_20260629_asset_acceptance_manual.json` records final Stage 0-7 in `acceptance_stages`.
- `gate_status` remains the backward-compatible claim summary and must not replace `acceptance_stages`.
- `blocked_claims` remains a legacy claim-allowed map; new consumers should read `claim_boundary.blocked_claim_status.*.blocked`.

**2026-06-29 execution ledger:** An implementation audit found that this plan has advanced beyond the unchecked boxes below. Treat the table here as the current source of execution truth; the detailed Task sections remain as historical implementation notes and reproduction instructions.

| Task | Current status | Evidence | Remaining work |
| --- | --- | --- | --- |
| 1. Material Closure Data Model | COMPLETE | `2216337`, `standalone_tools/labutopia_poc/material_closure.py`, `tests/labutopia_poc/test_material_closure_contract.py` | None. |
| 2. Negative Material Closure Tests | COMPLETE | `87fdf96`, `assert_material_claims_are_derived()`, overclaim and remote dependency tests | None. |
| 3. Emit Generic `asset_acceptance` Material Object | COMPLETE | `bb5919e`, `asset_acceptance.material_closure` in `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json` | None. |
| 4. Validate Generic Asset Acceptance Fields | COMPLETE | `8b18ab6`, package validator checks `asset_acceptance.acceptance_stages` and material claims | None. |
| 5. Full Material Closure Follow-Up | PARTIAL | `50ee478`; package material gate is closed with `fallback_surface_count=0` and `full_material_closure_claim_allowed=true` | Full source-native material closure remains blocked by two wrapper-local authored materials: `button` and `Group/_900_1`. |
| 6. Asset Acceptance Record and PM Evidence | COMPLETE | `f715acf` plus `35768e1`; final record contains `acceptance_stages`, `gate_status`, and `claim_boundary.blocked_claim_status` | Overall record is still `WARN` because blocked claims remain. |
| 7. Final Verification | VERIFIED | `python standalone_tools/labutopia_poc/validate_task_package.py`; focused pytest listed in Task 7; `git diff --check`; claim-text grep | No dedicated final-docs commit was needed after `35768e1`; repeat verification before any future claim upgrade. |

**Current next work:** Do not restart at Task 1. The next engineering batch is a separate `Full Native Material Provenance` follow-up: audit whether `/World/DryingBox_01/button` and `/World/DryingBox_01/Group/_900_1` can be restored to source-native material binding. If they cannot, keep `native_material_closure_claim_allowed=false` and `full_native_material_closure_claim_allowed=false`, then document the permanent waiver; do not downgrade the already-passing package material gate.

---

## File Map

| File | Responsibility |
| --- | --- |
| `standalone_tools/labutopia_poc/asset_acceptance.py` | Shared Stage 0-7 registry and ordered-stage validator. |
| `standalone_tools/labutopia_poc/material_closure.py` | New reusable material dependency, binding, fallback, waiver, and claim derivation module. |
| `tests/labutopia_poc/test_asset_acceptance_contract.py` | Unit tests for Stage 0-7 ordering and ids. |
| `tests/labutopia_poc/test_material_closure_contract.py` | New unit tests for material closure positive and negative cases. |
| `standalone_tools/labutopia_poc/build_asset_overlay.py` | Emit `asset_acceptance.acceptance_stages` and `asset_acceptance.material_closure` while keeping current Aluminum compatibility fields. |
| `standalone_tools/labutopia_poc/validate_task_package.py` | Validate generic `asset_acceptance` stage/material fields and reject overclaims. |
| `tests/labutopia_poc/test_validate_task_package.py` | Add package-level negative tests for stale bindings, fallback overclaim, and missing mirror evidence. |
| `standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py` | Include Stage 0-7 `acceptance_stages` and claim boundary in eval-path diagnostics. |
| `docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md` | Canonical PM/engineering SOP. |
| `docs/labutopia_lab_poc/evidence_manifests/README.md` | Machine-readable manifest field guide. |
| `docs/records/2026-06-22-labutopia-ebench-weekly-report.md` | PM status entry and link to the SOP. |
| `docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html` | GitHub Pages weekly report link to the SOP. |

## Task 1: Material Closure Data Model

**Status:** COMPLETE in commit `2216337`. Keep this section for TDD reproduction only; do not re-run it by deleting existing code.

**Files:**
- Create: `standalone_tools/labutopia_poc/material_closure.py`
- Create: `tests/labutopia_poc/test_material_closure_contract.py`

- [ ] **Step 1: Write the scoped-claim test**

```python
def test_scoped_local_mirror_does_not_allow_full_native_material_closure():
    from standalone_tools.labutopia_poc.material_closure import (
        derive_material_closure_claims,
    )

    report = derive_material_closure_claims(
        asset_id="LabUtopia/DryingBox_01",
        dependency_records=[
            {
                "material_name": "Aluminum_Anodized_Charcoal",
                "resolution_mode": "local_mirror",
                "local_mirror_sha256": "640855d3890c6faaae6346a850ef9f366d4b397c0f4313e25c7ac0b9230c106a",
                "texture_dependency_records": [
                    {"package_relative_path": "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_BaseColor.png", "sha256": "d1d042502d7d94bca13cee10c63ab5b3801fb0a46e26d79169e13f5b9c7b5a31"},
                    {"package_relative_path": "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_Normal.png", "sha256": "6dc1cb1b23a9abd766188a85ccbad1a2639d0a9a334f284e359c6c5d4438608e"},
                    {"package_relative_path": "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_ORM.png", "sha256": "768f2dbb4f702a9624b912b431efd1a6a8e0ff3e93744cf54f3866ef8f7986e9"},
                ],
            }
        ],
        fallback_surface_records=[
            {"runtime_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Group/_900_1", "displayColor_fallback_status": "authored"},
            {"runtime_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/button", "displayColor_fallback_status": "authored"},
            {"runtime_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/panel", "displayColor_fallback_status": "authored"},
        ],
        waiver_records=[],
    )

    assert report["material_status"] == "mixed_native_and_fallback"
    assert report["aluminum_material_closure_claim_allowed"] is True
    assert report["native_material_closure_claim_allowed"] is False
    assert report["full_native_material_closure_claim_allowed"] is False
    assert report["derived_counts"]["fallback_surface_count"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/labutopia_poc/test_material_closure_contract.py::test_scoped_local_mirror_does_not_allow_full_native_material_closure -q
```

Expected: FAIL with `ModuleNotFoundError` because `material_closure.py` does not exist.

- [ ] **Step 3: Implement minimal claim derivation**

Create `standalone_tools/labutopia_poc/material_closure.py` with:

```python
from __future__ import annotations

from typing import Any


def _is_aluminum_record(record: dict[str, Any]) -> bool:
    return record.get("material_name") == "Aluminum_Anodized_Charcoal"


def derive_material_closure_claims(
    *,
    asset_id: str,
    dependency_records: list[dict[str, Any]],
    fallback_surface_records: list[dict[str, Any]],
    waiver_records: list[dict[str, Any]],
) -> dict[str, Any]:
    local_mirror_count = sum(
        1 for record in dependency_records if record.get("resolution_mode") == "local_mirror"
    )
    remote_unmirrored_unwaived_count = sum(
        1 for record in dependency_records if record.get("resolution_mode") == "remote_unmirrored_unwaived"
    )
    waiver_count = len(waiver_records)
    fallback_surface_count = len(fallback_surface_records)
    aluminum_local = any(
        _is_aluminum_record(record) and record.get("resolution_mode") == "local_mirror"
        for record in dependency_records
    )
    full_allowed = (
        remote_unmirrored_unwaived_count == 0
        and waiver_count == 0
        and fallback_surface_count == 0
        and bool(dependency_records)
    )
    material_status = "resolved_native_material" if full_allowed else "mixed_native_and_fallback"
    reason = None if full_allowed else "fallback_surfaces_or_waivers_remain"
    if fallback_surface_count > 0:
        reason = "fallback_surfaces_remain_after_aluminum_local_mirror"

    return {
        "schema_version": 1,
        "asset_id": asset_id,
        "material_status": material_status,
        "dependency_records": dependency_records,
        "fallback_surface_records": fallback_surface_records,
        "waiver_records": waiver_records,
        "derived_counts": {
            "remote_unmirrored_unwaived_count": remote_unmirrored_unwaived_count,
            "remote_waiver_count": waiver_count,
            "local_mirror_count": local_mirror_count,
            "fallback_surface_count": fallback_surface_count,
        },
        "closure_claim_allowed": full_allowed,
        "aluminum_material_closure_claim_allowed": aluminum_local,
        "native_material_closure_claim_allowed": full_allowed,
        "full_native_material_closure_claim_allowed": full_allowed,
        "native_material_closure_reason": reason,
        "forbidden_claims": [] if full_allowed else ["full_native_material_closure"],
    }
```

- [ ] **Step 4: Run the new test**

Run:

```bash
python -m pytest tests/labutopia_poc/test_material_closure_contract.py -q
```

Expected: PASS for the new scoped-claim test.

- [ ] **Step 5: Commit**

```bash
git add standalone_tools/labutopia_poc/material_closure.py tests/labutopia_poc/test_material_closure_contract.py
git commit -m "test: add reusable material closure contract"
```

## Task 2: Negative Material Closure Tests

**Status:** COMPLETE in commit `87fdf96`. Current tests include stale-count, remote-dependency, unsupported-resolution, and wrapper-authored-material overclaim protection.

**Files:**
- Modify: `tests/labutopia_poc/test_material_closure_contract.py`
- Modify: `standalone_tools/labutopia_poc/material_closure.py`

- [ ] **Step 1: Add overclaim and missing mirror tests**

Append these tests:

```python
import pytest


def test_rejects_full_closure_overclaim_with_fallback_surface():
    from standalone_tools.labutopia_poc.material_closure import (
        assert_material_claims_are_derived,
    )

    claimed = {
        "full_native_material_closure_claim_allowed": True,
        "derived_counts": {"fallback_surface_count": 1},
    }

    with pytest.raises(AssertionError, match="full material closure overclaim"):
        assert_material_claims_are_derived(claimed)


def test_rejects_remote_dependency_without_mirror_or_waiver():
    from standalone_tools.labutopia_poc.material_closure import (
        derive_material_closure_claims,
    )

    report = derive_material_closure_claims(
        asset_id="LabUtopia/DryingBox_01",
        dependency_records=[
            {
                "material_name": "ExampleRemote",
                "resolution_mode": "remote_unmirrored_unwaived",
            }
        ],
        fallback_surface_records=[],
        waiver_records=[],
    )

    assert report["derived_counts"]["remote_unmirrored_unwaived_count"] == 1
    assert report["native_material_closure_claim_allowed"] is False
    assert "remote_dependency_unmirrored_unwaived" in report["blockers"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/labutopia_poc/test_material_closure_contract.py -q
```

Expected: FAIL because `assert_material_claims_are_derived` and `blockers` do not exist.

- [ ] **Step 3: Implement blocker derivation and overclaim assertion**

Extend `material_closure.py`:

```python
def _derive_blockers(
    *,
    remote_unmirrored_unwaived_count: int,
    waiver_count: int,
    fallback_surface_count: int,
) -> list[str]:
    blockers: list[str] = []
    if remote_unmirrored_unwaived_count:
        blockers.append("remote_dependency_unmirrored_unwaived")
    if waiver_count:
        blockers.append("explicit_material_waiver_open")
    if fallback_surface_count:
        blockers.append("fallback_surfaces_remain_after_aluminum_local_mirror")
    return blockers


def assert_material_claims_are_derived(report: dict[str, Any]) -> None:
    counts = report.get("derived_counts") or {}
    fallback_count = int(counts.get("fallback_surface_count") or 0)
    if fallback_count and report.get("full_native_material_closure_claim_allowed") is True:
        raise AssertionError("full material closure overclaim: fallback surfaces remain")
```

Inside `derive_material_closure_claims()`, compute `blockers = _derive_blockers(...)` and include `"blockers": blockers` in the returned dict.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_material_closure_contract.py -q
```

Expected: all tests in `test_material_closure_contract.py` pass.

- [ ] **Step 5: Commit**

```bash
git add standalone_tools/labutopia_poc/material_closure.py tests/labutopia_poc/test_material_closure_contract.py
git commit -m "test: reject material closure overclaims"
```

## Task 3: Emit Generic `asset_acceptance` Material Object

**Status:** COMPLETE in commit `bb5919e`, later refined by `50ee478` and `35768e1`. The current manifest emits both `asset_acceptance.acceptance_stages` and `asset_acceptance.material_closure`.

**Files:**
- Modify: `standalone_tools/labutopia_poc/build_asset_overlay.py`
- Modify: `tests/labutopia_poc/test_build_asset_overlay.py`
- Modify: `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json`

- [ ] **Step 1: Add manifest schema expectation**

Add a test that generated manifest contains:

```python
def test_manifest_contains_generic_asset_acceptance_material_closure(tmp_path):
    labutopia_root = tmp_path / "LabUtopia"
    source_dir = labutopia_root / "assets" / "chemistry_lab" / "lab_001"
    source_dir.mkdir(parents=True)
    (source_dir / "lab_001.usd").write_text("#usda 1.0\n", encoding="utf-8")
    _write_native_material_fixture(source_dir)

    overlay_root = tmp_path / "overlay" / "assets"
    build_asset_overlay(
        labutopia_root=labutopia_root,
        overlay_root=overlay_root,
        drying_box_strategy="native_complex",
    )

    manifest_path = overlay_root / "manifests" / "labutopia_level1_poc.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    material = manifest["asset_acceptance"]["material_closure"]
    assert material["asset_id"] == "LabUtopia/DryingBox_01"
    assert material["material_status"] == "mixed_native_and_fallback"
    assert material["derived_counts"]["local_mirror_count"] == 1
    assert material["derived_counts"]["fallback_surface_count"] == 3
    assert material["aluminum_material_closure_claim_allowed"] is True
    assert material["full_native_material_closure_claim_allowed"] is False
```

- [ ] **Step 2: Run the focused test**

Run:

```bash
python -m pytest tests/labutopia_poc/test_build_asset_overlay.py -q
```

Expected: FAIL because `asset_acceptance.material_closure` is missing.

- [ ] **Step 3: Emit the generic object**

In `build_asset_overlay.py`, import:

```python
from standalone_tools.labutopia_poc.material_closure import derive_material_closure_claims
```

When the existing Aluminum/fallback material summary is assembled, add:

```python
manifest["asset_acceptance"] = {
    "material_closure": derive_material_closure_claims(
        asset_id="LabUtopia/DryingBox_01",
        dependency_records=[aluminum_dependency_record],
        fallback_surface_records=fallback_records,
        waiver_records=[],
    )
}
```

Keep existing compatibility fields such as `remote_aluminum_disposition`, `material_closure_followups`, and `fallback_display_color_policy` until all downstream validators migrate.

- [ ] **Step 4: Regenerate manifest**

Run:

```bash
python standalone_tools/labutopia_poc/build_asset_overlay.py --drying-box-strategy native_complex
```

Expected: `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json` contains `asset_acceptance.material_closure`.

- [ ] **Step 5: Verify tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_build_asset_overlay.py tests/labutopia_poc/test_validate_task_package.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add standalone_tools/labutopia_poc/build_asset_overlay.py standalone_tools/labutopia_poc/material_closure.py tests/labutopia_poc/test_build_asset_overlay.py configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json
git commit -m "feat: emit generic asset material closure evidence"
```

## Task 4: Validate Generic Asset Acceptance Fields

**Status:** COMPLETE in commit `8b18ab6`, later refined by `35768e1`. The package validator now rejects missing or unordered acceptance stages and material overclaims.

**Files:**
- Modify: `standalone_tools/labutopia_poc/validate_task_package.py`
- Modify: `tests/labutopia_poc/test_validate_task_package.py`

- [ ] **Step 1: Add validator negative test for full closure overclaim**

```python
def test_validate_rejects_full_material_closure_overclaim(tmp_path):
    from standalone_tools.labutopia_poc.material_closure import (
        assert_material_claims_are_derived,
    )

    report = {
        "derived_counts": {"fallback_surface_count": 3},
        "full_native_material_closure_claim_allowed": True,
    }

    with pytest.raises(AssertionError, match="full material closure overclaim"):
        assert_material_claims_are_derived(report)
```

- [ ] **Step 2: Run focused validation tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_validate_task_package.py -q
```

Expected: the new test passes if Task 2 is complete; package validator still does not inspect `asset_acceptance`.

- [ ] **Step 3: Add package validator checks**

Inside `validate_task_package.py`, after existing material follow-up checks, assert:

```python
asset_acceptance = manifest.get("asset_acceptance")
require(isinstance(asset_acceptance, dict), f"{manifest_path}: missing asset_acceptance")
material = asset_acceptance.get("material_closure")
require(isinstance(material, dict), f"{manifest_path}: missing asset_acceptance.material_closure")
require(material.get("asset_id") == "LabUtopia/DryingBox_01", f"{manifest_path}: material closure asset_id mismatch")
require(material.get("derived_counts", {}).get("fallback_surface_count") == 3, f"{manifest_path}: fallback surface count mismatch")
require(material.get("full_native_material_closure_claim_allowed") is False, f"{manifest_path}: full material closure overclaim")
assert_material_claims_are_derived(material)
```

Import `assert_material_claims_are_derived` from `standalone_tools.labutopia_poc.material_closure`.

- [ ] **Step 4: Run static validator**

Run:

```bash
python standalone_tools/labutopia_poc/validate_task_package.py
```

Expected: `LabUtopia task package validation OK`.

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_validate_task_package.py tests/labutopia_poc/test_material_closure_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add standalone_tools/labutopia_poc/validate_task_package.py tests/labutopia_poc/test_validate_task_package.py
git commit -m "test: validate asset acceptance material claims"
```

## Task 5: Full Material Closure Follow-Up for Remaining Surfaces

**Status:** PARTIAL. Package-level material closure is COMPLETE: Aluminum is local-mirrored, `panel` is source-resolved by native `GeomSubset` binding, runtime `fallback_surface_count=0`, and `full_material_closure_claim_allowed=true`. Full source-native material closure is NOT complete: `button` and `Group/_900_1` are still `wrapper_local_preview_surface`, so `native_material_closure_claim_allowed=false` and `full_native_material_closure_claim_allowed=false`.

**Next follow-up:** Reframe the remaining work as `Full Native Material Provenance`, not as a blocker for the Lift2 contract or package material gate. The follow-up must either restore source-native binding for both wrapper-local surfaces, or record explicit permanent waiver(s) while keeping native claims blocked.

**Historical note:** The original xfail-style test below was written before package closure reached `fallback_surface_count=0`. Do not reintroduce it as-is. A new follow-up test should assert that `wrapper_authored_material_count` becomes `0` before `full_native_material_closure_claim_allowed` may become `true`.

**Files:**
- Modify: `standalone_tools/labutopia_poc/build_asset_overlay.py`
- Modify: `standalone_tools/labutopia_poc/validate_task_package.py`
- Modify: `tests/labutopia_poc/test_build_asset_overlay.py`
- Modify: `tests/labutopia_poc/test_validate_task_package.py`
- Modify: `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json`

- [ ] **Step 1: Add expected native binding test**

```python
@pytest.mark.xfail(reason="Full Material Closure follow-up not implemented")
def test_dryingbox_full_material_closure_has_no_fallback_surfaces(tmp_path):
    labutopia_root = tmp_path / "LabUtopia"
    source_dir = labutopia_root / "assets" / "chemistry_lab" / "lab_001"
    source_dir.mkdir(parents=True)
    (source_dir / "lab_001.usd").write_text("#usda 1.0\n", encoding="utf-8")
    _write_native_material_fixture(source_dir)

    overlay_root = tmp_path / "overlay" / "assets"
    build_asset_overlay(
        labutopia_root=labutopia_root,
        overlay_root=overlay_root,
        drying_box_strategy="native_complex",
    )

    manifest_path = overlay_root / "manifests" / "labutopia_level1_poc.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    material = manifest["asset_acceptance"]["material_closure"]
    assert material["derived_counts"]["fallback_surface_count"] == 0
    assert material["material_status"] == "resolved_native_material"
    assert material["full_native_material_closure_claim_allowed"] is True
```

- [ ] **Step 2: Locate source materials**

Run:

```bash
python standalone_tools/labutopia_poc/audit_native_dryingbox.py --labutopia-root /cpfs/shared/simulation/zhuzihou/dev/LabUtopia --output-root saved/diagnostics/native_dryingbox_material_audit_manual
```

Expected: `audit.json` records whether `Group/_900_1`, `button`, and `panel` have source `material:binding`, authored `displayColor`, or missing binding in the native asset.

- [ ] **Step 3: Add native binding or waiver records**

For each fallback path:

```text
/World/labutopia_level1_poc/obj_obj_DryingBox_01/Group/_900_1
/World/labutopia_level1_poc/obj_obj_DryingBox_01/button
/World/labutopia_level1_poc/obj_obj_DryingBox_01/panel
```

Choose exactly one disposition:

```text
native_binding_restored
local_mirror
explicit_waiver
```

If using `explicit_waiver`, include `waiver_id`, owner, reason, affected path, expiry/review date, and blocked claims. Do not set `full_native_material_closure_claim_allowed=true` while any waiver remains.

- [ ] **Step 4: Regenerate overlay and manifest**

Run:

```bash
python standalone_tools/labutopia_poc/build_asset_overlay.py --drying-box-strategy native_complex
python standalone_tools/labutopia_poc/validate_task_package.py
```

Expected: validator passes. If all three surfaces are native-bound and no waiver remains, fallback count becomes `0`; otherwise full material closure remains blocked with explicit waiver records.

- [ ] **Step 5: Re-run material and package tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_material_closure_contract.py tests/labutopia_poc/test_build_asset_overlay.py tests/labutopia_poc/test_validate_task_package.py -q
```

Expected: PASS. Remove the `xfail` only when package fallback surfaces are zero and full native material closure is still gated by source-native material provenance, not by fallback count alone.

- [ ] **Step 6: Commit**

```bash
git add standalone_tools/labutopia_poc/build_asset_overlay.py standalone_tools/labutopia_poc/validate_task_package.py tests/labutopia_poc/test_build_asset_overlay.py tests/labutopia_poc/test_validate_task_package.py configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json
git commit -m "feat: close DryingBox native material surfaces"
```

## Task 6: Asset Acceptance Record and PM Evidence

**Status:** COMPLETE in commit `f715acf`, expanded by `35768e1`. The current evidence record is intentionally `WARN` because render/showcase and official leaderboard/policy claims remain blocked.

**Files:**
- Create: `docs/labutopia_lab_poc/evidence_manifests/dryingbox_asset_acceptance_<timestamp>.json`
- Modify: `standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py`
- Modify: `docs/records/2026-06-22-labutopia-ebench-weekly-report.md`
- Modify: `docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html`

- [ ] **Step 1: Add final record writer contract test**

```python
def test_asset_acceptance_record_contains_allowed_and_blocked_claims(tmp_path):
    record = {
        "schema_version": 1,
        "asset_id": "LabUtopia/DryingBox_01",
        "task_lane": "ebench/labutopia_lab_poc/lift2_candidate",
        "gate_status": {
            "task_runtime": "PASS",
            "evaluator_robot_contract": "PASS",
            "material_closure": "PASS",
        },
        "allowed_claims": {
            "task_runtime_ready": True,
            "lift2_contract_ready": True,
        },
        "blocked_claims": {
            "official_leaderboard_claim_allowed": False,
            "policy_success_claim_allowed": False,
        },
    }
    assert record["allowed_claims"]["lift2_contract_ready"] is True
    assert record["blocked_claims"]["policy_success_claim_allowed"] is False
```

Place this in the most relevant existing diagnostics contract test file, usually `tests/labutopia_poc/test_render_diagnostics_contract.py`.

- [ ] **Step 2: Capture fresh eval-path evidence**

Run:

```bash
conda run -p /cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310 \
  python standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py \
  --task level1_open_door \
  --output-root saved/diagnostics/dryingbox_asset_acceptance_manual
```

Expected: writes diagnostics with evaluator-camera frame paths, hashes, material status, metric status, and claim boundary.

- [ ] **Step 3: Generate final acceptance JSON**

Create a dated manifest under:

```text
docs/labutopia_lab_poc/evidence_manifests/dryingbox_asset_acceptance_<timestamp>.json
```

The manifest must include:

```json
{
  "asset_id": "LabUtopia/DryingBox_01",
  "task_lane": "ebench/labutopia_lab_poc/lift2_candidate",
  "gate_status": {},
  "allowed_claims": {},
  "blocked_claims": {},
  "artifact_paths": [],
  "artifact_sha256": {},
  "verification": []
}
```

Do not include `official_leaderboard_claim_allowed=true` or `policy_success_claim_allowed=true` unless those separate official/policy gates have evidence.

- [ ] **Step 4: Update PM docs**

Update the weekly Markdown and HTML so they say:

```text
DryingBox 已成为 EBench Asset Acceptance Pipeline 的 reference asset。它通过哪些 gate、还阻塞哪些 claim，都以 asset_acceptance_record.json 为准。PM 周报只引用 allowed_claims，不把 diagnostic/WARN 图写成最终展示图。
```

- [ ] **Step 5: Browser-review weekly HTML**

Run a desktop and mobile screenshot pass with Chromium:

```bash
/root/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome --headless --disable-gpu --no-sandbox --window-size=1440,1800 --screenshot=/tmp/labutopia_weekly_pipeline_desktop.png file:///root/.config/superpowers/worktrees/GenManip/labutopia-material-aluminum-mirror/docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html
/root/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome --headless --disable-gpu --no-sandbox --window-size=390,1600 --screenshot=/tmp/labutopia_weekly_pipeline_mobile.png file:///root/.config/superpowers/worktrees/GenManip/labutopia-material-aluminum-mirror/docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html
```

Expected: no broken layout, no missing report links, no raw markdown visible.

- [ ] **Step 6: Commit**

```bash
git add standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py tests/labutopia_poc/test_render_diagnostics_contract.py docs/labutopia_lab_poc/evidence_manifests/dryingbox_asset_acceptance_*.json docs/records/2026-06-22-labutopia-ebench-weekly-report.md docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html
git commit -m "docs: record DryingBox asset acceptance evidence"
```

## Task 7: Final Verification

**Status:** VERIFIED for the current package state after `35768e1`. Repeat this task before any future claim upgrade, especially before changing `pm_showcase_ready`, `official_*`, or `full_native_material_closure_claim_allowed`.

**Files:**
- Verify: full package and docs.

- [ ] **Step 1: Run static validator**

Run:

```bash
python standalone_tools/labutopia_poc/validate_task_package.py
```

Expected: `LabUtopia task package validation OK`.

- [ ] **Step 2: Run focused test suites**

Run:

```bash
python -m pytest tests/labutopia_poc/test_material_closure_contract.py tests/labutopia_poc/test_build_asset_overlay.py tests/labutopia_poc/test_validate_task_package.py tests/labutopia_poc/test_render_diagnostics_contract.py tests/labutopia_poc/test_lift2_eval_contract_probe.py -q
```

Expected: PASS.

- [ ] **Step 3: Run docs whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Confirm claim text**

Run:

```bash
rg -n "official leaderboard|policy success|full native material closure|EBench Asset Acceptance Pipeline|asset_acceptance" docs configs/tasks/ebench/README.md
```

Expected: docs consistently say local Lift2 contract is not official leaderboard, policy success is not proven, package material closure can pass with `fallback_surface_count=0`, and full native material closure is only true after wrapper-local authored materials have source-native provenance.

- [ ] **Step 5: Commit final docs if needed**

```bash
git add docs configs/tasks/ebench/README.md
git commit -m "docs: finalize EBench asset acceptance pipeline"
```
