from __future__ import annotations

from standalone_tools.labutopia_poc import cold_runtime_sandbox_probe as probe


def test_claim_boundary_keeps_broader_claims_false():
    boundary = probe.build_claim_boundary("PASS")

    assert boundary == {
        "cold_runtime_sandbox_probe_passed": True,
        "official_leaderboard_claim_allowed": False,
        "policy_success_claim_allowed": False,
        "pm_showcase_ready": False,
        "native_material_closure_claim_allowed": False,
        "full_native_material_closure_claim_allowed": False,
    }


def test_claim_boundary_is_false_when_probe_does_not_pass():
    assert probe.build_claim_boundary("FAIL")[
        "cold_runtime_sandbox_probe_passed"
    ] is False
    assert probe.build_claim_boundary("BLOCKED")[
        "cold_runtime_sandbox_probe_passed"
    ] is False


def test_status_derivation_blocks_static_validation_failure():
    status = probe.derive_parent_status(
        static_validation_status="FAIL",
        child_status="PASS",
        runtime_counts={
            "remote_uri_count": 0,
            "user_cache_path_count": 0,
            "unauthorized_outside_sandbox_runtime_path_count": 0,
            "non_allowlisted_search_path_count": 0,
            "missing_required_prim_count": 0,
        },
    )

    assert status == "FAIL"


def test_status_derivation_rejects_runtime_leakage():
    status = probe.derive_parent_status(
        static_validation_status="PASS",
        child_status="PASS",
        runtime_counts={
            "remote_uri_count": 1,
            "user_cache_path_count": 0,
            "unauthorized_outside_sandbox_runtime_path_count": 0,
            "non_allowlisted_search_path_count": 0,
            "missing_required_prim_count": 0,
        },
    )

    assert status == "FAIL"


def test_status_derivation_passes_only_clean_child_pass():
    status = probe.derive_parent_status(
        static_validation_status="PASS",
        child_status="PASS",
        runtime_counts={
            "remote_uri_count": 0,
            "user_cache_path_count": 0,
            "unauthorized_outside_sandbox_runtime_path_count": 0,
            "non_allowlisted_search_path_count": 0,
            "missing_required_prim_count": 0,
        },
    )

    assert status == "PASS"
