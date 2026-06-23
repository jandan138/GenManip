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

Runtime diagnostics added on 2026-06-23:

| Task | Run ID | Boundary | Readback stats | Recorder stats |
| --- | --- | --- | --- | --- |
| `level1_pick` | `labutopia_render_diag_pick_20260623_070712` | `readback_black_before_recorder` | `channel_max=[0,0,0]`, `nonzero=0` | `channel_max=[0,0,0]`, `nonzero=0` |
| `level1_place` | `labutopia_render_diag_level1_place_20260623_070855` | `readback_black_before_recorder` | `channel_max=[0,0,0]`, `nonzero=0` | `channel_max=[0,0,0]`, `nonzero=0` |
| `level1_open_door` | `labutopia_render_diag_level1_open_door_20260623_070933` | `readback_black_before_recorder` | `channel_max=[0,0,0]`, `nonzero=0` | `channel_max=[0,0,0]`, `nonzero=0` |

Diagnostic paths:

```text
saved/diagnostics/labutopia_render_diag_pick_20260623_070712/level1_pick/diagnostics.json
saved/diagnostics/labutopia_render_diag_level1_place_20260623_070855/level1_place/diagnostics.json
saved/diagnostics/labutopia_render_diag_level1_open_door_20260623_070933/level1_open_door/diagnostics.json
docs/labutopia_lab_poc/evidence_manifests/render_diagnostics_20260623.json
```

Independent visual review of the three diagnostic readback images returned FAIL for all three because each image is a uniform black frame.

Recorder boundary conclusion:

```text
EpisodeRecorder is not the primary black-frame source. The RGB array is already black immediately after get_eval_camera_data(), and the same raw frame is passed into EpisodeRecorder.record_obs().
```

Camera/render evidence:

```text
camera2 prim_path: /Camera/LabUtopiaCamera2
camera2 render_product_path: /Render/RenderProduct_Replicator_01
render product camera relationship target: /Camera/LabUtopiaCamera2
camera2 position: [0.1, 0.0, 2.5]
camera2 orientation in diagnostics: [-0.7071, ~0, ~0, 0.7071]
```

The render product binding appears valid, so the most likely immediate camera-side problem is camera pose/axes or lighting/readback timing, not recorder file writing.

Layout evidence:

```text
obj_conical_bottle02 position ~= [10.236, 0.128, 0.285], scale ~= [1e-4, 1e-4, 1e-4]
obj_beaker2 position ~= [9.748, 0.601, 0.075]
obj_target_plat position ~= [8.590, 0.000, 0.300], scale z ~= 1e-4
obj_DryingBox_01 position ~= [45.884, 1.912, 0.000001], scale ~= [0.001, 0.001, 0.001]
obj_DryingBox_01_handle position ~= [-148.763, -294.393, 328.592]
```

This means the asset import/layout is also faulty. A camera-only fix may make a frame non-black, but it would not make the Franka task or official Lift2 baseline evaluable because task objects are not normalized into a valid robot workspace.

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

1. Asset import/layout is not valid for GenManip/Franka task execution.
   - The selected objects remain in source LabUtopia lab coordinates, far from the Franka/table workspace.
   - The open-door handle is imported as a direct child payload and appears to lose the parent drying-box transform/scale.
   - This is a baseline-evaluability blocker, not just a visual defect.
2. Eval camera readback is black before recorder writing.
   - The diagnostics prove the black frame exists immediately after `get_eval_camera_data()`.
   - Candidate causes: camera axes/pose points at empty/dark view, missing deterministic lighting, or readback before valid render accumulation.
   - Render product binding to `/Camera/LabUtopiaCamera2` appears valid in diagnostics.
3. Task layout is not yet a real LabUtopia reset layout.
   - LabUtopia source position ranges are in `task_semantics.yml`, but the runtime task YAMLs have empty `object_config` and null layout.
   - The fallback metadata captures the live loaded scene rather than sampling or enforcing LabUtopia task-specific reset poses.
4. Direct-render report screenshots used non-eval camera choices.
   - The report images were captured with changed lighting and viewpoint and no committed producer script.
   - This makes them unsuitable for proving task-scene correctness.
5. Overlay wrapper and task semantics are not yet aligned enough for visual or metric claims.
   - The wrapper payload exposes prims under GenManip-friendly names, but visible mesh bbox, wrapper pose, and semantic coordinates still need a measured consistency check.
6. The `open_door` camera is using a shared POC view instead of the source task's task-specific view.
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

1. Fix/validate camera axes handling in the free-camera loader path, then rerun diagnostics with only that variable changed.
2. Add deterministic lighting to the runtime overlay, then rerun diagnostics with only lighting changed.
3. Rebuild or supplement the overlay so nested LabUtopia parts preserve composed transforms, especially `DryingBox_01/handle`.
4. Normalize selected task objects into the GenManip/Franka workspace and record explicit task reset layouts instead of relying on fallback live-scene metadata.
5. Add static USD validation for object centers, bounds, scales, nested-part transform preservation, and at least one light.
6. After layout and camera/lighting are fixed, regenerate all three eval-path reset frames and run independent visual QA.
7. Write an evidence manifest for any future PM image. It must include `run_id`, task name, source eval frame path, report image path, sha256, camera config, asset root, commit hash, and `direct_render=false`.

## Documentation Decision

The weekly report must say the current images failed visual review. The images may remain as historical failed evidence only if clearly marked. They must not be presented as accepted render evidence until P0 render/layout closure passes.
