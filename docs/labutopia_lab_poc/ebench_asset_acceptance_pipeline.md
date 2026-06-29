# EBench Asset Acceptance Pipeline

## 一句话结论

`Package Material Closure / Aluminum Local Mirror follow-up` 完成后，应沉淀为一套通用的 `EBench Asset Acceptance Pipeline`。以后 LabUtopia 或外部资产进入 EBench，不再靠“看起来能加载”判断，而是按 asset、USD composition、material、physics、articulation、task runtime 和 render evidence 七类 gate 签收。

这套流程的口径是：**不是写了流程就保证所有资产正常，而是资产只有通过这些 gate，才允许声明 `EBench-ready`。**

## 给产品经理的通俗解释

可以把资产进入 EBench 理解成“把一个真实实验室物件搬进评测工厂”。搬进去不只要看见它，还要确认：

- 文件齐不齐：USD、MDL、texture、payload、reference 不能临时去公网找。
- 放得对不对：坐标、scale、root prim、wrapper path 不能错。
- 材质对不对：不能只靠 fallback displayColor 假装有颜色。
- 物理稳不稳：不能飞、倒、穿模、抖动。
- 关节准不准：门、抽屉、按钮的 joint、axis、limit、drive 和 metric 不能读错。
- 任务能不能跑：reset、step、observation、camera、metric、result logging 必须闭环。
- 图能不能验：最终要看 evaluator camera，不只看 Isaac viewer。

DryingBox 是第一套模板：我们已经证明 native complex `DryingBox_01` 能进入 EBench，door `RevoluteJoint` metric 可读，Lift2 local contract 可评，Aluminum remote material 已 local mirror，runtime material readback 中真正 `fallback_only` surface 已降为 0。当前它已经可以作为 EBench package-level reference asset；但 `button` 和 `Group/_900_1` 仍是 wrapper-local authored material，所以还不能宣称 source-native full material closure。

更通俗地说：DryingBox 的 package material gate 已通过，因为所有 remote material dependency 已本地化、runtime fallback-only surface 为 0，并且 wrapper-local material override 已显式记录。DryingBox 的 source-native full material closure 仍未通过，因为 `button` 和 `Group/_900_1` 在原生 USD 中没有可恢复的有效 `material:binding`；我们保留 wrapper-local `PreviewSurface` 是为了任务可读性，不把它包装成 native claim。

## 术语边界：Gate 和 Acceptance Stage 不是一回事

后续所有文档和代码统一使用这两个概念：

- `Gate` 是“能不能宣称”的质量分类。例如 `Gate 7: Render Evidence Gate` 只回答图像证据能不能对 PM 或工程验收负责。
- `Acceptance Stage` 是“工程执行顺序”的里程碑。例如 `Stage 7: Evaluator Robot Contract` 只回答本地 Lift2 official-baseline-style contract 是否可评。
- Gate 编号和 Stage 编号不一一对应。`Stage 7 passed` 不等于 `Render Evidence Gate` 已变成 showcase-ready，也不等于 official leaderboard 或 policy success。
- Stage 5 的 eval-path 图是机器诊断证据；最终图片能不能对 PM 展示，仍由 `render_evidence` gate 和 `pm_showcase_ready` claim boundary 决定。

机器可读落地已经完成：

- `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json` 中的 `asset_acceptance.acceptance_stages` 记录 Stage 0-4 的资产包接入证据。
- `docs/labutopia_lab_poc/evidence_manifests/dryingbox_asset_acceptance_20260629_asset_acceptance_manual.json` 中的 `acceptance_stages` 汇总 Stage 0-7 的最终证据、状态、artifact paths、hash 和 claim boundary。
- `gate_status` 继续保留，作为老字段和 PM claim summary；它不替代 `acceptance_stages`。
- `blocked_claims` 是历史兼容字段，里面的布尔值仍表示 `claim_allowed`；新消费者应读取 `claim_boundary.blocked_claim_status.*.blocked`，避免把 `false` 误解成“不阻塞”。

## 多 agent 评审后的统一口径

三路评审把这套流程收敛成一句话：

```text
EBench Asset Acceptance Pipeline 不是模型拿分流水线，而是一套把外部
asset package 验收到 GenManip/EBench 可评链路里的 evidence-gated workflow。
每个 Gate 只允许升级对应的 Claim Boundary；没有 evidence manifest，就不能
把状态写成完成。
```

给实习生执行时的规则更简单：

```text
不要先写完成了。先补 run_id、command、artifact path、manifest 字段、
PASS/FAIL/BLOCKED、allowed claims 和 blocked claims。PM 周报只引用
evidence manifest 已经证明的结论；diagnostic/WARN 只能写成诊断证据，
不能写成验收完成。
```

## Gate 总览

| Gate | 解决的问题 | 通过后能说什么 | 不能说什么 |
| --- | --- | --- | --- |
| 1. `Asset Intake Gate` | 资产和依赖是否登记完整 | 资产包输入完整、来源清楚 | 不能说已经能渲染或可评 |
| 2. `USD Composition Gate` | USD 在 EBench wrapper 下是否正确 compose | runtime prim path、scale、payload/reference 可解析 | 不能说物理或材质已经闭环 |
| 3. `Material Closure Gate` | MDL/texture/material binding 是否本地闭合 | package/native material claim 必须按 derived flags 分开声明 | 不能把 package material gate pass 说成 source-native full closure |
| 4. `Physics Closure Gate` | mass、inertia、collision、contact 是否稳定 | reset 后物理状态有限、稳定 | 不能说 articulated task metric 已正确 |
| 5. `Articulation Closure Gate` | joint/axis/limit/drive/metric 是否正确 | 门/抽屉/按钮等 articulated object 可被任务读写 | 不能说策略能完成任务 |
| 6. `Task Runtime Gate` | EBench task 是否能 reset/step/logging | 本地任务链路可评 | 不能说 official leaderboard 或 policy success |
| 7. `Render Evidence Gate` | evaluator camera 图是否可读 | PM 和工程都能用图验收任务目标 | 不能用 polished viewer 图替代 eval-path evidence |

工程执行时建议保留一个 `Stage 0` 作为声明阶段，后面 1-7 才是验收阶段。这样不会破坏现有周报里 `Acceptance Stage 1-7` 的口径，同时能避免“还没声明资产合同就开始跑任务”的混乱。

| Stage | 名称 | 要完成的事情 | 当前 DryingBox 对应状态 |
| --- | --- | --- | --- |
| 0 | `Asset Contract Declaration` | 声明 `source_prim_path`、`wrapper_prim_path`、task roles、camera、metric DOF、material policy | 已抽成 `acceptance_stages` schema |
| 1 | `Static USD/Physics Audit` | 只读 source USD，盘点 hierarchy、API schema、rigid bodies、joints、mass/inertia、material binding | 已完成 DryingBox audit |
| 2 | `Isolated Native Physics Smoke` | 不进 EBench，单独跑 Isaac，确认 root/handle/joint 有限稳定 | 已完成 native-only smoke |
| 3 | `EBench Wrapper Composition` | 生成 wrapper，保留 native payload，校验 object map、nested handle、wrapper-local material binding | 已完成 native wrapper |
| 4 | `Additive Physics + Articulation Override` | 只用 additive layer 修 fixed base、joint target、inertia、collision、reset target | 已完成 DryingBox override |
| 5 | `Task Runtime + Eval Readback` | task 能 reset/step、metric/logging/result 写出，eval camera 能读图 | Franka/native open_door 已通过 |
| 6 | `Evidence Package + Claim Boundary` | 生成 manifest、frame hash、allowed/blocked claims，避免过度汇报 | 已有 acceptance manifest |
| 7 | `Evaluator Robot Contract` | Lift2 official-baseline-style lane 的 observation/camera/action/reward/logging 全 PASS | 本地 Lift2 contract 已 PASS |

## Gate 1: Asset Intake Gate

目标：资产进入 EBench 前，先把“有什么文件、来自哪里、运行时怎么找”说清楚。

Required evidence:

```text
asset_uid
asset_family
source_repo_or_dataset
source_usd_path
package_relative_usd_path
payload_paths
reference_paths
mdl_paths
texture_paths
external_uri_count
remote_dependency_records
source_license_or_policy
```

Pass condition:

- 所有 USD、payload、reference、MDL、texture 都有 package-relative path。
- 远端依赖必须二选一：`local_mirror` 或 `explicit_waiver`。
- `explicit_waiver` 必须有 waiver id、reason、owner 和关闭计划。

Cold/offline package validation 当前指静态依赖闭环：已知 runtime MDL、texture、package-local records 必须能在 package root 或 staged overlay root 下找到，SHA256/bytes 必须匹配，runtime path 不能指向公网、S3、`omniverse://` 或用户 cache。它还不是 network-blocked Isaac sandbox run；sandbox run 应在静态依赖闭环稳定后作为后续阶段补上。

DryingBox 当前对应状态：

```text
Aluminum_Anodized_Charcoal.mdl: local_mirror
Aluminum_Anodized textures: local_mirror
panel: source-resolved by native GeomSubset material binding
button, Group/_900_1: wrapper-local PreviewSurface material overrides
runtime fallback_only surfaces: 0
full native material closure: blocked by wrapper-local overrides
```

## Gate 2: USD Composition Gate

目标：确认资产在 EBench runtime wrapper 里真的 compose 成预期的 scene，而不是路径看起来存在但 runtime 下丢层级、丢 payload 或 scale 错。

Required checks:

```text
root_prim_exists=true
runtime_prim_path_exists=true
payload_reference_resolved=true
root_scale_is_expected=true
wrapper_local_looks_scope_exists=true
runtime_object_key_mapped=true
task_object_center_in_workspace=true
```

Typical commands:

```bash
python standalone_tools/labutopia_poc/build_asset_overlay.py --drying-box-strategy native_complex
python standalone_tools/labutopia_poc/validate_task_package.py
```

Pass condition:

- `scene.usda` can be generated deterministically.
- `assets_manifest.json` records source-to-runtime object mapping.
- Runtime object keys match evaluator expectations.
- Static bounds/center are in robot workspace.

## Gate 3: Material Closure Gate

目标：材质不能只靠“有颜色”过关。必须判断 native material binding、MDL、texture、wrapper-local override、`GeomSubset` 覆盖和真正 fallback-only surfaces。

注意：`primvars:displayColor` 本身不等于 fallback。很多 source USD 会同时保留 `displayColor` 和有效 `material:binding`。只有满足“没有有效 bound material、也没有 `GeomSubset` 或其他 source-resolved 证据、最终靠 `displayColor` 才能显示”的 surface，才计入 `fallback_surface_count`。

推荐拆成 6 个 material 子门禁：

| 子门禁 | 通过条件 |
| --- | --- |
| `material_dependency_inventory` | 静态扫描 USD material binding、MDL source asset、MDL import 和 texture reference |
| `local_mirror_resolution` | 每个本地 mirror 都有 package-relative path、bytes、SHA256、texture hash 和 `MDL_SYSTEM_PATH` 覆盖 |
| `runtime_binding_resolution` | composed runtime USD 里 `ComputeBoundMaterial` 不指向 stale `/World/Looks`，也不丢绑定 |
| `source_resolved_surface_inventory` | 父 prim 没有 direct material 时，必须证明子 `GeomSubset` 覆盖完整 |
| `wrapper_local_override_inventory` | wrapper-local material 必须记录 source status、runtime path、reason，且不能升级为 native claim |
| `fallback_surface_inventory` | 只有 fallback-only mesh 才计入 fallback；有 bound material 的 `displayColor` 只算辅助 authored color |
| `claim_derivation` | claim flags 只能由证据字段派生，不能手写成 true |
| `evidence_manifest_consistency` | generator manifest、validator summary、docs manifest 的 count/blocker/claim 一致 |

Implementation rule: generic material shape checks live in `asset_acceptance_validation.py`. Asset-specific validators pass a `MaterialClosureExpectation` that includes expected claim flags and native provenance status; they should not reimplement provenance blocker path/count/status checks by hand.

Offline dependency rule: package-local MDL/texture records, source-scene copied MDL/texture records, helper MDL imports, and `static_material_dependency_gate.remote_dependency_records` use `offline_package_validation.py` for reusable local-file, SHA256, byte-count, remote URI, allowed-root, and waiver-claim checks. Configured runtime path fields must resolve under the packaged `common/` root, the asset overlay root, or an explicit staged scene root such as `overlay_root / scene_usds/.../lab_001`, and must point to files that actually exist. Asset-specific validators still own exact expected material names, expected texture sets, and task-specific claim boundaries.

Material states:

```text
resolved_native_material
resolved_material_with_local_overrides
mixed_native_and_fallback
local_mirror
explicit_waiver
fallback_display_color
missing_binding
```

Required machine fields:

```text
material_status
remote_only_dependency_count
remote_unmirrored_unwaived_count
waiver_count
local_mirror_count
closure_claim_allowed
full_material_closure_claim_allowed
aluminum_material_closure_claim_allowed
native_material_closure_claim_allowed
full_native_material_closure_claim_allowed
native_material_closure_reason
native_material_provenance
source_resolved_surface_records
authored_material_records
fallback_surface_records
material_binding_records
texture_dependency_records
worker_mdl_system_path
```

Recommended machine object:

```json
{
  "asset_acceptance": {
    "acceptance_stages_schema_version": 1,
    "acceptance_stages": [
      {
        "stage_index": 0,
        "stage_id": "asset_contract_declaration",
        "stage_name": "Asset Contract Declaration",
        "status": "PASS",
        "evidence": {
          "source_prim_path": "/World/DryingBox_01",
          "wrapper_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
          "primary_evidence_camera": "camera2",
          "metric_joint_name": "RevoluteJoint",
          "material_policy": "owned_world_looks_payload_with_wrapper_local_rebind_and_local_overrides"
        }
      }
    ],
    "material_closure": {
      "schema_version": 1,
      "asset_id": "LabUtopia/DryingBox_01",
      "closure_level": "package_material_closed_with_local_overrides",
      "material_status": "resolved_material_with_local_overrides",
      "claim_scope": ["dependency:Aluminum_Anodized_Charcoal", "asset_package:DryingBox_01"],
      "dependency_records": [],
      "binding_summary": {},
      "source_resolved_surface_records": [],
      "authored_material_records": [],
      "fallback_surface_records": [],
      "waiver_records": [],
      "derived_counts": {
        "remote_unmirrored_unwaived_count": 0,
        "local_mirror_count": 1,
        "source_resolved_surface_count": 1,
        "wrapper_authored_material_count": 2,
        "fallback_surface_count": 0
      },
      "full_material_closure_claim_allowed": true,
      "full_native_material_closure_claim_allowed": false,
      "forbidden_claims": ["full_native_material_closure"]
    }
  }
}
```

Claim policy:

- 单个材质依赖关闭时，只能说 `aluminum_material_closure_claim_allowed=true` 这类 scoped claim。
- 当所有 remote dependency 已 local mirror/waiver 管理，runtime 没有 fallback-only surface，并且 wrapper-local override 均显式记录时，允许 `full_material_closure_claim_allowed=true`，表示 EBench package material gate 可过。
- 全资产所有可见 surface 都恢复为 source-native material binding、MDL 和 texture 后，才允许 `full_native_material_closure_claim_allowed=true`。
- overclaim 是非豁免错误：如果还有 fallback-only surface，任何 manifest 或文档把 package/full closure 写成 true，都必须 fail。
- `native_material_provenance` 记录为什么 native claim 还不能升级；validator 会检查 blocker count、source/runtime path、runtime material path、`source_binding_status`、`source_material_binding=null` 和 `blocked_claims`。
- 只要存在 wrapper-local authored material，就必须保持：

```text
native_material_closure_claim_allowed=false
full_native_material_closure_claim_allowed=false
```

DryingBox current material closure:

```text
Aluminum_Anodized_Charcoal -> local_mirror
panel -> native GeomSubset material binding covers all faces
Group/_900_1 -> wrapper-local task_indicator_mat
button -> wrapper-local task_button_mat
runtime fallback_only surface count -> 0
full_material_closure_claim_allowed -> true
full_native_material_closure_claim_allowed -> false
native_material_provenance.status -> blocked_by_wrapper_local_overrides
native_material_provenance.blockers -> Group/_900_1, button
```

## Gate 4: Physics Closure Gate

目标：资产不能只在 viewer 里看着正常，还要进入 EBench reset 后稳定。

Required checks:

```text
fixed_base_policy
mass_records
inertia_records
collision_approximation
gravity_enabled_policy
contact_with_table
reset_pose_finite
post_reset_velocity_finite
no_exploding_transform
no_table_penetration
```

Pass condition:

- reset 后 root transform、joint state、velocity 都有限。
- asset 不飞、不倒、不穿桌、不无限抖动。
- physics override 是 additive layer，并记录原始值和 after 值。

Fail condition:

- 缺失或重复 `PhysicsScene`。
- 任务相关 body 没有 `RigidBodyAPI` 或 collision。
- mass/inertia 非正数，COM/principal axes 无效。
- joint `body0/body1` 指向不存在或非 rigid body 的 prim。
- root/handle drift 不受控，或出现未分类 PhysX warning。
- runtime material binding 未解析，且没有可读性证据或 waiver。

DryingBox 当前对应状态：

```text
runtime_physics_stable=true
additive physics override exists
native_eval_readback_ready=true
```

## Gate 5: Articulation Closure Gate

目标：门、抽屉、按钮、旋钮等 articulated object 必须确认 joint 语义，而不是只看视觉。

Required checks:

```text
joint_path
joint_type
joint_axis
joint_limit_lower
joint_limit_upper
drive_target
initial_joint_state
metric_joint_name
ignored_dofs
task_relevant_dof_count
```

Pass condition:

- 任务 metric 读的是正确 joint。
- 非任务 DOF 被明确 ignore 或 lock。
- open/close 初始状态可复现。
- reset 后 joint 不爆值。

Fail condition:

- 缺失 `ArticulationRootAPI`。
- active DOF 不明确，或 metric 指向了错误 joint。
- target position 与 reset 后读数偏差超过 `1e-3`。
- nested handle path 缺失。
- 把辅助 `PrismaticJoint` 当成 open-door 任务成功 DOF。

DryingBox 当前对应状态：

```text
metric_reads_door_revolute_joint=true
ignored_dof=button PrismaticJoint
open_door metric reads RevoluteJoint, not PrismaticJoint
```

## Gate 6: Task Runtime Gate

目标：资产进入真实 EBench task 后，必须能完成 reset、step、observation、camera、metric、result logging。

Required checks:

```text
reset_reachable
step_reachable
observation_schema_pass
camera_schema_pass
action_schema_pass
reward_success_fields_pass
metric_logging_pass
result_info_written
result_json_written
run_id_isolated
port_isolated
```

Pass condition:

- 每个 task 都能 reset/step。
- `result_info.json` 和 `result.json` 正常写出。
- live probe 能读到 observation、camera、action、reward/success、logging schema。
- 和其他工程师或 EOS 任务 run_id/port/worktree 隔离。

Fail condition:

- reset 或 step 没返回可用 observation。
- action schema 与 robot contract 不匹配。
- metric、reward/success 或 result logging 缺字段。
- 出现 `non_finite_arm_state` 这类无效终止，却被写成任务完成。

Boundary:

```text
task_runtime_ready=true
policy_success_claim_allowed=false
official_leaderboard_claim_allowed=false
```

## Gate 7: Render Evidence Gate

目标：最终验收图必须来自 evaluator camera readback，而不是只看 Isaac viewer 或手工展示截图。

Required evidence:

```text
evaluator_camera_name
frame_path
frame_sha256
rgb_min
rgb_max
rgb_mean
render_validation_passed
task_render_accepted
visual_review_status
pm_showcase_ready
```

Pass condition:

- 图不是黑屏。
- 任务目标可读。
- 关键 affordance 可见，比如 handle、door panel、target tray。
- 若视觉审阅是 `WARN`，只能作为 diagnostic evidence，不能作为 polished PM showcase。

Fail condition:

- 黑屏、低纹理、required object missing 或 severe clipping。
- 缺 frame SHA256、run_id、seed、episode id 或 camera config。
- 只提供 Isaac viewer/direct-render 截图，没有 evaluator camera readback。
- scene-readback fallback 没有对应 on-camera RGB 证据。

## 统一 Claim Boundary

任何 asset acceptance record 都必须带下面这些字段，防止对 PM 或论文叙述过度承诺：

```json
{
  "schema_version": 1,
  "asset_id": "LabUtopia/DryingBox_01",
  "task_lane": "ebench/labutopia_lab_poc/lift2_candidate",
  "gate_status": {
    "asset_intake": "PASS",
    "usd_composition": "PASS",
    "material_closure": "PASS",
    "physics_closure": "PASS",
    "articulation_closure": "PASS",
    "task_runtime": "PASS",
    "render_evidence": "WARN",
    "evaluator_robot_contract": "PASS"
  },
  "acceptance_stages_schema_version": 1,
  "acceptance_stages": [
    {
      "stage_index": 5,
      "stage_id": "task_runtime_eval_readback",
      "status": "PASS",
      "gate_keys": ["task_runtime", "render_evidence"],
      "evidence": {
        "native_eval_readback_ready": true,
        "task_render_accepted": true,
        "render_evidence_gate_status": "WARN"
      }
    },
    {
      "stage_index": 6,
      "stage_id": "evidence_package_claim_boundary",
      "status": "WARN",
      "evidence": {
        "allowed_claims": {},
        "blocked_claims": {}
      }
    }
  ],
  "allowed_claims": {
    "ebench_asset_ready": false,
    "task_runtime_ready": true,
    "task_render_accepted": true,
    "full_material_closure_claim_allowed": true,
    "lift2_contract_ready": true,
    "local_official_baseline_style_contract_ready": true
  },
  "blocked_claims": {
    "native_material_closure_claim_allowed": false,
    "full_native_material_closure_claim_allowed": false,
    "official_baseline_evaluable": false,
    "official_leaderboard_claim_allowed": false,
    "policy_success_claim_allowed": false,
    "pm_showcase_ready": false
  },
  "claim_boundary": {
    "blocked_claim_status": {
      "pm_showcase_ready": {
        "claim_allowed": false,
        "blocked": true
      }
    }
  }
}
```

推荐解释：

```text
EBench-ready means the asset passed local package, runtime, material, physics,
articulation, task, and render gates for a named task lane. It does not mean
official leaderboard reproduction or policy success unless those gates are
separately run and recorded.
```

## 对 DryingBox 的落地顺序

1. 先把 material report 扩展成通用 schema：不再只服务 Aluminum，而是覆盖任意 asset 的 MDL/texture/material binding、`GeomSubset`、wrapper-local override 和 fallback-only surface。
2. 完成 DryingBox package material closure：Aluminum local mirror、`panel` source-resolved、`Group/_900_1` 和 `button` wrapper-local material override，runtime `fallback_surface_count=0`。
3. 把 `native_material_provenance` blocker 写进 manifest，并用 `asset_acceptance_validation.py` 的 `MaterialClosureExpectation` 统一校验 blocker count、path、binding status 和 blocked claims。
4. 增加 cold/offline package validation：验证不依赖公网和缓存。
5. 对 DryingBox 重新跑 evaluator camera readback，产出 diagnostic image；如需对外展示，再单独补拍 PM-facing image 并通过 `pm_showcase_ready` 边界。
6. 生成 `asset_acceptance_record.json`，把 Stage 0-7 的状态、hash、allowed claims 和 blocked claims 汇总到 `acceptance_stages`，同时保留 `gate_status` 作为兼容摘要。
7. 将 DryingBox 作为第一个 `EBench Asset Acceptance Pipeline` reference asset；source-native full material closure 如有需要，作为独立 provenance follow-up 推进。

## 后续产物

| 产物 | 用途 |
| --- | --- |
| `asset_acceptance_record.json` | 每个资产的机器可读验收总表 |
| `material_closure_report.json` | MDL/texture/material binding/fallback/waiver 证据 |
| `physics_closure_report.json` | mass/inertia/collision/reset stability 证据 |
| `articulation_closure_report.json` | joint/axis/limit/metric 证据 |
| `task_runtime_report.json` | reset/step/observation/camera/result logging 证据 |
| `render_evidence_report.json` | evaluator camera frame/hash/visual review 证据 |
| PM-facing HTML section | 用通俗语言解释资产是否真的可交付 |

## 验收记录写法

每次推进一个资产，都应该先生成机器证据，再写 PM 汇报。推荐顺序：

```text
1. 写清 asset_id、task_lane、run_id 和 isolated port/worktree。
2. 记录 command、artifact path、SHA256、PASS/FAIL/BLOCKED。
3. 由 validator 生成 allowed_claims 和 blocked_claims。
4. PM 文案只引用 allowed_claims；blocked_claims 必须保留在边界说明里。
5. diagnostic/WARN 图可以放进证据，但不能标成 polished showcase。
```

## 不允许的表述

- 不能因为 task 能 reset/step 就说 material closure 完成。
- 不能因为 EBench package material closure 完成就说 source-native full material closure 完成。
- 不能因为 local Lift2 contract 通过就说 official leaderboard 复现。
- 不能用 viewer screenshot 替代 evaluator camera evidence。
- 不能把 `score=0.0` 解释成 asset gate 失败；它通常是 policy/controller 结果。

## 当前推荐下一步

DryingBox 已经可以作为第一个 reference acceptance package。下一步把这套 pipeline 的 schema 和 validator helpers 从 DryingBox 专项抽成通用资产入口；真实 Lift2 baseline/policy gate 单独推进。source-native full material closure 不是 package gate blocker，后续只有在需要升级 `full_native_material_closure_claim_allowed=true` 时，才继续做真实 native binding replacement。
