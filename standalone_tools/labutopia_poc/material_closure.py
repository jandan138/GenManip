from __future__ import annotations

from copy import deepcopy
from typing import Any


SUPPORTED_DEPENDENCY_RESOLUTION_MODES = {
    "local_mirror",
    "remote_unmirrored_unwaived",
}


def _is_aluminum_record(record: dict[str, Any]) -> bool:
    return record.get("material_name") == "Aluminum_Anodized_Charcoal"


def _derive_counts(
    *,
    dependency_records: list[dict[str, Any]],
    fallback_surface_records: list[dict[str, Any]],
    waiver_records: list[dict[str, Any]],
) -> dict[str, int]:
    local_mirror_count = sum(
        1
        for record in dependency_records
        if record.get("resolution_mode") == "local_mirror"
    )
    remote_unmirrored_unwaived_count = sum(
        1
        for record in dependency_records
        if record.get("resolution_mode") == "remote_unmirrored_unwaived"
    )
    unsupported_dependency_resolution_mode_count = sum(
        1
        for record in dependency_records
        if record.get("resolution_mode") not in SUPPORTED_DEPENDENCY_RESOLUTION_MODES
    )
    return {
        "remote_unmirrored_unwaived_count": remote_unmirrored_unwaived_count,
        "remote_waiver_count": len(waiver_records),
        "local_mirror_count": local_mirror_count,
        "unsupported_dependency_resolution_mode_count": (
            unsupported_dependency_resolution_mode_count
        ),
        "fallback_surface_count": len(fallback_surface_records),
    }


def _derive_blockers(
    remote_unmirrored_unwaived_count: int,
    waiver_count: int,
    fallback_surface_count: int,
    unsupported_dependency_resolution_mode_count: int = 0,
    dependency_evidence_missing: bool = False,
) -> list[str]:
    blockers: list[str] = []
    if remote_unmirrored_unwaived_count:
        blockers.append("remote_dependency_unmirrored_unwaived")
    if waiver_count:
        blockers.append("explicit_material_waiver_open")
    if fallback_surface_count:
        blockers.append("fallback_surfaces_remain_after_aluminum_local_mirror")
    if unsupported_dependency_resolution_mode_count:
        blockers.append("unsupported_dependency_resolution_mode")
    if dependency_evidence_missing:
        blockers.append("dependency_evidence_missing")
    return blockers


def assert_material_claims_are_derived(report: dict[str, Any]) -> None:
    has_evidence_records = any(
        key in report
        for key in ("dependency_records", "fallback_surface_records", "waiver_records")
    )
    if has_evidence_records:
        dependency_records = report.get("dependency_records") or []
        fallback_surface_records = report.get("fallback_surface_records") or []
        waiver_records = report.get("waiver_records") or []
        counts = _derive_counts(
            dependency_records=dependency_records,
            fallback_surface_records=fallback_surface_records,
            waiver_records=waiver_records,
        )
        dependency_evidence_missing = not bool(dependency_records)
    else:
        counts = report.get("derived_counts") or {}
        dependency_evidence_missing = False
    blocker_counts = (
        int(counts.get("remote_unmirrored_unwaived_count") or 0),
        int(counts.get("remote_waiver_count") or 0),
        int(counts.get("unsupported_dependency_resolution_mode_count") or 0),
        int(counts.get("fallback_surface_count") or 0),
    )
    blockers = report.get("blockers") or []
    overclaimed = any(
        report.get(flag) is True
        for flag in (
            "closure_claim_allowed",
            "native_material_closure_claim_allowed",
            "full_native_material_closure_claim_allowed",
        )
    )
    if overclaimed and (
        any(blocker_counts) or blockers or dependency_evidence_missing
    ):
        raise AssertionError("full material closure overclaim: blockers remain")


def derive_material_closure_claims(
    *,
    asset_id: str,
    dependency_records: list[dict[str, Any]],
    fallback_surface_records: list[dict[str, Any]],
    waiver_records: list[dict[str, Any]],
) -> dict[str, Any]:
    dependency_records = deepcopy(dependency_records)
    fallback_surface_records = deepcopy(fallback_surface_records)
    waiver_records = deepcopy(waiver_records)
    counts = _derive_counts(
        dependency_records=dependency_records,
        fallback_surface_records=fallback_surface_records,
        waiver_records=waiver_records,
    )
    blockers = _derive_blockers(
        counts["remote_unmirrored_unwaived_count"],
        counts["remote_waiver_count"],
        counts["fallback_surface_count"],
        counts["unsupported_dependency_resolution_mode_count"],
        not bool(dependency_records),
    )
    aluminum_local = any(
        _is_aluminum_record(record)
        and record.get("resolution_mode") == "local_mirror"
        for record in dependency_records
    )
    full_allowed = (
        counts["remote_unmirrored_unwaived_count"] == 0
        and counts["remote_waiver_count"] == 0
        and counts["fallback_surface_count"] == 0
        and counts["unsupported_dependency_resolution_mode_count"] == 0
        and bool(dependency_records)
        and counts["local_mirror_count"] == len(dependency_records)
    )

    material_status = (
        "resolved_native_material" if full_allowed else "mixed_native_and_fallback"
    )
    native_material_closure_reason = (
        None if full_allowed else blockers[0]
    )

    return {
        "schema_version": 1,
        "asset_id": asset_id,
        "material_status": material_status,
        "dependency_records": dependency_records,
        "fallback_surface_records": fallback_surface_records,
        "waiver_records": waiver_records,
        "derived_counts": counts,
        "blockers": blockers,
        "closure_claim_allowed": full_allowed,
        "aluminum_material_closure_claim_allowed": aluminum_local,
        "native_material_closure_claim_allowed": full_allowed,
        "full_native_material_closure_claim_allowed": full_allowed,
        "native_material_closure_reason": native_material_closure_reason,
        "forbidden_claims": [] if full_allowed else ["full_native_material_closure"],
    }
