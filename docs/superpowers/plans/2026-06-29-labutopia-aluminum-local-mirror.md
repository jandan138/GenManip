# LabUtopia Aluminum Local Mirror Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `Aluminum_Anodized_Charcoal.mdl` 从 remote waiver 改成 package-local mirror follow-up，同时保持 Lift2 baseline contract 语义不变。

**Architecture:** Lift2 Stage 7 继续表示“本地 official-baseline-style contract 可评”，不因为材质 follow-up 重新定义验收标准。Aluminum follow-up 只改变 Aluminum material dependency evidence：`resolution_mode=local_mirror`、本地 `info:mdl:sourceAsset` override、source URL、package-relative mirror path、sha256、bytes、worker `MDL_SYSTEM_PATH` 覆盖，以及 `.mdl` 引用的 texture closure。`material_status=mixed_native_and_fallback` 和 `native_material_closure_claim_allowed=false` 仍保持不变，直到 Stage 2 遗留 fallback surfaces 也完成 native material binding。

**Tech Stack:** Python generator and validator, pytest, USD/MDL package layout, EBench task manifest JSON, LabUtopia docs.

---

## Boundary

这次 follow-up 做三件事：

- 把 `https://omniverse-content-production.s3.us-west-2.amazonaws.com/Materials/Base/Metals/Aluminum_Anodized_Charcoal.mdl` mirror 到本地 package。
- 同步 mirror `.mdl` 内部引用的三张 texture：`Aluminum_Anodized_BaseColor.png`、`Aluminum_Anodized_ORM.png`、`Aluminum_Anodized_Normal.png`。
- 更新 generator、validator、tests、manifest 和文档，让 Aluminum 单项 evidence 从 `explicit_waiver` 变成 `local_mirror`。

这次 follow-up 不做三件事：

- 不把 Aluminum local mirror 写进 Lift2 Stage 7 pass/fail 条件。
- 不把 `material_status` 改成 `resolved_native_material`。
- 不把 `native_material_closure_claim_allowed` 改成 `true`。
- 不宣称 full material closure；`Group/_900_1`、`button`、`panel` 的 fallback displayColor 仍是后续 native material binding follow-up。

## Files

- Modify: `standalone_tools/labutopia_poc/build_asset_overlay.py`
  - 生成 `local_mirror` Aluminum gate、runtime asset、wrapper report、physics report。
  - 在 overlay package 写入 Aluminum `.mdl` 和 texture mirror。
  - 在 wrapper layer 中对 Aluminum Shader 写本地 `info:mdl:sourceAsset` override。
  - 在 material dependency report 中记录 mirror sha、bytes、texture sha、source URL。
- Modify: `standalone_tools/labutopia_poc/validate_task_package.py`
  - 将 expected Aluminum disposition 改为 local mirror。
  - 保留 `mixed_native_and_fallback` 和 closure-open 断言。
  - 增加 mirror file existence、hash、texture dependency records 断言。
- Modify: `tests/labutopia_poc/test_build_asset_overlay.py`
  - RED: generator native strategy 应写出 local mirror evidence。
  - RED: material dependency report 应把 Aluminum 标成 local mirror。
- Modify: `tests/labutopia_poc/test_validate_task_package.py`
  - RED: committed package manifest 应声明 Aluminum local mirror。
  - 保留 Lift2 contract/Stage 4 physics assertions。
- Modify: `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json`
  - Regenerated package manifest evidence；仅 Aluminum 单项从 waiver 改为 local mirror。
- Create: `configs/tasks/ebench/labutopia_lab_poc/common/miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl`
  - Package-local mirrored MDL.
- Create:
  - `configs/tasks/ebench/labutopia_lab_poc/common/miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_BaseColor.png`
  - `configs/tasks/ebench/labutopia_lab_poc/common/miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_ORM.png`
  - `configs/tasks/ebench/labutopia_lab_poc/common/miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_Normal.png`
- Modify: `docs/labutopia_lab_poc/lift2_readiness.md`
  - PM-facing status: Lift2 可评已闭环；Aluminum remote dependency follow-up 独立推进。
- Modify: `docs/superpowers/plans/2026-06-24-ebench-native-dryingbox.md`
  - Acceptance stage wording: material follow-up belongs after Stage 7, not inside Stage 7.

### Task 1: RED Generator Expectations

**Files:**
- Modify: `tests/labutopia_poc/test_build_asset_overlay.py`

- [x] **Step 1: Write the failing test changes**

Change Aluminum assertions in `test_build_asset_overlay_native_strategy_writes_stage4_physics_override_report` to expect local mirror:

```python
assert report["remote_aluminum_disposition"] == "local_mirror"
assert report["material_closure_kept_open"] is True

gate = report["static_material_dependency_gate"]
assert gate["remote_waiver_count"] == 0
assert gate["local_mirror_count"] == 1
record = gate["remote_dependency_records"][0]
assert record["resolution_mode"] == "local_mirror"
assert record["source_url"] == (
    "https://omniverse-content-production.s3.us-west-2.amazonaws.com/"
    "Materials/Base/Metals/Aluminum_Anodized_Charcoal.mdl"
)
assert record["local_mirror_path"] == (
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl"
)
assert record["local_mirror_sha256"]
assert record["local_mirror_bytes"] > 0
assert record["worker_resolved_path"] == (
    "{ASSETS_DIR}/miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl"
)
assert record["worker_mdl_system_path_covered"] is True
assert record["waiver_id"] is None
assert record["waiver_reason"] is None
assert record["closure_claim_allowed"] is False
assert record["aluminum_material_closure_claim_allowed"] is True
assert record["native_material_closure_claim_allowed"] is False
assert record["full_native_material_closure_claim_allowed"] is False
```

Change material dependency assertions to expect:

```python
aluminum = material_dependencies["Aluminum_Anodized_Charcoal"]
assert aluminum["dependency_location_status"] == "local_mirror"
assert aluminum["offline_material_closure_status"] == "resolved_local_mirror"
assert aluminum["remote_aluminum_disposition"] == "local_mirror"
assert aluminum["material_closure_kept_open"] is False
assert aluminum["texture_paths"] == [
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_BaseColor.png",
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_ORM.png",
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_Normal.png",
]
```

- [x] **Step 2: Run test to verify RED**

Run:

```bash
python -m pytest tests/labutopia_poc/test_build_asset_overlay.py::test_build_asset_overlay_native_strategy_writes_stage4_physics_override_report -q
```

Historical RED expectation: before implementation this failed because the generator still emitted `explicit_waiver`.

### Task 2: GREEN Generator Local Mirror

**Files:**
- Modify: `standalone_tools/labutopia_poc/build_asset_overlay.py`

- [x] **Step 1: Add mirror constants**

Add constants near the existing Aluminum waiver constants:

```python
DRYING_BOX_ALUMINUM_SOURCE_URL = (
    "https://omniverse-content-production.s3.us-west-2.amazonaws.com/"
    "Materials/Base/Metals/Aluminum_Anodized_Charcoal.mdl"
)
DRYING_BOX_ALUMINUM_MIRROR_RELATIVE = (
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl"
)
DRYING_BOX_ALUMINUM_TEXTURE_RELATIVES = (
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_BaseColor.png",
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_ORM.png",
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_Normal.png",
)
```

- [x] **Step 2: Implement mirror writing**

Add a helper that copies from bundled package mirror sources into the overlay when building:

```python
def _write_aluminum_local_mirror(overlay_root: Path) -> dict[str, object]:
    mirror_root = overlay_root / "miscs/mdl/labutopia/mdl"
    mirror_root.mkdir(parents=True, exist_ok=True)
    source_root = PACKAGE_ROOT / "common/miscs/mdl/labutopia/mdl"
    files = [DRYING_BOX_ALUMINUM_MIRROR_RELATIVE, *DRYING_BOX_ALUMINUM_TEXTURE_RELATIVES]
    records = []
    for relative in files:
        destination = overlay_root / relative
        source = source_root / Path(relative).relative_to("miscs/mdl/labutopia/mdl")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        records.append(
            {
                "relative_path": relative,
                "sha256": _sha256(destination),
                "bytes": destination.stat().st_size,
            }
        )
    return {
        "mdl": records[0],
        "textures": records[1:],
    }
```

Call this helper before material reports are assembled so manifest evidence references files present in the overlay.

- [x] **Step 3: Convert waiver reports to local mirror**

Change `_drying_box_static_material_dependency_gate()` to emit:

```python
"remote_waiver_count": 0,
"local_mirror_count": 1,
"resolution_mode": "local_mirror",
"source_url": DRYING_BOX_ALUMINUM_SOURCE_URL,
"local_mirror_path": DRYING_BOX_ALUMINUM_MIRROR_RELATIVE,
"local_mirror_sha256": mirror_record["mdl"]["sha256"],
"local_mirror_bytes": mirror_record["mdl"]["bytes"],
"worker_resolved_path": "{ASSETS_DIR}/" + DRYING_BOX_ALUMINUM_MIRROR_RELATIVE,
"worker_mdl_system_path_covered": True,
"waiver_id": None,
"waiver_reason": None,
"closure_claim_allowed": False,
"aluminum_material_closure_claim_allowed": True,
"native_material_closure_claim_allowed": False,
"full_native_material_closure_claim_allowed": False,
```

Keep:

```python
"material_status": "mixed_native_and_fallback"
"material_closure_kept_open": True
```

- [x] **Step 4: Run generator test to verify GREEN**

Run:

```bash
python -m pytest tests/labutopia_poc/test_build_asset_overlay.py::test_build_asset_overlay_native_strategy_writes_stage4_physics_override_report -q
```

Expected: PASS.

### Task 3: RED Validator And Package Manifest

**Files:**
- Modify: `tests/labutopia_poc/test_validate_task_package.py`
- Modify: `standalone_tools/labutopia_poc/validate_task_package.py`

- [x] **Step 1: Change package-level tests to local mirror**

In `test_assets_manifest_declares_stage4_physics_override_and_material_gate`, expect:

```python
assert runtime_asset["remote_aluminum_disposition"] == "local_mirror"
assert runtime_asset["material_closure_kept_open"] is True
assert gate["remote_waiver_count"] == 0
assert gate["local_mirror_count"] == 1
assert aluminum_records[0]["resolution_mode"] == "local_mirror"
assert aluminum_records[0]["waiver_id"] is None
assert aluminum_records[0]["closure_claim_allowed"] is False
assert aluminum_records[0]["aluminum_material_closure_claim_allowed"] is True
assert aluminum_records[0]["native_material_closure_claim_allowed"] is False
assert aluminum_records[0]["full_native_material_closure_claim_allowed"] is False
assert report["material_validator_summary"]["remote_aluminum_disposition"] == "local_mirror"
assert report["material_validator_summary"]["native_material_closure_open"] is True
```

- [x] **Step 2: Run validator tests to verify RED**

Run:

```bash
python -m pytest tests/labutopia_poc/test_validate_task_package.py::test_assets_manifest_declares_stage4_physics_override_and_material_gate -q
```

Historical RED expectation: before the manifest regeneration this failed because committed evidence still recorded `explicit_waiver`.

### Task 4: GREEN Validator And Manifest

**Files:**
- Modify: `standalone_tools/labutopia_poc/validate_task_package.py`
- Modify: `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json`
- Create: Aluminum mirror assets under `configs/tasks/ebench/labutopia_lab_poc/common/miscs/mdl/labutopia/mdl/`

- [x] **Step 1: Add validator expected constants**

Set expected Aluminum gate to local mirror and add expected texture paths:

```python
EXPECTED_DRYING_BOX_REMOTE_ALUMINUM_GATE = {
    "status": "passed",
    "remote_dependency_policy": "local_mirror_required_or_explicit_waiver",
    "remote_unmirrored_unwaived_count": 0,
    "remote_waiver_count": 0,
    "local_mirror_count": 1,
    ...
}
EXPECTED_DRYING_BOX_ALUMINUM_TEXTURE_PATHS = [
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_BaseColor.png",
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_ORM.png",
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_Normal.png",
]
```

- [x] **Step 2: Assert local mirror files and hashes**

In Aluminum material validation, require:

```python
_assert(
    aluminum.get("dependency_location_status") == "local_mirror"
    and aluminum.get("offline_material_closure_status") == "resolved_local_mirror",
    f"{manifest_path}: Aluminum material must be package-local mirror",
)
for key in ("sha256", "bytes", "source_url", "local_mirror_path"):
    _assert(aluminum.get(key), f"{manifest_path}: Aluminum mirror missing {key}")
for texture_path in EXPECTED_DRYING_BOX_ALUMINUM_TEXTURE_PATHS:
    _assert(texture_path in aluminum.get("texture_hashes", {}), ...)
    _assert((PACKAGE_ROOT / "common" / texture_path).exists(), ...)
```

- [x] **Step 3: Copy verified mirror assets into package**

Use the verified files:

```bash
mkdir -p configs/tasks/ebench/labutopia_lab_poc/common/miscs/mdl/labutopia/mdl/Aluminum_Anodized
cp /tmp/labutopia_aluminum_mirror_probe/Aluminum_Anodized_Charcoal.mdl configs/tasks/ebench/labutopia_lab_poc/common/miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl
cp /tmp/labutopia_aluminum_mirror_probe/Aluminum_Anodized/*.png configs/tasks/ebench/labutopia_lab_poc/common/miscs/mdl/labutopia/mdl/Aluminum_Anodized/
```

Expected hashes:

```text
640855d3890c6faaae6346a850ef9f366d4b397c0f4313e25c7ac0b9230c106a  Aluminum_Anodized_Charcoal.mdl
d1d042502d7d94bca13cee10c63ab5b3801fb0a46e26d79169e13f5b9c7b5a31  Aluminum_Anodized_BaseColor.png
768f2dbb4f702a9624b912b431efd1a6a8e0ff3e93744cf54f3866ef8f7986e9  Aluminum_Anodized_ORM.png
6dc1cb1b23a9abd766188a85ccbad1a2639d0a9a334f284e359c6c5d4438608e  Aluminum_Anodized_Normal.png
```

- [x] **Step 4: Regenerate package manifest if needed**

Run the repo’s existing package generation path or the targeted generator command used by prior stages. Then copy the generated manifest evidence into `configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json` only if paths remain package-relative and hashes match local files.

The regenerated manifest must also include the four Aluminum mirror files in top-level `copied_files`, not only in material-specific reports.

- [x] **Step 5: Run validator test to verify GREEN**

Run:

```bash
python -m pytest tests/labutopia_poc/test_validate_task_package.py::test_assets_manifest_declares_stage4_physics_override_and_material_gate -q
```

Expected: PASS.

### Task 5: Docs And Product Explanation

**Files:**
- Modify: `docs/labutopia_lab_poc/lift2_readiness.md`
- Modify: `docs/superpowers/plans/2026-06-24-ebench-native-dryingbox.md`

- [x] **Step 1: Update PM-facing wording**

Add this status language:

```markdown
Aluminum remote dependency follow-up 已从 waiver 进入 local mirror 路线：我们会把官方 Omniverse `Aluminum_Anodized_Charcoal.mdl` 和它引用的三张 texture 放进 EBench package，本地 worker 不再临时去公网取这个材质。这个动作提升离线可复现性，但它不改变 Lift2 baseline contract；Lift2 可评仍看 Stage 7 的任务加载、资产装配、door joint 和 eval readback。full material closure 仍未声明，因为 `Group/_900_1`、`button`、`panel` 还有 fallback displayColor，需要单独做 native binding 修复。
```

- [x] **Step 2: Update acceptance stage wording**

In `2026-06-24-ebench-native-dryingbox.md`, add a post-Stage-7 follow-up section:

```markdown
#### Follow-up: Aluminum local mirror

Scope: independent material closure follow-up after Lift2 contract pass.
Pass condition: `Aluminum_Anodized_Charcoal.mdl` resolves from package-local `miscs/mdl/labutopia/mdl`, sha/bytes are recorded, texture dependencies are local and hashed, and waiver id is removed.
Non-goal: this does not mark `material_status=resolved_native_material` while fallback surfaces still exist.
```

- [x] **Step 3: Verify docs have no false closure claim**

Run:

```bash
rg -n "full material closure|resolved_native_material|explicit_waiver|local_mirror|ALUMINUM_REMOTE_MDL_001" docs/labutopia_lab_poc docs/superpowers/plans
```

Expected: docs distinguish local mirror from full material closure and do not say Stage 7 requires Aluminum local mirror.

### Task 6: Final Verification And Review

**Files:**
- All modified files.

- [x] **Step 1: Run targeted tests**

Run:

```bash
python -m pytest tests/labutopia_poc/test_build_asset_overlay.py tests/labutopia_poc/test_validate_task_package.py tests/labutopia_poc/test_lift2_eval_contract_probe.py -q
```

Expected: all tests pass.

- [x] **Step 2: Run validator CLI**

Run:

```bash
python standalone_tools/labutopia_poc/validate_task_package.py
```

Expected: exits 0.

- [x] **Step 3: Request multi-agent review**

Ask read-only reviewers to check:

```text
1. Contract boundary: no Lift2 Stage 7 pass/fail semantics changed.
2. Material closure: Aluminum mirror is local and hashed, but full closure is not claimed.
3. Docs: PM wording is understandable and does not overpromise.
```

- [x] **Step 4: Commit and push**

Run:

```bash
git status --short
git add standalone_tools/labutopia_poc/build_asset_overlay.py standalone_tools/labutopia_poc/validate_task_package.py tests/labutopia_poc/test_build_asset_overlay.py tests/labutopia_poc/test_validate_task_package.py configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json configs/tasks/ebench/labutopia_lab_poc/common/miscs/mdl/labutopia/mdl docs/labutopia_lab_poc/lift2_readiness.md docs/superpowers/plans/2026-06-24-ebench-native-dryingbox.md docs/superpowers/plans/2026-06-29-labutopia-aluminum-local-mirror.md
git commit -m "docs: plan LabUtopia Aluminum local mirror follow-up"
git push -u origin labutopia-material-aluminum-mirror
git status --short
```

Expected: commit pushed; worktree clean.

## Self-Review

- Spec coverage: plan covers mirror asset placement, generator evidence, validator evidence, tests, docs, and final verification.
- Placeholder scan: no open placeholders remain; all commands and expected outcomes are concrete.
- Type consistency: all contract fields use existing manifest vocabulary: `remote_aluminum_disposition`, `static_material_dependency_gate`, `material_validator_summary`, `local_mirror_path`, `worker_mdl_system_path_covered`, `material_closure_kept_open`.
