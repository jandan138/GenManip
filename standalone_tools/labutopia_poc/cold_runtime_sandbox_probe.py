#!/usr/bin/env python3
"""Cold-runtime sandbox probe for LabUtopia EBench task packages."""

from __future__ import annotations


PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED"


def build_claim_boundary(status: str) -> dict[str, bool]:
    return {
        "cold_runtime_sandbox_probe_passed": status == PASS,
        "official_leaderboard_claim_allowed": False,
        "policy_success_claim_allowed": False,
        "pm_showcase_ready": False,
        "native_material_closure_claim_allowed": False,
        "full_native_material_closure_claim_allowed": False,
    }


def derive_parent_status(
    *,
    static_validation_status: str,
    child_status: str,
    runtime_counts: dict[str, int],
) -> str:
    if static_validation_status == BLOCKED or child_status == BLOCKED:
        return BLOCKED
    if static_validation_status != PASS or child_status != PASS:
        return FAIL
    blocking_keys = (
        "remote_uri_count",
        "user_cache_path_count",
        "unauthorized_outside_sandbox_runtime_path_count",
        "non_allowlisted_search_path_count",
        "missing_required_prim_count",
    )
    if any(int(runtime_counts.get(key) or 0) for key in blocking_keys):
        return FAIL
    return PASS
