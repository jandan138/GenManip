# LabUtopia EBench Render Visual Investigation

Date: 2026-06-23

## Scope

This record summarizes the visual and technical investigation for the LabUtopia Franka POC render images that were added to the 2026-06-22 weekly report.

The original JPG images are historical failed evidence. The latest evaluator readback PNGs are now non-black and task-level visibility isolation makes `level1_pick` readable and `level1_place` basically readable for PM diagnosis. `level1_open_door` runtime physics has been stabilized with a sanitized DryingBox surrogate and now starts at the expected closed joint target. The 2026-06-24 formal single-handle front-camera retake makes the DryingBox frame, door panel, and one orange handle/action point visible. Independent image-only QA rates the old-vs-current comparison PASS for PM diagnostic reporting, with `open_door` PASS/WARN as diagnostic evidence only. Therefore `task_render_accepted=false` and `official_baseline_evaluable=false` remain the correct claim boundary until `render_validation` and formal task visual QA pass.

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

## 2026-06-23 P0a/P0b Follow-Up

P0a camera axes/pose and P0b deterministic lighting were applied after the black-frame diagnostics:

```text
camera_axes support: genmanip/utils/standalone/camera_pose_utils.py
camera setup call site: genmanip/utils/usd_utils/camera_utils.py
camera2 retarget: configs/cameras/labutopia_franka_poc.yml -> position [9.6, 0.0, 2.5], camera_axes: usd
deterministic light: /World/labutopia_level1_poc/DeterministicDomeLight, DomeLight intensity 1000
runtime overlay: /cpfs/shared/simulation/zhuzihou/dev/_datasets/EBench-Assets-Overlay/labutopia_level1_poc/assets/scene_usds/labutopia/level1_poc/lab_001/scene.usda
```

New controlled eval-path diagnostics:

```text
level1_pick:  saved/diagnostics/labutopia_p0a_p0b_pick_20260623_155645/level1_pick/diagnostics.json
level1_place: saved/diagnostics/labutopia_p0a_p0b_place_20260623_155831/level1_place/diagnostics.json
manifest:     docs/labutopia_lab_poc/evidence_manifests/render_p0a_p0b_20260623.json
```

Observed boundary:

```text
level1_pick:  readback_visible, camera2 nonzero_pixels=65536, channel_max=[228,228,228]
level1_place: readback_visible, camera2 nonzero_pixels=65536, channel_max=[228,228,228]
```

This closes the pure-black readback failure for the pick/place controlled P0 diagnostics. It does not close task visual acceptance. Both frames are still nearly flat gray:

```text
level1_pick:  unique RGB colors=36, RGB std ~= [1.31, 1.31, 1.30]
level1_place: unique RGB colors=40, RGB std ~= [1.35, 1.35, 1.34]
```

Visual inspection shows a tiny gray mark on a mostly gray frame, not task-relevant objects. Therefore the next blocker remains asset/layout normalization, not recorder writing.

Layout evidence:

```text
obj_conical_bottle02 position ~= [10.236, 0.128, 0.285], scale ~= [1e-4, 1e-4, 1e-4]
obj_beaker2 position ~= [9.748, 0.601, 0.075]
obj_target_plat position ~= [8.590, 0.000, 0.300], scale z ~= 1e-4
obj_DryingBox_01 position ~= [45.884, 1.912, 0.000001], scale ~= [0.001, 0.001, 0.001]
obj_DryingBox_01_handle position ~= [-148.763, -294.393, 328.592]
```

This means the asset import/layout is also faulty. A camera-only fix may make a frame non-black, but it would not make the Franka task or official Lift2 baseline evaluable because task objects are not normalized into a valid robot workspace.

## 2026-06-23 P1 Asset/Layout Follow-Up

P1 changed the asset composition strategy and regenerated the LabUtopia overlay. The main corrections are:

- The task objects are normalized into the Franka/table workspace instead of staying in source LabUtopia coordinates.
- `DryingBox_01/handle` is no longer duplicated as an independent top-level payload.
- The runtime handle object resolves to the nested path `/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle`.
- The generated overlay authors deterministic light and display-color fallbacks.

Static USD readback after rebuilding the overlay:

```text
obj_conical_bottle02: world_translate ~= [0.28, 0.00, 0.80], bbox ~= [0.093, 0.093, 0.165]
obj_beaker2:         world_translate ~= [0.27, 0.18, 0.84], bbox ~= [0.111, 0.111, 0.090]
obj_target_plat:     world_translate ~= [0.26,-0.24, 0.776], bbox ~= [0.100, 0.100, 0.0001]
obj_DryingBox_01:    world_translate ~= [0.75, 0.10, 0.78], bbox ~= [0.576, 0.741, 0.630]
obj_DryingBox_01_handle nested path:
  /World/labutopia_level1_poc/obj_obj_DryingBox_01/handle
  world_translate ~= [0.456, 0.249, 1.109], bbox ~= [0.048, 0.048, 0.202]
top-level /World/labutopia_level1_poc/obj_obj_DryingBox_01_handle: invalid, as intended
```

New eval-path diagnostics with the shared oblique camera:

| Task | Run ID | Boundary | Visual QA | Notes |
| --- | --- | --- | --- | --- |
| `level1_pick` | `labutopia_p1_layout_pick_20260623_170924` | `readback_visible` | BLOCKER | Non-black and spatially plausible, but the yellow bottle is too small and visually confused with the drying box/door. |
| `level1_place` | `labutopia_p1_layout_place_20260623_171047` | `readback_visible` | BLOCKER | Non-black, but source object and yellow target platform are not readable as a place relation. |
| `level1_open_door` | `labutopia_p1_layout_open_door_20260623_171256` | `readback_visible` | WARN | Door is readable, but handle/action target is weak; runtime articulation is unstable. |

Evidence manifest:

```text
docs/labutopia_lab_poc/evidence_manifests/render_p1_asset_layout_20260623.json
```

Independent visual QA conclusion:

```text
level1_pick: BLOCKER
level1_place: BLOCKER
level1_open_door: WARN
```

Baseline evaluability review conclusion at this stage:

```text
official_baseline_evaluable=false
task_render_accepted=false
primary blocker at this stage: open_door runtime articulation/PhysX instability
secondary blocker: pick/place task-object visibility
```

At this P1 stage, the `open_door` runtime diagnostic became the most important blocker. Although static USD readback was sane, runtime articulation reported:

```text
articulation_state.obj_DryingBox_01.joint_positions ~= [3.888585221393613e+16, 0.0]
logs include Invalid PhysX transform warnings
logs include huge bbox warnings for task objects during reset
```

Therefore P1 is only partially closed:

```text
static_usd_ok=true
camera_readback_visible=true
runtime_physics_stable=false
task_render_accepted=false
official_baseline_evaluable=false
```

## 2026-06-23 P1 Visibility Isolation Follow-Up

After the first P1 asset/layout run, task-level visibility isolation was added through `preprocess_config` so each task hides non-task objects before capture. This makes the diagnostic images easier for PM review without changing the baseline claim boundary.

Visibility-isolation eval-path diagnostics at this stage:

| Task | Run ID | Boundary | Visual status | Notes |
| --- | --- | --- | --- | --- |
| `level1_pick` | `labutopia_p1_visibility_pick_20260623_175050` | `readback_visible` | readable, pending formal QA | Only the tabletop and blue bottle remain visible; the pick target is clear. |
| `level1_place` | `labutopia_p1_visibility_place_20260623_175232` | `readback_visible` | basically readable, pending formal QA | The beaker and yellow target platform are visible together; a closer final camera would improve polish. |
| `level1_open_door` | `labutopia_p1_visibility_open_door_20260623_175404` | `readback_visible` | superseded runtime blocker | The box/door are visible, but this run had invalid articulation state and has been superseded by the later aligned-hinge run below. |

Report assets originally copied from these diagnostics:

```text
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-pick-eval-readback-p1.png
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-place-eval-readback-p1.png
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door-eval-readback-p1.png
```

The `open_door` report PNG has since been replaced by the aligned-hinge stable runtime diagnostic recorded below.

The original copied report PNGs were 512x512 evaluator readback frames with these hashes:

```text
level1_pick:      78e193beb7bc469c5f8dd40eecb9e532c6cfe3b836b1db4a12c3275253e7755d
level1_place:     4a5603401f35f18c0039f31ebab2efba6cb895ff606842a709febe2a2402ecac
level1_open_door: 89dfb510ed0de0ee1b989953ed62f467fd31e9cc1857dc6a6060db8d4bebb1e4
```

Superseded open-door runtime blocker:

```text
runtime_sanity.runtime_physics_stable=false
joint_positions ~= [15733351251968.0, 0.0]
dof_names = [RevoluteJoint, PrismaticJoint]
claim_boundary.blockers includes runtime_physics_unstable
```

Additional read-only articulation review found that this is not a UID lookup problem. GenManip discovers `obj_DryingBox_01` as an articulation, but the underlying USD/PhysX topology remains unsafe:

- the composed articulation root still has scale `0.001`;
- several rigid links are named `mesh`, matching duplicate link-name warnings;
- some rigid links retain non-finite center of mass or invalid principal axes;
- at least one joint body target resolves to a collision prim without `PhysicsRigidBodyAPI`;
- the button prismatic joint exposes an extra DOF, so the runtime reports both `RevoluteJoint` and `PrismaticJoint`.

Recommended next fix is to strengthen static validation first, then replace the incremental DryingBox overrides with a sanitized runtime asset that bakes scale, uses unique rigid link names, keeps only required links/joints, and produces finite articulation state.

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

## 2026-06-23 P1 DryingBox Surrogate / Aligned Hinge Follow-Up

The runtime physics blocker above has been partially closed for the POC path. The overlay now uses a sanitized DryingBox runtime surrogate instead of relying on the malformed source articulation directly.

Key changes:

- The source `DryingBox_01` payload is not used for the runtime articulation.
- The surrogate articulation has no non-identity root scale.
- It exposes three stable rigid links: `body_link`, `door_link`, and `handle`.
- It uses a world fixed-base joint plus one `RevoluteJoint` for the door.
- The extra source `PrismaticJoint` is removed from the runtime articulation.
- Rigid links have finite mass, inertia, center of mass, and principal axes.
- The door hinge anchors are aligned after the body/door geometry update.

Static validation now reports:

```text
world_fixed_base_joint_paths = [/World/labutopia_level1_poc/obj_obj_DryingBox_01/BaseFixedJoint]
unexpected_joint_types = []
invalid_joint_body_targets = []
zero_mass_links = []
zero_inertia_links = []
invalid_center_of_mass_links = []
invalid_principal_axes_links = []
runtime_topology_ready = true
sanitized_for_physx = true
```

Superseded runtime diagnostic:

| Task | Run ID | Boundary | Runtime status | Visual QA |
| --- | --- | --- | --- | --- |
| `level1_open_door` | `labutopia_p1_open_door_skip_artpart_reset_trial_20260623_194939` | `readback_visible` | diagnosable, but closed start still wrong | FAIL |

Runtime evidence:

```text
diagnostic_error = None
runtime_physics_stable = true
dof_names = [RevoluteJoint]
joint_positions ~= [0.7112835049629211]
world_position ~= [0.75, 0.180000007, 0.779999971]
expected_closed_start = [0.0]
claim_boundary.blockers = [render_validation_not_passed]
official_baseline_evaluable = false
task_render_accepted = false
```

This run proved the sanitized topology was finite, but it was superseded because the closed-start target was not replayed after reset/warmup.

Intermediate camera retake that was rejected:

| Task | Run ID | Boundary | Visual QA | Reason rejected |
| --- | --- | --- | --- | --- |
| `level1_open_door` | `labutopia_p1_open_door_close_camera_20260623_123833` | `readback_visible` | FAIL | The orange handle/interaction point was clear, but the camera was too close: the drying-box body became an unidentifiable white/gray fragment, so a reviewer could not understand the open-door task context. |

Current runtime diagnostic after target replay, duplicate marker removal, handle-side correction, and formal front-camera retake:

| Task | Run ID | Boundary | Runtime status | Visual QA |
| --- | --- | --- | --- | --- |
| `level1_open_door` | `labutopia_p1_open_door_single_handle_formal_20260624_0001` | `readback_visible` | closed start fixed, door/frame/single handle visible | PASS/WARN diagnostic / not accepted |

Runtime evidence:

```text
diagnostic_error = None
runtime_physics_stable = true
dof_names = [RevoluteJoint]
joint_positions = [0.0]
expected_closed_start = [0.0]
orange_red_pixels = 2195
orange_red_bbox_xyxy = [241, 157, 276, 233]
non_floor_dark_mid_pixels = 7607
bluegrey_door_panel_pixels = 163648
claim_boundary.blockers = [render_validation_not_passed]
official_baseline_evaluable = false
task_render_accepted = false
```

Report asset now copied from:

```text
saved/diagnostics/labutopia_p1_open_door_single_handle_formal_20260624_0001/readback_after_get_eval_camera_data/camera2/00000.png
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door-eval-readback-p1.png
sha256 = f9b6c1ee41ac0a51a2377e4eed372b50a51ac4c793e5c0a52f7ef4f27a9e3e86
```

Independent image-only QA verdict for the old-vs-current report set:

```text
Overall verdict: PASS for PM-facing old-vs-current comparison evidence, with careful wording that the current images are evaluator readback diagnostics, not official baseline acceptance proof.
Old pick: FAIL; no identifiable target bottle, supports "target unclear".
Old place: FAIL; only a white plane on black background, supports "placement relation missing".
Old open_door: FAIL; close-up of dark/white box corner, no readable door, handle, or action point.
Current pick: PASS; centered blue bottle/flask-like target on tabletop.
Current place: PASS; teal object and yellow placement square are both visible.
Current open_door: PASS/WARN; cabinet/drying-box-like structure, door panel, and orange handle/action point are clearly in frame, but this remains diagnostic evidence rather than official baseline acceptance.
```

Updated interpretation:

```text
runtime_physics_stable=true
runtime_joint_target_matches=true
camera_readback_visible=true
single_handle_door_frame_visible=true
task_render_accepted=false
official_baseline_evaluable=false
primary remaining blocker: render_validation_not_passed / formal task visual QA not signed off
```

## Ranked Root-Cause Hypotheses

1. Asset import/layout is not valid for GenManip/Franka task execution.
   - Static object placement and nested handle discovery have been repaired for the POC.
   - The old DryingBox USD/PhysX topology was a baseline-evaluability blocker: non-identity root scale, duplicate rigid link names, invalid inertial attributes, invalid joint body targets, and an extra prismatic DOF.
   - The POC runtime path now uses a sanitized surrogate that passes static topology validation and latest runtime joint sanity.
   - The latest formal front-camera image makes the DryingBox frame, door panel, and single orange handle/action point visible for PM diagnosis.
   - The remaining blocker is the formal gate: diagnostics still report `render_validation_not_passed`, so this cannot be upgraded to task render acceptance or baseline evaluability.
2. Eval camera readback is black before recorder writing.
   - The first diagnostics proved the black frame existed immediately after `get_eval_camera_data()`.
   - P0a/P0b follow-up changed pick/place from `readback_black_before_recorder` to `readback_visible`.
   - Remaining visual failure is near-flat, low-texture output caused by asset/layout scale and placement defects.
   - Render product binding to `/Camera/LabUtopiaCamera2` appears valid in diagnostics.
3. Task layout is not yet a real LabUtopia reset layout.
   - LabUtopia source position ranges are in `task_semantics.yml`, and task-level visibility isolation now removes non-task objects for POC diagnosis.
   - Full reset sampling and formal task render acceptance are still not signed off.
4. Direct-render report screenshots used non-eval camera choices.
   - The report images were captured with changed lighting and viewpoint and no committed producer script.
   - This makes them unsuitable for proving task-scene correctness.
5. Overlay wrapper and task semantics are not yet aligned enough for visual or metric claims.
   - The wrapper payload exposes prims under GenManip-friendly names, but visible mesh bbox, wrapper pose, and semantic coordinates still need a measured consistency check.
6. The `open_door` PM diagnostic image is now usable, but the acceptance gate is still closed.
   - Articulation state now matches the expected closed target and the formal camera shows the door/frame/single handle.
   - The next step is not to overclaim the screenshot; it is to keep `render_validation_not_passed` as the hard blocker and run formal visual QA before any baseline statement.

## Claim Boundary

Allowed now:

```text
LabUtopia Franka POC can run through the local GenManip/EBench server-client smoke path and finalize 3/3 tasks with result files.
P0a/P0b controlled diagnostics prove camera2 readback is no longer pure black for pick/place after camera_axes/pose and deterministic lighting fixes.
P1 visibility diagnostics make pick readable and place basically readable as PM-facing diagnostic frames.
The latest open_door runtime diagnostic has stable DryingBox joint positions, matches the expected closed target [0.0], only exposes RevoluteJoint, and shows the DryingBox frame, door panel, and one orange handle/action point in the same evaluator readback frame.
```

Not allowed now:

```text
The three task render images are accepted.
The eval video path works.
Task reset layouts are visually verified.
The official Lift2 baseline is evaluable.
The current open_door screenshot proves visual task correctness.
The current report display QA proves task visual acceptance.
```

## Required Next Diagnostics

Run these in an isolated port/run_id so EOS or another engineer's run is not confused with this work:

1. Fix/validate camera axes handling in the free-camera loader path, then rerun diagnostics with only that variable changed. Done for P0a, with pick/place `readback_visible`.
2. Add deterministic lighting to the runtime overlay, then rerun diagnostics with only lighting changed. Done for P0b, with static validation and pick/place `readback_visible`.
3. Done for static POC layer: rebuild the overlay so selected task objects are in the Franka workspace and `DryingBox_01/handle` remains nested under the DryingBox.
4. Done for POC diagnosis: add task-level visibility isolation so pick/place are PM-readable.
5. Done for POC runtime layer: extend static USD/PhysX validation for DryingBox articulation root scale, duplicate rigid-link basenames, non-finite COM, invalid principal axes, invalid joint body targets, and unexpected extra DOFs.
6. Done for POC runtime layer: build a sanitized DryingBox runtime asset and rerun `level1_open_door` diagnostics until runtime joint positions are finite.
7. Done for POC runtime layer: fix `open_door` closed-start joint initialization, move the handle to the non-hinge side, remove the duplicate orange marker, and formalize the front camera.
8. Next: run browser display QA and formal task visual QA on the updated report set; keep `task_render_accepted=false` until `render_validation` passes.
9. Write an evidence manifest for any future PM image. It must include `run_id`, task name, source eval frame path, report image path, sha256, camera config, asset root, commit hash, and `direct_render=false`.

## Documentation Decision

The weekly report must keep the old JPGs as historical failed evidence and present the new PNGs as evaluator readback diagnostics. It may say `pick` is readable and `place` is basically readable for PM diagnosis. It may also say the latest `open_door` DryingBox articulation is diagnosable after removing the earlier joint explosion, that the closed-start target now matches `[0.0]`, and that the DryingBox frame, door panel, and one orange handle/action point are visible in the same evaluator frame. It must also say this is PM-facing diagnostic evidence only. It must not claim `task_render_accepted=true`, official Lift2 baseline evaluability, or open-door visual acceptance until formal task visual QA and `render_validation` pass.
