# LabUtopia Lift2 Candidate Readiness

Status as of 2026-06-28 19:14 UTC: **Stage 7 attempted, blocked**.

This page records the Acceptance Stage 7 Lift2 official-baseline-style contract
check for `ebench/labutopia_lab_poc/lift2_candidate`. It does not claim official
leaderboard reproduction, official EBench score release, model quality, or full
native MDL/texture material closure.

## Claim Boundary

- Franka/native Acceptance Stages 1-6 passed enough evidence for native
  `DryingBox_01` eval-path readback.
- Stage 7 is separate. It checks Lift2 observation, action, camera,
  reward/success, and logging contracts.
- Stage 7 is not passed here because reset/step/metric evidence could not be
  collected from a live Lift2 eval server.
- `lift2_contract_ready=false`.
- `official_baseline_evaluable=false`.
- `native_material_closure_claim_allowed=false`; Stage 7 consumes Stage 5/6
  material status and does not close the remote Aluminum waiver.

Evidence bundle:

```text
docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260628_191421/
```

Linked prior evidence:

```text
docs/labutopia_lab_poc/evidence_manifests/native_dryingbox_acceptance_20260628_183219.json
docs/labutopia_lab_poc/evidence_manifests/native_dryingbox_eval_20260628_183219.json
```

## Environment

Recommended runtime Python used for the Stage 7 probe:

```text
/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310/bin/python
```

`PYTHONPATH` included the external GenManip client:

```text
/cpfs/shared/simulation/zhuzihou/dev/genmanip-client/src
```

The probe used isolated run metadata:

```text
run_id=labutopia_lift2_schema_smoke_20260628_191421
host=127.0.0.1
port=18088
worker_id=0
```

Port `18088` was used to avoid interfering with the default `8087` lane or
another engineer's run.

## Preflight

The LabUtopia wrapper scene exists, but the Lift2 composite asset root is still
incomplete:

| Check | Status |
| --- | --- |
| LabUtopia wrapper scene | PASS |
| `saved/assets/robot_usds/lift2/robot.usd` | BLOCKED |
| `saved/assets/miscs/curobo/R5a/r5a_left_arm.yml` | BLOCKED |
| `saved/tasks/ebench/labutopia_lab_poc/lift2_candidate/level1_pick/meta_info.pkl` | BLOCKED |
| overlay `robot_usds/lift2/robot.usd` | BLOCKED |

The earlier Lift2 lane planning record already said not to run a long Lift2
smoke until the composite asset preflight passes. Therefore no long Isaac eval
server was started for this evidence bundle.

## Command Outputs

Static checks completed before the Stage 7 attempt:

```text
python -m pytest tests/labutopia_poc -q
165 passed, 1 skipped

python standalone_tools/labutopia_poc/validate_task_package.py
LabUtopia task package validation OK

python -m json.tool configs/tasks/ebench/labutopia_lab_poc/franka_poc/franka_poc.json
PASS

python -m json.tool configs/tasks/ebench/labutopia_lab_poc/lift2_candidate/lift2_candidate.json
PASS

git diff --check
PASS
```

`gmp submit` through `genmanip_client.cli`:

```text
command: submit ebench/labutopia_lab_poc/lift2_candidate --run_id labutopia_lift2_schema_smoke_20260628_191421 --host 127.0.0.1 --port 18088
exit_code: 1
finding: cannot connect to server at http://127.0.0.1:18088
log: docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260628_191421/gmp_submit.txt
```

`gmp eval` through `genmanip_client.cli`:

```text
command: eval --worker_ids 0 --run_id labutopia_lift2_schema_smoke_20260628_191421 --host 127.0.0.1 --port 18088 -a r5a -g lift2 --no_save_process --frame_save_interval 0 --chunk_size 1
exit_code: 1
finding: cannot connect to server at http://127.0.0.1:18088
log: docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260628_191421/gmp_eval.txt
```

`gmp status` through `genmanip_client.cli`:

```text
command: status --run_id labutopia_lift2_schema_smoke_20260628_191421 --host 127.0.0.1 --port 18088
exit_code: 1
finding: cannot connect to server at http://127.0.0.1:18088
log: docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260628_191421/gmp_status.txt
```

`lift2_eval_contract_probe`:

```text
command: python standalone_tools/labutopia_poc/lift2_eval_contract_probe.py --live --host 127.0.0.1 --port 18088 --worker-id 0 --run-id labutopia_lift2_schema_smoke_20260628_191421 --task-name level1_open_door --include-optional-internvla --output docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260628_191421/probe.json
exit_code: 0
finding: probe captured BLOCKED state instead of crashing
json: docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260628_191421/probe.json
```

## Per-Task Readiness Matrix

Every cell uses only `PASS`, `FAIL`, or `BLOCKED`.

| Task | Reset | Step | Reachability | Camera Framing | Metric | Finding |
| --- | --- | --- | --- | --- | --- | --- |
| `level1_pick` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | Live server was not started because Lift2 robot/curobo assets are missing; no reset evidence exists. |
| `level1_place` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | Live server was not started because Lift2 robot/curobo assets are missing; no reset evidence exists. |
| `level1_open_door` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | Live probe could not connect to `127.0.0.1:18088`; no reset/step/metric evidence exists. |

## Schema Matrix

| Row | Status | Finding |
| --- | --- | --- |
| Observation keys | BLOCKED | No reset observation schema was provided by a live server. |
| Camera input keys | BLOCKED | Required `video.overlook_camera_view`, `video.left_camera_view`, and `video.right_camera_view` could not be observed at reset. |
| Action dialects | PASS | Static action dialect matrix matches the 16D Lift2 joint-position action plus separate 3D `base_motion`. |
| Reward/success fields | BLOCKED | No GenManip/EBench step response or metric output was available. |
| Logging fields | BLOCKED | No completed live episode produced result path, seed, episode id, stdout/stderr, or exception stack from the server side. |

The probe also generated optional InternVLA-A1 action dialects, but those do
not upgrade readiness because live reset/step evidence is missing. Future live
reruns must use the same `run_id` for `gmp submit`, `gmp eval`, `gmp status`,
and `lift2_eval_contract_probe` so the probe cannot read a different server
state.

## Result

```text
Stage 7 attempted, blocked
lift2_contract_ready=false
local_official_baseline_style_contract_ready=false
official_baseline_evaluable=false
```

Only a future Stage 7 rerun with every per-task and schema row marked `PASS`
can support local official-baseline-style Lift2 readiness wording; it still
does not by itself claim official leaderboard reproduction or official EBench
score release.

## Next Engineering Items

1. Build a composite Lift2 asset root that combines the LabUtopia overlay with
   default `robot_usds/lift2` and `miscs/curobo/R5a` assets.
2. Start the eval server on an isolated port such as `18088` with explicit
   `ASSETS_DIR`.
3. Re-run `gmp submit`, `gmp eval -a r5a -g lift2`, `gmp status`, and
   `lift2_eval_contract_probe --live`.
4. Upgrade Stage 7 only if `level1_pick`, `level1_place`, and
   `level1_open_door` all have `PASS` for reset, step, reachability, camera
   framing, metric, observation schema, action schema, reward/success, and
   logging.
