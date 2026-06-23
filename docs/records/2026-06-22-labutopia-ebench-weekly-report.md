# 2026-06-22 LabUtopia EBench 接入周报

HTML 版产品汇报页：
`docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html`

## 一句话进展

本周已经把 LabUtopia 的 Franka POC 跑通到端到端 smoke 阶段：任务可以提交、场景可以加载、三个 level-1 任务可以 reset/step、结果可以落盘、最终状态可以正常 complete。

这说明当前最关键的“接入链路”已经打通。需要注意的是，这还不是任务求解成功，也不是官方 baseline 成绩；当前 smoke 使用默认动作，所以三个任务分数都是 `0.0`。2026-06-23 复核后还要补充一点：P0a/P0b 已把 pick/place 的 eval `camera2` 从纯黑修到非黑，但当前渲染/布局验收仍是 blocked，三张静态渲染图未通过视觉 QA，不能继续作为 PM-ready 渲染证据。

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

当前已经能正确加载 LabUtopia 的实验室场景资产，包括桌面、瓶子、烧杯、托盘、干燥箱、门把手等对象。

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

这部分已经通过实际 smoke 验证。这里的“资产加载”只表示 scene overlay 和对象名映射能进入 runtime，不表示 reset 后任务布局、相机画面或可评测视频已经验收。

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

2026-06-23 复核结论：当前三张静态渲染图未通过视觉验收，不能继续作为“任务渲染已闭环”的证据。它们保留为历史问题样例，用来说明下一步必须修复 eval camera、任务布局和可复现截图链路。

```text
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-pick.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-place.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door.jpg
```

这三张图来自同一个 LabUtopia Franka POC 任务包和同一个 LabUtopia overlay 资产根目录，但它们不是正常 eval recorder 产物，而是后补 direct-render 静态图。视觉复核后判定：`level1_pick` 只能算 WARN，`level1_place` 和 `level1_open_door` 是 FAIL。

需要特别说明：

- `run_id=labutopia_franka_render_smoke_20260622_150819` 跑过保存帧 smoke，但 eval recorder 的 `camera2` 帧当前是黑屏。
- 三个任务各 32 帧的 eval `camera2` 抽样统计均为纯黑：RGB min/max/mean 都是 0。
- 2026-06-23 新增 runtime 诊断后，三个任务都定位为 `readback_black_before_recorder`：黑帧在 `get_eval_camera_data()` 后就已经存在，recorder 写盘不是根因。
- 2026-06-23 P0a/P0b 修复后，`level1_pick` 和 `level1_place` 已变为 `readback_visible`，说明 camera axes/pose 和 deterministic lighting 对 pick/place 的黑帧源头有效；但 `level1_open_door` 尚未复验通过，新帧也几乎是纯灰低纹理，仍不能作为任务渲染验收图。
- 进一步检查发现资产/layout 也有硬问题：瓶子/烧杯/托盘仍在源 LabUtopia 坐标的 x≈8-10，干燥箱在 x≈45，把手甚至出现在百米量级坐标。这说明不能只调相机，必须同步修复导入布局。
- 当前 task YAML 仍是 `object_config: {}`、`layout_config.type: null`，还没有把 LabUtopia 原始 position_range 真正落成 GenManip reset-time 布局。
- 因此下一步必须先修复 eval camera/readback、任务布局和可复现截图脚本，再做 reset 后关键帧验收。

## 本周遇到的问题和解决方式

| 问题 | 表现 | 解决方式 | 当前状态 |
| --- | --- | --- | --- |
| 资产根目录不对 | 系统一开始会去错误目录找 LabUtopia 场景 | 增加 LabUtopia manifest 识别逻辑，运行时切换到 overlay asset root | 已解决 |
| 缺少 `meta_info.pkl` | 传统 GenManip 任务依赖采集包里的元信息，LabUtopia POC 没有这份文件 | 针对 LabUtopia POC，从实时场景里自动生成最小可用元信息 | 已解决 |
| camera cleanup 字段缺失 | 切换任务时 camera 清理报字段错误 | 补齐 camera 配置里的 cleanup flags | 已解决 |
| eval recorder `camera2` 黑屏 | 保存过程帧时 `camera2` 输出纯黑 | P0a/P0b 已修 camera axes/pose 和 deterministic lighting；pick/place 已从纯黑变为非黑 readback，open_door 尚未复验通过 | pick/place 部分解除，整体仍 blocked |
| 当前三张渲染图未通过视觉验收 | `pick` 目标不清，`place` 缺 beaker，`open_door` 缺门/把手/开门状态 | 降级为历史失败样例，新增调研记录和 P0-P2 修复计划 | 待重拍 |
| 资产导入/layout 坐标不闭环 | 任务物体仍在源 lab 坐标，open-door handle 导入后坐标异常放大 | 需要重建或补充 overlay，保留 nested part composed transform，并把任务物体归一到机器人工作空间 | 待闭环 |
| 最终进度不 complete | 任务已跑完，但进度没有写入，导致客户端最后等待超时 | 任务结束时写最小 `result_info.json`，并修复进度统计 | 已解决 |
| 后处理异常可能被误记为完成 | 如果后处理报错，不能用 0 分兜底伪装成成功 | 增加 fail-fast 逻辑和回归测试 | 已解决 |
| 端口/结果混淆风险 | EOS 侧也有人在跑任务，担心互相影响 | 使用独立 worktree、独立 run_id、独立端口 18088，并复核 8087 状态 | 已解决 |

## 当前进度判断

| 模块 | 产品视角状态 | 说明 |
| --- | --- | --- |
| LabUtopia 场景接入 | 已跑通 | 场景资产能加载，任务链路能跑完 |
| Franka POC smoke | 已完成 | 3 个任务全部 complete |
| 结果落盘 | 已完成 | per-task 和 final result 都能写出 |
| 渲染图/视频验收 | 未通过 | P0a/P0b 已让 pick/place eval readback 非黑；但画面仍近似纯灰，三张直渲图视觉 QA 不合格，视频和 reset 后任务布局仍需闭环 |
| 任务求解能力 | 未验证 | 当前默认动作得分 0.0，不代表策略能力 |
| 官方 baseline | 未进入本周结论 | 后续单独讨论和规划 |

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
34 passed, 1 skipped

python -m pytest tests/labutopia_poc/test_render_diagnostics_contract.py -q
2 passed

python standalone_tools/labutopia_poc/validate_task_package.py
LabUtopia task package validation OK
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
- P0a/P0b follow-up: `level1_pick/place` now `readback_visible`, but low-texture visual QA is still failed
- P0a/P0b evidence manifest: [docs/labutopia_lab_poc/evidence_manifests/render_p0a_p0b_20260623.json](../labutopia_lab_poc/evidence_manifests/render_p0a_p0b_20260623.json)
- static direct-render evidence: visual QA failed on 2026-06-23
- investigation: [docs/labutopia_lab_poc/render_visual_investigation_20260623.md](../labutopia_lab_poc/render_visual_investigation_20260623.md)
- plan: [docs/superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md](../superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md)

## 下周建议

先把“渲染和布局验收”补成真正闭环，再进入下一阶段机器人/baseline 讨论。

建议顺序：

1. P0a：已修相机 axes/pose 支持，让 pick/place 的 `camera2` 从 eval readback 直接产出非黑帧。
2. P0b：已补 deterministic lighting，避免只靠 direct-render 临时灯光。
3. P1：重建或补充 LabUtopia overlay，把任务对象和 nested handle 保持正确 transform，并放到 Franka 工作空间。
4. P2：用正常 eval-path 重新抓三任务关键帧，写 evidence manifest，并通过独立视觉 QA。
5. P3：图像验收通过后再替换 HTML 里的三张图，并恢复 PM 可见性汇报。
6. P4：再进入 Lift2 复合资产预检和官方 baseline 路线。

## 新增调研和计划文档

- [docs/labutopia_lab_poc/render_visual_investigation_20260623.md](../labutopia_lab_poc/render_visual_investigation_20260623.md)
- [docs/superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md](../superpowers/plans/2026-06-23-labutopia-ebench-render-layout-closure.md)
