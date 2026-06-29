from __future__ import annotations

from copy import deepcopy
from typing import Any


def _is_aluminum_record(record: dict[str, Any]) -> bool:
    return record.get("material_name") == "Aluminum_Anodized_Charcoal"


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
    waiver_count = len(waiver_records)
    fallback_surface_count = len(fallback_surface_records)
    aluminum_local = any(
        _is_aluminum_record(record)
        and record.get("resolution_mode") == "local_mirror"
        for record in dependency_records
    )
    full_allowed = (
        remote_unmirrored_unwaived_count == 0
        and waiver_count == 0
        and fallback_surface_count == 0
        and bool(dependency_records)
        and local_mirror_count == len(dependency_records)
    )

    material_status = (
        "resolved_native_material" if full_allowed else "mixed_native_and_fallback"
    )
    native_material_closure_reason = (
        None if full_allowed else "fallback_surfaces_or_waivers_remain"
    )
    if fallback_surface_count > 0:
        native_material_closure_reason = (
            "fallback_surfaces_remain_after_aluminum_local_mirror"
        )

    return {
        "schema_version": 1,
        "asset_id": asset_id,
        "material_status": material_status,
        "dependency_records": dependency_records,
        "fallback_surface_records": fallback_surface_records,
        "waiver_records": waiver_records,
        "derived_counts": {
            "remote_unmirrored_unwaived_count": remote_unmirrored_unwaived_count,
            "remote_waiver_count": waiver_count,
            "local_mirror_count": local_mirror_count,
            "fallback_surface_count": fallback_surface_count,
        },
        "closure_claim_allowed": full_allowed,
        "aluminum_material_closure_claim_allowed": aluminum_local,
        "native_material_closure_claim_allowed": full_allowed,
        "full_native_material_closure_claim_allowed": full_allowed,
        "native_material_closure_reason": native_material_closure_reason,
        "forbidden_claims": [] if full_allowed else ["full_native_material_closure"],
    }
