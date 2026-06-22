# LabUtopia Franka POC render smoke

Date: 2026-06-22

## Scope

This record tracks the render evidence added for the LabUtopia Franka POC weekly report.

The render evidence is PM-facing asset-visibility evidence only. It does not prove task success, official baseline readiness, video recording readiness, or correct reset-time task layout.

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

To keep the weekly report useful while preserving claim boundaries, the report uses static direct-render screenshots from the same EBench/GenManip-loaded LabUtopia stage and the same overlay asset root. The direct render only changes report lighting and camera viewpoint. It does not change task configuration, evaluator logic, or result scores.

## Report images

Committed report assets:

```text
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-pick.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-place.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door.jpg
```

Interpretation:

- `level1_pick`: static visibility of the loaded local tabletop target asset.
- `level1_place`: static visibility of the loaded target platform asset.
- `level1_open_door`: static visibility of the loaded drying-box geometry.

## Open risks

- Fix eval recorder `camera2` black frames.
- Close the gap between visible mesh bbox, wrapper pose, and task semantic coordinates.
- Capture reset-time keyframes for all three tasks through the normal eval recording path.
- Keep official Lift2 baseline claims blocked until Lift2 composite assets and official runner discovery are complete.
