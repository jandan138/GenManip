# 2026-06-22 LabUtopia EBench 接入周报

HTML 版产品汇报页：
`docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html`

## 一句话进展

本周已经把 LabUtopia 的 Franka POC 跑通到端到端 smoke 阶段：任务可以提交、场景可以加载、三个 level-1 任务可以 reset/step、结果可以落盘、最终状态可以正常 complete。

这说明当前最关键的“接入链路”已经打通。需要注意的是，这还不是任务求解成功，也不是官方 baseline 成绩；当前 smoke 使用默认动作，所以三个任务分数都是 `0.0`。2026-06-23 到 2026-06-24 最新复核补充：三任务现在都能通过 EBench/evaluator 正常读回非黑渲染图，资产静态坐标也已经从“明显导错”修到合理工作区；最新正式诊断中 `pick`、`place`、`open_door` 均为 `render_validation.passed=true`、`task_render_accepted=true`。P2 又把 `open_door` 从 P1 `sanitized_surrogate` 对照组推进到 LabUtopia native complex `DryingBox_01`：原生 visual/hierarchy/nested handle 保留，wrapper-local `Looks` 和 native `material:binding` 已重连，retake 图中蓝色门、白色侧面、把手、观察窗和控制面板可见，`native_complex_dryingbox_ready=true`。

2026-06-28 Stage 5/6 补充：原生 `DryingBox_01` 已通过 EBench/GenManip Franka/native `open_door` eval-path readback，`native_eval_readback_ready=true`、`eval_step_contract.passed=true`，metric 明确读取门的 `RevoluteJoint` 而不是按钮 `PrismaticJoint`。Stage 5 图可以作为机器诊断证据，但独立视觉审阅是 `WARN`，不是 showcase-ready 图片。当时材质边界仍是 `native_material_closure_status=open_remote_dependency_waived`；这个历史边界已在 2026-06-29 material follow-up 中升级为 package material closure pass，但 full native MDL/texture material closure 仍不能声明。

2026-06-29 Stage 7 补充：Lift2 official-baseline-style contract check 已通过本地合同验证。我们先把官方/default `robot_usds/lift2`、`miscs/curobo/R5a` 和 LabUtopia overlay 合成 composite asset root，再用隔离端口 `18188` 跑完整三任务 `gmp submit/eval/status`，`level1_pick`、`level1_place`、`level1_open_door` 都完成 reset/step/result_info/metric logging；随后又对三条任务分别跑 live contract probe，observation keys、camera input keys、action dialects、reward/success fields、logging fields 全部为 `PASS`。结论升级为 `Stage 7 passed`、`lift2_contract_ready=true`、`local_official_baseline_style_contract_ready=true`。边界仍然明确：三任务分数都是 `0.0`，说明当前简单动作没有解任务；`official_baseline_evaluable=false`，因为这还不是 official leaderboard 复现或官方 EBench score release。

2026-06-29 材质依赖收尾补充：`Aluminum_Anodized_Charcoal.mdl` 已作为独立 material closure follow-up 做 local mirror，不再依赖远端 Omniverse/S3 MDL。我们把 MDL 和三张 texture 放进 `miscs/mdl/labutopia/mdl`，并在 wrapper layer 里把 Aluminum Shader 的 `info:mdl:sourceAsset` 指向本地 `Aluminum_Anodized_Charcoal.mdl`。随后又把 `panel` 识别为原生 `GeomSubset material binding` 覆盖完整，把 `button` 和 `Group/_900_1` 改为 wrapper-local `PreviewSurface` material override。最新 runtime readback 中真正 `fallback_only` surface 为 0，`material_status=resolved_material_with_local_overrides`，所以 EBench package material gate 已通过；但 `native_material_closure_claim_allowed=false`、`full_native_material_closure_claim_allowed=false`，因为其中 2 个可见表面仍是 wrapper-local authored material，不是从 LabUtopia source-native material 恢复出来的。

2026-06-29 资产验收规范补充：我们把上述经验整理成 `EBench Asset Acceptance Pipeline`。这不是“模型拿分流水线”，而是把外部 asset package 验收到 GenManip/EBench 可评链路里的 evidence-gated workflow：asset intake、USD composition、material closure、physics、articulation、task runtime、render evidence 和 Lift2-style evaluator contract 每一项都要有 manifest 证据。PM 周报以后只引用 `allowed_claims`，不能把 `diagnostic/WARN` 图、单项材质 mirror 或本地 contract pass 写成 full closure、policy success 或 official leaderboard 成绩。

2026-06-29 `asset_acceptance_record` 补充：`DryingBox_01` 已生成第一份机器可读验收总表，作为 `EBench Asset Acceptance Pipeline` 的 reference asset 证据样板。通俗讲，这份 JSON 像一张资产准入清单：`acceptance_stages` 按 Stage 0-7 记录“工程推进到哪一步”，`gate_status` 和 `allowed_claims/blocked_claims` 记录“哪些话可以汇报，哪些话必须拦住”；同时新增 `claim_boundary.blocked_claim_status`，让机器消费者直接读到 `blocked=true`，避免把历史兼容字段里的 `false` 读反。当前可说的是：`task_runtime_ready=true`、`task_render_accepted=true`、`runtime_physics_stable=true`、`lift2_contract_ready=true`、`full_material_closure_claim_allowed=true`；必须继续拦住的是：`full_native_material_closure_claim_allowed=false`、`official_leaderboard_claim_allowed=false`、`policy_success_claim_allowed=false`。因此 PM 周报可以说“DryingBox 已成为 reference asset，EBench 本地评测链路、包级材质闭环和 Lift2 contract 可评”，但不能说“官方榜单复现”“策略成功”或“source-native full material closure 完成”。

2026-06-29 cold runtime sandbox 补充：我们又用更严格的“冷目录运行时依赖扫描”复查 copied package。之前发现的问题是 wrapper 外层已经改了本地材质，但被 payload 进来的 `scene.usd` 里还保留 remote MDL 和 remote Sektion cabinet payload；dependency scanner 会继续看到这些远端引用。现在 overlay 生成器会在复制 `lab_001.usd` 后做 source scene payload sanitization：Aluminum 指向本地 mirror，Steel/Stainless 指向本地 `SubUSDs/materials`，非任务关键的 remote Sektion cabinet payload 被移除。最新 `cold_runtime_sandbox_probe` 为 `PASS`，`remote_uri_count=0`、`missing_local_dependency_count=0`。这只能说明 copied package 的 runtime dependency 不再回源；它不等于 official leaderboard、policy success、PM showcase，也不等于 full native material closure。

术语边界也已收口：`Gate` 是质量/宣称分类，`Acceptance Stage` 是执行顺序。`Gate 7` 是 `Render Evidence Gate`，而 `Stage 7` 是 `Evaluator Robot Contract`；两者编号不一一对应。Stage 5 的图可以证明 eval-path readback 存在，但 PM showcase 是否可用仍要看 `render_evidence` gate 和 `pm_showcase_ready=false` 的边界。

## 本周完成了什么

### 1. LabUtopia POC 任务包已可运行

当前已经跑通 3 个 Franka POC 任务：

| 任务 | 当前状态 | 说明 |
| --- | --- | --- |
| `level1_pick` | 已跑通 | 能 reset、step、写结果 |
| `level1_place` | 已跑通 | 能 reset、step、写结果 |
| `level1_open_door` | 已跑通 | 能 reset、step、写结果 |

最新 smoke 结果：

```text
run_id=labutopia_franka_smoke_clean8_20260622_100208
status=complete
completed=3/3
score=0.0 for all tasks
```

### 2. LabUtopia 场景资产加载已跑通

当前已经能加载 LabUtopia 的实验室场景资产，包括桌面、瓶子、烧杯、托盘、干燥箱、门把手等对象。2026-06-23 P1 复核后，瓶子、烧杯、托盘、干燥箱和门把手的静态 USD 坐标/尺寸已经落在 Franka 工作区附近，门把手也不再作为一个独立飞走的顶层物体，而是挂在干燥箱内部路径上。

简单理解，资产加载现在是这样做的：

1. 任务配置里只写相对路径，例如：

```text
scene_usds/labutopia/level1_poc/lab_001/scene
```

2. 系统识别到这是 LabUtopia POC 任务后，会读取：

```text
configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json
```

3. 这个 manifest 告诉系统真正的 LabUtopia 资产目录在哪里：

```text
/cpfs/shared/simulation/zhuzihou/dev/_datasets/EBench-Assets-Overlay/labutopia_level1_poc/assets
```

4. 运行时会把 `ASSETS_DIR` 临时切换到这个目录，所以相对路径会被解析成真实的 `scene.usda` 文件。

5. 加载完成后，manifest 还会把 LabUtopia 原始对象映射成 GenManip 运行时可以识别的对象名，例如：

```text
conical_bottle02 -> obj_conical_bottle02
beaker2 -> obj_beaker2
DryingBox_01 -> obj_DryingBox_01
table -> table
```

这部分已经通过实际 smoke、静态 USD readback 和三任务 evaluator camera readback 验证。这里的“资产加载”表示 scene overlay、对象名映射和当前相机读回链路能进入 runtime；`pick/place` 当前任务图已经可读并通过渲染门禁，`open_door` 的底层物理读数已稳定且回到关闭位，P2 retake 图能看出 LabUtopia 原生 `DryingBox_01` 是 upright，蓝色门、白色侧面和 nested handle 可见，三任务最新正式诊断均为 `render_validation.passed=true`，native open_door 诊断为 `native_complex_dryingbox_ready=true`。

### 3. 结果记录链路已修复

之前任务虽然能跑，但最后可能因为结果没有正确写入而卡在结束阶段。现在已经修复：

- 每个任务结束后都会写 `result_info.json`
- 最终会生成总结果 `result.json`
- server 不会再在最后一个任务结束后等待到超时
- 如果后处理真的报错，系统会 fail fast，不会把错误伪装成“已完成”

### 4. 与 EOS/其他工程师任务做了隔离

本次验证使用独立端口：

```text
LabUtopia POC smoke: 18088
EOS/其他工程师任务: 8087
```

验证结束后：

```text
18088 已关闭
8087 仍正常在线
```

所以当前 LabUtopia POC 测试没有干扰 EOS 那边正在跑的任务。

## P0：黑屏问题与修复（产品向说明）

HTML 版详见周报页 [P0 黑屏](docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html#p0) 章节。

### P0 是什么

后端 smoke（reset/step/写结果）跑通之后的第一道「渲染读图门禁」：走 EBench 正式评测链路拍 `camera2`，三个任务不能再出现 **纯黑图**。

- P0 目标：eval readback 有有效像素（`readback_visible`）
- P0 不负责：PM 可读任务图（P1）、策略得分、官方 Lift2 baseline

### 当时看到了什么

6/22 render smoke（`run_id=labutopia_franka_render_smoke_20260622_150819`）保存的 `camera2` 帧全部纯黑（RGB min/max/mean = 0）。最初周报 JPG 是手工 direct-render 截图，不能代表评测链路真实画面。

### 先排除了什么

诊断脚本证明：`readback_black_before_recorder`——图在 `get_eval_camera_data()` 阶段就已全黑，**不是** EpisodeRecorder 写 PNG 弄坏的。问题在相机/光照/场景渲染。

### 黑屏是三件事叠在一起

| 原因 | 产品化解释 | 责任归属 | P0 处理 |
| --- | --- | --- | --- |
| **P0a · 相机位姿没生效** | YAML 写了相机位置，但 GenManip「简化相机格式」运行时没应用，相机对着空处 | GenManip 代码缺口 + 我们选了这条相机路径 | 修 `camera_utils.py`；临时把 camera2 挪到物体区域 |
| **P0b · overlay 缺光** | overlay 场景只搬了物体，没把 LabUtopia 原生灯光带过来 | LabUtopia 接入方式 | overlay 生成器补 `DeterministicDomeLight`（强度 1000） |
| **坐标错位** | 机器人在 x≈-0.4，物体还在 x≈8–45 的源场景坐标 | 接入配置 | P0 临时挪相机；**物体归位是 P1** |

### 什么是 overlay 场景（P0b 改这里）

**overlay** = 为 LabUtopia 单独生成的 EBench 兼容场景包，放在 `_datasets/EBench-Assets-Overlay/labutopia_level1_poc/assets/`，**不修改**官方 `EBench-Assets`。

P0b 改的代码（GenManip 接入分支，非 LabUtopia 主仓库）：

- `standalone_tools/labutopia_poc/build_asset_overlay.py` — 生成 `scene.usda` 时写入 DomeLight
- `standalone_tools/labutopia_poc/validate_task_package.py` — 静态校验灯光存在
- `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json` — 记录契约

### 为什么 EBench 原生没踩坑

GenManip 按 YAML 有没有 `pixel_size` 分两条相机路径：

| 路径 | 识别方式 | 谁在用 | P0 前是否设位姿 |
| --- | --- | --- | --- |
| **SimBox Style** | 有 `pixel_size`、完整内参 | 官方 Lift2 baseline（`fixed_camera_lift2_simbox.yml`） | 会 |
| **GenManip Style** | 简化字段，从 LabUtopia 抄来 | Franka POC（`labutopia_franka_poc.yml`） | P0 前不会（已修） |

结论：不是 EBench 整体坏了，是我们 POC 走了少测的 GenManip Style 路径；官方可评最终仍要切 SimBox + Lift2（`lift2_candidate`）。

### P0 修完边界

**可以说：**

- eval 链路不再纯黑
- 黑屏在 readback 阶段，不是 recorder
- GenManip Style 位姿缺口已修；overlay 已补光

**还不能说：**

- P0 后一度是「灰底小点」图（`FAIL_LOW_TEXTURE`）→ P1 才解决
- PM 可读任务图 → P1 通过
- 官方 baseline 可评 → 未验证

P0 证据：

- [render_diagnostics_20260623.json](labutopia_lab_poc/evidence_manifests/render_diagnostics_20260623.json) — 初始纯黑诊断
- [render_p0a_p0b_20260623.json](labutopia_lab_poc/evidence_manifests/render_p0a_p0b_20260623.json) — P0 修复后非黑
- [render_visual_investigation_20260623.md](labutopia_lab_poc/render_visual_investigation_20260623.md) — 技术复盘

## 有没有渲染图验证？

2026-06-23 到 2026-06-24 最新复核结论：现在已经有从 EBench/evaluator 路径读回的非黑图，说明“能不能通过评测链路拍到东西”这个问题已经推进闭环。旧 JPG 保留为历史失败样例，P1 PNG 是更可信的 eval-path 证据：`pick` 目标瓶清楚，`place` 烧杯和黄色托盘关系可读，`open_door` 已从物理爆值、黑箱角和大橙色块推进到关闭位正确、门板/框架/细橙色把手可识别。P2 retake PNG 进一步证明 `open_door` 已回到 LabUtopia native complex `DryingBox_01`，不是箱子倒置，而是旧 P2 图的材质/证据视角未闭环；新图中原生箱体 upright，蓝色门、白色侧面、把手、观察窗和控制面板可见。三任务最新正式诊断均为 `render_validation.passed=true`、`task_render_accepted=true`，native open_door 诊断为 `native_complex_dryingbox_ready=true`。

```text
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-pick.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-place.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-pick-eval-readback-p1.png
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-place-eval-readback-p1.png
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door-eval-readback-p1.png
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door-native-readback-p2.png
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door-native-retake-p2.png
```

旧的三张 JPG 保留为历史失败样例。P1 的三张 PNG 来自正常 evaluator camera readback，不是 direct-render 截图；它们说明链路能拍到场景，pick/place 通过任务级隐藏后已经能让 PM 看懂任务目标，open_door 已从“只看到黑箱角/看不见把手/把手像一大片橙色面板”推进到“关闭位正确、门板/框架/细把手可识别”。旧 P2 native PNG 说明 open_door 已经不再只停留在 surrogate 对照组，但材质证据和证据视角还没有闭环，容易误读成箱子倒了；P2 retake PNG 能清楚看到 upright 的蓝门、白侧面、handle、window 和 control panel。后续 2026-06-29 材质收尾进一步把 Aluminum 做 local mirror，把 `panel` 记为 source-resolved `GeomSubset`，并把 `button`/`Group/_900_1` 记为 wrapper-local override。这说明任务渲染门禁、Franka POC native gate 和 package material gate 已经通过，但不等于官方 Lift2 baseline 已经可评，也不等于 full native material closure。

`open_door` 的 USD 铰接物体问题已经单独整理成解释性教学页：`docs/records/evidence/2026-06-24-usd-articulation-dryingbox-tutorial/index.html`。这篇页面面向产品经理解释 `USD articulation`、`ArticulationRootAPI`、`RevoluteJoint`、P1 `sanitized_surrogate` 对照组、P2 native complex `DryingBox_01` 已通过的前五步 gate、门把手层级和 claim boundary。

给产品经理看的前后对照：

| 任务 | 旧图问题 | 已经做的修复 | 现在还差什么 |
| --- | --- | --- | --- |
| `level1_pick` | 抓取目标不明显，只看图无法判断“要抓哪个瓶子” | 修正 eval camera readback、相机朝向、光照，把瓶子归一到 Franka 工作区，并在 pick 任务里隐藏烧杯、托盘、干燥箱等非目标物体 | 当前新图已经能让 PM 看懂“抓这个蓝色瓶子”，并已通过任务渲染门禁 |
| `level1_place` | 看不出源物体和目标托盘的关系，不像一个放置任务 | 修正托盘、烧杯、瓶子坐标和颜色标记，并在 place 任务里隐藏瓶子和干燥箱，只保留烧杯与目标托盘 | 当前新图能看懂“把烧杯放到黄色托盘附近”，并已通过任务渲染门禁 |
| `level1_open_door` | 几乎只拍到黑色箱体角，门板、把手、铰链和动作目标都不清楚；中间版本又出现把手像大橙色面板的问题；旧 P2 native 图还因为材质和证据相机未闭环，看起来像箱子倒了 | 把门把手恢复为干燥箱内部子部件，不再作为独立物体飞走；生成 P1 `sanitized_surrogate` 对照组，固定底座并只保留一个门关节；再补关节初始目标回放、把手位置修正、删除重复橙色块、缩细把手和任务专用正面相机；P2 回到 LabUtopia native complex `DryingBox_01`，只用 `additive physics override` 修 runtime 物理；随后修 wrapper-local `Looks` 和 native `material:binding`，用 retake camera 重拍；背景解释见 `docs/records/evidence/2026-06-24-usd-articulation-dryingbox-tutorial/index.html` | P1 证明门任务可读；P2 retake 证明原生 DryingBox_01 upright，蓝门、白侧面和 nested handle 能通过 EBench readback；Stage 7 又补上本地 Lift2 contract。 |

需要特别说明：

- 旧问题：早期 eval recorder `camera2` 纯黑，根因在 recorder 写盘之前的 readback 阶段。
- 已推进：P0/P1 后，`level1_pick`、`level1_place`、`level1_open_door` 都是 `readback_visible`。
- 已推进：静态 USD readback 显示瓶子、烧杯、托盘、干燥箱、门把手的坐标和尺寸合理；门把手路径是 `/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle`，不是独立飞走物体。
- 已推进：任务级隐藏后，`level1_pick` 当前图只保留目标瓶，`level1_place` 当前图只保留烧杯和目标托盘，PM 可以看懂任务目标和关系。
- 已推进：`level1_open_door` 旧版本运行期关节读数曾出现 `1.573e13` 量级；P1 `sanitized_surrogate` 对照组最新诊断只暴露 `RevoluteJoint`，关节读数为 `0.0`，仿真能完成 readback，问题已经从“爆掉不可看/只看到黑箱角/把手像大橙色面板”收敛到“门板、框架和细橙色把手可识别”。
- 已复核：独立视觉审阅认为当前 old-vs-current 对照可用于 PM 汇报；旧图确实支持“目标不清、放置关系缺失、看不到门把手”的问题描述，当前三张新图均可作为任务渲染通过证据。
- 已推进：LabUtopia native complex `DryingBox_01` 已通过 Franka POC native gate；证据包括 `asset audit`、native-only Isaac smoke、EBench wrapper、`additive physics override`、wrapper-local `Looks`/`material:binding` 修复和 `open_door` native retake。
- 已推进：本地 official-baseline-style Lift2 contract 已通过。完整三任务 `gmp eval` 能 reset、step、写 `result_info` 和 metric；三条单任务 live probe 都验证了 Lift2 observation/camera/action/reward/logging schema。仍不能宣称 official leaderboard 复现或官方 EBench score release；当前 `official_baseline_evaluable=false` 是边界，不是本地合同失败。
- 因此下一步不是继续修三张截图，也不是继续打磨 surrogate；Stage 7 本地合同已补上，后续应转入真实 Lift2 baseline runner 的策略评测和官方成绩边界管理。

## 本周遇到的问题和解决方式

| 问题 | 表现 | 解决方式 | 当前状态 |
| --- | --- | --- | --- |
| 资产根目录不对 | 系统一开始会去错误目录找 LabUtopia 场景 | 增加 LabUtopia manifest 识别逻辑，运行时切换到 overlay asset root | 已解决 |
| 缺少 `meta_info.pkl` | 传统 GenManip 任务依赖采集包里的元信息，LabUtopia POC 没有这份文件 | 针对 LabUtopia POC，从实时场景里自动生成最小可用元信息 | 已解决 |
| camera cleanup 字段缺失 | 切换任务时 camera 清理报字段错误 | 补齐 camera 配置里的 cleanup flags | 已解决 |
| eval recorder `camera2` 黑屏 | 保存过程帧时 `camera2` 输出纯黑 | P0a：修 GenManip Style 相机位姿生效 + 临时对准物体区域；P0b：overlay 补 `DeterministicDomeLight`；详见 [P0 章节](docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html#p0) | 黑屏解除（PM 可读任务图属 P1） |
| 当前任务图验收边界 | `pick` 已清楚，`place` 关系可读；`open_door` 已能读回且关闭位正确，门板/框架/细把手可识别 | 三任务最新正式诊断均为 `render_validation.passed=true`；P2 又补上 native complex `DryingBox_01` 的 EBench readback 证据；Stage 7 已补上本地 Lift2 contract | 任务渲染/native gate/Lift2 contract 通过 |
| `open_door` 运行期物理不稳定 | 旧版本 runtime articulation joint position 爆到 `1.573e13`，并伴随 PhysX transform warning | P1 已用 DryingBox `sanitized_surrogate`、固定底座、对齐后的门铰链和关节目标回放修复；P2 已把稳定性迁移到 LabUtopia native complex `DryingBox_01`，并通过 `native_dryingbox_visual_retake_final_20260624_0002` 读回验证 | native gate 已通过 |
| 资产导入/layout 静态坐标 | 之前任务物体在源 lab 坐标，handle 变成异常放大的独立物体 | P1 已把对象归一到 Franka 工作区，并把 handle 保留为 DryingBox 内部子路径 | 静态层已推进 |
| 最终进度不 complete | 任务已跑完，但进度没有写入，导致客户端最后等待超时 | 任务结束时写最小 `result_info.json`，并修复进度统计 | 已解决 |
| 后处理异常可能被误记为完成 | 如果后处理报错，不能用 0 分兜底伪装成成功 | 增加 fail-fast 逻辑和回归测试 | 已解决 |
| 端口/结果混淆风险 | EOS 侧也有人在跑任务，担心互相影响 | 使用独立 worktree、独立 run_id、独立端口 18088，并复核 8087 状态 | 已解决 |

## 当前进度判断

| 模块 | 产品视角状态 | 说明 |
| --- | --- | --- |
| LabUtopia 场景接入 | 已跑通 | 场景资产能加载，任务链路能跑完 |
| Franka POC smoke | 已完成 | 3 个任务全部 complete |
| 结果落盘 | 已完成 | per-task 和 final result 都能写出 |
| 渲染图/视频验收 | 任务渲染通过 | 三任务 eval readback 已非黑；pick 已清楚，place 关系可读，open_door 关闭位正确、门板/框架/细把手可识别；三任务最新正式诊断均为 `render_validation.passed=true` |
| Native complex DryingBox | Franka POC gate 已通过 | P2 open_door 证据来自 LabUtopia native complex `DryingBox_01`；保留 native visual/hierarchy/nested handle，只用 `additive physics override` 修 runtime 物理 |
| Cold runtime sandbox | 运行时依赖闭环已通过 | copied package 在冷目录里 compose 成功，`remote_uri_count=0`、`missing_local_dependency_count=0`；这不升级 official/policy/showcase/native material claims |
| 任务求解能力 | 未验证 | 当前默认动作得分 0.0，不代表策略能力 |
| Lift2 contract | 本地合同通过 | `lift2_candidate` 三任务可通过 Lift2/R5a eval path reset、step、写结果，并通过 observation/camera/action/reward/logging live probe |
| 官方 baseline | 未发布官方成绩 | 本地 official-baseline-style contract 已通过，但这不是 official leaderboard reproduction；三任务当前 score/success_rate 仍是 0 |
| 资产验收 Record | 已生成 reference asset 记录 | `DryingBox_01` 已生成 `asset_acceptance_record`：`acceptance_stages` 记录 Stage 0-7，`gate_status` 记录 claim gates；task runtime、runtime physics、evaluator robot contract、USD composition 和 package material closure 通过；overall 仍是 `WARN`，因为 Stage 5 图是诊断证据且官方榜单/策略成功/full native material closure 仍不可声明 |

## 验证证据

本周保留的主要证据：

```text
run_id=labutopia_franka_smoke_clean8_20260622_100208
status=complete
completed_episodes=3
total_episodes=3
```

测试和校验：

```text
python -m pytest tests/labutopia_poc -q
193 passed, 1 skipped

python -m pytest tests/labutopia_poc/test_render_diagnostics_contract.py -q
53 passed

python standalone_tools/labutopia_poc/validate_task_package.py
LabUtopia task package validation OK

report display QA
Chromium desktop/mobile screenshots passed for the updated weekly report. The DOM contains `acceptance_stages`, `Stage 0-7`, `gate_status`, `asset_acceptance_record`, and `claim_boundary.blocked_claim_status`; 11 local images and 41 local links resolve to files. Evidence: `/tmp/labutopia_stage_registry_browser_review_20260629/weekly-desktop.png`, `weekly-mobile.png`, and `weekly-mobile-tall.png`. This checks report display only, not official baseline evaluability.
```

结果文件：

```text
saved/eval_results/ebench/labutopia_franka_smoke_clean8_20260622_100208/result.json
saved/eval_results/ebench/labutopia_franka_smoke_clean8_20260622_100208/.../level1_pick/000/result_info.json
saved/eval_results/ebench/labutopia_franka_smoke_clean8_20260622_100208/.../level1_place/000/result_info.json
saved/eval_results/ebench/labutopia_franka_smoke_clean8_20260622_100208/.../level1_open_door/000/result_info.json
```

渲染补证复核：

- `run_id=labutopia_franka_render_smoke_20260622_150819`
- eval recorder `camera2` frames: black, sampled RGB min/max/mean all 0
- runtime diagnostics: `level1_pick/place/open_door` all `readback_black_before_recorder`
- evidence manifest: [docs/labutopia_lab_poc/evidence_manifests/render_diagnostics_20260623.json](../labutopia_lab_poc/evidence_manifests/render_diagnostics_20260623.json)
- P1 follow-up: `level1_pick/place/open_door` now `readback_visible`; latest task-level hiding makes pick readable and place relation readable, while open_door has closed joint target `[0.0]`, visible door/frame/thin orange handle, and `render_validation.passed=true`
- independent image-only review: old-vs-current comparison is PASS for PM-facing evidence; P2 native retake is PASS with high confidence: DryingBox is upright, blue front door, white side body, handle, observation window and control panel are visible; none of this should be described as official baseline execution
- P0a/P0b evidence manifest: [docs/labutopia_lab_poc/evidence_manifests/render_p0a_p0b_20260623.json](../labutopia_lab_poc/evidence_manifests/render_p0a_p0b_20260623.json)
- P1 evidence manifest: [docs/labutopia_lab_poc/evidence_manifests/render_p1_asset_layout_20260623.json](../labutopia_lab_poc/evidence_manifests/render_p1_asset_layout_20260623.json)
- P2 native DryingBox audit: `saved/diagnostics/native_dryingbox_audit_20260624_091136/audit.json`, SHA256 `e6eab4a6fc6a6b3ddddbabc2717a674c606c83255467db8b97bfbdac085aad4d`
- P2 native-only Isaac smoke: `saved/diagnostics/native_dryingbox_smoke_20260624_091152/smoke.json`, SHA256 `fdab719564440d8528623785b55662acb38b74cf607d249dce963885082664a4`
- P2 native EBench retake diagnostics: `saved/diagnostics/native_dryingbox_visual_retake_final_20260624_0002/diagnostics.json`, SHA256 `d93069572347c6a30260bc856de126193c531633be3167f4ecc7fb76ce8d7bf6`; boundary is `render_validation.passed=true`, `native_complex_dryingbox_ready=true`, `task_render_accepted=true`, `official_baseline_evaluable=false`
- Latest Stage 5 native eval readback diagnostics: `saved/diagnostics/dryingbox_asset_acceptance_manual/diagnostics.json`; boundary is `native_eval_readback_ready=true`, `native_complex_dryingbox_ready=true`, `runtime_physics_stable=true`, `metric_reads_door_revolute_joint=true`, `native_material_closure_status=resolved_material_with_local_overrides`, `fallback_surface_count=0`, `native_material_closure_claim_allowed=false`
- Historical Stage 5 native eval readback diagnostics: `saved/diagnostics/labutopia_native_open_door_eval_20260628_183219/diagnostics.json`; historical boundary was `native_material_closure_status=open_remote_dependency_waived`
- Stage 5 referenced native smoke mirror: [docs/labutopia_lab_poc/evidence_manifests/native_dryingbox_smoke_20260628_143638.json](../labutopia_lab_poc/evidence_manifests/native_dryingbox_smoke_20260628_143638.json), SHA256 `d6fefeec5ffea1b6b6209e512e3b9588a3f0c07e2abd1cfaa50d841dfd516c33`; committed mirror removes machine-local absolute paths.
- Stage 6 acceptance evidence manifest: [docs/labutopia_lab_poc/evidence_manifests/native_dryingbox_acceptance_20260628_183219.json](../labutopia_lab_poc/evidence_manifests/native_dryingbox_acceptance_20260628_183219.json)
- Stage 7 Lift2 readiness report: [docs/labutopia_lab_poc/lift2_readiness.md](../labutopia_lab_poc/lift2_readiness.md)
- Stage 7 machine evidence manifest: [docs/labutopia_lab_poc/evidence_manifests/native_dryingbox_stage7_lift2_contract_20260629_0404.json](../labutopia_lab_poc/evidence_manifests/native_dryingbox_stage7_lift2_contract_20260629_0404.json)
- Stage 7 evidence bundle: [docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260629_0404/](../labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260629_0404/)
- Aluminum material mirror follow-up: [docs/records/2026-06-29-labutopia-aluminum-material-mirror-closure.md](2026-06-29-labutopia-aluminum-material-mirror-closure.md)
- Aluminum material mirror machine evidence: [docs/labutopia_lab_poc/evidence_manifests/aluminum_material_mirror_closure_20260629_045413.json](../labutopia_lab_poc/evidence_manifests/aluminum_material_mirror_closure_20260629_045413.json)
- EBench Asset Acceptance Pipeline SOP: [docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md](../labutopia_lab_poc/ebench_asset_acceptance_pipeline.md)
- Evidence manifest field guide: [docs/labutopia_lab_poc/evidence_manifests/README.md](../labutopia_lab_poc/evidence_manifests/README.md)
- DryingBox asset acceptance record: [docs/labutopia_lab_poc/evidence_manifests/dryingbox_asset_acceptance_20260629_asset_acceptance_manual.json](../labutopia_lab_poc/evidence_manifests/dryingbox_asset_acceptance_20260629_asset_acceptance_manual.json)
- Asset acceptance implementation plan: [docs/superpowers/plans/2026-06-29-ebench-asset-acceptance-pipeline.md](../superpowers/plans/2026-06-29-ebench-asset-acceptance-pipeline.md)
- static direct-render evidence: visual QA failed on 2026-06-23
- investigation: [docs/labutopia_lab_poc/render_visual_investigation_20260623.md](../labutopia_lab_poc/render_visual_investigation_20260623.md)
- plan: [docs/superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md](../superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md)

## 下周建议

先把“渲染和 native DryingBox gate”作为 Franka POC 阶段闭环，再进入下一阶段 Lift2 baseline 讨论。

建议顺序：

1. P0a/P0b：已修相机 readback 和 deterministic lighting，让 eval path 不再黑屏。
2. P1a：已把对象静态坐标和 nested handle 归一到 Franka 工作区。
3. P1b：已用 DryingBox `sanitized_surrogate` 对照组和关节目标回放修复 `open_door` runtime articulation/PhysX 爆值与关闭位问题。
4. P1c：已完成任务级相机/构图复验，三任务 `render_validation.passed=true`。
5. P1d：已用正常 eval-path 重新抓三任务关键帧，写 evidence manifest，并完成独立视觉复核。
6. P2 / Acceptance Stage 5：已完成 LabUtopia native complex `DryingBox_01` eval-path readback：asset audit、native-only Isaac smoke、EBench wrapper、additive physics override、runtime material readback、door `RevoluteJoint` metric 和 frame hash 都有证据。
7. Acceptance Stage 6：已新增 acceptance manifest 和 PM claim boundary。历史边界是 Aluminum remote waiver open，最新图为机器诊断证据且视觉审阅 `WARN`，不能写成 polished showcase；material follow-up 已单独把 package material closure 收口。
8. Acceptance Stage 7：本地 Lift2 official-baseline-style contract 已通过。下一步不再是补 composite asset root，而是把这条 `lift2_candidate` lane 交给真实 Lift2 baseline runner 做策略评测；同时保留 0% score 边界和 official baseline 边界。
9. Material follow-up：package material closure 已通过：Aluminum local mirror、`panel` 原生 `GeomSubset` 覆盖、`button` 和 `Group/_900_1` wrapper-local material override 都有证据；full native material closure 仍未完成，因为 wrapper-local override 不能冒充 source-native material。
10. Asset acceptance record：已生成 DryingBox reference record，并已把 Stage 0-7 写成机器可读 `acceptance_stages`。下一步不是重开原来的 acceptance stages，而是在这个 reference record 基础上进入真实 Lift2 baseline/policy gate；如果后续需要论文级 source-native material provenance，再单独做 full native material closure follow-up。
11. Cold runtime sandbox：已补上 copied package 的冷目录 runtime dependency scan。当前 `status=PASS`、`remote_uri_count=0`、`missing_local_dependency_count=0`，说明 overlay 不再在运行时解析到公网/S3/原始目录/cache；但 official leaderboard、policy success、PM showcase 和 full native material closure 仍保持 blocked。

## 新增调研和计划文档

- [docs/labutopia_lab_poc/render_visual_investigation_20260623.md](../labutopia_lab_poc/render_visual_investigation_20260623.md)
- [docs/superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md](../superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md)
- [docs/superpowers/plans/2026-06-24-ebench-native-dryingbox.md](../superpowers/plans/2026-06-24-ebench-native-dryingbox.md)
- [docs/records/evidence/2026-06-24-usd-articulation-dryingbox-tutorial/index.html](evidence/2026-06-24-usd-articulation-dryingbox-tutorial/index.html)
- [docs/labutopia_lab_poc/evidence_manifests/render_p1_asset_layout_20260623.json](../labutopia_lab_poc/evidence_manifests/render_p1_asset_layout_20260623.json)
- [docs/labutopia_lab_poc/evidence_manifests/native_dryingbox_acceptance_20260628_183219.json](../labutopia_lab_poc/evidence_manifests/native_dryingbox_acceptance_20260628_183219.json)
- [docs/labutopia_lab_poc/lift2_readiness.md](../labutopia_lab_poc/lift2_readiness.md)
- [docs/labutopia_lab_poc/evidence_manifests/native_dryingbox_stage7_lift2_contract_20260629_0404.json](../labutopia_lab_poc/evidence_manifests/native_dryingbox_stage7_lift2_contract_20260629_0404.json)
- [docs/labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260629_0404/](../labutopia_lab_poc/evidence_manifests/lift2_contract_probe_20260629_0404/)
- [docs/labutopia_lab_poc/ebench_asset_acceptance_pipeline.md](../labutopia_lab_poc/ebench_asset_acceptance_pipeline.md)
- [docs/labutopia_lab_poc/evidence_manifests/README.md](../labutopia_lab_poc/evidence_manifests/README.md)
- [docs/superpowers/plans/2026-06-29-ebench-asset-acceptance-pipeline.md](../superpowers/plans/2026-06-29-ebench-asset-acceptance-pipeline.md)
