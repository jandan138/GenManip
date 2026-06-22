# 2026-06-22 LabUtopia EBench Lift2 Baseline Lane Planning

## Context

Franka POC wiring smoke is closed with retained evidence:

```text
run_id=labutopia_franka_smoke_clean8_20260622_100208
status=complete
completed_episodes=3/3
scores=0.0 for pick/place/open_door
claim_boundary=wiring smoke, not task solving
```

The next product question is whether LabUtopia can be moved toward an
EBench-official lift2 baseline evaluable lane without overclaiming.

## Decision / Change

Adopt an EOS-style staged lane:

```text
P0 runtime asset and environment preflight
P1 lift2_candidate dry smoke
P2 official lift2 baseline discovery
P3 official baseline local contrast attempt
P4 closure and PM update
```

The plan is saved at:

```text
docs/superpowers/plans/2026-06-22-ebench-labutopia-lift2-baseline-lane.md
```

## Files Touched

Planning only:

```text
docs/superpowers/plans/2026-06-22-ebench-labutopia-lift2-baseline-lane.md
docs/records/2026-06-22-labutopia-ebench-lift2-baseline-lane-planning.md
```

## Validation

EOS reference patterns reviewed:

```text
/cpfs/user/zhuzihou/dev/embodied-eval-os/CLAUDE.md
/cpfs/user/zhuzihou/dev/embodied-eval-os/adapters/ebench/README.md
/cpfs/user/zhuzihou/dev/embodied-eval-os/docs/records/2026-06-15-bpl8-ebench-owned-task-score-lane-planning.md
/cpfs/user/zhuzihou/dev/embodied-eval-os/docs/records/2026-06-19-bpl19m-official-style-online-policy-rollout-planning.md
/cpfs/user/zhuzihou/dev/embodied-eval-os/docs/records/2026-06-20-bpl19q-q2-official-native-smoke-closure.md
```

Local preflight observation:

```text
LabUtopia overlay runtime scene exists.
LabUtopia overlay root does not contain robot_usds/lift2/robot.usd.
LabUtopia overlay root does not contain miscs/curobo/R5a/r5a_left_arm.yml.
```

## Known Limitations

This record is a planning record. It does not claim lift2 dry smoke, official
baseline execution, official leaderboard comparability, or task success.

## Next Actions

Start P0 only. Do not run a long lift2 smoke until the composite runtime asset
root preflight passes.
