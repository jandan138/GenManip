# LabUtopia Franka POC render smoke

Date: 2026-06-22

## Scope

This record tracks the render evidence added for the LabUtopia Franka POC weekly report.

The render evidence is historical failed evidence. It does not prove asset visibility, task success, official baseline readiness, video recording readiness, or correct reset-time task layout.

## Environment

Conda environment:

```text
/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310
```

Task package:

```text
ebench/labutopia_lab_poc/franka_poc
```

LabUtopia overlay root:

```text
/cpfs/shared/simulation/zhuzihou/dev/_datasets/EBench-Assets-Overlay/labutopia_level1_poc/assets
```

## Render smoke

EBench server/client render smoke run:

```text
run_id=labutopia_franka_render_smoke_20260622_150819
config=ebench/labutopia_lab_poc/franka_poc
port=18090
save_process=true
frame_save_interval=1
```

Result summary:

```text
level1_pick score=0.0 sr=0.0
level1_place score=0.0 sr=0.0
level1_open_door score=0.0 sr=0.0
```

The `0.0` score is expected for this wiring smoke because it uses default/no-op behavior. It should not be interpreted as a policy result.

## Camera finding

The eval recorder wrote per-task PNG frames under the render smoke run directory, but the recorded `camera2` RGB frames were black.

Observed implication:

```text
eval recorder camera2: not usable for PM visual evidence yet
```

Follow-up eval-path diagnostics on 2026-06-23 narrowed the failure boundary:

```text
level1_pick: readback_black_before_recorder
level1_place: readback_black_before_recorder
level1_open_door: readback_black_before_recorder
```

That means the frame is already pure black immediately after `get_eval_camera_data()` and before `EpisodeRecorder` writes PNG files. Recorder writing is therefore ruled out as the primary black-frame source.

Diagnostic runs:

```text
saved/diagnostics/labutopia_render_diag_pick_20260623_070712/level1_pick/diagnostics.json
saved/diagnostics/labutopia_render_diag_level1_place_20260623_070855/level1_place/diagnostics.json
saved/diagnostics/labutopia_render_diag_level1_open_door_20260623_070933/level1_open_door/diagnostics.json
```

Evidence manifest:

```text
docs/labutopia_lab_poc/evidence_manifests/render_diagnostics_20260623.json
```

P0a/P0b follow-up on 2026-06-23:

```text
camera axes/pose: camera2 now uses camera_axes: usd and position [9.6, 0.0, 2.5]
deterministic lighting: runtime overlay scene authors /World/labutopia_level1_poc/DeterministicDomeLight
level1_pick: readback_visible
level1_place: readback_visible
```

Follow-up evidence:

```text
saved/diagnostics/labutopia_p0a_p0b_pick_20260623_155645/level1_pick/diagnostics.json
saved/diagnostics/labutopia_p0a_p0b_place_20260623_155831/level1_place/diagnostics.json
docs/labutopia_lab_poc/evidence_manifests/render_p0a_p0b_20260623.json
```

This fixes the pure-black readback failure for controlled pick/place P0 diagnostics. It still does not provide accepted task render evidence: the regenerated frames are nearly flat gray and show only a tiny mark, so report images must not be replaced yet.

The initial weekly report used static direct-render screenshots from the same EBench/GenManip-loaded LabUtopia stage and the same overlay asset root. Follow-up visual QA on 2026-06-23 found those screenshots are not acceptable as task-scene evidence. The direct render changed report lighting and camera viewpoint, and it did not prove task configuration, evaluator logic, result scores, or reset-time visual correctness.

## Report images

Committed report assets:

```text
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-pick.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-place.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door.jpg
```

Follow-up visual QA:

- `level1_pick`: WARN. Some object-like shapes are visible, but the pick target is not clearly identifiable.
- `level1_place`: FAIL. Only the target platform/slab is visible; the beaker and place relation are missing.
- `level1_open_door`: FAIL. Only a drying-box corner/cuboid is visible; door, handle, hinge, and open state are not identifiable.

## Open risks

- Keep P0a/P0b evidence scoped correctly: camera2 readback is no longer pure black for pick/place, but frames are still not task-accepted.
- Close the gap between visible mesh bbox, wrapper pose, and task semantic coordinates.
- Make LabUtopia reset-time task layout explicit instead of relying on fallback live-scene metadata.
- Fix LabUtopia asset import/layout red flags: selected objects are still in source-lab coordinates, and the open-door handle is imported as an invalid independent child transform.
- Capture reset-time keyframes for all three tasks through the normal eval recording path.
- Replace the current report images only after independent visual QA passes.
- Keep official Lift2 baseline claims blocked until Lift2 composite assets and official runner discovery are complete.

## Follow-up Records

- [docs/labutopia_lab_poc/render_visual_investigation_20260623.md](render_visual_investigation_20260623.md)
- [docs/superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md](../superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md)
