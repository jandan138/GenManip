# EBench Native DryingBox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the final `level1_open_door` asset path with LabUtopia native complex `DryingBox_01`, preserving native visual/hierarchy/handle while using only additive USD physics overrides needed for Isaac/EBench runtime stability.

**Architecture:** Keep the current P1 `sanitized_surrogate` as a debugging baseline and introduce a separate native gate lane. The native lane must pass asset audit, native-only Isaac smoke, EBench wrapper import, additive physics override, eval readback, documentation evidence, and Lift2 preflight in sequence.

**Tech Stack:** Python 3.10, USD Python APIs (`pxr.Usd`, `pxr.UsdPhysics`, `pxr.UsdGeom`), Isaac Sim 4.1 runtime, GenManip/EBench task configs, pytest, static HTML docs.

---

## Multi-Agent Review Summary

Three independent reviews agreed on the boundary:

| Perspective | Conclusion |
| --- | --- |
| USD/PhysX | Current `DryingBox` implementation is `sanitized_surrogate`: `source_payload_used=false`, hand-written `Cube` geometry for `body_link`, `door_link`, and `handle`, plus `BaseFixedJoint`, `RevoluteJoint`, and `HandleFixedJoint`. It is not native complex `DryingBox_01`. |
| EBench integration | Current object map, render contract, validator, and diagnostics are tuned for the surrogate. Native complex `DryingBox` requires new gates for object map, joint contract, physics stability, and render validation. |
| PM/docs | Docs must not imply the surrogate equals native. The correct story is P1 surrogate baseline first, then P2 native visual/hierarchy/handle plus additive physics override. |

Known native risks to verify before any fix:

- `ArticulationRootAPI` placement and root `xformOp:scale`, suspected around `[0.001, 0.001, 0.001]`.
- Joint `body0/body1` targets, especially any target that resolves to a prim without `RigidBodyAPI`.
- Native `RevoluteJoint` axis/frame, suspected different from surrogate `axis=Z`.
- Zero or invalid `mass`, `diagonalInertia`, `centerOfMass`, and `principalAxes`.
- Native button `PrismaticJoint` adding an extra DOF or changing DOF order.
- Nested native handle path, likely under `/handle/mesh`, and how GenManip should expose it as the task handle.
- Fixed-base behavior: surrogate has explicit `BaseFixedJoint`; native must not drift.

## File Map

| File | Responsibility |
| --- | --- |
| `standalone_tools/labutopia_poc/audit_native_dryingbox.py` | New read-only USD audit tool for the original LabUtopia `DryingBox_01`. |
| `standalone_tools/labutopia_poc/run_native_dryingbox_smoke.py` | New Isaac smoke tool that loads native `DryingBox` without EBench wrapper and records joint/runtime state. |
| `standalone_tools/labutopia_poc/build_asset_overlay.py` | Add a native strategy beside the existing `sanitized_surrogate`; do not delete the surrogate until native gates pass. |
| `standalone_tools/labutopia_poc/validate_task_package.py` | Split validator into surrogate baseline checks and native complex checks. |
| `standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py` | Add native strategy metadata, native audit linkage, and non-color-only render validation. |
| `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json` | Record native strategy metadata, audit artifact path, and native wrapper contract. |
| `configs/tasks/ebench/labutopia_lab_poc/common/task_semantics.yml` | Confirm `open_door` handle and articulation part mapping for native path. |
| `configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_open_door.yml` | Confirm metric `joint_name`, target positions, and handle part path against native DOF readback. |
| `configs/tasks/ebench/labutopia_lab_poc/lift2_candidate/level1_open_door.yml` | Mirror the validated native object contract for Lift2 candidate only after Franka native gate passes. |
| `tests/labutopia_poc/test_native_dryingbox_audit.py` | New tests for audit output schema and known native risk capture. |
| `tests/labutopia_poc/test_build_asset_overlay.py` | Add expectations for native strategy wrapper while keeping surrogate tests. |
| `tests/labutopia_poc/test_validate_task_package.py` | Add native validator tests for root scale, body rels, mass/inertia, DOF names, and handle mapping. |
| `tests/labutopia_poc/test_render_diagnostics_contract.py` | Add native diagnostics contract: audit hash, native strategy, joint readback, and claim boundary. |
| `docs/records/evidence/2026-06-24-usd-articulation-dryingbox-tutorial/index.html` | Keep PM teaching page updated with exact native evidence and claim boundaries. |
| `docs/records/2026-06-22-labutopia-ebench-weekly-report.md` | Keep weekly report aligned with native gate status. |

## Task 1: Native Asset Audit

**Files:**
- Create: `standalone_tools/labutopia_poc/audit_native_dryingbox.py`
- Create: `tests/labutopia_poc/test_native_dryingbox_audit.py`
- Output artifact: `saved/diagnostics/native_dryingbox_audit_<timestamp>/audit.json`

- [ ] **Step 1: Write the audit schema test**

```python
def test_native_dryingbox_audit_schema(tmp_path):
    from standalone_tools.labutopia_poc.audit_native_dryingbox import audit_native_dryingbox

    report = audit_native_dryingbox(
        labutopia_root="/cpfs/shared/simulation/zhuzihou/dev/LabUtopia",
        source_prim_path="/World/DryingBox_01",
    )

    assert report["source_prim_path"] == "/World/DryingBox_01"
    assert "stage_path" in report
    assert "stage_sha256" in report
    assert "articulation_roots" in report
    assert "rigid_bodies" in report
    assert "joints" in report
    assert "handle_candidates" in report
    assert "risk_flags" in report
```

- [ ] **Step 2: Run test and verify it fails before implementation**

Run: `python3 -m pytest tests/labutopia_poc/test_native_dryingbox_audit.py -q`

Expected: FAIL because `standalone_tools.labutopia_poc.audit_native_dryingbox` does not exist.

- [ ] **Step 3: Implement read-only USD audit**

Implement `audit_native_dryingbox()` using `pxr.Usd`, `pxr.UsdPhysics`, and `pxr.UsdGeom`. The report must include:

- source stage path and SHA256.
- every prim under `/World/DryingBox_01` with path, type, applied API schemas, xformOps, visibility.
- every prim with `RigidBodyAPI`, including `MassAPI` values.
- every joint with type, axis, limits, local frame, `physics:body0`, `physics:body1`, and target validity.
- handle candidates containing `handle` in the path.
- risk flags for non-identity root scale, zero mass, zero inertia, invalid COM, invalid principal axes, invalid joint body target, unexpected joint type, and multiple active DOFs.

- [ ] **Step 4: Run audit and save artifact**

Run:

```bash
python3 standalone_tools/labutopia_poc/audit_native_dryingbox.py \
  --labutopia-root /cpfs/shared/simulation/zhuzihou/dev/LabUtopia \
  --output-root saved/diagnostics/native_dryingbox_audit_$(date -u +%Y%m%d_%H%M%S)
```

Expected: exit `0`, writes `audit.json`, and prints the output path.

- [ ] **Step 5: Commit**

```bash
git add standalone_tools/labutopia_poc/audit_native_dryingbox.py tests/labutopia_poc/test_native_dryingbox_audit.py
git commit -m "test: audit native DryingBox asset"
```

## Task 2: Native-Only Isaac Smoke

**Files:**
- Create: `standalone_tools/labutopia_poc/run_native_dryingbox_smoke.py`
- Create: `tests/labutopia_poc/test_native_dryingbox_smoke_contract.py`
- Output artifact: `saved/diagnostics/native_dryingbox_smoke_<timestamp>/smoke.json`

- [ ] **Step 1: Write smoke output contract test**

```python
def test_native_dryingbox_smoke_report_contract():
    required_keys = {
        "stage_path",
        "source_prim_path",
        "joint_names",
        "initial_joint_positions",
        "post_step_joint_positions",
        "root_pose_finite",
        "handle_pose_finite",
        "runtime_physics_stable",
        "physx_warnings",
    }
    sample = {
        "stage_path": "saved/diagnostics/native_dryingbox_smoke_x/native_dryingbox.usda",
        "source_prim_path": "/World/DryingBox_01",
        "joint_names": ["RevoluteJoint"],
        "initial_joint_positions": [0.0],
        "post_step_joint_positions": [0.0],
        "root_pose_finite": True,
        "handle_pose_finite": True,
        "runtime_physics_stable": True,
        "physx_warnings": [],
    }
    assert required_keys.issubset(sample)
```

- [ ] **Step 2: Implement smoke runner**

Use the same conda environment as current testing:

`/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310`

The tool must:

- create a minimal stage containing native `DryingBox_01`;
- run Isaac for 60-120 physics steps;
- read articulation joint names and positions;
- read root and handle poses;
- capture PhysX warnings;
- write `smoke.json`;
- keep EBench/Franka out of this stage.

- [ ] **Step 3: Run native-only smoke**

Run:

```bash
conda run -p /cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310 \
  python standalone_tools/labutopia_poc/run_native_dryingbox_smoke.py \
  --labutopia-root /cpfs/shared/simulation/zhuzihou/dev/LabUtopia \
  --output-root saved/diagnostics/native_dryingbox_smoke_$(date -u +%Y%m%d_%H%M%S)
```

Expected: exit `0` only when all reported positions are finite and `runtime_physics_stable=true`. If it exits nonzero, preserve the artifact and do not continue to Task 3.

- [ ] **Step 4: Commit**

```bash
git add standalone_tools/labutopia_poc/run_native_dryingbox_smoke.py tests/labutopia_poc/test_native_dryingbox_smoke_contract.py
git commit -m "test: smoke native DryingBox in Isaac"
```

## Task 3: Native EBench Wrapper Strategy

**Files:**
- Modify: `standalone_tools/labutopia_poc/build_asset_overlay.py`
- Modify: `tests/labutopia_poc/test_build_asset_overlay.py`
- Modify: `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json`

- [ ] **Step 1: Add test for native strategy metadata**

The generated manifest must contain:

```json
{
  "drying_box_runtime_asset": {
    "strategy": "native_complex_with_additive_physics_override",
    "source_payload_used": true,
    "source_prim_path": "/World/DryingBox_01",
    "wrapper_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
    "handle_policy": "nested_native_handle",
    "surrogate_kept_for_debug_baseline": true
  }
}
```

- [ ] **Step 2: Implement separate native strategy**

Add a switch such as `--drying-box-strategy native_complex` to `build_asset_overlay.py`. The native path must:

- payload/reference `@scene.usd@</World/DryingBox_01>`;
- keep wrapper path `/World/labutopia_level1_poc/obj_obj_DryingBox_01`;
- keep a nested handle path or explicit verified native handle part;
- write native strategy metadata;
- keep the existing surrogate builder available for regression comparison.

- [ ] **Step 3: Regenerate overlay with native strategy**

Run:

```bash
python3 standalone_tools/labutopia_poc/build_asset_overlay.py --drying-box-strategy native_complex
python3 standalone_tools/labutopia_poc/validate_task_package.py
```

Expected: validator initially fails until Task 4 adds native validation rules. Preserve the generated USD for inspection.

- [ ] **Step 4: Commit**

```bash
git add standalone_tools/labutopia_poc/build_asset_overlay.py tests/labutopia_poc/test_build_asset_overlay.py configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json
git commit -m "feat: add native DryingBox overlay strategy"
```

## Task 4: Additive Physics Override And Native Validator

**Files:**
- Modify: `standalone_tools/labutopia_poc/build_asset_overlay.py`
- Modify: `standalone_tools/labutopia_poc/validate_task_package.py`
- Modify: `tests/labutopia_poc/test_validate_task_package.py`
- Modify: `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json`
- Modify: `configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_open_door.yml`

- [ ] **Step 1: Write failing validator tests**

Tests must assert the native wrapper:

- preserves native payload;
- has `ArticulationRootAPI` on the correct root;
- does not leave invalid joint `body0/body1` targets;
- has finite positive mass and nonzero inertia for active rigid bodies;
- has finite `centerOfMass` and valid `principalAxes`;
- binds `open_door` metric to the actual native `RevoluteJoint` DOF name;
- maps handle to the verified nested native path;
- records whether button `PrismaticJoint` is isolated or intentionally ignored by metric.

- [ ] **Step 2: Implement additive overrides**

Implement only additive USD overrides on native prims:

- root scale/unit fix or wrapper transform policy;
- finite mass/inertia/COM/principal axes;
- valid joint body targets;
- fixed-base relationship if native root drifts;
- reset target `[0.0]` for the door joint;
- DOF filtering or metric binding for non-door joints.

- [ ] **Step 3: Run validator**

Run:

```bash
python3 standalone_tools/labutopia_poc/validate_task_package.py
python3 -m pytest tests/labutopia_poc/test_validate_task_package.py -q
```

Expected: both commands exit `0`.

- [ ] **Step 4: Commit**

```bash
git add standalone_tools/labutopia_poc/build_asset_overlay.py standalone_tools/labutopia_poc/validate_task_package.py tests/labutopia_poc/test_validate_task_package.py configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_open_door.yml
git commit -m "feat: validate native DryingBox physics overrides"
```

## Task 5: Native open_door Eval Readback

**Status, 2026-06-24 UTC:** Franka POC native gate passed for `level1_open_door`.
The native LabUtopia `DryingBox_01` now loads through the EBench path with native
visual hierarchy preserved, additive physics overrides applied, stable runtime
readback, and a visible task target in `camera2`. This is still not an official
Lift2 baseline claim; `official_baseline_evaluable` intentionally remains
`false` until Task 7 runs the official baseline lane.

Final evidence chain:

| Evidence | Artifact | Result |
| --- | --- | --- |
| Native asset audit | `saved/diagnostics/native_dryingbox_audit_20260624_091136/audit.json` | Captures native topology and known USD/PhysX risk flags before runtime fixes. |
| Native-only Isaac smoke | `saved/diagnostics/native_dryingbox_smoke_20260624_091152/smoke.json` | `runtime_physics_stable=true`, native `DryingBox_01` and handle load without EBench wrapper. |
| EBench eval readback | `saved/diagnostics/native_dryingbox_open_door_eval_explicit_20260624_093156/diagnostics.json` | `boundary_classification=readback_visible`, `native_complex_dryingbox_ready=true`, `runtime_physics_stable=true`, `task_render_accepted=true`, `official_baseline_evaluable=false`. |

Key implementation notes:

- Preserve native root unit scale `0.001`; forcing identity scale made child
  part transforms explode outside the camera workspace.
- Use the native `RevoluteJoint` as the open-door target and ignore the native
  button `PrismaticJoint` for this metric, so the extra native DOF does not
  break the door-state check.
- Use native scene readback and projected task-part evidence when color masks
  are too brittle for complex source assets, but require local PNG evidence
  around the projected task part before accepting the fallback. The local PNG
  evidence must match the object's RGB contract mask, so unrelated texture at
  the projected point cannot pass as `DryingBox` or handle evidence.
- The final formal `camera2` is a front-side view from `+Y`, so the orange
  handle is visible instead of hidden on the far side of the box.

**Files:**
- Modify: `standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py`
- Modify: `tests/labutopia_poc/test_render_diagnostics_contract.py`
- Output artifact: `saved/diagnostics/native_dryingbox_open_door_eval_<timestamp>/diagnostics.json`

- [x] **Step 1: Update diagnostics contract**

Diagnostics must include these fields. The SHA256 values below are format examples; the implementation must replace them with the actual `audit.json` and `smoke.json` SHA256 values produced in Tasks 1 and 2.

```json
{
  "drying_box_strategy": "native_complex_with_additive_physics_override",
  "native_asset_audit_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "native_smoke_sha256": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
  "native_complex_dryingbox_ready": true,
  "runtime_physics_stable": true,
  "task_render_accepted": true,
  "official_baseline_evaluable": false
}
```

- [x] **Step 2: Adjust render validation**

Stop relying only on surrogate-specific color masks. Native path can use bbox, segmentation, object map, visible area, handle part pose, and optional minimal material override.

- [x] **Step 3: Run open_door eval readback**

Run:

```bash
conda run -p /cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310 \
  python standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py \
  --task level1_open_door \
  --output-root saved/diagnostics/native_dryingbox_open_door_eval_$(date -u +%Y%m%d_%H%M%S)
```

Expected: `boundary_classification=readback_visible`, `runtime_physics_stable=true`, `native_complex_dryingbox_ready=true`, and `task_render_accepted=true`.

- [ ] **Step 4: Commit**

```bash
git add standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py tests/labutopia_poc/test_render_diagnostics_contract.py
git commit -m "test: capture native DryingBox eval readback"
```

## Task 6: Documentation Evidence Update

**Files:**
- Modify: `docs/records/evidence/2026-06-24-usd-articulation-dryingbox-tutorial/index.html`
- Modify: `docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html`
- Modify: `docs/records/2026-06-22-labutopia-ebench-weekly-report.md`

- [ ] **Step 1: Add native evidence section**

Add side-by-side evidence:

- old failed JPG;
- P1 surrogate baseline PNG;
- P2 native complex DryingBox eval readback PNG;
- audit JSON path/hash;
- smoke JSON path/hash;
- diagnostics JSON path/hash.

- [ ] **Step 2: Update claim boundary**

Only after Task 5 passes, update:

- `native_complex_dryingbox_ready=true`;
- keep `official_baseline_evaluable=false`;
- state that native visual/hierarchy/handle are preserved with additive physics override.

- [ ] **Step 3: Browser visual review**

Run a local static server from `docs` and review desktop/tablet/mobile. Required checks:

- no broken images;
- no horizontal overflow;
- native gate section is readable;
- weekly report links to tutorial;
- tutorial explains surrogate vs native without contradiction.

- [ ] **Step 4: Commit**

```bash
git add docs/records/evidence/2026-06-24-usd-articulation-dryingbox-tutorial/index.html docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html docs/records/2026-06-22-labutopia-ebench-weekly-report.md
git commit -m "docs: record native DryingBox evidence"
```

## Task 7: Lift2 And Official Baseline Gate

**Files:**
- Modify: `configs/tasks/ebench/labutopia_lab_poc/lift2_candidate/level1_open_door.yml`
- Modify: `genmanip/core/evaluator/labutopia_assets.py`
- Create or modify: `tests/labutopia_poc/test_labutopia_composite_assets.py`
- Create or modify: `standalone_tools/labutopia_poc/run_lift2_smoke.py`
- Create or modify: `standalone_tools/labutopia_poc/discover_official_lift2_baseline.py`

- [ ] **Step 1: Composite asset preflight**

Verify the candidate root contains:

- LabUtopia scene overlay;
- `robot_usds/lift2/robot.usd`;
- `miscs/curobo/R5a/r5a_left_arm.yml`;
- native DryingBox wrapper assets and diagnostics metadata.

- [ ] **Step 2: Lift2 dry smoke**

Run `ebench/labutopia_lab_poc/lift2_candidate` on an isolated port. Expected: `complete`, `3/3` result files, and `official_baseline_execution=false`.

- [ ] **Step 3: Official runner discovery**

Locate official EBench/OpenPI/Lift2 runner files and record:

- file paths;
- SHA256 hashes;
- command entrypoints;
- required environment variables;
- whether policy execution was run.

- [ ] **Step 4: Commit**

```bash
git add configs/tasks/ebench/labutopia_lab_poc/lift2_candidate/level1_open_door.yml genmanip/core/evaluator/labutopia_assets.py tests/labutopia_poc/test_labutopia_composite_assets.py standalone_tools/labutopia_poc/run_lift2_smoke.py standalone_tools/labutopia_poc/discover_official_lift2_baseline.py
git commit -m "test: gate native DryingBox for Lift2"
```

## Verification Commands

Run these before changing PM-facing claims:

```bash
python3 -m pytest tests/labutopia_poc -q
python3 standalone_tools/labutopia_poc/validate_task_package.py
python3 standalone_tools/labutopia_poc/audit_native_dryingbox.py --labutopia-root /cpfs/shared/simulation/zhuzihou/dev/LabUtopia --output-root saved/diagnostics/native_dryingbox_audit_manual
```

Run Isaac-dependent checks inside:

`/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310`

Required final claim boundary:

```text
task_render_accepted=true
native_complex_dryingbox_ready=true
official_baseline_evaluable=false
```

Only after Lift2 official gates pass may `official_baseline_evaluable` be reconsidered.
