# Asset Acceptance Reusable Validators Design

## Context

DryingBox is now the first reference asset for the `EBench Asset Acceptance Pipeline`. The pipeline has machine-readable `acceptance_stages`, generic material claim derivation in `material_closure.py`, and DryingBox-specific package validation in `validate_task_package.py`.

The next useful step is not another DryingBox-only rule. It is to extract the reusable validation shape that future assets need: a caller should be able to pass an expected material closure contract and provenance blocker list, then get the same strict checks currently protecting DryingBox.

## Approaches Considered

1. **Recommended: small helper module with typed expectations.** Add `standalone_tools/labutopia_poc/asset_acceptance_validation.py` with dataclasses for material closure expectations and native provenance blockers. `validate_task_package.py` keeps DryingBox constants but delegates reusable checks to the helper. This is low risk and gives future assets a clear API.

2. **Large validator rewrite.** Replace most of `_validate_asset_acceptance_material_closure()` with a generic registry-driven validator. This would reduce duplication eventually, but the file also validates package paths, physics override reports, camera contracts, and DryingBox-specific USD assumptions. Doing it now risks changing behavior without product value.

3. **Documentation-only standard.** Keep code as-is and only document how to add a new asset. This is insufficient: future assets could still copy/paste incomplete checks or forget `native_material_provenance` enforcement.

## Recommended Design

Create a reusable helper module:

```text
standalone_tools/labutopia_poc/asset_acceptance_validation.py
```

It owns validation primitives that are asset-agnostic:

- `NativeMaterialProvenanceBlocker`: expected source prim, runtime prim, runtime material, and source binding status.
- `MaterialClosureExpectation`: expected asset id, material status, derived counts, source-resolved runtime paths, wrapper-authored runtime paths, wrapper-authored material targets, and native provenance blockers.
- `assert_asset_acceptance_material_closure(manifest_path, material, expectation, related_reports=None)`: validates schema, counts, claim boundary, records, and native provenance blockers.

The helper should raise `AssertionError` with the same message fragments currently used by `validate_task_package.py`, such as `material closure derived_counts mismatch`, `native material provenance blocker mismatch`, and `native material provenance blockers must retain source evidence and blocked claims`.

`validate_task_package.py` remains the package-level orchestrator. It should keep DryingBox constants and package cross-checks that are not generic, such as static gate dependency records deriving from `drying_box_wrapper_composition`. The new helper handles the reusable material closure shape, while DryingBox-specific USD/material dependency checks stay in place.

## Data Flow

1. `build_asset_overlay.py` writes `asset_acceptance.material_closure`.
2. `validate_task_package.py` loads `common/assets_manifest.json`.
3. `validate_task_package.py` builds a DryingBox `MaterialClosureExpectation` from existing constants.
4. `assert_asset_acceptance_material_closure()` validates the generic material contract.
5. `validate_task_package.py` performs extra DryingBox cross-checks against `drying_box_wrapper_composition`, static material gate, and runtime USD reports.

## Error Handling

Keep `AssertionError` because existing tests and CLI behavior already rely on it. The helper should not print, mutate manifests, or read files. It should accept `manifest_path` only for diagnostic messages.

The helper must reject:

- missing `asset_acceptance.material_closure`
- wrong `asset_id` or `schema_version`
- derived count mismatches
- package/native claim boundary overclaims
- missing or malformed source-resolved and wrapper-authored records
- missing or malformed `native_material_provenance`
- wrong provenance blocker paths, material targets, source binding statuses, blocker count, `source_material_binding`, replacement flag, or `blocked_claims`

## Testing

Add focused unit tests for the helper in:

```text
tests/labutopia_poc/test_asset_acceptance_validation.py
```

Tests should cover:

- a minimal valid material closure with two native provenance blockers
- mismatch in provenance blocker path
- mismatch in source binding status
- native/full-native overclaim while wrapper-authored materials remain

Then update existing package tests to ensure `validate_task_package.py` still rejects the DryingBox provenance mismatch and the full package validator still passes.

## Non-Goals

- Do not rewrite the whole package validator.
- Do not change the manifest schema emitted by `build_asset_overlay.py`.
- Do not make DryingBox `full_native_material_closure_claim_allowed=true`.
- Do not move USD runtime, physics, camera, or Lift2 contract validation into the new helper.

## Acceptance Criteria

- Future assets can reuse the helper by constructing `MaterialClosureExpectation`.
- DryingBox validation behavior and error message fragments remain compatible with current tests.
- `python standalone_tools/labutopia_poc/validate_task_package.py` passes.
- `python -m pytest tests/labutopia_poc -q` passes.
- Worktree is committed and pushed cleanly.
