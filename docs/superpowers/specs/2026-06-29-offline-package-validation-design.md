# Offline Package Validation Design

## Context

The DryingBox package now has strong material and physics evidence, and the reusable material validator has separated generic material-closure shape from DryingBox-specific constants. The next pipeline gap is `cold/offline package validation`: proving that known USD, MDL, texture, payload, and material dependency records no longer require network or user cache at runtime.

Current validation already checks many DryingBox facts, but the logic is embedded in `validate_task_package.py`. It verifies the Aluminum local mirror, texture hashes, `MDL_SYSTEM_PATH` coverage, and static material dependency gate. That is good DryingBox coverage, but future assets still lack a reusable helper that can reject remote runtime paths, missing local files, hash drift, or byte-count drift from common dependency records.

## Approaches Considered

1. **Recommended: static offline dependency helper.** Add a pure helper module such as `offline_package_validation.py` that consumes existing dependency records and allowed roots. It validates local paths, hashes, byte counts, remote URI blocking, and explicit waiver boundaries. `validate_task_package.py` keeps DryingBox-specific expectations and calls the helper for reusable file-dependency checks.

2. **New manifest section.** Add `asset_acceptance.offline_package` with a full dependency inventory for every USD, MDL, texture, payload, and reference. This may be cleaner later, but it changes the manifest contract before the current fields have proven insufficient and would duplicate existing `material_dependency_report`, `static_material_dependency_gate`, and `acceptance_stages` data.

3. **Full cold sandbox runtime probe.** Copy the package into an isolated directory, clear caches, block network, and run USD or Isaac composition there. This is stronger proof, but too heavy as the first step because it depends on Isaac/Omniverse runtime behavior and can be flaky. It should follow deterministic static validation.

## Recommended Design

Create a focused reusable module:

```text
standalone_tools/labutopia_poc/offline_package_validation.py
```

It should expose:

```python
@dataclass(frozen=True)
class OfflineDependencyRoots:
    package_root: Path
    overlay_root: Path | None = None


@dataclass(frozen=True)
class OfflineDependencyExpectation:
    allowed_location_statuses: set[str]
    required_local_path_fields: set[str]
    optional_informational_uri_fields: set[str]


def assert_offline_dependency_records(
    manifest_path: object,
    records: object,
    roots: OfflineDependencyRoots,
    expectation: OfflineDependencyExpectation,
) -> None:
    ...
```

The helper is read-only. It should not crawl USD or mutate manifests in this phase. It only validates records already produced by existing pipeline steps. For this first implementation, the caller supplies record lists from:

- `drying_box_wrapper_composition.material_dependency_report`
- nested `texture_dependency_records`
- `static_material_dependency_gate.remote_dependency_records`

The helper should validate:

- Fields such as `local_mirror_path`, `relative_path`, and `worker_resolved_path` resolve under `package_root` or explicit `overlay_root`.
- Runtime dependency fields cannot point to `http://`, `https://`, `omniverse://`, S3, user cache, or arbitrary absolute paths.
- `source_url` remains allowed only as provenance metadata for records that have local mirror evidence.
- Any record claiming `local_mirror_copied_with_package`, `local_file_copied_with_source_scene`, or `resolution_mode=local_mirror` has a local file, positive byte count, and SHA256.
- Hash and byte-count mismatches fail.
- `explicit_waiver` records are allowed only when they do not claim package/full/native material closure.

`validate_task_package.py` remains the DryingBox orchestrator. It should keep exact DryingBox constants: expected Aluminum hash, expected Aluminum texture set, `MDL_SYSTEM_PATH`, wrapper-local overrides, native provenance blockers, and physics report paths. The reusable helper only removes repeated file-dependency mechanics.

## Claim Boundary

Passing offline dependency validation means:

```text
offline_package_dependencies_resolved=true
```

It does not imply:

```text
full_native_material_closure_claim_allowed=true
official_leaderboard_claim_allowed=true
policy_success_claim_allowed=true
pm_showcase_ready=true
```

PM wording should be: "known package dependencies are local and hash-checked." It should not be: "the asset is fully native-material closed" or "official EBench score is ready."

## Error Handling

Keep `AssertionError` for consistency with existing validators. Error messages should name the manifest path, material/dependency record identity when available, and the failing field, for example:

```text
assets_manifest.json: Aluminum_Anodized_Charcoal local_mirror_path is missing
assets_manifest.json: Aluminum_Anodized_Charcoal local_mirror_path hash mismatch
assets_manifest.json: texture dependency worker_resolved_path must not point to a remote URI
```

## Testing

Add focused unit tests in:

```text
tests/labutopia_poc/test_offline_package_validation.py
```

Tests should cover:

- valid local mirror MDL and texture records
- remote runtime URI rejection while preserving informational `source_url`
- missing file rejection
- SHA256 mismatch rejection
- byte-count mismatch rejection
- absolute outside-root path rejection
- explicit waiver does not allow closure claims

Then integrate with `validate_task_package.py` and keep existing DryingBox tests passing. A narrow DryingBox regression test should corrupt one copied dependency record in a fixture and prove the package validator rejects it.

## Non-Goals

- Do not add a new manifest section in this step.
- Do not build a network-blocking sandbox runner in this step.
- Do not weaken existing DryingBox-specific checks.
- Do not change material closure claim derivation.
- Do not claim source-native full material closure from offline file presence alone.

## Acceptance Criteria

- Future assets can reuse `assert_offline_dependency_records()` for local file/hash/remote-path checks.
- DryingBox package validation still passes and still keeps existing Aluminum-specific exact checks.
- Tests cover valid, missing, remote, hash mismatch, byte mismatch, outside-root, and waiver cases.
- `python standalone_tools/labutopia_poc/validate_task_package.py` passes.
- `python -m pytest tests/labutopia_poc -q` passes.
- Worktree is committed and pushed cleanly.
