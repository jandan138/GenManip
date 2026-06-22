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

目前没有保留“产品可审阅”的渲染图或视频证据。

原因是这次 smoke 的目标是先验证接入链路，所以运行时使用了：

```text
--no_save_process
--frame_save_interval 0
```

这会关闭过程图片/视频保存，减少运行成本和干扰。因此当前证据主要是：

- server/client 成功完成
- 场景资产路径解析正确
- reset/step 正常返回
- 3 个任务都有 `result_info.json`
- 最终 status 是 `complete`

这能证明“链路跑通”，但不能证明“画面渲染效果符合产品预期”。渲染图验收需要作为后续单独一项补上。

建议下一次渲染验收保留：

```text
reset 后第一帧截图
每个任务一张关键视角截图
必要时保留短视频或 merged mp4
```

## 本周遇到的问题和解决方式

| 问题 | 表现 | 解决方式 | 当前状态 |
| --- | --- | --- | --- |
| 资产根目录不对 | 系统一开始会去错误目录找 LabUtopia 场景 | 增加 LabUtopia manifest 识别逻辑，运行时切换到 overlay asset root | 已解决 |
| 缺少 `meta_info.pkl` | 传统 GenManip 任务依赖采集包里的元信息，LabUtopia POC 没有这份文件 | 针对 LabUtopia POC，从实时场景里自动生成最小可用元信息 | 已解决 |
| camera cleanup 字段缺失 | 切换任务时 camera 清理报字段错误 | 补齐 camera 配置里的 cleanup flags | 已解决 |
| 最终进度不 complete | 任务已跑完，但进度没有写入，导致客户端最后等待超时 | 任务结束时写最小 `result_info.json`，并修复进度统计 | 已解决 |
| 后处理异常可能被误记为完成 | 如果后处理报错，不能用 0 分兜底伪装成成功 | 增加 fail-fast 逻辑和回归测试 | 已解决 |
| 端口/结果混淆风险 | EOS 侧也有人在跑任务，担心互相影响 | 使用独立 worktree、独立 run_id、独立端口 18088，并复核 8087 状态 | 已解决 |

## 当前进度判断

| 模块 | 产品视角状态 | 说明 |
| --- | --- | --- |
| LabUtopia 场景接入 | 已跑通 | 场景资产能加载，任务链路能跑完 |
| Franka POC smoke | 已完成 | 3 个任务全部 complete |
| 结果落盘 | 已完成 | per-task 和 final result 都能写出 |
| 渲染图/视频验收 | 未完成 | 本轮没有保存图片/视频，需要后续补 |
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

## 下周建议

先补一个“渲染图验收”小闭环，再进入下一阶段机器人/baseline 讨论。

建议顺序：

1. 开一轮保存图片的短 smoke。
2. 为三个任务各保留 reset 后截图。
3. 检查截图里场景、目标物、桌面、门/干燥箱是否可见且位置合理。
4. 更新本周证据文档，明确“渲染验收通过/未通过”。
5. 再进入下一阶段机器人和 baseline 的细化讨论。
