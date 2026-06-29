# DryingBox Full Native Material Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the DryingBox material boundary explicit enough that EBench package material closure stays PASS while source-native material closure remains blocked unless real native provenance exists.

**Architecture:** Treat `Full Native Material Provenance` as an additive claim-boundary follow-up. Do not replace the passing package material gate. Add native-provenance records, validators, and docs that explain why `button` and `Group/_900_1` stay wrapper-local, and ensure no code path can turn wrapper-local preview materials into native closure claims.

**Tech Stack:** Python 3.10, USD Python APIs (`pxr.Usd`, `pxr.UsdShade`, `pxr.UsdGeom`), pytest, JSON manifests, Markdown docs.

---

## Current Evidence

Read-only audits agree that the remaining wrapper-local surfaces are not safely recoverable as source-native material bindings:

| Surface | Source evidence | Runtime disposition | Claim effect |
| --- | --- | --- | --- |
| `/World/DryingBox_01/button` | no `material:binding`; `ComputeBoundMaterial` fails; no authored `primvars:displayColor` | wrapper-local `/Looks/task_button_mat` | blocks `native_material_closure_claim_allowed` and `full_native_material_closure_claim_allowed` |
| `/World/DryingBox_01/Group/_900_1` | no usable binding target; authored empty or unbound source binding evidence; black `primvars:displayColor` | wrapper-local `/Looks/task_indicator_mat` | blocks `native_material_closure_claim_allowed` and `full_native_material_closure_claim_allowed` |
| `/World/DryingBox_01/panel` | parent mesh is unbound, but child `GeomSubset` prims bind to `mdl_0007`, `mdl_0008`, and `Aluminum_Anodized_Charcoal` | source-resolved by native `GeomSubset` coverage | does not block package material closure |

Fresh local audit artifact:

```text
/tmp/labutopia_native_dryingbox_material_audit_20260629/audit.json
source stage: /cpfs/shared/simulation/zhuzihou/dev/LabUtopia/assets/chemistry_lab/lab_001/lab_001.usd
source sha256: 26212d40a78cd28f2bc3a38b2e06f05875b3096501c7d6dd5ccbe9a6e9019983
```

Current package invariants that must not regress:

```text
closure_claim_allowed=true
full_material_closure_claim_allowed=true
fallback_surface_count=0
waiver_records=[]
wrapper_authored_material_count=2
native_material_closure_claim_allowed=false
full_native_material_closure_claim_allowed=false
material_status=resolved_material_with_local_overrides
```

## File Map

| File | Responsibility |
| --- | --- |
| `standalone_tools/labutopia_poc/material_closure.py` | Derive package and native material claims from counts, authored records, and native provenance blockers. |
| `tests/labutopia_poc/test_material_closure_contract.py` | Unit tests for native-provenance blockers and no-overclaim behavior. |
| `standalone_tools/labutopia_poc/build_asset_overlay.py` | Emit native provenance records for wrapper-local surfaces and keep package material gate PASS. |
| `tests/labutopia_poc/test_build_asset_overlay.py` | Assert manifest fields for `button`, `Group/_900_1`, and current package/native claim split. |
| `standalone_tools/labutopia_poc/validate_task_package.py` | Validate additive native-provenance fields and reject native overclaims. |
| `tests/labutopia_poc/test_validate_task_package.py` | Negative tests for native claim overreach and malformed provenance records. |
| `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json` | Generated package manifest with native provenance evidence. |
| `docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md` | PM/engineering SOP explaining package closure versus source-native closure. |
| `docs/labutopia_lab_poc/evidence_manifests/README.md` | Machine-readable field guide for native material provenance. |

## Task 1: Freeze Native Claim Invariants

**Files:**
- Modify: `tests/labutopia_poc/test_material_closure_contract.py`

- [ ] **Step 1: Write package-versus-native regression test**

Append this test:

```python
def test_package_material_closure_stays_true_with_wrapper_authored_native_blockers():
    from standalone_tools.labutopia_poc.material_closure import (
        derive_material_closure_claims,
    )

    report = derive_material_closure_claims(
        asset_id="LabUtopia/DryingBox_01",
        dependency_records=[_aluminum_dependency_record()],
        fallback_surface_records=[],
        waiver_records=[],
        source_resolved_surface_records=[
            {
                "runtime_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/panel",
                "resolution_mode": "native_geomsubset_material_binding",
            }
        ],
        authored_material_records=[
            {
                "runtime_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/button",
                "resolution_mode": "wrapper_local_preview_surface",
            },
            {
                "runtime_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Group/_900_1",
                "resolution_mode": "wrapper_local_preview_surface",
            },
        ],
    )

    assert report["closure_claim_allowed"] is True
    assert report["full_material_closure_claim_allowed"] is True
    assert report["derived_counts"]["fallback_surface_count"] == 0
    assert report["derived_counts"]["wrapper_authored_material_count"] == 2
    assert report["native_material_closure_claim_allowed"] is False
    assert report["full_native_material_closure_claim_allowed"] is False
    assert report["native_material_closure_reason"] == "wrapper_local_material_overrides_present"
```

- [ ] **Step 2: Run the focused test**

Run:

```bash
python -m pytest tests/labutopia_poc/test_material_closure_contract.py::test_package_material_closure_stays_true_with_wrapper_authored_native_blockers -q
```

Expected: PASS if current behavior is preserved. If it fails, stop and inspect because the existing package/native claim split regressed.

- [ ] **Step 3: Commit**

```bash
git add tests/labutopia_poc/test_material_closure_contract.py
git commit -m "test: freeze DryingBox material claim split"
```

## Task 2: Add Native Provenance Fields

**Files:**
- Modify: `standalone_tools/labutopia_poc/build_asset_overlay.py`
- Modify: `tests/labutopia_poc/test_build_asset_overlay.py`
- Modify: `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json`

- [ ] **Step 1: Write manifest field test**

Add this expectation to the existing native material manifest test:

```python
    provenance = material["native_material_provenance"]
    assert provenance["status"] == "blocked_by_wrapper_local_overrides"
    assert provenance["source_native_blocker_surface_count"] == 2
    assert provenance["native_wrapper_override_surface_count"] == 2
    assert provenance["native_claim_blocker_records"] == [
        {
            "source_prim_path": "/World/DryingBox_01/Group/_900_1",
            "runtime_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Group/_900_1",
            "source_binding_status": "empty_authored_binding_in_stage2_source_readback",
            "source_material_binding": None,
            "runtime_material_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/task_indicator_mat",
            "replacement_required_for_full_native_closure": True,
            "blocked_claims": [
                "native_material_closure",
                "full_native_material_closure",
            ],
        },
        {
            "source_prim_path": "/World/DryingBox_01/button",
            "runtime_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/button",
            "source_binding_status": "unbound_in_stage2_source_readback",
            "source_material_binding": None,
            "runtime_material_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/task_button_mat",
            "replacement_required_for_full_native_closure": True,
            "blocked_claims": [
                "native_material_closure",
                "full_native_material_closure",
            ],
        },
    ]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/labutopia_poc/test_build_asset_overlay.py::test_manifest_contains_generic_asset_acceptance_material_closure -q
```

Expected: FAIL with missing `native_material_provenance`.

- [ ] **Step 3: Implement provenance builder**

In `build_asset_overlay.py`, add a helper that derives the object from `DRYING_BOX_WRAPPER_LOCAL_MATERIAL_OVERRIDES` and inject it into `asset_acceptance.material_closure`:

```python
def _drying_box_native_material_provenance() -> dict[str, object]:
    root_path = _drying_box_root_path()
    blocker_records = []
    for relative_path, material in sorted(
        DRYING_BOX_WRAPPER_LOCAL_MATERIAL_OVERRIDES.items()
    ):
        runtime_material_path = f"{root_path}/Looks/{material['material_name']}"
        blocker_records.append(
            {
                "source_prim_path": f"/World/DryingBox_01/{relative_path}",
                "runtime_prim_path": f"{root_path}/{relative_path}",
                "source_binding_status": material["source_binding_status"],
                "source_material_binding": None,
                "runtime_material_path": runtime_material_path,
                "replacement_required_for_full_native_closure": True,
                "blocked_claims": [
                    "native_material_closure",
                    "full_native_material_closure",
                ],
            }
        )
    return {
        "schema_version": 1,
        "status": "blocked_by_wrapper_local_overrides"
        if blocker_records
        else "resolved_source_native",
        "source_native_blocker_surface_count": len(blocker_records),
        "native_wrapper_override_surface_count": len(blocker_records),
        "native_claim_blocker_records": blocker_records,
    }
```

After `derive_material_closure_claims(...)`, set:

```python
material_closure["native_material_provenance"] = (
    _drying_box_native_material_provenance()
)
```

- [ ] **Step 4: Regenerate manifest**

Run:

```bash
python standalone_tools/labutopia_poc/build_asset_overlay.py --drying-box-strategy native_complex --physics-override-output-root saved/diagnostics/native_dryingbox_physics_override_20260629_aluminum_mirror
cp /cpfs/shared/simulation/zhuzihou/dev/_datasets/EBench-Assets-Overlay/labutopia_level1_poc/assets/manifests/labutopia_level1_poc.json configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json
```

Expected: manifest contains `asset_acceptance.material_closure.native_material_provenance`.

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_build_asset_overlay.py tests/labutopia_poc/test_material_closure_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add standalone_tools/labutopia_poc/build_asset_overlay.py tests/labutopia_poc/test_build_asset_overlay.py configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json
git commit -m "feat: record DryingBox native material provenance blockers"
```

## Task 3: Validate Native Provenance Claims

**Files:**
- Modify: `standalone_tools/labutopia_poc/validate_task_package.py`
- Modify: `tests/labutopia_poc/test_validate_task_package.py`

- [ ] **Step 1: Add package validator negative test**

Add a test that mutates a manifest copy so the native claim flags stay false, but `native_material_provenance` is internally inconsistent. Use this mutation:

```python
material = manifest["asset_acceptance"]["material_closure"]
material["native_material_closure_claim_allowed"] = False
material["full_native_material_closure_claim_allowed"] = False
material["native_material_provenance"]["status"] = "blocked_by_wrapper_local_overrides"
material["native_material_provenance"]["source_native_blocker_surface_count"] = 2
material["native_material_provenance"]["native_wrapper_override_surface_count"] = 2
material["native_material_provenance"]["native_claim_blocker_records"] = [
    {
        "source_prim_path": "/World/DryingBox_01/not_the_button",
        "runtime_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/not_the_button",
        "source_binding_status": "unbound_in_stage2_source_readback",
        "source_material_binding": None,
        "runtime_material_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/task_button_mat",
        "replacement_required_for_full_native_closure": True,
        "blocked_claims": [
            "native_material_closure",
            "full_native_material_closure",
        ],
    }
]
```

Expected failure message: `native material provenance blocker mismatch`.

- [ ] **Step 2: Run focused test to verify it fails**

Run:

```bash
python -m pytest tests/labutopia_poc/test_validate_task_package.py -q
```

Expected: FAIL because validator does not yet inspect provenance record count and exact path consistency.

- [ ] **Step 3: Add validator checks**

Inside the material validation block, require:

```python
provenance = material.get("native_material_provenance")
require(isinstance(provenance, dict), f"{manifest_path}: missing native material provenance")
require(provenance.get("status") == "blocked_by_wrapper_local_overrides", f"{manifest_path}: native provenance status mismatch")
require(provenance.get("source_native_blocker_surface_count") == 2, f"{manifest_path}: source-native blocker surface count mismatch")
require(provenance.get("native_wrapper_override_surface_count") == 2, f"{manifest_path}: native wrapper override surface count mismatch")
require(material.get("native_material_closure_claim_allowed") is False, f"{manifest_path}: native material closure overclaim")
require(material.get("full_native_material_closure_claim_allowed") is False, f"{manifest_path}: full native material closure overclaim")
```

Also validate:

```python
blocker_records = provenance.get("native_claim_blocker_records")
require(isinstance(blocker_records, list), f"{manifest_path}: missing native provenance blockers")
require(len(blocker_records) == 2, f"{manifest_path}: native material provenance blocker count mismatch")
expected_blockers = {
    (
        "/World/DryingBox_01/Group/_900_1",
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Group/_900_1",
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/task_indicator_mat",
    ),
    (
        "/World/DryingBox_01/button",
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/button",
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/task_button_mat",
    ),
}
actual_blockers = {
    (
        record.get("source_prim_path"),
        record.get("runtime_prim_path"),
        record.get("runtime_material_path"),
    )
    for record in blocker_records
}
require(actual_blockers == expected_blockers, f"{manifest_path}: native material provenance blocker mismatch")
```

Then validate each blocker record includes `source_binding_status`, `source_material_binding=None`, `replacement_required_for_full_native_closure=True`, and both native blocked claims.

- [ ] **Step 4: Run validator and tests**

Run:

```bash
python standalone_tools/labutopia_poc/validate_task_package.py
python -m pytest tests/labutopia_poc/test_validate_task_package.py -q
```

Expected: validator OK and tests PASS.

- [ ] **Step 5: Commit**

```bash
git add standalone_tools/labutopia_poc/validate_task_package.py tests/labutopia_poc/test_validate_task_package.py
git commit -m "test: validate DryingBox native material provenance"
```

## Task 4: Update Evidence Docs and PM SOP

**Files:**
- Modify: `docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md`
- Modify: `docs/labutopia_lab_poc/evidence_manifests/README.md`
- Modify: `docs/superpowers/plans/2026-06-29-ebench-asset-acceptance-pipeline.md`

- [ ] **Step 1: Document final product-facing wording**

Add wording that says:

```text
DryingBox 的 package material gate 已通过，因为所有 remote material dependency 已本地化、runtime fallback-only surface 为 0，并且 wrapper-local material override 已显式记录。
DryingBox 的 source-native full material closure 仍未通过，因为 `button` 和 `Group/_900_1` 在原生 USD 中没有可恢复的有效 material:binding；我们保留 wrapper-local PreviewSurface 是为了任务可读性，不把它包装成 native claim。
```

- [ ] **Step 2: Run claim-text check**

Run:

```bash
rg -n "package material|source-native|native_material_provenance|full_native_material_closure|wrapper-local" docs/labutopia_lab_poc docs/superpowers/plans/2026-06-29-ebench-asset-acceptance-pipeline.md
```

Expected: docs consistently separate package gate from source-native claim.

- [ ] **Step 3: Commit**

```bash
git add docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md docs/labutopia_lab_poc/evidence_manifests/README.md docs/superpowers/plans/2026-06-29-ebench-asset-acceptance-pipeline.md
git commit -m "docs: explain DryingBox native material provenance boundary"
```

## Task 5: Final Verification

**Files:**
- Verify full package.

- [ ] **Step 1: Run static validator**

Run:

```bash
python standalone_tools/labutopia_poc/validate_task_package.py
```

Expected: `LabUtopia task package validation OK`.

- [ ] **Step 2: Run focused tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_material_closure_contract.py tests/labutopia_poc/test_build_asset_overlay.py tests/labutopia_poc/test_validate_task_package.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full LabUtopia POC tests**

Run:

```bash
python -m pytest tests/labutopia_poc -q
```

Expected: PASS.

- [ ] **Step 4: Run whitespace and status checks**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: no whitespace errors; only intended files changed before commit.

- [ ] **Step 5: Commit final docs if needed**

Only run this commit command if Task 5 created additional uncommitted documentation changes:

```bash
git add docs configs standalone_tools tests
git commit -m "docs: finalize DryingBox native material provenance follow-up"
```
