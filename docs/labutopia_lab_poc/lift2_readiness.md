# LabUtopia Lift2 Candidate Readiness

Status as of 2026-06-28 20:26:53 UTC, recorded under the 2026-06-29 local run
stamp: **Stage 7 passed** for the local official-baseline-style Lift2 contract.

This page records Acceptance Stage 7 for
`ebench/labutopia_lab_poc/lift2_candidate`. It proves the local data/runtime
contract for Lift2-style evaluation, not policy quality, official leaderboard
reproduction, official EBench score release, or full native MDL/texture material
closure.

For the full multi-gate SOP, see
[EBench Asset Acceptance Pipeline](ebench_asset_acceptance_pipeline.md). This
page is only the Stage 7 record inside that broader pipeline.

## Claim Boundary

- Franka/native Acceptance Stages 1-6 already proved native `DryingBox_01`
  eval-path readback.
- Stage 7 now separately checks Lift2 reset, step, camera, observation/action,
  reward/success, metric, and logging contracts.
- `lift2_contract_ready=true`.
- `local_official_baseline_style_contract_ready=true`.
- `official_baseline_evaluable=false`; this is not an official leaderboard run.
- `native_material_closure_claim_allowed=false`; Stage 7 consumes Stage 5/6
  material status and does not require material follow-up completion.
- Post-Stage-7 follow-up on 2026-06-29 closed the Aluminum remote waiver via
  package-local mirror, but full native material closure remains open because
  fallback surfaces still need native material binding.
- The complete three-task eval finished with `score=0.0` and `success_rate=0`
  for all tasks. That means the tested simple/default action did not solve the
  tasks; it does not invalidate the runtime/data contract.

Evidence:

```text
docs/labutopia_lab_poc/evidence_manifests/native_dryingbox_stage7_lift2_contract_20260629_0404.json
docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260629_0404/
docs/labutopia_lab_poc/evidence_manifests/aluminum_material_mirror_closure_20260629_045413.json
```

Linked prior evidence:

```text
docs/labutopia_lab_poc/evidence_manifests/native_dryingbox_acceptance_20260628_183219.json
docs/labutopia_lab_poc/evidence_manifests/native_dryingbox_eval_20260628_183219.json
```

## Environment

Runtime Python:

```text
/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310/bin/python
```

Key environment additions:

```text
CUROBO_SRC=/cpfs/shared/simulation/mamengchen/curobo-wbc-backup/src
GENMANIP_CLIENT_SRC=/cpfs/shared/simulation/zhuzihou/dev/genmanip-client/src
LABUTOPIA_POC_ASSETS_OVERLAY_ROOT=/root/.config/superpowers/worktrees/GenManip/labutopia-stage5-eval-readback/saved/assets
```

The worktree `saved/assets` symlink points to the composite asset root:

```text
/cpfs/shared/simulation/zhuzihou/dev/_datasets/EBench-Assets-Composite/labutopia_level1_poc_lift2_codex/assets
```

That composite root combines the official/default Lift2 resources with the
LabUtopia overlay. The preflight evidence confirms these required paths exist:

```text
saved/assets/robot_usds/lift2/robot.usd
saved/assets/miscs/curobo/R5a/r5a_left_arm.yml
saved/assets/scene_usds/labutopia/level1_poc/lab_001/scene.usda
saved/assets/manifests/labutopia_level1_poc.json
saved/assets/manifests/native_dryingbox_physics_override.json
```

The isolated eval server used port `18188`. It was stopped after the probes.
Port `8087` remained open for another task and was not touched.

## Command Outputs

Full three-task Lift2 candidate eval:

```text
run_id=labutopia_lift2_composite_20260629_0404
host=127.0.0.1
port=18188
command=gmp submit/eval/status through genmanip_client.cli
status=complete
completed=3
score=0.0 for level1_pick, level1_place, level1_open_door
```

Logs:

```text
docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260629_0404/gmp_submit.txt
docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260629_0404/gmp_eval.txt
docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260629_0404/gmp_status.txt
docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260629_0404/result_info_summary.txt
```

Live contract probes were run as separate single-task jobs so each task has its
own reset observation and step responses:

```text
level1_pick:      labutopia_lift2_contract_probe_live_20260629_0416_pick
level1_place:     labutopia_lift2_contract_probe_live_20260629_0416_place
level1_open_door: labutopia_lift2_contract_probe_live_20260629_0416
```

Probe JSON:

```text
docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260629_0404/probe_level1_pick.json
docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260629_0404/probe_level1_place.json
docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260629_0404/probe.json
```

Each individual probe JSON is a schema/live-step snapshot for one task. The
Stage 7 pass claim is made only by the final manifest above, which merges these
live probe rows with the complete three-task `gmp eval` task matrix.

## Per-Task Readiness Matrix

Every cell uses only `PASS`, `FAIL`, or `BLOCKED`.

| Task | Reset | Step | Reachability | Camera Inputs | Metric | Finding |
| --- | --- | --- | --- | --- | --- | --- |
| `level1_pick` | PASS | PASS | PASS | PASS | PASS | Full `gmp eval` reached result_info and metric_score; live probe exposed image-shaped Lift2 camera inputs and all action dialects produced step responses. Score remains `0.0`. |
| `level1_place` | PASS | PASS | PASS | PASS | PASS | Full `gmp eval` reached result_info and metric_score; live probe exposed image-shaped Lift2 camera inputs and all action dialects produced step responses. Score remains `0.0`. |
| `level1_open_door` | PASS | PASS | PASS | PASS | PASS | Full `gmp eval` reached result_info and metric_score; live probe exposed image-shaped Lift2 camera inputs and all action dialects produced step responses. Score remains `0.0`. |

## Schema Matrix

| Row | Status | Finding |
| --- | --- | --- |
| Observation keys | PASS | All three live probes expose required Lift2 baseline inputs: `instruction`, `state.joints`, `state.gripper`, `state.base`, `state.ee_pose`, `video.*`, `timestep`, `reset`, and `robot_id`. |
| Camera input keys | PASS | All three live probes expose image-shaped `video.overlook_camera_view`, `video.left_camera_view`, and `video.right_camera_view`. |
| Action dialects | PASS | Zero action, OpenPI-style relative `base_motion`, X-VLA-style absolute `base_motion`, and optional InternVLA-A1 dialects all match the 16D Lift2 joint-position contract and produce live step responses. |
| Reward/success fields | PASS | Live step responses expose GenManip/EBench metric/reward/success fields rather than relying on LabUtopia expert-controller `done`. |
| Logging fields | PASS | Run id, worker id, episode id, seed, result path, stdout, and stderr paths are recorded in the evidence bundle. |

## Result

```text
Stage 7 passed
lift2_contract_ready=true
local_official_baseline_style_contract_ready=true
official_baseline_evaluable=false
```

Product wording:

```text
LabUtopia lift2_candidate lane has passed the local official-baseline-style
Lift2 contract. It can reset, step, read camera/observation/action schemas,
record reward/metric/logging, and write results for all three candidate tasks.
This is still not an official EBench score release, and the 0% score is a
policy-quality result, not a runtime-contract failure.
```

## Remaining Work

1. Hand this lane to the actual Lift2 baseline execution path and keep run IDs
   separate from the local contract probes.
2. Improve policy/controller behavior separately; Stage 7 only proves the lane
   can be evaluated.
3. Close the remaining full material-closure blockers for `Group/_900_1`,
   `button`, and `panel`; Aluminum is now local-mirrored, but those fallback
   surfaces still prevent `resolved_native_material`.
4. Implement the generic `asset_acceptance` manifest fields described in
   [EBench Asset Acceptance Pipeline](ebench_asset_acceptance_pipeline.md) so
   future PM reports derive claims from manifest evidence instead of manual text.

## Post-Stage-7 Material Follow-Up

On 2026-06-29, `Aluminum_Anodized_Charcoal.mdl` was mirrored into the LabUtopia
EBench package:

```text
miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl
miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_BaseColor.png
miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_Normal.png
miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_ORM.png
```

The wrapper layer now overrides the Aluminum Shader with
`info:mdl:sourceAsset = @Aluminum_Anodized_Charcoal.mdl@`, and worker
`MDL_SYSTEM_PATH` covers `{ASSETS_DIR}/miscs/mdl/labutopia/mdl`.

This closes the Aluminum remote dependency:

```text
remote_aluminum_disposition=local_mirror
remote_only_dependency_count=0
waiver_count=0
closure_claim_allowed=false
aluminum_material_closure_claim_allowed=true
```

It does not change the Stage 7 Lift2 contract claim and does not allow full
native material closure yet:

```text
native_material_closure_claim_allowed=false
full_native_material_closure_claim_allowed=false
native_material_closure_reason=fallback_surfaces_remain_after_aluminum_local_mirror
```
