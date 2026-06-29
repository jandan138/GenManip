from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from standalone_tools.labutopia_poc.material_closure import (
    assert_material_claims_are_derived,
)


EXPECTED_NATIVE_BLOCKED_CLAIMS = [
    "native_material_closure",
    "full_native_material_closure",
]


@dataclass(frozen=True)
class NativeMaterialProvenanceBlocker:
    source_prim_path: str
    runtime_prim_path: str
    runtime_material_path: str
    source_binding_status: str

    @property
    def path_key(self) -> tuple[str, str, str]:
        return (
            self.source_prim_path,
            self.runtime_prim_path,
            self.runtime_material_path,
        )


@dataclass(frozen=True)
class MaterialClosureExpectation:
    asset_id: str
    material_status: str
    derived_counts: dict[str, int]
    source_resolved_runtime_paths: set[str]
    wrapper_authored_runtime_paths: set[str]
    wrapper_authored_material_targets: set[str]
    native_provenance_blockers: set[NativeMaterialProvenanceBlocker]

    @property
    def native_provenance_path_keys(self) -> set[tuple[str, str, str]]:
        return {blocker.path_key for blocker in self.native_provenance_blockers}

    @property
    def native_binding_status_by_source(self) -> dict[str, str]:
        return {
            blocker.source_prim_path: blocker.source_binding_status
            for blocker in self.native_provenance_blockers
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _path(path: object) -> str:
    return str(path)


def assert_asset_acceptance_material_closure(
    manifest_path: object,
    material: object,
    expectation: MaterialClosureExpectation,
    related_reports: dict[str, Any] | None = None,
) -> None:
    prefix = _path(manifest_path)
    _require(
        related_reports is None or isinstance(related_reports, dict),
        f"{prefix}: related_reports must be a mapping when provided",
    )
    _require(
        isinstance(material, dict),
        f"{prefix}: missing asset_acceptance.material_closure",
    )
    _require(
        material.get("asset_id") == expectation.asset_id,
        f"{prefix}: material closure asset_id mismatch",
    )
    _require(
        material.get("schema_version") == 1,
        f"{prefix}: material closure schema_version must be 1",
    )
    counts = material.get("derived_counts")
    _require(
        isinstance(counts, dict),
        f"{prefix}: material closure derived_counts must be a mapping",
    )
    _require(
        counts == expectation.derived_counts,
        f"{prefix}: material closure derived_counts mismatch",
    )
    _require(
        material.get("material_status") == expectation.material_status,
        f"{prefix}: material closure must use local override status",
    )
    _require(
        material.get("blockers") == [],
        f"{prefix}: package material closure must not retain blockers",
    )
    waiver_records = material.get("waiver_records")
    _require(
        isinstance(waiver_records, list)
        and all(isinstance(record, dict) for record in waiver_records),
        f"{prefix}: explicit material waivers must be record mappings",
    )
    try:
        assert_material_claims_are_derived(material)
    except AssertionError as exc:
        raise AssertionError(f"{prefix}: {exc}") from exc
    _require(
        material.get("aluminum_material_closure_claim_allowed") is True
        and material.get("closure_claim_allowed") is True
        and material.get("full_material_closure_claim_allowed") is True
        and material.get("native_material_closure_claim_allowed") is False
        and material.get("full_native_material_closure_claim_allowed") is False,
        f"{prefix}: material closure claim boundary mismatch",
    )
    _require(
        material.get("forbidden_claims") == ["full_native_material_closure"],
        f"{prefix}: full native material closure must remain forbidden",
    )
    source_resolved_records = material.get("source_resolved_surface_records")
    _require(
        isinstance(source_resolved_records, list)
        and {
            record.get("runtime_prim_path")
            for record in source_resolved_records
            if isinstance(record, dict)
        }
        == expectation.source_resolved_runtime_paths,
        f"{prefix}: source_resolved_surface_records must cover panel GeomSubset material coverage",
    )
    for record in source_resolved_records:
        _require(
            isinstance(record, dict)
            and record.get("resolution_mode") == "native_geomsubset_material_binding"
            and record.get("geomsubset_coverage_status") == "covers_all_faces"
            and record.get("covered_face_count") == record.get("face_count"),
            f"{prefix}: source-resolved surfaces must record full GeomSubset coverage",
        )
    authored_material_records = material.get("authored_material_records")
    _require(
        isinstance(authored_material_records, list)
        and {
            record.get("runtime_prim_path")
            for record in authored_material_records
            if isinstance(record, dict)
        }
        == expectation.wrapper_authored_runtime_paths,
        f"{prefix}: authored_material_records must cover local override surfaces",
    )
    for record in authored_material_records:
        _require(
            isinstance(record, dict)
            and record.get("resolution_mode") == "wrapper_local_preview_surface"
            and record.get("runtime_material_path")
            in expectation.wrapper_authored_material_targets
            and record.get("native_material_closure_claim_allowed") is False,
            f"{prefix}: wrapper-authored material record must keep native claim blocked",
        )
    _assert_native_material_provenance(prefix, material, expectation)


def _assert_native_material_provenance(
    prefix: str,
    material: dict[str, Any],
    expectation: MaterialClosureExpectation,
) -> None:
    provenance = material.get("native_material_provenance")
    _require(
        isinstance(provenance, dict),
        f"{prefix}: missing native material provenance",
    )
    _require(
        provenance.get("schema_version") == 1,
        f"{prefix}: native material provenance schema_version must be 1",
    )
    _require(
        provenance.get("status") == "blocked_by_wrapper_local_overrides",
        f"{prefix}: native provenance status mismatch",
    )
    expected_count = len(expectation.native_provenance_blockers)
    _require(
        provenance.get("source_native_blocker_surface_count") == expected_count,
        f"{prefix}: source-native blocker surface count mismatch",
    )
    _require(
        provenance.get("native_wrapper_override_surface_count") == expected_count,
        f"{prefix}: native wrapper override surface count mismatch",
    )
    blocker_records = provenance.get("native_claim_blocker_records")
    _require(
        isinstance(blocker_records, list)
        and all(isinstance(record, dict) for record in blocker_records),
        f"{prefix}: missing native provenance blockers",
    )
    actual_blockers = {
        (
            record.get("source_prim_path"),
            record.get("runtime_prim_path"),
            record.get("runtime_material_path"),
        )
        for record in blocker_records
    }
    _require(
        actual_blockers == expectation.native_provenance_path_keys,
        f"{prefix}: native material provenance blocker mismatch",
    )
    _require(
        len(blocker_records) == expected_count,
        f"{prefix}: native material provenance blocker count mismatch",
    )
    binding_status_by_source = expectation.native_binding_status_by_source
    for record in blocker_records:
        source_prim_path = record.get("source_prim_path")
        _require(
            record.get("source_binding_status")
            == binding_status_by_source.get(source_prim_path)
            and record.get("source_material_binding") is None
            and record.get("replacement_required_for_full_native_closure") is True
            and record.get("blocked_claims") == EXPECTED_NATIVE_BLOCKED_CLAIMS,
            f"{prefix}: native material provenance blockers must retain source evidence and blocked claims",
        )
