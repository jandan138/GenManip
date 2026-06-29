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
    "material_closure": "PASS",
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

`material_closure` 必须拆清楚 package-level claim 和 source-native claim：

```json
{
  "material_closure": {
    "material_status": "resolved_material_with_local_overrides",
    "remote_unmirrored_unwaived_count": 0,
    "remote_waiver_count": 0,
    "local_mirror_count": 1,
    "source_resolved_surface_count": 1,
    "wrapper_authored_material_count": 2,
    "fallback_surface_count": 0,
    "dependency_records": [],
    "source_resolved_surface_records": [],
    "authored_material_records": [],
    "fallback_surface_records": [],
    "waiver_records": [],
    "aluminum_material_closure_claim_allowed": true,
    "full_material_closure_claim_allowed": true,
    "native_material_closure_claim_allowed": false,
    "full_native_material_closure_claim_allowed": false,
    "native_material_closure_reason": "wrapper_local_material_overrides_present",
    "native_material_provenance": {
      "schema_version": 1,
      "status": "blocked_by_wrapper_local_overrides",
      "source_native_blocker_surface_count": 2,
      "native_wrapper_override_surface_count": 2,
      "native_claim_blocker_records": [
        {
          "source_prim_path": "/World/DryingBox_01/Group/_900_1",
          "runtime_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Group/_900_1",
          "source_binding_status": "empty_authored_binding_in_stage2_source_readback",
          "source_material_binding": null,
          "runtime_material_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/task_indicator_mat",
          "replacement_required_for_full_native_closure": true,
          "blocked_claims": ["native_material_closure", "full_native_material_closure"]
        },
        {
          "source_prim_path": "/World/DryingBox_01/button",
          "runtime_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/button",
          "source_binding_status": "unbound_in_stage2_source_readback",
          "source_material_binding": null,
          "runtime_material_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/task_button_mat",
          "replacement_required_for_full_native_closure": true,
          "blocked_claims": ["native_material_closure", "full_native_material_closure"]
        }
      ]
    }
  }
}
```

规则：

- 单个 material dependency 已 local mirror，只能升级 scoped dependency claim。
- 当 runtime `fallback_surface_count=0`，且 wrapper-local override 已显式记录时，`full_material_closure_claim_allowed` 可以是 `true`，表示 EBench package material gate 已通过。
- 只要存在 wrapper-local authored material，`full_native_material_closure_claim_allowed` 必须是 `false`。
- `native_material_provenance` 是 source-native claim 的刹车字段：它说明哪些 wrapper-local material override 还没有 source-native `material:binding` 证据，且每条 blocker 必须写清 source path、runtime path、runtime material path、source binding status 和 blocked claims。
- hash mismatch、missing texture、stale `/World/Looks` binding、unknown unbound mesh 和 overclaim 都是 FAIL。
- explicit waiver 可以保留资产验收边界，但不能让 package material closure 或 native material closure 自动变成 true。
- `primvars:displayColor` 不自动等于 fallback；有有效 `material:binding` 时只算 authored auxiliary color，只有 fallback-only surface 才计入 `fallback_surface_count`。

Reusable validator boundary:

- New assets should construct `MaterialClosureExpectation` instead of copy/pasting DryingBox assertions; the expectation includes material status, claim flags, forbidden claims, native provenance status, and blocker paths.
- `NativeMaterialProvenanceBlocker` records are the reusable unit for surfaces that have package-visible wrapper material but cannot claim source-native material binding.
- Asset-specific validators may still add package checks for source files, physics reports, camera contracts, or task semantics.

Offline dependency record checklist:

- Runtime path fields must be package-relative, `{ASSETS_DIR}`-relative, or under an explicit staged overlay root.
- Configured runtime path fields must resolve to files that actually exist; a missing `{ASSETS_DIR}/...` file or slashless `does_not_exist.mdl` value is a validation failure even if the path syntax is under an allowed root.
- Remote URI checks are case-insensitive, so `HTTPS://...` is rejected the same way as `https://...`.
- For source-scene copied records, `relative_path` is relative to the staged source scene directory, for example `overlay_root / scene_usds/labutopia/level1_poc/lab_001`, not necessarily the overlay asset root itself.
- `static_material_dependency_gate.remote_dependency_records`, `material_dependency_report`, nested `texture_dependency_records`, and `helper_mdl_imports` should all go through the reusable offline dependency validator when they claim local runtime closure.
- `source_url` is provenance only; it cannot be the runtime dependency path.
- Package-local and source-scene copied files must record SHA256 and byte count, and validators must reject hash or byte drift.
- Any record claiming local runtime closure must include at least one local path field, such as `local_mirror_path` or `relative_path`.
- `explicit_waiver` may explain an open dependency, but it cannot allow package/full/native closure claims by itself.
- Offline dependency pass does not upgrade native material closure, official leaderboard, policy success, or PM showcase claims.

## Cold Runtime Sandbox Probe 字段

`cold_runtime_sandbox_probe` 记录 copied package 在冷目录里的最小 runtime compose 结果：

```json
{
  "status": "PASS",
  "mode": "pxr-compose",
  "sandbox": {
    "network_isolation_mode": "best_effort_env_and_resolved_dependency_probe"
  },
  "environment": {
    "non_allowlisted_search_path_count": 0
  },
  "runtime": {
    "remote_uri_count": 0,
    "user_cache_path_count": 0,
    "unauthorized_outside_sandbox_runtime_path_count": 0,
    "allowlisted_builtin_runtime_path_count": 0,
    "missing_required_prim_paths": []
  },
  "claim_boundary": {
    "cold_runtime_sandbox_probe_passed": true,
    "official_leaderboard_claim_allowed": false,
    "policy_success_claim_allowed": false,
    "pm_showcase_ready": false,
    "native_material_closure_claim_allowed": false,
    "full_native_material_closure_claim_allowed": false
  }
}
```

PM 可以说：复制到冷目录后，解析到的 runtime dependency 没有回源到原始 `/cpfs`、公网 URI 或用户 cache。PM 不能说：这已经是系统级断网证明，或 official/policy/render showcase 已完成。

Source scene payload sanitization 是 cold runtime probe 的常见配套修复。即使 wrapper layer 已经有本地 material override，dependency scanner 仍会递归读取 payload 进来的 source layer；如果 source layer 里还留着 remote `info:mdl:sourceAsset`、remote `payload` 或 remote `reference`，cold runtime 仍会失败。DryingBox 的当前处理是：

- `Aluminum_Anodized_Charcoal.mdl`: rewrite to package-local mirror under `miscs/mdl/labutopia/mdl`.
- `Steel_Stainless.mdl`: rewrite to existing `SubUSDs/materials/Steel_Stainless.mdl`.
- `Stainless_Steel.mdl`: rewrite to a generated local shim derived from `Steel_Stainless.mdl`, only for runtime dependency closure.
- remote Sektion cabinet payload: removed from copied source layer because it is not task-critical for `level1_open_door`.

PM 可以说：DryingBox copied package 的 runtime dependency 已经闭环，cold runtime probe 没有看到 remote URI。PM 不能说：`Stainless_Steel.mdl` 已经恢复成原始 remote vMaterials 的视觉等价材质，或 `full_native_material_closure_claim_allowed=true`。

## PM 文案映射

| Manifest 字段 | PM 可以怎么说 | PM 不能怎么说 |
| --- | --- | --- |
| `task_runtime_ready=true` | 任务能 reset/step/logging，本地链路可评 | 策略已经会做任务 |
| `task_render_accepted=true` | eval camera 能拍到可读任务图 | 官方榜单成绩已复现 |
| `lift2_contract_ready=true` | 本地 Lift2 official-baseline-style contract 通过 | official leaderboard 已发布 |
| `aluminum_material_closure_claim_allowed=true` | Aluminum 远端材质依赖已 local mirror | DryingBox 全部 native 材质已恢复 |
| `full_material_closure_claim_allowed=true` | EBench package material gate 已通过 | source-native full material closure 已完成 |
| `cold_runtime_sandbox_probe_passed=true` | copied package 在冷目录 compose 时没有 remote URI 或缺失本地依赖 | official leaderboard、policy success 或 PM showcase 已完成 |
| `full_native_material_closure_claim_allowed=false` | 仍不能宣称 source-native 全闭环 | 把它解读为 package material gate 未通过 |
| `pm_showcase_ready=false` | 当前图只能作为诊断证据 | 当前图可直接对外展示 |

## 当前 DryingBox 状态示例

```text
Stage 7 local Lift2 contract: PASS
Aluminum local mirror: PASS
EBench package material closure: PASS
full native material closure: BLOCKED by wrapper-local button and Group/_900_1 materials
native material provenance: BLOCKED by /World/DryingBox_01/button and /World/DryingBox_01/Group/_900_1
policy success: BLOCKED / not evaluated
official leaderboard: BLOCKED / not an official run
```

这说明 DryingBox 当前已经能证明“本地可评链路通过”和“包级材质闭环通过”，但还不能证明“策略成功”“官方成绩发布”或“source-native 全材质闭环完成”。PM 汇报时可以说 package material gate 通过，不能把 `button` 和 `Group/_900_1` 的 wrapper-local `PreviewSurface` 说成原生材质已恢复。
