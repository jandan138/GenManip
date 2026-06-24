# EBench LabUtopia POC Status

Updated: 2026-06-24

## PM Summary

EBench LabUtopia POC has reached a runnable end-to-end smoke state inside the GenManip evaluation server. The current Franka POC profile can be submitted through the client, reset three LabUtopia level-1 tasks, run one action step per task, record per-task results, and produce a final evaluation result without timing out at the end.

This is a wiring and platform-readiness milestone, not a task-solving milestone. The smoke uses the client default action, so all three task scores are 0.0. That is expected for this check: it proves the benchmark package, scene assets, server lifecycle, progress accounting, and result writing path are connected.

## Current State

| Area | Status | Notes |
| --- | --- | --- |
| Franka POC package | Ready for smoke | `ebench/labutopia_lab_poc/franka_poc` includes `level1_pick`, `level1_place`, `level1_open_door`. |
| Asset loading | Ready for smoke | LabUtopia POC overrides `ASSETS_DIR` to the EBench overlay and resolves the runtime `scene.usda`. |
| Scene metadata | Ready for smoke | Missing collected-package `meta_info.pkl` is synthesized from the live LabUtopia scene for POC tasks. |
| Camera cleanup | Ready for smoke | POC camera configs now include cleanup flags required by GenManip camera reset. |
| Result lifecycle | Ready for smoke | Episodes that terminate before recorder finalize persist minimal `result_info.json`; real post-processing exceptions now fail fast instead of being hidden as completed results. |
| Render/readback evidence | Task render accepted | 2026-06-24 formal diagnostics moved all three tasks to `readback_visible` with `render_validation.passed=true`; `level1_pick` target is clear, `level1_place` relation is readable, and P1 `level1_open_door` surrogate baseline shows closed joint target `[0.0]` plus visible door/frame/thin handle. |
| Asset/layout acceptance | P1 accepted; native pending | Static selected objects now sit in the Franka workspace and the DryingBox handle is nested again. DryingBox runtime USD/PhysX topology is stabilized for the POC through a `sanitized_surrogate`; this is a debugging baseline, not proof that LabUtopia native complex `DryingBox_01` is evaluable. |
| Native complex DryingBox | Not yet proven | New hard requirement: replace the final `open_door` route with LabUtopia native complex `DryingBox_01`, preserving native visual/hierarchy/handle and using only additive physics overrides for runtime stability. |
| Lift2 official baseline | Not yet proven | Architecture is prepared to add/evaluate the lift2 candidate profile, but the official baseline smoke still needs to be run. |

## Evidence

Latest isolated smoke:

- Run ID: `labutopia_franka_smoke_clean8_20260622_100208`
- Server port: `18088`
- Existing EOS/other-engineer port: `8087`, left untouched and still online after the run
- Final status: `complete`, `3/3` episodes completed
- Final result: all three tasks recorded `score=0.0`, `sr=0.0`
- Regression tests: `python -m pytest tests/labutopia_poc -q` -> `64 passed, 1 skipped`
- Diagnostics contract: included in the full LabUtopia POC test suite above
- Package validator: `python standalone_tools/labutopia_poc/validate_task_package.py` -> `LabUtopia task package validation OK`

Details are recorded in `docs/labutopia_lab_poc/franka_smoke.md`.

## Runtime Decision

Use this conda environment for current testing:

`/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310`

Reason: it is already compatible with Isaac Sim 4.1, Ray, GenManip client, cuRobo source injection, and the EBench/LabUtopia asset overlay. We do not source `/isaac-sim/setup_python_env.sh`; the clean conda environment plus explicit `PYTHONPATH`/`LD_LIBRARY_PATH` is the tested path.

## Risks And Next Steps

The immediate next lane is planned in
`docs/superpowers/plans/2026-06-24-ebench-native-dryingbox.md`.
The Lift2 lane remains queued after the native DryingBox gate:
`docs/superpowers/plans/2026-06-22-ebench-labutopia-lift2-baseline-lane.md`.

1. P0 render source fix: camera axes/pose handling and deterministic lighting now make all three tasks `camera2` readback non-black.
2. P1 asset/layout fix: static objects and nested handle are normalized into the robot workspace; task-level hiding now makes pick/place PM-readable diagnostics.
3. P1b open_door physics fix: stronger DryingBox USD/PhysX validation and sanitized articulation topology are in place for the POC; keep the runtime sanity gate active and label this as `sanitized_surrogate` baseline evidence.
4. P1d evidence regeneration: completed formal eval-path capture for the three Franka tasks; current claim boundary is `task_render_accepted=true`, `native_complex_dryingbox_ready=false`, `official_baseline_evaluable=false`.
5. P2 native complex DryingBox gate: follow `docs/superpowers/plans/2026-06-24-ebench-native-dryingbox.md` before Lift2 work. Required stages are asset audit, native-only Isaac smoke, EBench wrapper import, additive physics override, open_door eval readback, tutorial evidence update, and only then Lift2 gating.
6. P3 runtime asset preflight: build/verify a LabUtopia composite asset root before running lift2. Current observation: the scene overlay exists, but lift2 robot and cuRobo assets are not present under the scene-only overlay root.
7. P4 lift2 dry smoke: run `ebench/labutopia_lab_poc/lift2_candidate` on an isolated port, require `complete` and `3/3` result files, keep `official_baseline_execution=false`.
8. P5 official baseline discovery: locate official EBench lift2/OpenPI runner files, retain paths and hashes, do not execute policy yet.
9. P6 official baseline local contrast: run one official-style online loop only after P5 passes, retain source terminal evidence, keep `standard_model_score=null` until a separate score-release gate.
10. Closure: write EOS-style dated records with artifact linkage, forbidden-claims, and path-leakage checks before changing PM-facing claims.
