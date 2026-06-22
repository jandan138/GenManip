# EBench LabUtopia Lift2 Baseline Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move from Franka wiring smoke to an EOS-style, evidence-gated LabUtopia `lift2_candidate` lane that can truthfully support an "EBench official lift2 baseline is locally evaluable" claim after the required gates pass.

**Architecture:** Treat LabUtopia as an EBench/GenManip compatibility lane with strict claim boundaries. Keep LabUtopia-specific asset composition, smoke scripts, official-baseline discovery, and evidence reports outside generic evaluator core; core runtime changes are allowed only when they preserve existing GenManip contracts. Use staged gates: preflight first, dry lift2 smoke second, official-baseline loop third, closure/evidence package last.

**Tech Stack:** Python 3.10, Isaac Sim 4.1 runtime conda env, Ray Eval Server, GenManip client, LabUtopia POC config package, pytest, EOS-style evidence records.

---

## EOS-Style Claim Boundary

Allowed after P1 dry smoke:

```text
LabUtopia lift2_candidate can be submitted, reset, stepped, and finalized locally through the GenManip/EBench server-client path.
```

Allowed only after P3 official-baseline gate:

```text
The local environment can run one EBench official lift2 baseline-style online evaluation attempt on LabUtopia POC tasks and retain terminal source evidence.
```

Not allowed until a later benchmark-reproduction gate:

```text
official leaderboard reproduction
leaderboard comparability
benchmark-wide model quality
model superiority
backend parity
real-world safety
hardware readiness
official EBench score release
```

## File Structure

- Modify `genmanip/core/evaluator/labutopia_assets.py`
  - Owns LabUtopia POC asset-root resolution.
  - Next change: build or select a composite runtime asset root that contains LabUtopia scene overlay plus default GenManip robot/curobo assets needed by Lift2.
- Modify `genmanip/core/evaluator/isaac_worker_pool.py`
  - Uses LabUtopia asset override through `resolve_labutopia_poc_assets_override`.
  - Should not learn official-policy concepts.
- Modify `standalone_tools/labutopia_poc/validate_task_package.py`
  - Owns static package validation.
  - Next change: validate lift2 runtime robot/camera/curobo asset readiness under the effective asset root.
- Create `standalone_tools/labutopia_poc/run_lift2_smoke.py`
  - Thin, reproducible wrapper around the proven server/client command sequence.
  - Writes a machine-readable smoke report.
- Create `standalone_tools/labutopia_poc/discover_official_lift2_baseline.py`
  - Discovers official EBench/OpenPI/lift2 runner files and records paths/hashes.
  - Does not execute a policy.
- Create `tests/labutopia_poc/test_labutopia_composite_assets.py`
  - TDD coverage for the composite asset root contract.
- Create `tests/labutopia_poc/test_lift2_smoke_report_contract.py`
  - TDD coverage for the smoke report schema and claim flags.
- Create `docs/records/2026-06-22-labutopia-ebench-lift2-baseline-lane-planning.md`
  - EOS-style dated planning record.
- Update `docs/superpowers/plans/2026-06-22-ebench-labutopia-poc.md`
  - PM-facing status should point to this lane plan as the next execution path.

## Current Known Preflight Finding

The current LabUtopia overlay root contains the LabUtopia runtime scene but does not contain Lift2 robot assets:

```text
overlay_root=/cpfs/shared/simulation/zhuzihou/dev/_datasets/EBench-Assets-Overlay/labutopia_level1_poc/assets
overlay_root/scene_usds/labutopia/level1_poc/lab_001/scene.usda exists
overlay_root/robot_usds/lift2/robot.usd missing
overlay_root/miscs/curobo/R5a/r5a_left_arm.yml missing
```

Therefore P0 must happen before any serious `lift2_candidate` smoke. Do not start by blindly running lift2 for hours.

## P0: Runtime Asset And Environment Preflight

**Files:**
- Modify: `genmanip/core/evaluator/labutopia_assets.py`
- Modify: `standalone_tools/labutopia_poc/validate_task_package.py`
- Test: `tests/labutopia_poc/test_labutopia_composite_assets.py`
- Test: `tests/labutopia_poc/test_validate_task_package.py`

- [ ] **Step 1: Write failing composite asset root test**

Create `tests/labutopia_poc/test_labutopia_composite_assets.py` with a test that builds a temporary default asset root and LabUtopia scene overlay root:

```python
from pathlib import Path

from genmanip.core.evaluator.labutopia_assets import build_labutopia_runtime_asset_root


def test_composite_asset_root_contains_overlay_scene_and_default_lift2_assets(tmp_path):
    default_root = tmp_path / "default_assets"
    overlay_root = tmp_path / "overlay_assets"
    runtime_root = tmp_path / "runtime_assets"

    (default_root / "robot_usds/lift2").mkdir(parents=True)
    (default_root / "robot_usds/lift2/robot.usd").write_text("# lift2", encoding="utf-8")
    (default_root / "miscs/curobo/R5a").mkdir(parents=True)
    (default_root / "miscs/curobo/R5a/r5a_left_arm.yml").write_text("robot_cfg: {}", encoding="utf-8")
    (overlay_root / "scene_usds/labutopia/level1_poc/lab_001").mkdir(parents=True)
    (overlay_root / "scene_usds/labutopia/level1_poc/lab_001/scene.usda").write_text("# scene", encoding="utf-8")

    result = build_labutopia_runtime_asset_root(default_root, overlay_root, runtime_root)

    assert (Path(result) / "scene_usds/labutopia/level1_poc/lab_001/scene.usda").exists()
    assert (Path(result) / "robot_usds/lift2/robot.usd").exists()
    assert (Path(result) / "miscs/curobo/R5a/r5a_left_arm.yml").exists()
```

- [ ] **Step 2: Run test and confirm RED**

Run:

```bash
python -m pytest tests/labutopia_poc/test_labutopia_composite_assets.py -q
```

Expected:

```text
Module import or function missing failure for build_labutopia_runtime_asset_root
```

- [ ] **Step 3: Implement composite asset root**

Implement `build_labutopia_runtime_asset_root(default_root, overlay_root, runtime_root)` in `genmanip/core/evaluator/labutopia_assets.py`.

Contract:

```text
runtime_root/scene_usds -> overlay_root/scene_usds
runtime_root/manifests -> overlay_root/manifests when present
runtime_root/miscs/mdl/labutopia -> overlay_root/miscs/mdl/labutopia when present
runtime_root/robot_usds -> default_root/robot_usds
runtime_root/miscs/curobo -> default_root/miscs/curobo
```

Use symlinks when possible. If symlink creation fails, copy directories with `shutil.copytree(..., dirs_exist_ok=True)`.

- [ ] **Step 4: Route LabUtopia override through composite root**

Update `resolve_labutopia_poc_assets_override()` so LabUtopia POC configs return the composite runtime root instead of the scene-only overlay root.

Runtime root should be deterministic and gitignored:

```text
saved/assets/labutopia_level1_poc_runtime
```

- [ ] **Step 5: Extend validator for lift2 runtime assets**

Update `standalone_tools/labutopia_poc/validate_task_package.py` so `validate_task_package()` checks:

```text
effective_labutopia_asset_root/scene_usds/labutopia/level1_poc/lab_001/scene.usda
effective_labutopia_asset_root/robot_usds/lift2/robot.usd
saved/assets/miscs/curobo/R5a/r5a_left_arm.yml
configs/cameras/fixed_camera_lift2_simbox.yml cleanup flags
```

- [ ] **Step 6: Verify P0**

Run:

```bash
python -m pytest tests/labutopia_poc/test_labutopia_composite_assets.py tests/labutopia_poc/test_validate_task_package.py -q
python standalone_tools/labutopia_poc/validate_task_package.py
```

Expected:

```text
all selected tests pass
LabUtopia task package validation OK
```

## P1: Lift2 Candidate Dry Smoke

**Files:**
- Create: `standalone_tools/labutopia_poc/run_lift2_smoke.py`
- Create: `tests/labutopia_poc/test_lift2_smoke_report_contract.py`
- Update: `docs/labutopia_lab_poc/franka_smoke.md` only if shared smoke conventions change
- Create: `docs/labutopia_lab_poc/lift2_smoke.md`

- [ ] **Step 1: Write smoke report contract test**

Create `tests/labutopia_poc/test_lift2_smoke_report_contract.py`:

```python
from standalone_tools.labutopia_poc.run_lift2_smoke import build_smoke_report


def test_lift2_smoke_report_keeps_claim_boundary():
    report = build_smoke_report(
        run_id="labutopia_lift2_smoke_example",
        status="complete",
        completed_episodes=3,
        total_episodes=3,
        results={
            "ebench/labutopia_lab_poc/lift2_candidate/level1_pick": 0.0,
            "ebench/labutopia_lab_poc/lift2_candidate/level1_place": 0.0,
            "ebench/labutopia_lab_poc/lift2_candidate/level1_open_door": 0.0,
        },
        save_process=False,
    )

    assert report["profile"] == "lift2_candidate"
    assert report["dry_smoke_status"] == "complete"
    assert report["official_baseline_execution"] is False
    assert report["official_benchmark_reproduction"] is False
    assert report["official_leaderboard_comparable"] is False
    assert report["standard_model_score"] is None
```

- [ ] **Step 2: Run test and confirm RED**

Run:

```bash
python -m pytest tests/labutopia_poc/test_lift2_smoke_report_contract.py -q
```

Expected:

```text
Module import or function missing failure for run_lift2_smoke
```

- [ ] **Step 3: Implement report builder and CLI skeleton**

Create `standalone_tools/labutopia_poc/run_lift2_smoke.py` with:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_smoke_report(
    *,
    run_id: str,
    status: str,
    completed_episodes: int,
    total_episodes: int,
    results: dict[str, float],
    save_process: bool,
) -> dict[str, Any]:
    return {
        "profile": "lift2_candidate",
        "config": "ebench/labutopia_lab_poc/lift2_candidate",
        "run_id": run_id,
        "dry_smoke_status": status,
        "completed_episodes": completed_episodes,
        "total_episodes": total_episodes,
        "results": results,
        "save_process": save_process,
        "official_baseline_execution": False,
        "official_benchmark_reproduction": False,
        "official_leaderboard_comparable": False,
        "standard_model_score": None,
    }
```

The first version may require the operator to run server/client commands manually and then pass `--status-json`; it must not hide process execution details.

- [ ] **Step 4: Run isolated lift2 dry smoke**

Use the same isolation contract as Franka:

```bash
PY=/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310/bin/python
ENV=/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310
WORKTREE=/root/.config/superpowers/worktrees/GenManip/labutopia-ebench-poc
CUROBO_SRC=/cpfs/shared/simulation/mamengchen/curobo-wbc-backup/src
CUDA11_LIB=/isaac-sim/exts/omni.isaac.ml_archive/pip_prebundle/nvidia/cuda_runtime/lib
RUN_ID=labutopia_lift2_smoke_$(date -u +%Y%m%d_%H%M%S)
export ACCEPT_EULA=Y OMNI_KIT_ACCEPT_EULA=YES PYTHONNOUSERSITE=1
export RAY_ADDRESS=local RAY_USAGE_STATS_ENABLED=0 RAY_TMPDIR=/tmp/gm_lift2
export PYTHONPATH="$CUROBO_SRC:$WORKTREE"
export LD_LIBRARY_PATH="$CUDA11_LIB:$ENV/lib/python3.10/site-packages/torch/lib:${LD_LIBRARY_PATH:-}"
"$PY" ray_eval_server.py --host 127.0.0.1 --port 18088 --run_id "$RUN_ID" --no_save_process --episode_recorder_save_every 0 --reset_timeout 1200 --step_timeout 1200 --load_config_timeout 300
```

In a separate shell:

```bash
PY=/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310/bin/python
ENV=/cpfs/shared/simulation/zhuzihou/dev/conda-managed/envs/embodied-eval-os-sim-isaacsim41-genmanip-py310
WORKTREE=/root/.config/superpowers/worktrees/GenManip/labutopia-ebench-poc
export PYTHONNOUSERSITE=1
export PYTHONPATH="$ENV/lib/python3.10:$ENV/lib/python3.10/site-packages:/cpfs/shared/simulation/zhuzihou/dev/genmanip-client/src:$WORKTREE"
"$PY" - <<'PY'
import os
from genmanip_client.cli import main
raise SystemExit(main(['submit', 'ebench/labutopia_lab_poc/lift2_candidate', '--run_id', os.environ['RUN_ID'], '--host', '127.0.0.1', '--port', '18088']))
PY
"$PY" - <<'PY'
import os
from genmanip_client.cli import main
raise SystemExit(main(['eval', '--worker_ids', '0', '--run_id', os.environ['RUN_ID'], '--host', '127.0.0.1', '--port', '18088', '--no_save_process', '--frame_save_interval', '0', '--chunk_size', '1']))
PY
```

- [ ] **Step 5: P1 acceptance**

Accept P1 only if all are true:

```text
server did not attach to or disrupt 8087
18088 is down after cleanup
8087 remains reachable after cleanup
status=complete
completed_episodes=3
result_info.json exists for level1_pick, level1_place, level1_open_door
official_baseline_execution=false
standard_model_score=null
```

If any condition fails, create `docs/labutopia_lab_poc/lift2_smoke.md` with `dry_smoke_status=blocked_with_evidence` and list the exact blocker.

## P2: Official Lift2 Baseline Discovery Gate

**Files:**
- Create: `standalone_tools/labutopia_poc/discover_official_lift2_baseline.py`
- Create: `tests/labutopia_poc/test_official_lift2_baseline_discovery_contract.py`
- Create: `docs/labutopia_lab_poc/official_lift2_baseline_discovery.md`

- [ ] **Step 1: Write discovery contract test**

Create `tests/labutopia_poc/test_official_lift2_baseline_discovery_contract.py`:

```python
from standalone_tools.labutopia_poc.discover_official_lift2_baseline import build_discovery_report


def test_discovery_report_is_no_execution_and_no_score():
    report = build_discovery_report(
        source_root="/tmp/EBench",
        discovered_files=["baselines/openpi/scripts/pi_eval_client_online.py"],
        missing_files=[],
    )

    assert report["discovery_status"] == "passed"
    assert report["official_baseline_execution_attempted"] is False
    assert report["standard_model_score"] is None
    assert report["official_benchmark_reproduction"] is False
    assert report["official_leaderboard_comparable"] is False
```

- [ ] **Step 2: Implement discovery report builder**

The discovery script must check candidate roots in this order:

```text
$EBENCH_ROOT
/cpfs/shared/simulation/zhuzihou/dev/EBench
/cpfs/user/zhuzihou/dev/EBench
/cpfs/user/zhuzihou/dev/embodied-eval-os/.external/EBench
```

It must record whether these files exist:

```text
scripts/launch_pi_onlineeval.sh
baselines/openpi/scripts/pi_eval_client_online.py
baselines/openpi/third_party/openpi/scripts/serve_policy.py
baselines/openpi/src/openpi/training/config.py
```

- [ ] **Step 3: Run discovery**

Run:

```bash
python standalone_tools/labutopia_poc/discover_official_lift2_baseline.py --output docs/labutopia_lab_poc/official_lift2_baseline_discovery.json
```

Acceptance:

```text
discovery_status=passed or blocked_with_evidence
official_baseline_execution_attempted=false
standard_model_score=null
```

## P3: Official Baseline Local Contrast Attempt

**Files:**
- Create: `standalone_tools/labutopia_poc/run_official_lift2_baseline_contrast.py`
- Create: `tests/labutopia_poc/test_official_lift2_baseline_contrast_report.py`
- Create: `docs/labutopia_lab_poc/official_lift2_baseline_contrast.md`

- [ ] **Step 1: Mirror EOS BPL-19Q shape**

The local contrast runner must follow this loop shape:

```text
GenManip reset_result
-> official client observation prep
-> policy inference
-> official action prep
-> GenManip step or step_chunk
-> repeat until terminal result or max cycle
```

Do not implement fixed action replay as a substitute for online control.

- [ ] **Step 2: Add report contract test**

Create `tests/labutopia_poc/test_official_lift2_baseline_contrast_report.py`:

```python
from standalone_tools.labutopia_poc.run_official_lift2_baseline_contrast import build_contrast_report


def test_official_contrast_report_keeps_source_score_separate():
    report = build_contrast_report(
        run_id="example",
        status="executed",
        policy_cycle_count=2,
        terminal_result_present=True,
        source_metric_score_value=0.0,
    )

    assert report["official_baseline_execution_attempted"] is True
    assert report["official_eval_loop_status"] == "executed"
    assert report["source_metric_score_value"] == 0.0
    assert report["standard_model_score"] is None
    assert report["score_source_from_official_runner"] is False
    assert report["official_benchmark_reproduction"] is False
    assert report["official_leaderboard_comparable"] is False
```

- [ ] **Step 3: Execute only after P2 passed**

Run the official contrast attempt only when P2 discovery has retained runner paths and environment requirements.

Acceptance:

```text
official_baseline_execution_attempted=true
official_eval_loop_status=executed or blocked_with_evidence
terminal_result_present=true for executed attempts
source_metric_score_value retained separately
standard_model_score=null
score_source_from_official_runner=false
official_benchmark_reproduction=false
official_leaderboard_comparable=false
artifact_linkage_audit_status=passed
forbidden_claims_audit_status=passed
path_leakage_audit_status=passed
```

## P4: Closure Record And PM Update

**Files:**
- Create: `docs/records/2026-06-22-labutopia-lift2-dry-smoke-closure.md` after P1
- Create: `docs/records/2026-06-22-labutopia-official-lift2-baseline-contrast-closure.md` after P3
- Update: `docs/superpowers/plans/2026-06-22-ebench-labutopia-poc.md`

- [ ] **Step 1: Write closure record**

Use this exact structure:

```markdown
# 2026-06-22 LabUtopia Lift2 Dry Smoke Closure

## Context
## Decision / Change
## Files touched
## Validation
## Known limitations
## Next actions
```

- [ ] **Step 2: Update PM-facing plan**

Only use these words if P1 passed:

```text
Lift2 dry smoke completed.
```

Only use these words if P3 passed:

```text
Official lift2 baseline local contrast executed with retained terminal source evidence.
```

Do not use:

```text
official leaderboard comparable
official benchmark reproduced
official score released
baseline solved LabUtopia
```

## Verification Before Handoff

Run all before claiming the lane is ready for PM update:

```bash
python -m pytest tests/labutopia_poc -q
python standalone_tools/labutopia_poc/validate_task_package.py
curl -fsS http://127.0.0.1:18088/docs >/tmp/labutopia_18088_check.out 2>&1; echo "18088=$?"
curl -fsS http://127.0.0.1:8087/docs >/tmp/labutopia_8087_check.out 2>&1; echo "8087=$?"
```

Expected:

```text
tests pass
LabUtopia task package validation OK
18088=7 after cleanup
8087=0
```
