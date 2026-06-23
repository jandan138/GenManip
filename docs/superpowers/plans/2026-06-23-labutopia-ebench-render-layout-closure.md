# LabUtopia EBench Render/Layout Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the failed LabUtopia render evidence with reproducible eval-path frames that show task-relevant reset layouts for `level1_pick`, `level1_place`, and `level1_open_door`.

**Architecture:** Treat render/layout closure as a P0 gate before Lift2 baseline work. First instrument the normal eval camera path, then make task reset layout explicit, then regenerate visual evidence through a reproducible script and independent visual review. Keep all runs isolated by worktree, port, run_id, and result directory to avoid confusion with EOS or another engineer's work.

**Tech Stack:** Python 3.10, Isaac Sim 4.1 conda env, GenManip evaluator, EBench server/client, Pillow-based image stats, pytest, static GitHub Pages docs.

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

**Files:**
- Create: `standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py`
- Create: `tests/labutopia_poc/test_render_diagnostics_contract.py`

- [ ] **Step 1: Write diagnostics contract test**

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

- [ ] **Step 2: Run the test and confirm RED**

Run:

```bash
python -m pytest tests/labutopia_poc/test_render_diagnostics_contract.py -q
```

Expected:

```text
ImportError or missing function failure
```

- [ ] **Step 3: Implement the pure-Python diagnostics helpers**

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

- [ ] **Step 4: Run the test and confirm GREEN**

Run:

```bash
python -m pytest tests/labutopia_poc/test_render_diagnostics_contract.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Add Isaac runtime capture mode**

Extend `capture_eval_render_diagnostics.py` with an `argparse` CLI that accepts:

```text
--config ebench/labutopia_lab_poc/franka_poc
--task level1_pick
--run-id labutopia_render_diag_YYYYMMDD_HHMMSS
--port 18091
--output-dir saved/diagnostics/labutopia_render_diag_YYYYMMDD_HHMMSS
--save-one-step
```

The CLI must write:

```text
diagnostics.json
camera1/00000.png
camera2/00000.png
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

- [ ] **Step 6: Run isolated camera diagnostics**

Use the conda Python:

```bash
/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310/bin/python \
  standalone_tools/labutopia_poc/capture_eval_render_diagnostics.py \
  --config ebench/labutopia_lab_poc/franka_poc \
  --task level1_pick \
  --run-id labutopia_render_diag_$(date +%Y%m%d_%H%M%S) \
  --port 18091 \
  --output-dir saved/diagnostics/labutopia_render_diag_pick \
  --save-one-step
```

Expected:

```text
diagnostics.json written
camera frame stats recorded for camera1 and camera2
camera prim path, render product path, world pose, focal data, RGB stats, and nonzero count recorded immediately after get_eval_camera_data()
no process remains on port 18091 after completion
```

- [ ] **Step 7: Repeat diagnostics for all tasks**

Run the same command for:

```text
level1_pick
level1_place
level1_open_door
```

Expected:

```text
Each task has camera frame stats and object pose diagnostics.
If camera2 is black, diagnostics identify whether camera1 is also black.
level1_open_door additionally records articulation names, drying-box pose, handle pose, and handle/object projection into camera2.
```

## P1: Reset-Time Task Layout Closure

**Files:**
- Modify: `configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_pick.yml`
- Modify: `configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_place.yml`
- Modify: `configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_open_door.yml`
- Modify: `configs/cameras/labutopia_franka_poc.yml` or create task-specific camera configs
- Test: `tests/labutopia_poc/test_validate_task_package.py`

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

- [ ] **Step 4: Decide camera fix from P0 diagnostics**

Use the P0 diagnostics to choose one outcome:

```text
Outcome A: render product/readback broken -> fix camera creation/readback before changing poses.
Outcome B: pose/lighting broken only -> update camera pose and lighting config.
Outcome C: task-specific view needed -> create task-specific camera config for open_door.
```

Do not change all variables at once.

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

Replace:

```text
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-pick.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-place.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door.jpg
```

Do not replace them with direct-render images unless the report clearly labels them as non-eval-path diagnostic images.

- [ ] **Step 5: Update PM report wording**

Allowed wording after the gate passes:

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
    '当前三张渲染图未通过视觉验收',
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
