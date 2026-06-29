# Asset Acceptance Reusable Validators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract reusable asset acceptance material validator helpers so future EBench assets can reuse the DryingBox package/native material claim boundary checks.

**Architecture:** Add a focused `asset_acceptance_validation.py` module with typed expectation objects and pure assertion helpers. Keep DryingBox expected values in `validate_task_package.py`, and delegate reusable material closure/provenance checks to the new module without changing manifest schema or claim semantics.

**Tech Stack:** Python 3.10, dataclasses, pytest, JSON manifests, existing LabUtopia POC validator.

---

## File Map

| File | Responsibility |
| --- | --- |
| `standalone_tools/labutopia_poc/asset_acceptance_validation.py` | New generic validation helper module for material closure expectations and native provenance blockers. |
| `tests/labutopia_poc/test_asset_acceptance_validation.py` | New unit tests for valid closure, provenance mismatch, binding-status mismatch, and native overclaim. |
| `standalone_tools/labutopia_poc/validate_task_package.py` | Keep DryingBox constants and package cross-checks; construct `MaterialClosureExpectation` and call the reusable helper. |
| `tests/labutopia_poc/test_validate_task_package.py` | Existing tests should keep passing; adjust only if an assertion message changes intentionally. |

## Task 1: Add Reusable Validator Unit Tests

**Files:**
- Create: `tests/labutopia_poc/test_asset_acceptance_validation.py`

- [ ] **Step 1: Create the failing helper tests**

Create `tests/labutopia_poc/test_asset_acceptance_validation.py` with this content:

```python
from __future__ import annotations

import copy

import pytest

from standalone_tools.labutopia_poc.asset_acceptance_validation import (
    MaterialClosureExpectation,
    NativeMaterialProvenanceBlocker,
    assert_asset_acceptance_material_closure,
)


ROOT = "/World/labutopia_level1_poc/obj_obj_DryingBox_01"


def _expectation() -> MaterialClosureExpectation:
    return MaterialClosureExpectation(
        asset_id="LabUtopia/DryingBox_01",
        material_status="resolved_material_with_local_overrides",
        derived_counts={
            "remote_unmirrored_unwaived_count": 0,
            "remote_waiver_count": 0,
            "explicit_material_waiver_count": 0,
            "local_mirror_count": 1,
            "unsupported_dependency_resolution_mode_count": 0,
            "fallback_surface_count": 0,
            "source_resolved_surface_count": 1,
            "wrapper_authored_material_count": 2,
        },
        source_resolved_runtime_paths={f"{ROOT}/panel"},
        wrapper_authored_runtime_paths={
            f"{ROOT}/Group/_900_1",
            f"{ROOT}/button",
        },
        wrapper_authored_material_targets={
            f"{ROOT}/Looks/task_indicator_mat",
            f"{ROOT}/Looks/task_button_mat",
        },
        native_provenance_blockers={
            NativeMaterialProvenanceBlocker(
                source_prim_path="/World/DryingBox_01/Group/_900_1",
                runtime_prim_path=f"{ROOT}/Group/_900_1",
                runtime_material_path=f"{ROOT}/Looks/task_indicator_mat",
                source_binding_status=(
                    "empty_authored_binding_in_stage2_source_readback"
                ),
            ),
            NativeMaterialProvenanceBlocker(
                source_prim_path="/World/DryingBox_01/button",
                runtime_prim_path=f"{ROOT}/button",
                runtime_material_path=f"{ROOT}/Looks/task_button_mat",
                source_binding_status="unbound_in_stage2_source_readback",
            ),
        },
    )


def _valid_material_closure() -> dict[str, object]:
    return {
        "schema_version": 1,
        "asset_id": "LabUtopia/DryingBox_01",
        "material_status": "resolved_material_with_local_overrides",
        "dependency_records": [
            {
                "material_name": "Aluminum_Anodized_Charcoal",
                "resolution_mode": "local_mirror",
            }
        ],
        "fallback_surface_records": [],
        "waiver_records": [],
        "source_resolved_surface_records": [
            {
                "runtime_prim_path": f"{ROOT}/panel",
                "resolution_mode": "native_geomsubset_material_binding",
                "geomsubset_coverage_status": "covers_all_faces",
                "covered_face_count": 158,
                "face_count": 158,
            }
        ],
        "authored_material_records": [
            {
                "runtime_prim_path": f"{ROOT}/Group/_900_1",
                "resolution_mode": "wrapper_local_preview_surface",
                "runtime_material_path": f"{ROOT}/Looks/task_indicator_mat",
                "native_material_closure_claim_allowed": False,
            },
            {
                "runtime_prim_path": f"{ROOT}/button",
                "resolution_mode": "wrapper_local_preview_surface",
                "runtime_material_path": f"{ROOT}/Looks/task_button_mat",
                "native_material_closure_claim_allowed": False,
            },
        ],
        "derived_counts": _expectation().derived_counts,
        "blockers": [],
        "closure_claim_allowed": True,
        "full_material_closure_claim_allowed": True,
        "aluminum_material_closure_claim_allowed": True,
        "native_material_closure_claim_allowed": False,
        "full_native_material_closure_claim_allowed": False,
        "native_material_closure_reason": (
            "wrapper_local_material_overrides_present"
        ),
        "forbidden_claims": ["full_native_material_closure"],
        "native_material_provenance": {
            "schema_version": 1,
            "status": "blocked_by_wrapper_local_overrides",
            "source_native_blocker_surface_count": 2,
            "native_wrapper_override_surface_count": 2,
            "native_claim_blocker_records": [
                {
                    "source_prim_path": "/World/DryingBox_01/Group/_900_1",
                    "runtime_prim_path": f"{ROOT}/Group/_900_1",
                    "source_binding_status": (
                        "empty_authored_binding_in_stage2_source_readback"
                    ),
                    "source_material_binding": None,
                    "runtime_material_path": f"{ROOT}/Looks/task_indicator_mat",
                    "replacement_required_for_full_native_closure": True,
                    "blocked_claims": [
                        "native_material_closure",
                        "full_native_material_closure",
                    ],
                },
                {
                    "source_prim_path": "/World/DryingBox_01/button",
                    "runtime_prim_path": f"{ROOT}/button",
                    "source_binding_status": "unbound_in_stage2_source_readback",
                    "source_material_binding": None,
                    "runtime_material_path": f"{ROOT}/Looks/task_button_mat",
                    "replacement_required_for_full_native_closure": True,
                    "blocked_claims": [
                        "native_material_closure",
                        "full_native_material_closure",
                    ],
                },
            ],
        },
    }


def test_asset_acceptance_material_closure_helper_accepts_valid_boundary():
    assert_asset_acceptance_material_closure(
        "assets_manifest.json",
        _valid_material_closure(),
        _expectation(),
    )


def test_asset_acceptance_material_closure_helper_rejects_blocker_path_mismatch():
    material = copy.deepcopy(_valid_material_closure())
    material["native_material_provenance"]["native_claim_blocker_records"][0][
        "source_prim_path"
    ] = "/World/DryingBox_01/not_the_indicator"

    with pytest.raises(
        AssertionError,
        match="native material provenance blocker mismatch",
    ):
        assert_asset_acceptance_material_closure(
            "assets_manifest.json",
            material,
            _expectation(),
        )


def test_asset_acceptance_material_closure_helper_rejects_binding_status_mismatch():
    material = copy.deepcopy(_valid_material_closure())
    material["native_material_provenance"]["native_claim_blocker_records"][1][
        "source_binding_status"
    ] = "empty_authored_binding_in_stage2_source_readback"

    with pytest.raises(
        AssertionError,
        match=(
            "native material provenance blockers must retain source evidence "
            "and blocked claims"
        ),
    ):
        assert_asset_acceptance_material_closure(
            "assets_manifest.json",
            material,
            _expectation(),
        )


def test_asset_acceptance_material_closure_helper_rejects_native_overclaim():
    material = copy.deepcopy(_valid_material_closure())
    material["native_material_closure_claim_allowed"] = True

    with pytest.raises(
        AssertionError,
        match="native material closure overclaim",
    ):
        assert_asset_acceptance_material_closure(
            "assets_manifest.json",
            material,
            _expectation(),
        )
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```bash
python -m pytest tests/labutopia_poc/test_asset_acceptance_validation.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'standalone_tools.labutopia_poc.asset_acceptance_validation'`.

- [ ] **Step 3: Commit is not required yet**

Do not commit after Task 1; Task 2 provides the implementation that makes this test file pass.

## Task 2: Implement Generic Material Closure Helper

**Files:**
- Create: `standalone_tools/labutopia_poc/asset_acceptance_validation.py`
- Modify: `tests/labutopia_poc/test_asset_acceptance_validation.py` only if import or assertion messages need exact alignment.

- [ ] **Step 1: Add the helper module**

Create `standalone_tools/labutopia_poc/asset_acceptance_validation.py` with this content:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from standalone_tools.labutopia_poc.material_closure import (
    assert_material_claims_are_derived,
)


EXPECTED_NATIVE_BLOCKED_CLAIMS = [
    "native_material_closure",
    "full_native_material_closure",
]


@dataclass(frozen=True)
class NativeMaterialProvenanceBlocker:
    source_prim_path: str
    runtime_prim_path: str
    runtime_material_path: str
    source_binding_status: str

    @property
    def path_key(self) -> tuple[str, str, str]:
        return (
            self.source_prim_path,
            self.runtime_prim_path,
            self.runtime_material_path,
        )


@dataclass(frozen=True)
class MaterialClosureExpectation:
    asset_id: str
    material_status: str
    derived_counts: dict[str, int]
    source_resolved_runtime_paths: set[str]
    wrapper_authored_runtime_paths: set[str]
    wrapper_authored_material_targets: set[str]
    native_provenance_blockers: set[NativeMaterialProvenanceBlocker]

    @property
    def native_provenance_path_keys(self) -> set[tuple[str, str, str]]:
        return {blocker.path_key for blocker in self.native_provenance_blockers}

    @property
    def native_binding_status_by_source(self) -> dict[str, str]:
        return {
            blocker.source_prim_path: blocker.source_binding_status
            for blocker in self.native_provenance_blockers
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _path(path: object) -> str:
    return str(path)


def assert_asset_acceptance_material_closure(
    manifest_path: object,
    material: object,
    expectation: MaterialClosureExpectation,
    related_reports: dict[str, Any] | None = None,
) -> None:
    prefix = _path(manifest_path)
    _require(
        related_reports is None or isinstance(related_reports, dict),
        f"{prefix}: related_reports must be a mapping when provided",
    )
    _require(
        isinstance(material, dict),
        f"{prefix}: missing asset_acceptance.material_closure",
    )
    _require(
        material.get("asset_id") == expectation.asset_id,
        f"{prefix}: material closure asset_id mismatch",
    )
    _require(
        material.get("schema_version") == 1,
        f"{prefix}: material closure schema_version must be 1",
    )
    counts = material.get("derived_counts")
    _require(
        isinstance(counts, dict),
        f"{prefix}: material closure derived_counts must be a mapping",
    )
    _require(
        counts == expectation.derived_counts,
        f"{prefix}: material closure derived_counts mismatch",
    )
    _require(
        material.get("material_status") == expectation.material_status,
        f"{prefix}: material closure must use local override status",
    )
    _require(
        material.get("blockers") == [],
        f"{prefix}: package material closure must not retain blockers",
    )
    waiver_records = material.get("waiver_records")
    _require(
        isinstance(waiver_records, list)
        and all(isinstance(record, dict) for record in waiver_records),
        f"{prefix}: explicit material waivers must be record mappings",
    )
    try:
        assert_material_claims_are_derived(material)
    except AssertionError as exc:
        raise AssertionError(f"{prefix}: {exc}") from exc
    _require(
        material.get("aluminum_material_closure_claim_allowed") is True
        and material.get("closure_claim_allowed") is True
        and material.get("full_material_closure_claim_allowed") is True
        and material.get("native_material_closure_claim_allowed") is False
        and material.get("full_native_material_closure_claim_allowed") is False,
        f"{prefix}: material closure claim boundary mismatch",
    )
    _require(
        material.get("forbidden_claims") == ["full_native_material_closure"],
        f"{prefix}: full native material closure must remain forbidden",
    )
    source_resolved_records = material.get("source_resolved_surface_records")
    _require(
        isinstance(source_resolved_records, list)
        and {
            record.get("runtime_prim_path")
            for record in source_resolved_records
            if isinstance(record, dict)
        }
        == expectation.source_resolved_runtime_paths,
        f"{prefix}: source_resolved_surface_records must cover panel GeomSubset material coverage",
    )
    for record in source_resolved_records:
        _require(
            isinstance(record, dict)
            and record.get("resolution_mode") == "native_geomsubset_material_binding"
            and record.get("geomsubset_coverage_status") == "covers_all_faces"
            and record.get("covered_face_count") == record.get("face_count"),
            f"{prefix}: source-resolved surfaces must record full GeomSubset coverage",
        )
    authored_material_records = material.get("authored_material_records")
    _require(
        isinstance(authored_material_records, list)
        and {
            record.get("runtime_prim_path")
            for record in authored_material_records
            if isinstance(record, dict)
        }
        == expectation.wrapper_authored_runtime_paths,
        f"{prefix}: authored_material_records must cover local override surfaces",
    )
    for record in authored_material_records:
        _require(
            isinstance(record, dict)
            and record.get("resolution_mode") == "wrapper_local_preview_surface"
            and record.get("runtime_material_path")
            in expectation.wrapper_authored_material_targets
            and record.get("native_material_closure_claim_allowed") is False,
            f"{prefix}: wrapper-authored material record must keep native claim blocked",
        )
    _assert_native_material_provenance(prefix, material, expectation)


def _assert_native_material_provenance(
    prefix: str,
    material: dict[str, Any],
    expectation: MaterialClosureExpectation,
) -> None:
    provenance = material.get("native_material_provenance")
    _require(
        isinstance(provenance, dict),
        f"{prefix}: missing native material provenance",
    )
    _require(
        provenance.get("schema_version") == 1,
        f"{prefix}: native material provenance schema_version must be 1",
    )
    _require(
        provenance.get("status") == "blocked_by_wrapper_local_overrides",
        f"{prefix}: native provenance status mismatch",
    )
    expected_count = len(expectation.native_provenance_blockers)
    _require(
        provenance.get("source_native_blocker_surface_count") == expected_count,
        f"{prefix}: source-native blocker surface count mismatch",
    )
    _require(
        provenance.get("native_wrapper_override_surface_count") == expected_count,
        f"{prefix}: native wrapper override surface count mismatch",
    )
    blocker_records = provenance.get("native_claim_blocker_records")
    _require(
        isinstance(blocker_records, list)
        and all(isinstance(record, dict) for record in blocker_records),
        f"{prefix}: missing native provenance blockers",
    )
    actual_blockers = {
        (
            record.get("source_prim_path"),
            record.get("runtime_prim_path"),
            record.get("runtime_material_path"),
        )
        for record in blocker_records
    }
    _require(
        actual_blockers == expectation.native_provenance_path_keys,
        f"{prefix}: native material provenance blocker mismatch",
    )
    _require(
        len(blocker_records) == expected_count,
        f"{prefix}: native material provenance blocker count mismatch",
    )
    binding_status_by_source = expectation.native_binding_status_by_source
    for record in blocker_records:
        source_prim_path = record.get("source_prim_path")
        _require(
            record.get("source_binding_status")
            == binding_status_by_source.get(source_prim_path)
            and record.get("source_material_binding") is None
            and record.get("replacement_required_for_full_native_closure") is True
            and record.get("blocked_claims") == EXPECTED_NATIVE_BLOCKED_CLAIMS,
            f"{prefix}: native material provenance blockers must retain source evidence and blocked claims",
        )
```

- [ ] **Step 2: Run helper tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_asset_acceptance_validation.py -q
```

Expected: `4 passed`.

- [ ] **Step 3: Run material closure contract tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_material_closure_contract.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

Run:

```bash
git add standalone_tools/labutopia_poc/asset_acceptance_validation.py tests/labutopia_poc/test_asset_acceptance_validation.py
git commit -m "test: add reusable asset acceptance validator helper"
```

## Task 3: Delegate DryingBox Material Validation to Helper

**Files:**
- Modify: `standalone_tools/labutopia_poc/validate_task_package.py`
- Modify: `tests/labutopia_poc/test_validate_task_package.py` only if message expectations need exact alignment.

- [ ] **Step 1: Add imports**

In `standalone_tools/labutopia_poc/validate_task_package.py`, extend the imports near the current `material_closure` import:

```python
from standalone_tools.labutopia_poc.asset_acceptance_validation import (
    MaterialClosureExpectation,
    NativeMaterialProvenanceBlocker,
    assert_asset_acceptance_material_closure,
)
```

- [ ] **Step 2: Replace DryingBox native provenance constants with blocker objects**

Replace `EXPECTED_DRYING_BOX_NATIVE_PROVENANCE_BLOCKERS` and `EXPECTED_DRYING_BOX_NATIVE_PROVENANCE_BINDING_STATUS` with:

```python
EXPECTED_DRYING_BOX_NATIVE_PROVENANCE_BLOCKERS = {
    NativeMaterialProvenanceBlocker(
        source_prim_path="/World/DryingBox_01/Group/_900_1",
        runtime_prim_path=(
            "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Group/_900_1"
        ),
        runtime_material_path=(
            "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/"
            "task_indicator_mat"
        ),
        source_binding_status="empty_authored_binding_in_stage2_source_readback",
    ),
    NativeMaterialProvenanceBlocker(
        source_prim_path="/World/DryingBox_01/button",
        runtime_prim_path="/World/labutopia_level1_poc/obj_obj_DryingBox_01/button",
        runtime_material_path=(
            "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/"
            "task_button_mat"
        ),
        source_binding_status="unbound_in_stage2_source_readback",
    ),
}
```

- [ ] **Step 3: Add DryingBox expectation helper**

Near the DryingBox constants, add:

```python
def _drying_box_material_closure_expectation() -> MaterialClosureExpectation:
    return MaterialClosureExpectation(
        asset_id="LabUtopia/DryingBox_01",
        material_status="resolved_material_with_local_overrides",
        derived_counts={
            "remote_unmirrored_unwaived_count": 0,
            "remote_waiver_count": 0,
            "explicit_material_waiver_count": 0,
            "local_mirror_count": 1,
            "unsupported_dependency_resolution_mode_count": 0,
            "fallback_surface_count": 0,
            "source_resolved_surface_count": 1,
            "wrapper_authored_material_count": 2,
        },
        source_resolved_runtime_paths=EXPECTED_DRYING_BOX_SOURCE_RESOLVED_PATHS,
        wrapper_authored_runtime_paths=EXPECTED_DRYING_BOX_AUTHORED_MATERIAL_PATHS,
        wrapper_authored_material_targets=(
            EXPECTED_DRYING_BOX_AUTHORED_MATERIAL_TARGETS
        ),
        native_provenance_blockers=EXPECTED_DRYING_BOX_NATIVE_PROVENANCE_BLOCKERS,
    )
```

- [ ] **Step 4: Delegate reusable checks**

In `_validate_asset_acceptance_material_closure()`, keep the existing `asset_acceptance` and `material` extraction, then replace the generic count/status/claim/source-resolved/authored/provenance checks with:

```python
    assert_asset_acceptance_material_closure(
        manifest_path,
        material,
        _drying_box_material_closure_expectation(),
    )
```

Keep the DryingBox cross-checks that compare `dependency_records` with `drying_box_wrapper_composition.static_material_dependency_gate` and fallback records with `fallback_display_color_policy`.

- [ ] **Step 5: Run package validator tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_validate_task_package.py -q
```

Expected: `50 passed`.

- [ ] **Step 6: Run focused helper and package tests together**

Run:

```bash
python -m pytest tests/labutopia_poc/test_asset_acceptance_validation.py tests/labutopia_poc/test_validate_task_package.py -q
```

Expected: PASS.

- [ ] **Step 7: Run static package validator**

Run:

```bash
python standalone_tools/labutopia_poc/validate_task_package.py
```

Expected: `LabUtopia task package validation OK`.

- [ ] **Step 8: Commit**

Run:

```bash
git add standalone_tools/labutopia_poc/validate_task_package.py tests/labutopia_poc/test_validate_task_package.py
git commit -m "refactor: delegate DryingBox material closure validation"
```

## Task 4: Document the Reusable Helper Boundary

**Files:**
- Modify: `docs/labutopia_lab_poc/evidence_manifests/README.md`
- Modify: `docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md`

- [ ] **Step 1: Add helper guidance to the field guide**

In `docs/labutopia_lab_poc/evidence_manifests/README.md`, after the Material Closure rules, add:

```markdown
Reusable validator boundary:

- New assets should construct `MaterialClosureExpectation` instead of copy/pasting DryingBox assertions.
- `NativeMaterialProvenanceBlocker` records are the reusable unit for surfaces that have package-visible wrapper material but cannot claim source-native material binding.
- Asset-specific validators may still add package checks for source files, physics reports, camera contracts, or task semantics.
```

- [ ] **Step 2: Add SOP guidance**

In `docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md`, under `Gate 3: Material Closure Gate`, add:

```markdown
Implementation rule: generic material shape checks live in `asset_acceptance_validation.py`. Asset-specific validators pass a `MaterialClosureExpectation`; they should not reimplement provenance blocker path/count/status checks by hand.
```

- [ ] **Step 3: Run claim-text check**

Run:

```bash
rg -n "MaterialClosureExpectation|NativeMaterialProvenanceBlocker|asset_acceptance_validation|native_material_provenance" docs/labutopia_lab_poc
```

Expected: docs mention the reusable helper and still mention `native_material_provenance`.

- [ ] **Step 4: Commit**

Run:

```bash
git add docs/labutopia_lab_poc/evidence_manifests/README.md docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md
git commit -m "docs: document reusable asset acceptance validator helpers"
```

## Task 5: Final Verification and Push

**Files:**
- Verify the whole LabUtopia POC package.

- [ ] **Step 1: Run static validator**

Run:

```bash
python standalone_tools/labutopia_poc/validate_task_package.py
```

Expected: `LabUtopia task package validation OK`.

- [ ] **Step 2: Run focused tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_asset_acceptance_validation.py tests/labutopia_poc/test_material_closure_contract.py tests/labutopia_poc/test_build_asset_overlay.py tests/labutopia_poc/test_validate_task_package.py -q
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

- [ ] **Step 5: Push**

Run:

```bash
git status -sb
git push
git status -sb
```

Expected: branch is even with upstream and worktree is clean.
