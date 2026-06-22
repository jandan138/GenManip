# LabUtopia Franka POC Smoke

Run date: 2026-06-22

## Goal

Verify that the LabUtopia Franka POC can run through GenManip/EBench client-server lifecycle: submit, reset, step, record results, finish all tasks, and shut down without interfering with the separate EOS service.

## Runtime

- Conda env: `/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310`
- Server port: `18088`
- EOS/other-engineer port: `8087`, not modified
- Run ID: `labutopia_franka_smoke_clean8_20260622_100208`
- Ray tmp dir: `/tmp/gm8877`

## Result Matrix

| Task | Reset | Step | Metric | Evidence |
| --- | --- | --- | --- | --- |
| `level1_pick` | PASS | PASS | PASS | reset completed in 87.73s, score persisted as 0.0 |
| `level1_place` | PASS | PASS | PASS | reset completed in 40.33s, score persisted as 0.0 |
| `level1_open_door` | PASS | PASS | PASS | reset completed in 41.31s, score persisted as 0.0 |

Final status: PASS. The client exited normally and the final evaluation result included all three tasks. The 0.0 scores are expected because this smoke uses default client actions, not a solving policy.

## Commands

Server:

```bash
PY=/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310/bin/python
ENV=/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310
CUROBO_SRC=/cpfs/shared/simulation/mamengchen/curobo-wbc-backup/src
CUDA11_LIB=/isaac-sim/exts/omni.isaac.ml_archive/pip_prebundle/nvidia/cuda_runtime/lib
RUN_ID=labutopia_franka_smoke_$(date -u +%Y%m%d_%H%M%S)
export ACCEPT_EULA=Y OMNI_KIT_ACCEPT_EULA=YES PYTHONNOUSERSITE=1
export RAY_ADDRESS=local RAY_USAGE_STATS_ENABLED=0 RAY_TMPDIR=/tmp/gm8877
export PYTHONPATH="$CUROBO_SRC:/root/.config/superpowers/worktrees/GenManip/labutopia-ebench-poc"
export LD_LIBRARY_PATH="$CUDA11_LIB:$ENV/lib/python3.10/site-packages/torch/lib:${LD_LIBRARY_PATH:-}"
$PY ray_eval_server.py --host 127.0.0.1 --port 18088 --run_id "$RUN_ID" --no_save_process --episode_recorder_save_every 0 --reset_timeout 1200 --step_timeout 1200 --load_config_timeout 300
```

Client:

```bash
PY=/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310/bin/python
ENV=/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310
export RUN_ID=labutopia_franka_smoke_clean8_20260622_100208
export PYTHONNOUSERSITE=1
export PYTHONPATH="$ENV/lib/python3.10:$ENV/lib/python3.10/site-packages:/cpfs/shared/simulation/zhuzihou/dev/genmanip-client/src:/root/.config/superpowers/worktrees/GenManip/labutopia-ebench-poc"
$PY - <<'PY'
import os
from genmanip_client.cli import main
raise SystemExit(main(['submit', 'ebench/labutopia_lab_poc/franka_poc', '--run_id', os.environ['RUN_ID'], '--host', '127.0.0.1', '--port', '18088']))
PY
$PY - <<'PY'
import os
from genmanip_client.cli import main
raise SystemExit(main(['eval', '--worker_ids', '0', '--run_id', os.environ['RUN_ID'], '--host', '127.0.0.1', '--port', '18088', '--no_save_process', '--frame_save_interval', '0', '--chunk_size', '1']))
PY
```

## Raw Evidence

Client reset/final output:

```text
Reset complete in 87.73s
Reset complete in 40.33s
Reset complete in 41.31s
Reset complete in 1.01s
Final Evaluation Result
(1/1)ebench/labutopia_lab..        0.00%
(1/1)ebench/labutopia_lab..        0.00%
(1/1)ebench/labutopia_lab..        0.00%
Client closed.
```

Final status:

```json
{"data":{"status":"complete","benchmark_id":"ebench","run_id":"labutopia_franka_smoke_clean8_20260622_100208","total_episodes":3,"completed_episodes":3,"in_progress_episodes":0,"active_workers":[],"results":{"ebench/labutopia_lab_poc/franka_poc/level1_pick":0.0,"ebench/labutopia_lab_poc/franka_poc/level1_place":0.0,"ebench/labutopia_lab_poc/franka_poc/level1_open_door":0.0}}}
```

Result files:

```text
saved/eval_results/ebench/labutopia_franka_smoke_clean8_20260622_100208/ebench/labutopia_lab_poc/franka_poc/level1_open_door/000/result_info.json
saved/eval_results/ebench/labutopia_franka_smoke_clean8_20260622_100208/ebench/labutopia_lab_poc/franka_poc/level1_pick/000/result_info.json
saved/eval_results/ebench/labutopia_franka_smoke_clean8_20260622_100208/ebench/labutopia_lab_poc/franka_poc/level1_place/000/result_info.json
```

Key server log lines:

```text
Using LabUtopia POC assets overlay. previous_ASSETS_DIR=/root/.config/superpowers/worktrees/GenManip/labutopia-ebench-poc/saved/assets ASSETS_DIR=/cpfs/shared/simulation/zhuzihou/dev/_datasets/EBench-Assets-Overlay/labutopia_level1_poc/assets runtime_scene=/cpfs/shared/simulation/zhuzihou/dev/_datasets/EBench-Assets-Overlay/labutopia_level1_poc/assets/scene_usds/labutopia/level1_poc/lab_001/scene.usda
Starting background reset for worker=0 info={'info': 0.0, 'termination_reason': 'non_finite_arm_state'}
Saving final result for benchmark_id=ebench
```

## Notes

- The server was shut down after the run.
- Final port check: `18088=7`, `8087=0`; 18088 was offline and the separate EOS service on 8087 remained reachable.
- If `post_episode_process` raises an exception, the worker pool now fails fast and does not use the numeric done-info fallback to create a completed minimal result.
- USD material binding warnings and PhysX invalid-transform warnings appear during default-action smoke. They do not currently block reset/result completion, but they are relevant for baseline-policy scoring work.
