# LabUtopia EBench Render Visual Investigation

Date: 2026-06-23

## Scope

This record summarizes the visual and technical investigation for the three LabUtopia Franka POC render images that were added to the 2026-06-22 weekly report.

The conclusion is that the current three images are not acceptable as task-scene render evidence. They should be treated as failed visual evidence until the normal eval recorder path produces task-relevant reset-time frames.

## Reviewed Images

Committed report assets:

```text
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-pick.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-place.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door.jpg
```

## Multi-Agent Review

### Visual QA Reviewer

Verdict: FAIL overall.

| Task | Verdict | Visible evidence | Main risk |
| --- | --- | --- | --- |
| `level1_pick` | WARN | Some tabletop-like surface and white object shapes are visible. | Pick target is not clearly identifiable; material contrast and clipping make this weak evidence. |
| `level1_place` | FAIL | Only a white rectangular platform/slab is visible. | No beaker or place relation is visible. |
| `level1_open_door` | FAIL | A close-up of a dark cuboid/corner with white top is visible. | Door, handle, hinge, and open state are not identifiable. |

Retake requirements:

- `level1_pick`: target object centered, separated from the support surface, with enough contrast to identify it.
- `level1_place`: both the beaker and target platform visible in one frame, with their spatial relation clear.
- `level1_open_door`: wider frontal or three-quarter view showing drying box, door face, handle, hinge area, and open/closed state.

### Technical Reviewer

The report JPGs are documented, but there is no committed producer script or exact capture command for them. They are not normal eval recorder frames.

Key findings:

- `run_id=labutopia_franka_render_smoke_20260622_150819` saved process frames, but all checked `camera2` frames are pure black.
- The three report JPGs were direct-render static screenshots with report-specific lighting and camera viewpoint.
- Current task YAMLs use `object_config: {}` and `layout_config.type: null`, so LabUtopia source task position ranges are recorded but not actively applied as GenManip reset-time layouts.
- The shared POC camera config does not preserve the original LabUtopia `level1_open_door` camera viewpoints.
- The overlay wrapper proves selected prims can be discovered, but it does not by itself prove task-relevant object placement, visible bbox alignment, or baseline readiness.

### Product Reviewer

The PM-safe status is:

```text
Backend integration smoke is complete, but visual/layout validation is blocked.
```

The current images should be called debug screenshots or historical failed evidence, not PM-ready render evidence.

## Evidence Collected

Eval recorder frame stats from the render smoke run:

```text
run_id=labutopia_franka_render_smoke_20260622_150819
level1_pick camera2 frames: 32 checked path entries, sampled min=max=mean=0
level1_place camera2 frames: 32 checked path entries, sampled min=max=mean=0
level1_open_door camera2 frames: 32 checked path entries, sampled min=max=mean=0
```

Representative paths:

```text
saved/eval_results/ebench/labutopia_franka_render_smoke_20260622_150819/ebench/labutopia_lab_poc/franka_poc/level1_pick/000/*/camera2/00000.png
saved/eval_results/ebench/labutopia_franka_render_smoke_20260622_150819/ebench/labutopia_lab_poc/franka_poc/level1_place/000/*/camera2/00000.png
saved/eval_results/ebench/labutopia_franka_render_smoke_20260622_150819/ebench/labutopia_lab_poc/franka_poc/level1_open_door/000/*/camera2/00000.png
```

Relevant configuration:

```text
configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_pick.yml
configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_place.yml
configs/tasks/ebench/labutopia_lab_poc/franka_poc/level1_open_door.yml
configs/cameras/labutopia_franka_poc.yml
configs/tasks/ebench/labutopia_lab_poc/common/task_semantics.yml
standalone_tools/labutopia_poc/build_asset_overlay.py
genmanip/core/evaluator/labutopia_layout.py
genmanip/utils/loader/scene.py
```

## Ranked Root-Cause Hypotheses

1. Eval recorder camera path is broken before writing.
   - The saved PNGs are pure black, so the issue is upstream of report rendering and likely upstream of image file writing.
   - Candidate causes: camera pose points at empty/dark view, render product not bound to the intended Isaac camera prim, missing lighting in the normal eval path, or camera readback before valid rendering.
2. Task layout is not yet a real LabUtopia reset layout.
   - LabUtopia source position ranges are in `task_semantics.yml`, but the runtime task YAMLs have empty `object_config` and null layout.
   - The fallback metadata captures the live loaded scene rather than sampling or enforcing LabUtopia task-specific reset poses.
3. Direct-render report screenshots used non-eval camera choices.
   - The report images were captured with changed lighting and viewpoint and no committed producer script.
   - This makes them unsuitable for proving task-scene correctness.
4. Overlay wrapper and task semantics are not yet aligned enough for visual or metric claims.
   - The wrapper payload exposes prims under GenManip-friendly names, but visible mesh bbox, wrapper pose, and semantic coordinates still need a measured consistency check.
5. The `open_door` camera is using a shared POC view instead of the source task's task-specific view.
   - Original LabUtopia `level1_open_door.yaml` uses different camera positions from the shared POC camera config.

## Claim Boundary

Allowed now:

```text
LabUtopia Franka POC can run through the local GenManip/EBench server-client smoke path and finalize 3/3 tasks with result files.
```

Not allowed now:

```text
The three task render images are accepted.
The eval video path works.
Task reset layouts are visually verified.
The official Lift2 baseline is evaluable.
The current screenshots prove task correctness.
```

## Required Next Diagnostics

Run these in an isolated port/run_id so EOS or another engineer's run is not confused with this work:

1. Dump `camera1` and `camera2` world poses, render product paths, RGB min/max/mean/nonzero stats immediately after `get_eval_camera_data()`.
2. Save one raw camera frame before `EpisodeRecorder.record_obs()` to isolate camera readback from recorder output.
3. Change only `camera2` pose to a known direct-render viewpoint, then only lighting, to separate pose failure from lighting/readback failure.
4. Dump `scene.object_list.keys()`, wrapper world poses, object extents/bbox centers, and target object projections into `camera2`.
5. Add a reproducible render/capture script that writes all diagnostics and images under a unique `run_id`.
6. Write an evidence manifest for any future PM image. It must include `run_id`, task name, source eval frame path, report image path, sha256, camera config, asset root, commit hash, and `direct_render=false`.

## Documentation Decision

The weekly report must say the current images failed visual review. The images may remain as historical failed evidence only if clearly marked. They must not be presented as accepted render evidence until P0 render/layout closure passes.
