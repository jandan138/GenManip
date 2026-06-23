# LabUtopia EBench Render/Layout Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the failed LabUtopia render evidence with reproducible eval-path frames that show task-relevant reset layouts for `level1_pick`, `level1_place`, and `level1_open_door`.

**Architecture:** Treat render/layout closure as a P0 gate before Lift2 baseline work. First instrument the normal eval camera path, then make task reset layout explicit, then regenerate visual evidence through a reproducible script and independent visual review. Keep all runs isolated by worktree, port, run_id, and result directory to avoid confusion with EOS or another engineer's work.

**Tech Stack:** Python 3.10, Isaac Sim 4.1 conda env, GenManip evaluator, EBench server/client, Pillow-based image stats, pytest, static GitHub Pages docs.

**Current status update, 2026-06-24 00:30 UTC:** P0 black-frame readback is resolved for all three Franka POC tasks. P1 static asset/layout normalization is partially resolved: required objects are in the Franka workspace and the DryingBox handle is a nested part again. Task-level visibility isolation now makes `level1_pick` readable and `level1_place` basically readable for PM diagnosis. The `open_door` runtime articulation has been stabilized with a sanitized DryingBox surrogate, aligned hinge, target replay, handle-side correction, duplicate marker removal, and a formal front-camera config; the latest formal retake starts at the expected closed joint target and shows the DryingBox frame, door panel, and one orange handle/action point. Independent image-only QA rates the old-vs-current PM comparison PASS, with open_door PASS/WARN as diagnostic evidence. Formal task render acceptance remains false because diagnostics still report `render_validation_not_passed`.

---

## Claim Boundary

Allowed before this plan is complete:

```text
LabUtopia Franka POC server/client smoke runs complete and result files are written.
```

Allowed only after this plan is complete:

```text
The three Franka POC tasks have reproducible eval-path reset render evidence that passes visual QA.
```

Still not allowed after this plan:

```text
official Lift2 baseline score
leaderboard comparability
official policy quality claim
```

## File Structure

- Create `standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py`
  - Runs one controlled LabUtopia POC reset/camera capture in the Isaac environment.
  - Writes camera poses, render product paths, RGB stats, object pose/bbox diagnostics, and PNG frames under a unique output directory.
- Create `tests/labutopia_poc/test_render_diagnostics_contract.py`
  - Tests the diagnostics JSON schema and visual QA status logic without launching Isaac.
- Modify `configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_pick.yml`
  - Add render/layout readiness metadata and later explicit placement once diagnostics proves the coordinate contract.
- Modify `configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_place.yml`
  - Add render/layout readiness metadata and later explicit beaker/platform placement.
- Modify `configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_open_door.yml`
  - Add render/layout readiness metadata and later explicit drying-box placement plus task-specific camera requirements.
- Modify or create a task-specific camera config under `configs/cameras/`
  - Preserve the original LabUtopia `open_door` view or an equivalent EBench-safe view.
- Update `docs/labutopia_lab_poc/render_visual_investigation_20260623.md`
  - Append diagnostic outputs and visual review verdicts.
- Update weekly Markdown and HTML reports only after evidence state changes.

## P0: Camera Black-Frame Root Cause

Current status as of 2026-06-23:

```text
Diagnostic helper and runtime capture script exist.
tests/labutopia_poc/test_render_diagnostics_contract.py: 2 passed
LabUtopia POC regression tests: 34 passed, 1 skipped
level1_pick: readback_black_before_recorder
level1_place: readback_black_before_recorder
level1_open_door: readback_black_before_recorder
after P0a/P0b:
level1_pick: readback_visible, low-texture frame, not task accepted
level1_place: readback_visible, low-texture frame, not task accepted
level1_open_door: not revalidated; remains blocked by asset/layout work
after P1 asset/layout normalization:
level1_pick: readback_visible, target visible after task-level hiding, pending formal QA
level1_place: readback_visible, beaker/target relation basically readable after task-level hiding, pending formal QA
level1_open_door: readback_visible, runtime stable after sanitized surrogate and target replay, visual QA WARN/not accepted
```

Recorder writing is now ruled out as the primary black-frame source. P0a/P0b source fixes remove the pure-black readback failure. Task-level visibility isolation improves pick/place screenshots. The open-door physics blocker has been reduced to a visual framing blocker; task render acceptance remains blocked until formal visual QA passes.

**Files:**
- Create: `standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py`
- Create: `tests/labutopia_poc/test_render_diagnostics_contract.py`

- [x] **Step 1: Write diagnostics contract test**

Create `tests/labutopia_poc/test_render_diagnostics_contract.py` with this contract:

```python
from standalone_tools.labutopia_poc.capture_eval_render_diagnostics import (
    build_camera_frame_stats,
    classify_frame_stats,
)


def test_classify_black_frame_as_failed():
    stats = build_camera_frame_stats(
        camera_name="camera2",
        frame_path="camera2/00000.png",
        width=256,
        height=256,
        channel_min=[0, 0, 0],
        channel_max=[0, 0, 0],
        channel_mean=[0.0, 0.0, 0.0],
        nonzero_pixels=0,
    )

    assert classify_frame_stats(stats) == "black_frame_fail"


def test_classify_visible_frame_as_pass():
    stats = build_camera_frame_stats(
        camera_name="camera2",
        frame_path="camera2/00000.png",
        width=256,
        height=256,
        channel_min=[0, 1, 0],
        channel_max=[180, 190, 170],
        channel_mean=[72.0, 80.0, 69.0],
        nonzero_pixels=42000,
    )

    assert classify_frame_stats(stats) == "visible_frame"
```

- [x] **Step 2: Run the test and confirm RED**

Run:

```bash
python -m pytest tests/labutopia_poc/test_render_diagnostics_contract.py -q
```

Expected:

```text
ImportError or missing function failure
```

- [x] **Step 3: Implement the pure-Python diagnostics helpers**

Create `standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py` with:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class CameraFrameStats:
    camera_name: str
    frame_path: str
    width: int
    height: int
    channel_min: list[int]
    channel_max: list[int]
    channel_mean: list[float]
    nonzero_pixels: int


def build_camera_frame_stats(
    *,
    camera_name: str,
    frame_path: str,
    width: int,
    height: int,
    channel_min: list[int],
    channel_max: list[int],
    channel_mean: list[float],
    nonzero_pixels: int,
) -> dict[str, object]:
    return asdict(
        CameraFrameStats(
            camera_name=camera_name,
            frame_path=frame_path,
            width=width,
            height=height,
            channel_min=channel_min,
            channel_max=channel_max,
            channel_mean=channel_mean,
            nonzero_pixels=nonzero_pixels,
        )
    )


def classify_frame_stats(stats: dict[str, object]) -> Literal["black_frame_fail", "visible_frame"]:
    channel_max = stats["channel_max"]
    nonzero_pixels = int(stats["nonzero_pixels"])
    if not isinstance(channel_max, list):
        raise TypeError("channel_max must be a list")
    if max(int(value) for value in channel_max) == 0 or nonzero_pixels == 0:
        return "black_frame_fail"
    return "visible_frame"
```

- [x] **Step 4: Run the test and confirm GREEN**

Run:

```bash
python -m pytest tests/labutopia_poc/test_render_diagnostics_contract.py -q
```

Expected:

```text
2 passed
```

- [x] **Step 5: Add Isaac runtime capture mode**

Extend `capture_eval_render_diagnostics.py` with an `argparse` CLI that accepts:

```text
--config ebench/labutopia_lab_poc/franka_poc
--task level1_pick
--run-id labutopia_render_diag_YYYYMMDD_HHMMSS
--port 18091
--output-dir saved/diagnostics/labutopia_render_diag_YYYYMMDD_HHMMSS
--save-reset-frame
```

The CLI must write:

```text
diagnostics.json
readback_after_get_eval_camera_data/camera2/00000.png
recorder_png/camera2/00000.png
```

`diagnostics.json` must include:

```json
{
  "run_id": "labutopia_render_diag_YYYYMMDD_HHMMSS",
  "task": "level1_pick",
  "camera_frames": [],
  "camera_poses": {},
  "render_products": {},
  "render_product_binding": {},
  "object_world_poses": {},
  "object_extents": {},
  "projected_object_centers": {},
  "articulation_state": {},
  "claim_boundary": {
    "task_render_accepted": false,
    "official_baseline_evaluable": false
  }
}
```

- [x] **Step 6: Run isolated camera diagnostics**

Use the conda Python:

```bash
/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310/bin/python \
  standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py \
  --config ebench/labutopia_lab_poc/franka_poc \
  --task level1_pick \
  --run-id labutopia_render_diag_$(date +%Y%m%d_%H%M%S) \
  --port 18091 \
  --output-dir saved/diagnostics/labutopia_render_diag_pick \
  --save-reset-frame
```

Expected:

```text
diagnostics.json written
camera2 frame stats recorded for the normal eval path
camera prim path, render product path, world pose, RGB stats, and nonzero count recorded immediately after get_eval_camera_data()
no process remains on port 18091 after completion
```

- [x] **Step 7: Repeat diagnostics for all tasks**

Run the same command for:

```text
level1_pick
level1_place
level1_open_door
```

Expected:

```text
Each task has camera frame stats and object pose diagnostics.
If camera2 is black, diagnostics classify whether the boundary is before or after recorder writing.
Normal eval removes camera1; camera1 capture, object extents, and object projections remain follow-up instrumentation.
```

Observed:

```text
level1_pick: camera2 readback and recorder PNG are black, channel_max=[0,0,0], nonzero=0
level1_place: camera2 readback and recorder PNG are black, channel_max=[0,0,0], nonzero=0
level1_open_door: camera2 readback and recorder PNG are black, channel_max=[0,0,0], nonzero=0
```

Artifacts:

```text
saved/diagnostics/labutopia_render_diag_pick_20260623_070712/level1_pick/diagnostics.json
saved/diagnostics/labutopia_render_diag_level1_place_20260623_070855/level1_place/diagnostics.json
saved/diagnostics/labutopia_render_diag_level1_open_door_20260623_070933/level1_open_door/diagnostics.json
docs/labutopia_lab_poc/evidence_manifests/render_diagnostics_20260623.json
```

### P0 Follow-Up: Source Fix Order

Do the next source fixes in this order and keep one variable per run:

1. Camera axes/pose: done for controlled pick/place P0 diagnostics.
   - `configs/cameras/labutopia_franka_poc.yml`
   - `genmanip/utils/usd_utils/camera_utils.py`
   - `genmanip/utils/standalone/camera_pose_utils.py`
   - `camera_axes: usd` is honored for GenManip-style/free cameras.
   - `camera2` retargeted to `[9.6, 0.0, 2.5]`.
   - Evidence:

```text
saved/diagnostics/labutopia_p0a_p0b_pick_20260623_155645/level1_pick/diagnostics.json
saved/diagnostics/labutopia_p0a_p0b_place_20260623_155831/level1_place/diagnostics.json
```

2. Deterministic lighting: done for the runtime overlay.
   - `standalone_tools/labutopia_poc/build_asset_overlay.py`
   - `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json`
   - `standalone_tools/labutopia_poc/validate_task_package.py`
   - Runtime wrapper authors `/World/labutopia_level1_poc/DeterministicDomeLight` with intensity `1000`.
   - Acceptance: static validation confirms the light exists and pick/place eval readback is no longer pure black.
   - Evidence:

```text
docs/labutopia_lab_poc/evidence_manifests/render_p0a_p0b_20260623.json
python standalone_tools/labutopia_poc/validate_task_package.py -> OK
```

3. Asset/layout normalization:
   - Static layer is partially done: required objects are in the robot workspace and the nested handle preserves the DryingBox parent transform.
   - Task-level visibility isolation is done for POC diagnosis: pick hides beaker/target/DryingBox, place hides bottle/DryingBox, open_door hides bottle/beaker/target.
   - Runtime physics is now diagnosable for the POC `open_door` diagnostic after the sanitized DryingBox surrogate, aligned hinge, and target replay; the closed-start joint now matches the expected `0.0`.
   - Remaining acceptance gap: `open_door` now shows the DryingBox frame, door panel, and one orange handle/action point, but must not be upgraded beyond diagnostic evidence until `render_validation` and formal visual QA pass.
4. Eval-path regeneration:
   - Three P1 diagnostics now produce non-black evaluator readback frames.
   - Current P1 visibility images make pick readable and place basically readable, while the latest open_door single-handle front-camera image is PM-usable diagnostic evidence but still not accepted for baseline claims.

## P1: Reset-Time Task Layout Closure

Current P1 status:

```text
static_usd_ok: true
camera_readback_visible: true for level1_pick/place/open_door
task_visibility_isolated: true for level1_pick/place/open_door
pick_place_pm_readable: true, pending formal visual QA
runtime_physics_stable: true for latest open_door diagnostic, joint_positions = [0.0], expected_joint_positions = [0.0]
open_door_visual_qa: PASS/WARN diagnostic/not accepted, DryingBox frame + door panel + single handle visible, render_validation_not_passed
task_render_accepted: false
official_baseline_evaluable: false
```

Evidence:

```text
saved/diagnostics/labutopia_p1_visibility_pick_20260623_175050/diagnostics.json
saved/diagnostics/labutopia_p1_visibility_place_20260623_175232/diagnostics.json
saved/diagnostics/labutopia_p1_open_door_single_handle_formal_20260624_0001/diagnostics.json
docs/labutopia_lab_poc/evidence_manifests/render_p1_asset_layout_20260623.json
```

Immediate next order:

1. Keep static validation so malformed DryingBox USD/PhysX topology fails before runtime.
2. Keep the sanitized DryingBox asset and runtime sanity gate in place; do not regress to source DryingBox physics.
3. Keep the runtime sanity gate for finite articulation joint positions and finite object transforms.
4. Run formal visual QA for pick/place; keep `task_render_accepted=false` until signed off.
5. Keep the formal single-handle front-camera open_door image as PM-facing diagnostic evidence only; rerun browser display QA and formal task visual QA, and keep `task_render_accepted=false` until `render_validation` passes.

**Files:**
- Modify: `configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_pick.yml`
- Modify: `configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_place.yml`
- Modify: `configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_open_door.yml`
- Modify: `configs/cameras/labutopia_franka_poc.yml` or create task-specific camera configs
- Modify: `genmanip/utils/loader/preprocess_rules.py`
- Test: `tests/labutopia_poc/test_validate_task_package.py`
- Test: `tests/labutopia_poc/test_scene_preprocess_rules.py`

- [ ] **Step 1: Add static validation for render-layout readiness**

Extend `standalone_tools/labutopia_poc/validate_task_package.py` so each Franka POC task must declare a render/layout readiness block:

```yaml
labutopia_render_validation:
  required_visible_objects:
    - obj_conical_bottle02
  required_camera_names:
    - camera1
    - camera2
  task_visual_goal: pick_target_visible
```

Per-task required objects:

```text
level1_pick: obj_conical_bottle02
level1_place: obj_beaker2, obj_target_plat
level1_open_door: obj_DryingBox_01, obj_DryingBox_01_handle
```

Also require each task to declare the non-task objects hidden for diagnostic readability:

```text
level1_pick hidden: obj_beaker2, obj_target_plat, obj_DryingBox_01
level1_place hidden: obj_conical_bottle02, obj_DryingBox_01
level1_open_door hidden: obj_conical_bottle02, obj_beaker2, obj_target_plat
```

- [ ] **Step 2: Add failing tests for missing render-validation block**

Update `tests/labutopia_poc/test_validate_task_package.py` with assertions that every Franka POC YAML includes the required block and object list.

Run:

```bash
python -m pytest tests/labutopia_poc/test_validate_task_package.py -q
```

Expected:

```text
Failure showing missing labutopia_render_validation
```

- [ ] **Step 3: Add render-validation metadata to the three task YAMLs**

Add to `level1_pick.yml`:

```yaml
    labutopia_render_validation:
      required_visible_objects:
        - obj_conical_bottle02
      required_camera_names:
        - camera1
        - camera2
      task_visual_goal: pick_target_visible
```

Add to `level1_place.yml`:

```yaml
    labutopia_render_validation:
      required_visible_objects:
        - obj_beaker2
        - obj_target_plat
      required_camera_names:
        - camera1
        - camera2
      task_visual_goal: beaker_and_target_visible
```

Add to `level1_open_door.yml`:

```yaml
    labutopia_render_validation:
      required_visible_objects:
        - obj_DryingBox_01
        - obj_DryingBox_01_handle
      required_camera_names:
        - camera1
        - camera2
      task_visual_goal: door_and_handle_visible
```

- [ ] **Step 4: Apply source fixes from P0 diagnostics**

Use the P0 diagnostics to handle these outcomes in order:

```text
Outcome A: camera axes/pose likely wrong -> add camera_axes support and retest readback.
Outcome B: no deterministic lights -> add runtime overlay/task lighting and retest readback.
Outcome C: asset/layout invalid -> normalize required objects and nested parts before camera tuning.
Outcome D: task-specific view needed -> create task-specific camera config for open_door.
```

Do not change all variables at once.

- [x] **Step 4a: Add task-level visibility isolation**

Implemented `set_object_active` preprocessing so the runtime can hide non-task objects before eval readback. Targeted tests:

```text
python -m pytest tests/labutopia_poc/test_scene_preprocess_rules.py -q
2 passed
python -m pytest tests/labutopia_poc/test_validate_task_package.py::test_franka_tasks_hide_non_task_objects_for_evidence_readability -q
1 passed
python standalone_tools/labutopia_poc/validate_task_package.py
LabUtopia task package validation OK
```

Latest diagnostic outcome:

```text
level1_pick: readback_visible, PM-readable target bottle
level1_place: readback_visible, beaker and target platform visible together
level1_open_door: readback_visible, runtime_stable, visual_QA_WARN_NOT_ACCEPTED
```

- [ ] **Step 4b: Add DryingBox articulation topology validation**

Extend static validation to fail on:

```text
non-identity articulation root scale
duplicate rigid-link basenames such as mesh
non-finite physics:centerOfMass
zero or invalid physics:principalAxes
joint body targets that are not PhysicsRigidBodyAPI prims
unexpected extra DOFs if open-door should only expose the door revolute joint
```

This step must go red on the current overlay before building a sanitized DryingBox runtime asset.

- [ ] **Step 5: Run package validation**

Run:

```bash
python standalone_tools/labutopia_poc/validate_task_package.py
```

Expected:

```text
LabUtopia task package validation OK
```

## P2: Reproducible Evidence Regeneration

**Files:**
- Create: `docs/labutopia_lab_poc/evidence_manifests/render_layout_closure_YYYYMMDD_HHMMSS.json`
- Modify: `docs/labutopia_lab_poc/render_visual_investigation_20260623.md`
- Modify: `docs/labutopia_lab_poc/franka_render_smoke.md`
- Modify: `docs/records/2026-06-22-labutopia-ebench-weekly-report.md`
- Modify: `docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html`

- [ ] **Step 1: Run eval-path capture after P0/P1 fixes**

Run the diagnostic/capture script for all three tasks and save outputs under:

```text
saved/diagnostics/labutopia_render_closure_<timestamp>/
```

Expected:

```text
camera frames are not black
required objects are visible in at least one eval-path frame per task
diagnostics.json includes frame stats and claim_boundary.task_render_accepted=false until visual review passes
```

- [ ] **Step 2: Run visual QA review**

Use `render-visual-reviewer` on the three regenerated images.

Acceptance:

```text
level1_pick: PASS only if the pick target is clearly identifiable
level1_place: PASS only if beaker and target platform are visible together
level1_open_door: PASS only if drying box, door face, and handle are visible
common reject conditions: black frame, near-all-white/flat frame, target too tiny, severe clipping, wrong dimensions/channels, reused identical frame across different tasks
```

- [ ] **Step 3: Write evidence manifest**

Create `docs/labutopia_lab_poc/evidence_manifests/render_layout_closure_YYYYMMDD_HHMMSS.json`:

```json
{
  "run_id": "labutopia_render_closure_YYYYMMDD_HHMMSS",
  "commit": "git-commit-sha",
  "direct_render": false,
  "official_baseline_execution": false,
  "task_render_accepted": true,
  "camera_config": "configs/cameras/labutopia_franka_poc.yml",
  "asset_root": "/cpfs/shared/simulation/zhuzihou/dev/_datasets/EBench-Assets-Overlay/labutopia_level1_poc/assets",
  "images": {
    "level1_pick": {
      "source_frame": "saved/eval_results/ebench/<run_id>/.../level1_pick/.../camera2/00000.png",
      "report_image": "docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-pick.jpg",
      "sha256": "sha256",
      "visual_qa": "PASS"
    },
    "level1_place": {
      "source_frame": "saved/eval_results/ebench/<run_id>/.../level1_place/.../camera2/00000.png",
      "report_image": "docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-place.jpg",
      "sha256": "sha256",
      "visual_qa": "PASS"
    },
    "level1_open_door": {
      "source_frame": "saved/eval_results/ebench/<run_id>/.../level1_open_door/.../camera2/00000.png",
      "report_image": "docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door.jpg",
      "sha256": "sha256",
      "visual_qa": "PASS"
    }
  }
}
```

Reject the manifest if any image has `direct_render=true`, missing `source_frame`, missing `sha256`, or `visual_qa` not equal to `PASS`.

- [ ] **Step 4: Replace report images only after visual QA passes**

Keep old JPGs in the report as historical failed samples. Replace or add current diagnostic PNGs only with clear labels:

```text
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-pick-eval-readback-p1.png
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-place-eval-readback-p1.png
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door-eval-readback-p1.png
```

Do not replace them with direct-render images unless the report clearly labels them as non-eval-path diagnostic images.

- [ ] **Step 5: Update PM report wording**

Allowed wording after the partial P1 visibility update:

```text
旧 JPG 是历史失败样例；新 PNG 来自 evaluator camera readback。当前 pick 已清楚、place 基本可读，open_door 已从物理爆值和黑箱角推进到关闭位正确、门板/框架/单个橙色把手可识别。该图可用于 PM 诊断汇报，但 diagnostics 仍是 render_validation_not_passed，不能作为 baseline 可评证据。
```

Allowed wording after the full gate passes:

```text
三任务已有可复现的 eval-path reset 渲染证据，能看到各自任务关键对象；这证明渲染/布局闭环，不代表策略求解成功，也不代表官方 Lift2 baseline 成绩。
```

- [ ] **Step 6: Verify docs and tests**

Run:

```bash
git diff --check
python -m pytest tests/labutopia_poc -q
python standalone_tools/labutopia_poc/validate_task_package.py
python - <<'PY'
from pathlib import Path
html = Path('docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html').read_text(encoding='utf-8')
for text in [
    '旧图：历史失败样例',
    'level1_open_door · 可诊断 / 未验收',
    'render_visual_investigation_20260623.md',
    '2026-06-23-labutopia-ebench-render-layout-closure.md',
]:
    assert text in html, text
print('HTML evidence links OK')
PY
```

Expected:

```text
no whitespace errors
tests pass
validator OK
HTML evidence links OK
```

## Confusion Avoidance

Use these conventions for every new run:

```text
port: 18091 or above, never 8087
run_id prefix: labutopia_render_diag_ or labutopia_render_closure_
output root: saved/diagnostics/
report title: LabUtopia render/layout closure, not EOS
```

Before and after any Isaac run:

```bash
ps -eo pid,ppid,cmd | rg '18091|labutopia_render_diag|labutopia_render_closure|SimulationApp|kit/kit|ray' || true
```

Never delete or stop the existing EOS/other-engineer process on port `8087`.
