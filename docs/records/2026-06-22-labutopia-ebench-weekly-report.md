# 2026-06-22 LabUtopia EBench 接入周报

HTML 版产品汇报页：
`docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/index.html`

## 一句话进展

本周已经把 LabUtopia 的 Franka POC 跑通到端到端 smoke 阶段：任务可以提交、场景可以加载、三个 level-1 任务可以 reset/step、结果可以落盘、最终状态可以正常 complete。

这说明当前最关键的“接入链路”已经打通。需要注意的是，这还不是任务求解成功，也不是官方 baseline 成绩；当前 smoke 使用默认动作，所以三个任务分数都是 `0.0`。

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

这部分已经通过实际 smoke 验证。

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

已补三张静态渲染图，放在 HTML 汇报页里：

```text
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-pick.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-place.jpg
docs/records/evidence/2026-06-22-labutopia-ebench-weekly-report/assets/labutopia-franka-level1-open-door.jpg
```

这三张图来自同一个 LabUtopia Franka POC 任务包和同一个 LabUtopia overlay 资产根目录，均在 Isaac/Replicator 中从 EBench/GenManip 加载后的 stage 抓取。它们可以作为“资产可见性证据”，但还不能作为“画面/视频/任务布局已经验收”的结论。

需要特别说明：

- `run_id=labutopia_franka_render_smoke_20260622_150819` 跑过保存帧 smoke，但 eval recorder 的 `camera2` 帧当前是黑屏。
- 因此 HTML 里使用的是同一加载路径下的直渲静态截图，只补了报告用光照和相机视角，不改变任务配置、结果分数或 evaluator 逻辑。
- 当前还观察到部分对象的可见 mesh bbox、wrapper pose、任务语义坐标没有完全对齐；下一步必须修复这个问题，再做 reset 后关键帧验收。

## 本周遇到的问题和解决方式

| 问题 | 表现 | 解决方式 | 当前状态 |
| --- | --- | --- | --- |
| 资产根目录不对 | 系统一开始会去错误目录找 LabUtopia 场景 | 增加 LabUtopia manifest 识别逻辑，运行时切换到 overlay asset root | 已解决 |
| 缺少 `meta_info.pkl` | 传统 GenManip 任务依赖采集包里的元信息，LabUtopia POC 没有这份文件 | 针对 LabUtopia POC，从实时场景里自动生成最小可用元信息 | 已解决 |
| camera cleanup 字段缺失 | 切换任务时 camera 清理报字段错误 | 补齐 camera 配置里的 cleanup flags | 已解决 |
| eval recorder `camera2` 黑屏 | 保存过程帧时 `camera2` 输出黑屏 | 已补同一加载路径下的直渲静态图用于 PM 可见性汇报 | 待修复 |
| 可见 mesh 与 wrapper pose 未完全对齐 | 部分对象 bbox、wrapper pose、任务语义坐标存在偏移 | 先降级为“资产可见性证据”，不宣称任务布局验收完成 | 待闭环 |
| 最终进度不 complete | 任务已跑完，但进度没有写入，导致客户端最后等待超时 | 任务结束时写最小 `result_info.json`，并修复进度统计 | 已解决 |
| 后处理异常可能被误记为完成 | 如果后处理报错，不能用 0 分兜底伪装成成功 | 增加 fail-fast 逻辑和回归测试 | 已解决 |
| 端口/结果混淆风险 | EOS 侧也有人在跑任务，担心互相影响 | 使用独立 worktree、独立 run_id、独立端口 18088，并复核 8087 状态 | 已解决 |

## 当前进度判断

| 模块 | 产品视角状态 | 说明 |
| --- | --- | --- |
| LabUtopia 场景接入 | 已跑通 | 场景资产能加载，任务链路能跑完 |
| Franka POC smoke | 已完成 | 3 个任务全部 complete |
| 结果落盘 | 已完成 | per-task 和 final result 都能写出 |
| 渲染图/视频验收 | 已补静态可见性证据 | 已有三张直渲图；`camera2`、视频和 reset 后任务布局仍需闭环 |
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
23 passed, 1 skipped

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

渲染补证：

```text
run_id=labutopia_franka_render_smoke_20260622_150819
eval recorder camera2 frames: black
static direct-render evidence: 3 jpg files under docs/records/evidence/.../assets/
```

## 下周建议

先把“渲染和布局验收”补成真正闭环，再进入下一阶段机器人/baseline 讨论。

建议顺序：

1. 修复 eval recorder 的 `camera2` 黑屏问题。
2. 修复或解释可见 mesh bbox、wrapper pose、任务语义坐标的偏移。
3. 为三个任务各保留 reset 后关键截图。
4. 检查截图里目标物、桌面、门/干燥箱是否可见且位置合理。
5. 再进入 Lift2 复合资产预检和官方 baseline 路线。
