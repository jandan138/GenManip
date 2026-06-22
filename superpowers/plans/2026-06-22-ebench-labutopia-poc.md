# EBench LabUtopia POC Status

Updated: 2026-06-22

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
| Lift2 official baseline | Not yet proven | Architecture is prepared to add/evaluate the lift2 candidate profile, but the official baseline smoke still needs to be run. |

## Evidence

Latest isolated smoke:

- Run ID: `labutopia_franka_smoke_clean8_20260622_100208`
- Server port: `18088`
- Existing EOS/other-engineer port: `8087`, left untouched and still online after the run
- Final status: `complete`, `3/3` episodes completed
- Final result: all three tasks recorded `score=0.0`, `sr=0.0`
- Regression tests: `python -m pytest tests/labutopia_poc -q` -> `23 passed, 1 skipped`
- Package validator: `python standalone_tools/labutopia_poc/validate_task_package.py` -> `LabUtopia task package validation OK`

Details are recorded in `docs/labutopia_lab_poc/franka_smoke.md`.

## Runtime Decision

Use this conda environment for current testing:

`/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310`

Reason: it is already compatible with Isaac Sim 4.1, Ray, GenManip client, cuRobo source injection, and the EBench/LabUtopia asset overlay. We do not source `/isaac-sim/setup_python_env.sh`; the clean conda environment plus explicit `PYTHONPATH`/`LD_LIBRARY_PATH` is the tested path.

## Risks And Next Steps

The next lane is planned in
`docs/superpowers/plans/2026-06-22-ebench-labutopia-lift2-baseline-lane.md`.

1. P0 runtime asset preflight: build/verify a LabUtopia composite asset root before running lift2. Current observation: the scene overlay exists, but lift2 robot and cuRobo assets are not present under the scene-only overlay root.
2. P1 lift2 dry smoke: run `ebench/labutopia_lab_poc/lift2_candidate` on isolated port `18088`, require `complete` and `3/3` result files, keep `official_baseline_execution=false`.
3. P2 official baseline discovery: locate official EBench lift2/OpenPI runner files, retain paths and hashes, do not execute policy yet.
4. P3 official baseline local contrast: run one official-style online loop only after P2 passes, retain source terminal evidence, keep `standard_model_score=null` until a separate score-release gate.
5. Closure: write EOS-style dated records with artifact linkage, forbidden-claims, and path-leakage checks before changing PM-facing claims.
