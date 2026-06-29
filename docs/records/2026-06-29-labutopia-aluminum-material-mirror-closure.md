# 2026-06-29 LabUtopia Aluminum Material Mirror Closure

## 一句话结论

`Aluminum_Anodized_Charcoal.mdl` 已从 remote dependency / explicit waiver 改成 package-local mirror。这个 follow-up 关闭的是 Aluminum 这一项远端材质依赖，不改变 Stage 7 Lift2 contract，也不代表 full native MDL/texture material closure 已完成。

## 给产品经理的通俗解释

之前 `DryingBox_01` 有一个金属材质不在我们的 EBench package 里。运行时如果要完整解析它，需要去 Omniverse/S3 远端拿 `Aluminum_Anodized_Charcoal.mdl`。Stage 7 当时允许它用 explicit waiver 通过，因为 Stage 7 验的是任务能不能 reset、step、读 camera/observation/action、写 reward/metric/logging，而不是验所有材质是否离线闭合。

现在我们把这个远端材质和它引用的三张 texture 放进了任务包：

```text
miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl
miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_BaseColor.png
miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_Normal.png
miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_ORM.png
```

同时 runtime wrapper 里对 Aluminum Shader 加了本地 `info:mdl:sourceAsset = @Aluminum_Anodized_Charcoal.mdl@` override。worker 的 `MDL_SYSTEM_PATH` 已经包含 `{ASSETS_DIR}/miscs/mdl/labutopia/mdl`，所以本地 worker 可以从 package 里解析这个材质，不需要临时去公网拿这个 MDL。

## 当前边界

| 项目 | 状态 | 边界 |
| --- | --- | --- |
| Stage 7 Lift2 contract | 已通过 | 证明本地 `lift2_candidate` lane 能 reset/step/readback/logging；不等于 official leaderboard 成绩 |
| Aluminum material mirror | 已完成 | 关闭 `Aluminum_Anodized_Charcoal.mdl` remote waiver；不改变任务分数或 policy 能力 |
| Full native material closure | 未完成 | `Group/_900_1`、`button`、`panel` 仍有 fallback displayColor，需要后续 native binding 修复 |
| 官方 baseline 成绩 | 未发布 | 当前 `score=0.0` 是策略/动作结果，不是材质 mirror 能解决的问题 |

## 机器证据

```text
docs/labutopia_lab_poc/evidence_manifests/aluminum_material_mirror_closure_20260629_045413.json
configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json
```

关键字段：

```text
remote_aluminum_disposition=local_mirror
remote_only_dependency_count=0
waiver_count=0
closure_claim_allowed=false
aluminum_material_closure_claim_allowed=true
native_material_closure_claim_allowed=false
full_native_material_closure_claim_allowed=false
native_material_closure_reason=fallback_surfaces_remain_after_aluminum_local_mirror
```

## 验证命令

```text
python -m pytest tests/labutopia_poc/test_build_asset_overlay.py tests/labutopia_poc/test_validate_task_package.py -q
python -m pytest tests/labutopia_poc/test_render_diagnostics_contract.py tests/labutopia_poc/test_lift2_eval_contract_probe.py -q
```

当前结果分别为 `50 passed` 和 `56 passed`。
