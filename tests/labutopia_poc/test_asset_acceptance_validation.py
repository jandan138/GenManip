from __future__ import annotations

import copy
import inspect

import pytest

from standalone_tools.labutopia_poc.asset_acceptance_validation import (
    MaterialClosureExpectation,
    NativeMaterialProvenanceBlocker,
    assert_asset_acceptance_material_closure,
)


ROOT = "/World/labutopia_level1_poc/obj_obj_DryingBox_01"
NATIVE_ROOT = "/World/labutopia_level1_poc/obj_obj_FullyNative_01"


def _expectation() -> MaterialClosureExpectation:
    return MaterialClosureExpectation(
        asset_id="LabUtopia/DryingBox_01",
        material_status="resolved_material_with_local_overrides",
        derived_counts={
            "remote_unmirrored_unwaived_count": 0,
            "remote_waiver_count": 0,
            "explicit_material_waiver_count": 0,
            "local_mirror_count": 1,
            "unsupported_dependency_resolution_mode_count": 0,
            "fallback_surface_count": 0,
            "source_resolved_surface_count": 1,
            "wrapper_authored_material_count": 2,
        },
        claim_flags={
            "closure_claim_allowed": True,
            "full_material_closure_claim_allowed": True,
            "aluminum_material_closure_claim_allowed": True,
            "native_material_closure_claim_allowed": False,
            "full_native_material_closure_claim_allowed": False,
        },
        native_material_closure_reason=(
            "wrapper_local_material_overrides_present"
        ),
        forbidden_claims=["full_native_material_closure"],
        native_provenance_status="blocked_by_wrapper_local_overrides",
        source_resolved_runtime_paths={f"{ROOT}/panel"},
        wrapper_authored_runtime_paths={
            f"{ROOT}/Group/_900_1",
            f"{ROOT}/button",
        },
        wrapper_authored_material_targets={
            f"{ROOT}/Looks/task_indicator_mat",
            f"{ROOT}/Looks/task_button_mat",
        },
        native_provenance_blockers={
            NativeMaterialProvenanceBlocker(
                source_prim_path="/World/DryingBox_01/Group/_900_1",
                runtime_prim_path=f"{ROOT}/Group/_900_1",
                runtime_material_path=f"{ROOT}/Looks/task_indicator_mat",
                source_binding_status=(
                    "empty_authored_binding_in_stage2_source_readback"
                ),
            ),
            NativeMaterialProvenanceBlocker(
                source_prim_path="/World/DryingBox_01/button",
                runtime_prim_path=f"{ROOT}/button",
                runtime_material_path=f"{ROOT}/Looks/task_button_mat",
                source_binding_status="unbound_in_stage2_source_readback",
            ),
        },
    )


def _valid_material_closure() -> dict[str, object]:
    return {
        "schema_version": 1,
        "asset_id": "LabUtopia/DryingBox_01",
        "material_status": "resolved_material_with_local_overrides",
        "dependency_records": [
            {
                "material_name": "Aluminum_Anodized_Charcoal",
                "resolution_mode": "local_mirror",
            }
        ],
        "fallback_surface_records": [],
        "waiver_records": [],
        "source_resolved_surface_records": [
            {
                "runtime_prim_path": f"{ROOT}/panel",
                "resolution_mode": "native_geomsubset_material_binding",
                "geomsubset_coverage_status": "covers_all_faces",
                "covered_face_count": 158,
                "face_count": 158,
            }
        ],
        "authored_material_records": [
            {
                "runtime_prim_path": f"{ROOT}/Group/_900_1",
                "resolution_mode": "wrapper_local_preview_surface",
                "runtime_material_path": f"{ROOT}/Looks/task_indicator_mat",
                "native_material_closure_claim_allowed": False,
            },
            {
                "runtime_prim_path": f"{ROOT}/button",
                "resolution_mode": "wrapper_local_preview_surface",
                "runtime_material_path": f"{ROOT}/Looks/task_button_mat",
                "native_material_closure_claim_allowed": False,
            },
        ],
        "derived_counts": _expectation().derived_counts,
        "blockers": [],
        "closure_claim_allowed": True,
        "full_material_closure_claim_allowed": True,
        "aluminum_material_closure_claim_allowed": True,
        "native_material_closure_claim_allowed": False,
        "full_native_material_closure_claim_allowed": False,
        "native_material_closure_reason": (
            "wrapper_local_material_overrides_present"
        ),
        "forbidden_claims": ["full_native_material_closure"],
        "native_material_provenance": {
            "schema_version": 1,
            "status": "blocked_by_wrapper_local_overrides",
            "source_native_blocker_surface_count": 2,
            "native_wrapper_override_surface_count": 2,
            "native_claim_blocker_records": [
                {
                    "source_prim_path": "/World/DryingBox_01/Group/_900_1",
                    "runtime_prim_path": f"{ROOT}/Group/_900_1",
                    "source_binding_status": (
                        "empty_authored_binding_in_stage2_source_readback"
                    ),
                    "source_material_binding": None,
                    "runtime_material_path": f"{ROOT}/Looks/task_indicator_mat",
                    "replacement_required_for_full_native_closure": True,
                    "blocked_claims": [
                        "native_material_closure",
                        "full_native_material_closure",
                    ],
                },
                {
                    "source_prim_path": "/World/DryingBox_01/button",
                    "runtime_prim_path": f"{ROOT}/button",
                    "source_binding_status": "unbound_in_stage2_source_readback",
                    "source_material_binding": None,
                    "runtime_material_path": f"{ROOT}/Looks/task_button_mat",
                    "replacement_required_for_full_native_closure": True,
                    "blocked_claims": [
                        "native_material_closure",
                        "full_native_material_closure",
                    ],
                },
            ],
        },
    }


def test_asset_acceptance_material_closure_helper_accepts_valid_boundary():
    assert_asset_acceptance_material_closure(
        "assets_manifest.json",
        _valid_material_closure(),
        _expectation(),
    )


def test_asset_acceptance_material_closure_helper_api_is_material_only():
    parameters = inspect.signature(
        assert_asset_acceptance_material_closure
    ).parameters

    assert "related_reports" not in parameters


def test_asset_acceptance_material_closure_helper_uses_expectation_claim_boundary():
    expectation = MaterialClosureExpectation(
        asset_id="LabUtopia/FullyNative_01",
        material_status="resolved_native_material",
        derived_counts={
            "remote_unmirrored_unwaived_count": 0,
            "remote_waiver_count": 0,
            "explicit_material_waiver_count": 0,
            "local_mirror_count": 1,
            "unsupported_dependency_resolution_mode_count": 0,
            "fallback_surface_count": 0,
            "source_resolved_surface_count": 1,
            "wrapper_authored_material_count": 0,
        },
        claim_flags={
            "closure_claim_allowed": True,
            "full_material_closure_claim_allowed": True,
            "aluminum_material_closure_claim_allowed": False,
            "native_material_closure_claim_allowed": True,
            "full_native_material_closure_claim_allowed": True,
        },
        native_material_closure_reason=None,
        forbidden_claims=[],
        native_provenance_status="resolved_native_material",
        source_resolved_runtime_paths={f"{NATIVE_ROOT}/body"},
        wrapper_authored_runtime_paths=set(),
        wrapper_authored_material_targets=set(),
        native_provenance_blockers=set(),
    )
    material = {
        "schema_version": 1,
        "asset_id": "LabUtopia/FullyNative_01",
        "material_status": "resolved_native_material",
        "dependency_records": [
            {
                "material_name": "Steel_Brushed",
                "resolution_mode": "local_mirror",
            }
        ],
        "fallback_surface_records": [],
        "waiver_records": [],
        "source_resolved_surface_records": [
            {
                "runtime_prim_path": f"{NATIVE_ROOT}/body",
                "resolution_mode": "native_geomsubset_material_binding",
                "geomsubset_coverage_status": "covers_all_faces",
                "covered_face_count": 42,
                "face_count": 42,
            }
        ],
        "authored_material_records": [],
        "derived_counts": expectation.derived_counts,
        "blockers": [],
        "closure_claim_allowed": True,
        "full_material_closure_claim_allowed": True,
        "aluminum_material_closure_claim_allowed": False,
        "native_material_closure_claim_allowed": True,
        "full_native_material_closure_claim_allowed": True,
        "native_material_closure_reason": None,
        "forbidden_claims": [],
        "native_material_provenance": {
            "schema_version": 1,
            "status": "resolved_native_material",
            "source_native_blocker_surface_count": 0,
            "native_wrapper_override_surface_count": 0,
            "native_claim_blocker_records": [],
        },
    }

    assert_asset_acceptance_material_closure(
        "assets_manifest.json",
        material,
        expectation,
    )


def test_asset_acceptance_material_closure_helper_rejects_blocker_path_mismatch():
    material = copy.deepcopy(_valid_material_closure())
    material["native_material_provenance"]["native_claim_blocker_records"][0][
        "source_prim_path"
    ] = "/World/DryingBox_01/not_the_indicator"

    with pytest.raises(
        AssertionError,
        match="native material provenance blocker mismatch",
    ):
        assert_asset_acceptance_material_closure(
            "assets_manifest.json",
            material,
            _expectation(),
        )


def test_asset_acceptance_material_closure_helper_rejects_binding_status_mismatch():
    material = copy.deepcopy(_valid_material_closure())
    material["native_material_provenance"]["native_claim_blocker_records"][1][
        "source_binding_status"
    ] = "empty_authored_binding_in_stage2_source_readback"

    with pytest.raises(
        AssertionError,
        match=(
            "native material provenance blockers must retain source evidence "
            "and blocked claims"
        ),
    ):
        assert_asset_acceptance_material_closure(
            "assets_manifest.json",
            material,
            _expectation(),
        )


def test_asset_acceptance_material_closure_helper_rejects_native_overclaim():
    material = copy.deepcopy(_valid_material_closure())
    material["native_material_closure_claim_allowed"] = True

    with pytest.raises(
        AssertionError,
        match="native material closure overclaim",
    ):
        assert_asset_acceptance_material_closure(
            "assets_manifest.json",
            material,
            _expectation(),
        )
