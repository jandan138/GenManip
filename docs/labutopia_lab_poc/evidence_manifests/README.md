# LabUtopia EBench Evidence Manifest Field Guide

## 目的

这个目录里的 manifest 是 PM 汇报和工程签收的证据来源。以后外部 asset package 进入 EBench 时，不能先写“已完成”，而要先写清楚 `run_id`、`command`、`artifact path`、`PASS/FAIL/BLOCKED`、`allowed_claims` 和 `blocked_claims`。

## 标准顶层字段

每个验收记录建议包含：

```json
{
  "schema_version": 1,
  "recorded_at_utc": "2026-06-29T00:00:00Z",
  "asset_id": "LabUtopia/DryingBox_01",
  "task_lane": "ebench/labutopia_lab_poc/lift2_candidate",
  "stage": "acceptance_stage_7",
  "status": "PASS",
  "run_id": "example_run_id",
  "command": "python standalone_tools/labutopia_poc/example.py",
  "artifact_paths": [],
  "artifact_sha256": {},
  "gate_status": {},
  "allowed_claims": {},
  "blocked_claims": {},
  "verification": []
}
```

`status` 只允许使用：

```text
PASS
FAIL
BLOCKED
WARN
```

`WARN` 只能表示 diagnostic evidence 可用，不能表示验收完成。

## Gate 字段

推荐统一记录这些 gate：

```json
{
  "gate_status": {
    "asset_intake": "PASS",
    "usd_composition": "PASS",
    "material_closure": "BLOCKED",
    "physics_closure": "PASS",
    "articulation_closure": "PASS",
    "task_runtime": "PASS",
    "render_evidence": "WARN",
    "evaluator_robot_contract": "PASS"
  }
}
```

PM 文案只能说对应 `PASS` 的部分。比如 `task_runtime=PASS` 可以说“本地任务链路可评”，但不能推出 `policy_success=true`。

## Material Closure 字段

`material_closure` 必须拆清楚 scoped claim 和 full claim：

```json
{
  "material_closure": {
    "material_status": "mixed_native_and_fallback",
    "remote_unmirrored_unwaived_count": 0,
    "remote_waiver_count": 0,
    "local_mirror_count": 1,
    "fallback_surface_count": 3,
    "dependency_records": [],
    "fallback_surface_records": [],
    "waiver_records": [],
    "aluminum_material_closure_claim_allowed": true,
    "native_material_closure_claim_allowed": false,
    "full_native_material_closure_claim_allowed": false,
    "native_material_closure_reason": "fallback_surfaces_remain_after_aluminum_local_mirror"
  }
}
```

规则：

- 单个 material dependency 已 local mirror，只能升级 scoped claim。
- 只要存在 fallback surface，`full_native_material_closure_claim_allowed` 必须是 `false`。
- hash mismatch、missing texture、stale `/World/Looks` binding、unknown unbound mesh 和 overclaim 都是 FAIL。
- explicit waiver 可以保留资产验收边界，但不能让 full material closure 变成 true。

## PM 文案映射

| Manifest 字段 | PM 可以怎么说 | PM 不能怎么说 |
| --- | --- | --- |
| `task_runtime_ready=true` | 任务能 reset/step/logging，本地链路可评 | 策略已经会做任务 |
| `task_render_accepted=true` | eval camera 能拍到可读任务图 | 官方榜单成绩已复现 |
| `lift2_contract_ready=true` | 本地 Lift2 official-baseline-style contract 通过 | official leaderboard 已发布 |
| `aluminum_material_closure_claim_allowed=true` | Aluminum 远端材质依赖已 local mirror | DryingBox full material closure 已完成 |
| `pm_showcase_ready=false` | 当前图只能作为诊断证据 | 当前图可直接对外展示 |

## 当前 DryingBox 状态示例

```text
Stage 7 local Lift2 contract: PASS
Aluminum local mirror: PASS
full native material closure: BLOCKED by Group/_900_1, button, panel fallback surfaces
policy success: BLOCKED / not evaluated
official leaderboard: BLOCKED / not an official run
```

这说明 DryingBox 当前已经能证明“本地可评链路通过”，但还不能证明“策略成功”“官方成绩发布”或“全资产 native material closure 完成”。
