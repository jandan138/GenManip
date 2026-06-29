# Cold Runtime Sandbox Probe Design

## Context

The LabUtopia DryingBox acceptance lane now has static offline dependency validation: known MDL, texture, static gate, helper import, and source-scene copied records must resolve locally, match SHA256/bytes, avoid remote/cache paths, and stay within allowed roots. That closes the deterministic file-dependency layer.

The next gap is runtime isolation. Static validation says the files are present and hash-checked; it does not prove a copied package can compose from a cold directory with user caches isolated and runtime paths redirected to the copied asset root.

## Goal

Add a first `Cold Runtime Sandbox Probe` that proves a named LabUtopia package can be copied into a cold sandbox and composed through a minimal runtime path using only declared local package roots and explicit allowlisted built-ins.

The v1 success claim is deliberately narrow:

```text
cold_runtime_sandbox_probe_passed=true
```

This means:

- static package validation passed before the runtime probe;
- package config files were copied into a sandbox package config root;
- package `common/` runtime files were merged into a sandbox asset root using paths relative to `common/`, and the declared `overlay_root` was copied into the same asset root;
- child process environment used isolated `HOME` and cache roots;
- `{ASSETS_DIR}` and runtime search paths resolved to the sandbox copy;
- required USD composition completed in the child process;
- configured runtime asset paths and discovered runtime dependencies did not resolve back to source `/cpfs/...`, user caches, or remote URIs;
- built-in runtime dependencies, such as explicit `/isaac-sim/materials` entries, were counted separately from unauthorized outside-sandbox paths;
- output manifest records command, environment boundary, artifacts, hashes, and claim boundary.

It keeps these broader claims false:

```text
official_leaderboard_claim_allowed=false
policy_success_claim_allowed=false
pm_showcase_ready=false
native_material_closure_claim_allowed=false
full_native_material_closure_claim_allowed=false
```

## Approaches Considered

1. **Recommended: pure-Python subprocess/env isolation with `pxr-compose` as the required gate.**
   Copy the package config, merge package common runtime files into a temporary sandbox asset root, copy the asset overlay into that same root, isolate child environment variables, run a child subprocess that opens the copied runtime USD with `pxr.Usd`, and inspect resolved runtime paths. This is deterministic enough for local CI and directly tests the gap left by static offline validation.

2. **Orchestrated wrapper around existing heavy runtime probes.**
   Run `run_native_dryingbox_smoke.py` or the Stage 7 Lift2 contract path inside the cold sandbox. This is stronger runtime proof, but heavier and more environment-sensitive. It should be supported as optional modes after the required `pxr-compose` mode is stable.

3. **OS-level network-blocked sandbox.**
   Use `unshare`, `firejail`, Docker, or iptables to enforce kernel-level network isolation. This is the strongest cold-run proof, but may require privileges unavailable in the current environment. v1 must not overclaim kernel network blocking. It records `network_isolation_mode=best_effort_env_and_resolved_dependency_probe` unless a real OS-level guard is available.

## Recommended Design

Create:

```text
standalone_tools/labutopia_poc/cold_runtime_sandbox_probe.py
```

The required first mode is:

```text
--mode pxr-compose
```

Future optional modes can be added without changing the core report contract:

```text
--mode isaac-python-smoke
--mode lift2-contract
```

`isaac-python-smoke` must run through `/isaac-sim/python.sh` and remain opt-in/manual or nightly. It is skipped unless `/isaac-sim/python.sh` is executable and `LABUTOPIA_RUN_HEAVY_ISAAC_TESTS=1` is set. The default Python environment should not be expected to import `isaacsim`.

## Sandbox Layout

The parent runner builds a temporary layout like this:

```text
sandbox_root/
  package_config/
    configs/tasks/ebench/labutopia_lab_poc/...
  assets/
    miscs/...
    scene_usds/...
    assets/...
  home/
  cache/
  reports/
```

Copy rules:

- copy `configs/tasks/ebench/labutopia_lab_poc` to `sandbox_root/package_config/configs/tasks/ebench/labutopia_lab_poc`;
- copy package `common/` runtime files, including local mirror MDL and texture files, into `sandbox_root/assets` using paths relative to `common/`, so `common/miscs/mdl/test.mdl` becomes `sandbox_root/assets/miscs/mdl/test.mdl`;
- copy the declared `overlay_root` into `sandbox_root/assets`, preserving the runtime relative paths expected by `{ASSETS_DIR}`;
- if the `common/` copy and overlay copy target the same relative file, require byte-identical content or fail before child runtime;
- do not mutate the source manifest or source package files;
- run the child process only against the sandbox copies.

This makes the probe closer to how a packaged EBench worker will see the task: config is local, the runtime asset root is local, and source-machine `/cpfs/...` paths are not supposed to be needed for composition.

## Parent Runner Responsibilities

The parent runner:

- reads `assets_manifest.json`;
- runs `validate_task_package.py` or calls the validator before any runtime probe;
- supports an injectable static-validation command/callable for tests, defaulting to the real package validator in production runs;
- builds the sandbox layout above;
- creates isolated directories for `HOME`, `XDG_CACHE_HOME`, `OV_USER_CACHE_DIR`, `PIP_CACHE_DIR`, and other tool-specific cache variables that are present in the environment;
- rewrites runtime env values such as `{ASSETS_DIR}`, `PXR_AR_DEFAULT_SEARCH_PATH`, `MDL_SYSTEM_PATH`, and `MDL_USER_PATH` to the sandbox copy plus explicit allowlisted built-in roots;
- launches a child process using the same Python executable for `--mode pxr-compose`;
- enforces a deterministic default child timeout of 120 seconds, overridable by CLI;
- captures stdout, stderr, exit code, generated child report, artifact hashes, and duration;
- emits a machine-readable JSON report.

## Child Probe Responsibilities

The child probe receives the copied runtime scene path and:

- opens it with `pxr.Usd.Stage.Open`;
- calls `stage.Load()` so payloads are pulled into the composed stage;
- verifies required prims exist;
- discovers composed stage dependencies with `UsdUtils.ComputeAllDependencies` or the closest available `pxr` equivalent;
- traverses composed prim attributes and relationships for `Sdf.AssetPath` values, including `info:mdl:sourceAsset`;
- parses local MDL text for `import` and `texture_2d(...)` references, reusing the existing material audit patterns;
- rejects remote URI dependencies;
- rejects user cache paths;
- rejects unauthorized outside-sandbox runtime paths;
- records allowlisted built-in paths separately, for example `/isaac-sim/materials`;
- records composition status and dependency findings.

## Required Prim Sources

The probe should derive required prim paths from existing task metadata instead of hard-coding a single visual guess. The initial required set is:

- wrapper object root from the first available source in this order: `drying_box_runtime_asset.wrapper_prim_path`, `asset_acceptance.acceptance_stages[0].evidence.wrapper_prim_path`, then object mapping for `obj_DryingBox_01`;
- nested handle path from task semantics or the articulation contract;
- door joint path from `level1_open_door.yml` and the DryingBox acceptance contract;
- wrapper-local `/Looks` scope used by the packaged material bindings;
- task object roots for the selected lane;
- runtime scene root derived from `RUNTIME_USD_NAME`.

The report must include:

```json
{
  "required_prim_records": [],
  "missing_required_prim_paths": []
}
```

Any missing required prim prevents `PASS`.

## Runtime Dependency Discovery

The dependency scan has three levels:

1. **USD layer dependencies**
   Use `UsdUtils.ComputeAllDependencies(stage.GetRootLayer().identifier)` or an equivalent `pxr` API to collect layers, sublayers, references, payloads, and clips that the composed stage needs.

2. **Composed asset-path values**
   Traverse all prims, attributes, metadata, and relationships that can carry `Sdf.AssetPath` values. Record authored value, resolved path when available, dependency type, owning prim, and owning property.

3. **Local MDL dependency expansion**
   For every local MDL file discovered by USD dependency scanning, parse text for:

   ```text
   import "relative_or_absolute_file.mdl"
   import helper_module;
   import ::package::helper_module;
   texture_2d("relative_or_absolute_texture.png")
   ```

   Recursively inspect local helper MDL imports and texture references. Module-style imports should be resolved through the same effective MDL search paths used by the child process. Remote URI, user cache, source-machine absolute path, or unauthorized outside-sandbox leakage in nested MDL dependencies is a `FAIL`.

## Report Contract

The report should include:

```json
{
  "schema_version": 1,
  "status": "PASS",
  "mode": "pxr-compose",
  "asset_id": "LabUtopia/DryingBox_01",
  "task_lane": "ebench/labutopia_lab_poc/lift2_candidate",
  "started_at_utc": "2026-06-29T00:00:00Z",
  "ended_at_utc": "2026-06-29T00:00:10Z",
  "command": [],
  "child_timeout_seconds": 120,
  "static_validation": {
    "status": "PASS",
    "command": "python standalone_tools/labutopia_poc/validate_task_package.py"
  },
  "sandbox": {
    "sandbox_root": "/tmp/labutopia_cold_runtime_x",
    "package_config_root": "/tmp/labutopia_cold_runtime_x/package_config",
    "assets_dir": "/tmp/labutopia_cold_runtime_x/assets",
    "home": "/tmp/labutopia_cold_runtime_x/home",
    "xdg_cache_home": "/tmp/labutopia_cold_runtime_x/cache",
    "network_isolation_mode": "best_effort_env_and_resolved_dependency_probe"
  },
  "environment": {
    "effective_mdl_system_path_entries": [],
    "effective_mdl_user_path_entries": [],
    "effective_pxr_search_path_entries": [],
    "non_allowlisted_search_path_count": 0,
    "original_overlay_search_path_count": 0,
    "user_cache_env_count": 0
  },
  "runtime": {
    "runtime_scene": "/tmp/labutopia_cold_runtime_x/assets/scene_usds/labutopia/level1_poc/lab_001/scene.usda",
    "composition_ok": true,
    "required_prim_records": [],
    "missing_required_prim_paths": [],
    "resolved_runtime_dependency_records": [],
    "remote_uri_count": 0,
    "user_cache_path_count": 0,
    "unauthorized_outside_sandbox_runtime_path_count": 0,
    "allowlisted_builtin_runtime_path_count": 0
  },
  "artifacts": {
    "stdout_path": "",
    "stderr_path": "",
    "child_report_path": "",
    "sha256": {}
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

`status` must be `PASS`, `FAIL`, or `BLOCKED`:

- `PASS`: static validation passed, child process passed, required prims exist, and runtime path checks have zero remote/cache/unauthorized outside-sandbox findings.
- `FAIL`: runtime path leakage, remote URI, cache path, missing required prim, non-allowlisted search path, or composition error was detected.
- `BLOCKED`: required environment or runtime was unavailable, child process timed out, or static validation could not run.

## Runtime Path Boundary

The probe must distinguish runtime dependencies from provenance metadata:

- absolute provenance fields in `assets_manifest.json` may point to `/cpfs/...`; those are not runtime dependencies;
- runtime scene references, payloads, MDL source assets, texture assets, and configured runtime search paths must resolve under the sandbox copy or an explicit allowlist root;
- `{ASSETS_DIR}` must be substituted with the sandbox `assets_dir`, not the original overlay root;
- `source_url` remains provenance only and cannot become a runtime path.

Allowlist policy:

- `sandbox_root/assets` and `sandbox_root/package_config` are normal allowed roots;
- explicit built-ins such as `/isaac-sim/materials` may be counted under `allowlisted_builtin_runtime_path_count`;
- any other absolute runtime path outside the sandbox is counted under `unauthorized_outside_sandbox_runtime_path_count` and prevents `PASS`;
- any `MDL_SYSTEM_PATH`, `MDL_USER_PATH`, `PXR_AR_DEFAULT_SEARCH_PATH`, or equivalent search path entry outside the sandbox and outside the explicit built-in allowlist increments `non_allowlisted_search_path_count` and prevents `PASS`.

## Claim Boundary

PM wording allowed after v1 PASS:

```text
这个资产包已经通过 cold runtime sandbox 的第一层验证：复制到冷目录后，USD 能在隔离 HOME/cache 的子进程里 compose。配置和解析出的运行时依赖没有回源到原始 /cpfs 路径，没有指向公网 URI，也没有指向用户 cache。
```

Important caveat:

```text
这不是系统级断网证明；v1 没有使用 kernel network namespace、firewall 或 container network block。它证明的是我们能解析到的运行时依赖没有 remote URI / cache / source-path leakage。
```

PM wording not allowed:

```text
官方榜单已复现。
策略已经成功。
图片可直接对外展示。
source-native full material closure 已完成。
```

## Tests

Add:

```text
tests/labutopia_poc/test_cold_runtime_sandbox_probe.py
```

Required tests:

- report claim boundary keeps official leaderboard, policy success, PM showcase, and native material closure claims false;
- static validation failure prevents `PASS`;
- the parent runner can inject a stub static-validation command/callable so tiny USD fixture tests remain hermetic;
- remote URI dependency produces `FAIL`;
- user cache dependency produces `FAIL`;
- absolute runtime dependency to the original `/cpfs/...` source path produces `FAIL`;
- uppercase remote URI and uppercase cache-like path are still rejected;
- `{ASSETS_DIR}` substitution points to the sandbox copy;
- `MDL_SYSTEM_PATH`, `MDL_USER_PATH`, and `PXR_AR_DEFAULT_SEARCH_PATH` entries are recorded;
- non-allowlisted search path leakage prevents `PASS`;
- local MDL helper imports are inspected;
- module-style MDL imports such as `import helper;` and `import ::pkg::helper;` are inspected;
- nested `texture_2d(...)` references are inspected;
- nested MDL remote/cache/outside-sandbox leakage prevents `PASS`;
- built-in `/isaac-sim/materials` dependency is counted as allowlisted, not unauthorized;
- missing required prim prevents `PASS`;
- child process failure becomes `BLOCKED` or `FAIL`, never partial `PASS`;
- a tiny local USD fixture can compose in `pxr-compose` mode and produce `PASS`;
- optional `isaac-python-smoke` mode is skipped unless `/isaac-sim/python.sh` is executable and `LABUTOPIA_RUN_HEAVY_ISAAC_TESTS=1` is set.

## Non-Goals

- Do not make `isaac-python-smoke` required in v1.
- Do not run official Lift2 baseline or policy evaluation in this stage.
- Do not claim kernel-enforced network isolation unless the command actually uses an OS-level network namespace or equivalent.
- Do not mutate the package manifest.
- Do not replace static offline dependency validation; run it first and treat it as a prerequisite.
- Do not upgrade source-native material claims.

## Acceptance Criteria

- A spec and implementation plan exist for the cold runtime sandbox probe.
- The v1 implementation exposes a deterministic `pxr-compose` mode.
- The sandbox contains package config files, package `common/` runtime files, and the declared asset overlay.
- Package `common/` runtime files are merged into the sandbox asset root using paths relative to `common/`, not hidden under `assets/common`.
- The child process opens the sandbox runtime scene with `pxr.Usd.Stage.Open` and `stage.Load()`.
- Runtime dependency discovery covers USD layer dependencies, composed `Sdf.AssetPath` values, local MDL imports, and `texture_2d(...)` texture references.
- The report schema records sandbox env, effective search paths, child command, required prim findings, runtime path findings, artifacts, and claim boundary.
- Tests cover PASS, FAIL, and BLOCKED paths.
- Existing `validate_task_package.py` and `tests/labutopia_poc` continue passing.
