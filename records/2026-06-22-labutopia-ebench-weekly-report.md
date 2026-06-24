# 2026-06-22 LabUtopia EBench 接入周报

HTML 版产品汇报页：
`docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html`

## 一句话进展

本周已经把 LabUtopia 的 Franka POC 跑通到端到端 smoke 阶段：任务可以提交、场景可以加载、三个 level-1 任务可以 reset/step、结果可以落盘、最终状态可以正常 complete。

这说明当前最关键的“接入链路”已经打通。需要注意的是，这还不是任务求解成功，也不是官方 baseline 成绩；当前 smoke 使用默认动作，所以三个任务分数都是 `0.0`。2026-06-23 到 2026-06-24 最新复核补充：三任务现在都能通过 EBench/evaluator 正常读回非黑渲染图，资产静态坐标也已经从“明显导错”修到合理工作区；最新正式诊断中 `pick`、`place`、`open_door` 均为 `render_validation.passed=true`、`task_render_accepted=true`。当前可以说 Franka POC 的任务渲染门禁已过，但 `open_door` 证据仍是 P1 `sanitized_surrogate` 对照组，不是 LabUtopia native complex `DryingBox` 已调通；官方 Lift2 baseline 的复合资产和官方 runner 也还没验证。

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

这部分已经通过实际 smoke、静态 USD readback 和三任务 evaluator camera readback 验证。这里的“资产加载”表示 scene overlay、对象名映射和当前相机读回链路能进入 runtime；`pick/place` 当前任务图已经可读并通过渲染门禁，`open_door` 的底层物理读数已稳定且回到关闭位，最终细把手正式相机图也能看出门板、框架和动作点，三任务最新正式诊断均为 `render_validation.passed=true`。

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

## 有没有渲染图验证？

2026-06-23 到 2026-06-24 最新复核结论：现在已经有三张从 EBench/evaluator 路径读回的非黑图，说明“能不能通过评测链路拍到东西”这个问题已经推进闭环。旧 JPG 保留为历史失败样例，新 PNG 是更可信的 eval-path 证据：`pick` 目标瓶清楚，`place` 烧杯和黄色托盘关系可读，`open_door` 已从物理爆值、黑箱角和大橙色块推进到关闭位正确、门板/框架/细橙色把手可识别。三任务最新正式诊断均为 `render_validation.passed=true`、`task_render_accepted=true`。

```text
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-pick.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-place.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-pick-eval-readback-p1.png
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-place-eval-readback-p1.png
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door-eval-readback-p1.png
```

旧的三张 JPG 保留为历史失败样例。新的三张 PNG 来自正常 evaluator camera readback，不是 direct-render 截图；它们更适合说明今天的真实状态：链路能拍到场景，pick/place 通过任务级隐藏后已经能让 PM 看懂任务目标，open_door 已从“只看到黑箱角/看不见把手/把手像一大片橙色面板”推进到“关闭位正确、门板/框架/细把手可识别”。这说明任务渲染门禁已经通过，但不等于官方 Lift2 baseline 已经可评。

`open_door` 的 USD 铰接物体问题已经单独整理成解释性教学页：`docs/records/evidence/2026-06-24-usd-articulation-dryingbox-tutorial/index.html`。这篇页面面向产品经理解释 `USD articulation`、`ArticulationRootAPI`、`RevoluteJoint`、P1 `sanitized_surrogate` 对照组、P2 native complex `DryingBox` 七步 gate、门把手层级和 claim boundary。

给产品经理看的前后对照：

| 任务 | 旧图问题 | 已经做的修复 | 现在还差什么 |
| --- | --- | --- | --- |
| `level1_pick` | 抓取目标不明显，只看图无法判断“要抓哪个瓶子” | 修正 eval camera readback、相机朝向、光照，把瓶子归一到 Franka 工作区，并在 pick 任务里隐藏烧杯、托盘、干燥箱等非目标物体 | 当前新图已经能让 PM 看懂“抓这个蓝色瓶子”，并已通过任务渲染门禁 |
| `level1_place` | 看不出源物体和目标托盘的关系，不像一个放置任务 | 修正托盘、烧杯、瓶子坐标和颜色标记，并在 place 任务里隐藏瓶子和干燥箱，只保留烧杯与目标托盘 | 当前新图能看懂“把烧杯放到黄色托盘附近”，并已通过任务渲染门禁 |
| `level1_open_door` | 几乎只拍到黑色箱体角，门板、把手、铰链和动作目标都不清楚；中间版本又出现把手像大橙色面板的问题 | 把门把手恢复为干燥箱内部子部件，不再作为独立物体飞走；生成 P1 `sanitized_surrogate` 对照组，固定底座并只保留一个门关节；再补关节初始目标回放、把手位置修正、删除重复橙色块、缩细把手和任务专用正面相机；背景解释见 `docs/records/evidence/2026-06-24-usd-articulation-dryingbox-tutorial/index.html` | 最新图中关节已回到期望关闭位 `0.0`，门板、框架和细橙色把手可识别，并已通过任务渲染门禁；下一步先调通 LabUtopia native complex `DryingBox`，再接 Lift2 baseline gate |

需要特别说明：

- 旧问题：早期 eval recorder `camera2` 纯黑，根因在 recorder 写盘之前的 readback 阶段。
- 已推进：P0/P1 后，`level1_pick`、`level1_place`、`level1_open_door` 都是 `readback_visible`。
- 已推进：静态 USD readback 显示瓶子、烧杯、托盘、干燥箱、门把手的坐标和尺寸合理；门把手路径是 `/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle`，不是独立飞走物体。
- 已推进：任务级隐藏后，`level1_pick` 当前图只保留目标瓶，`level1_place` 当前图只保留烧杯和目标托盘，PM 可以看懂任务目标和关系。
- 已推进：`level1_open_door` 旧版本运行期关节读数曾出现 `1.573e13` 量级；P1 `sanitized_surrogate` 对照组最新诊断只暴露 `RevoluteJoint`，关节读数为 `0.0`，仿真能完成 readback，问题已经从“爆掉不可看/只看到黑箱角/把手像大橙色面板”收敛到“门板、框架和细橙色把手可识别”。
- 已复核：独立视觉审阅认为当前 old-vs-current 对照可用于 PM 汇报；旧图确实支持“目标不清、放置关系缺失、看不到门把手”的问题描述，当前三张新图均可作为任务渲染通过证据。
- 仍 blocked：LabUtopia native complex `DryingBox` 还没调通；下一步必须做 `asset audit`、native-only Isaac smoke、EBench wrapper、`additive physics override` 和 `open_door` eval readback gate。
- 仍 blocked：官方 Lift2 baseline 不能宣称可评，因为 Lift2 复合资产根目录和官方 runner 还没验证；当前 diagnostics claim boundary 是 `task_render_accepted=true`、`official_baseline_evaluable=false`。
- 因此下一步不是继续修三张截图，而是先把 native complex `DryingBox` 接入 gate 做完，再把 Lift2 baseline 所需的复合资产和官方 runner gate 接上。

## 本周遇到的问题和解决方式

| 问题 | 表现 | 解决方式 | 当前状态 |
| --- | --- | --- | --- |
| 资产根目录不对 | 系统一开始会去错误目录找 LabUtopia 场景 | 增加 LabUtopia manifest 识别逻辑，运行时切换到 overlay asset root | 已解决 |
| 缺少 `meta_info.pkl` | 传统 GenManip 任务依赖采集包里的元信息，LabUtopia POC 没有这份文件 | 针对 LabUtopia POC，从实时场景里自动生成最小可用元信息 | 已解决 |
| camera cleanup 字段缺失 | 切换任务时 camera 清理报字段错误 | 补齐 camera 配置里的 cleanup flags | 已解决 |
| eval recorder `camera2` 黑屏 | 保存过程帧时 `camera2` 输出纯黑 | 已修 camera axes/pose、deterministic lighting 和工作区相机；三任务当前 eval readback 均非黑 | 黑屏解除 |
| 当前新图验收边界 | `pick` 已清楚，`place` 关系可读；`open_door` 已能读回且关闭位正确，门板/框架/细把手可识别 | 三任务最新正式诊断均为 `render_validation.passed=true`；继续接 native complex `DryingBox` gate 和 Lift2 baseline 所需的复合资产/官方 runner gate | 任务渲染通过 |
| `open_door` 运行期物理不稳定 | 旧版本 runtime articulation joint position 爆到 `1.573e13`，并伴随 PhysX transform warning | P1 已用 DryingBox `sanitized_surrogate`、固定底座、对齐后的门铰链和关节目标回放修复；最新读数为 `0.0 rad` 且只暴露 `RevoluteJoint`。P2 要把同样稳定性迁移到 LabUtopia native complex `DryingBox` | P1 已解决；native 待验证 |
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
| Native complex DryingBox | 待验证 | 当前 open_door 证据来自 P1 `sanitized_surrogate` 对照组；下一步必须保留 LabUtopia native visual/hierarchy/handle，只用 `additive physics override` 修 runtime 物理 |
| 任务求解能力 | 未验证 | 当前默认动作得分 0.0，不代表策略能力 |
| 官方 baseline | 不能宣称可评 | 任务渲染门禁已过，但 Lift2 复合资产和官方 runner 还没闭环，diagnostics claim boundary 仍是 `official_baseline_evaluable=false` |

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
64 passed, 1 skipped

python -m pytest tests/labutopia_poc/test_render_diagnostics_contract.py -q
13 passed

python standalone_tools/labutopia_poc/validate_task_package.py
LabUtopia task package validation OK

report display QA
Playwright/Chromium desktop/tablet/mobile full-page audits passed; six report images load, the DOM contains the old-image section, new eval readback section, latest thin-handle `open_door`, task-render-pass wording, and official-baseline-not-yet-validated boundary text. Evidence: `/tmp/labutopia_weekly_p1_gate_review_20260624/desktop_full_report.png`, `/tmp/labutopia_weekly_p1_gate_review_20260624/tablet_full_report.png`, `/tmp/labutopia_weekly_p1_gate_review_20260624/mobile_full_report.png`, plus matching `*_audit.json` files. This checks report display only, not official baseline evaluability.
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
- independent image-only review: old-vs-current comparison is PASS for PM-facing evidence; the final thin-handle open_door retake is PASS, but none of this should be described as official baseline execution
- P0a/P0b evidence manifest: [docs/labutopia_lab_poc/evidence_manifests/render_p0a_p0b_20260623.json](../labutopia_lab_poc/evidence_manifests/render_p0a_p0b_20260623.json)
- P1 evidence manifest: [docs/labutopia_lab_poc/evidence_manifests/render_p1_asset_layout_20260623.json](../labutopia_lab_poc/evidence_manifests/render_p1_asset_layout_20260623.json)
- static direct-render evidence: visual QA failed on 2026-06-23
- investigation: [docs/labutopia_lab_poc/render_visual_investigation_20260623.md](../labutopia_lab_poc/render_visual_investigation_20260623.md)
- plan: [docs/superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md](../superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md)

## 下周建议

先把“渲染和布局验收”补成真正闭环，再进入下一阶段机器人/baseline 讨论。

建议顺序：

1. P0a/P0b：已修相机 readback 和 deterministic lighting，让 eval path 不再黑屏。
2. P1a：已把对象静态坐标和 nested handle 归一到 Franka 工作区。
3. P1b：已用 DryingBox `sanitized_surrogate` 对照组和关节目标回放修复 `open_door` runtime articulation/PhysX 爆值与关闭位问题。
4. P1c：已完成任务级相机/构图复验，三任务 `render_validation.passed=true`。
5. P1d：已用正常 eval-path 重新抓三任务关键帧，写 evidence manifest，并完成独立视觉复核。
6. P2：进入 LabUtopia native complex `DryingBox` gate：asset audit、native-only Isaac smoke、EBench wrapper、additive physics override、open_door eval readback。
7. P3：进入 Lift2 复合资产根目录和官方 runner 发现；这是官方 baseline 可评前的下一道硬门槛。

## 新增调研和计划文档

- [docs/labutopia_lab_poc/render_visual_investigation_20260623.md](../labutopia_lab_poc/render_visual_investigation_20260623.md)
- [docs/superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md](../superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md)
- [docs/superpowers/plans/2026-06-24-ebench-native-dryingbox.md](../superpowers/plans/2026-06-24-ebench-native-dryingbox.md)
- [docs/records/evidence/2026-06-24-usd-articulation-dryingbox-tutorial/index.html](evidence/2026-06-24-usd-articulation-dryingbox-tutorial/index.html)
- [docs/labutopia_lab_poc/evidence_manifests/render_p1_asset_layout_20260623.json](../labutopia_lab_poc/evidence_manifests/render_p1_asset_layout_20260623.json)
