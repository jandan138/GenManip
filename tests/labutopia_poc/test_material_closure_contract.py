import pytest


ALUMINUM_TEXTURE_RECORDS = [
    {
        "package_relative_path": (
            "miscs/mdl/labutopia/mdl/Aluminum_Anodized/"
            "Aluminum_Anodized_BaseColor.png"
        ),
        "sha256": "d1d042502d7d94bca13cee10c63ab5b3801fb0a46e26d79169e13f5b9c7b5a31",
    },
    {
        "package_relative_path": (
            "miscs/mdl/labutopia/mdl/Aluminum_Anodized/"
            "Aluminum_Anodized_Normal.png"
        ),
        "sha256": "6dc1cb1b23a9abd766188a85ccbad1a2639d0a9a334f284e359c6c5d4438608e",
    },
    {
        "package_relative_path": (
            "miscs/mdl/labutopia/mdl/Aluminum_Anodized/"
            "Aluminum_Anodized_ORM.png"
        ),
        "sha256": "768f2dbb4f702a9624b912b431efd1a6a8e0ff3e93744cf54f3866ef8f7986e9",
    },
]


def _aluminum_dependency_record():
    return {
        "material_name": "Aluminum_Anodized_Charcoal",
        "resolution_mode": "local_mirror",
        "local_mirror_sha256": (
            "640855d3890c6faaae6346a850ef9f366d4b397c0f4313e25c7ac0b9230c106a"
        ),
        "texture_dependency_records": ALUMINUM_TEXTURE_RECORDS,
    }


def test_scoped_local_mirror_does_not_allow_full_native_material_closure():
    from standalone_tools.labutopia_poc.material_closure import (
        derive_material_closure_claims,
    )

    report = derive_material_closure_claims(
        asset_id="LabUtopia/DryingBox_01",
        dependency_records=[_aluminum_dependency_record()],
        fallback_surface_records=[
            {
                "runtime_prim_path": (
                    "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Group/_900_1"
                ),
                "displayColor_fallback_status": "authored",
            },
            {
                "runtime_prim_path": (
                    "/World/labutopia_level1_poc/obj_obj_DryingBox_01/button"
                ),
                "displayColor_fallback_status": "authored",
            },
            {
                "runtime_prim_path": (
                    "/World/labutopia_level1_poc/obj_obj_DryingBox_01/panel"
                ),
                "displayColor_fallback_status": "authored",
            },
        ],
        waiver_records=[],
    )

    assert set(report) == {
        "schema_version",
        "asset_id",
        "material_status",
        "dependency_records",
        "fallback_surface_records",
        "waiver_records",
        "derived_counts",
        "blockers",
        "closure_claim_allowed",
        "aluminum_material_closure_claim_allowed",
        "native_material_closure_claim_allowed",
        "full_native_material_closure_claim_allowed",
        "native_material_closure_reason",
        "forbidden_claims",
    }
    assert report["material_status"] == "mixed_native_and_fallback"
    assert report["closure_claim_allowed"] is False
    assert report["aluminum_material_closure_claim_allowed"] is True
    assert report["native_material_closure_claim_allowed"] is False
    assert report["full_native_material_closure_claim_allowed"] is False
    assert report["native_material_closure_reason"] == (
        "fallback_surfaces_remain_after_aluminum_local_mirror"
    )
    assert report["forbidden_claims"] == ["full_native_material_closure"]
    assert report["derived_counts"] == {
        "remote_unmirrored_unwaived_count": 0,
        "remote_waiver_count": 0,
        "local_mirror_count": 1,
        "unsupported_dependency_resolution_mode_count": 0,
        "fallback_surface_count": 3,
    }
    assert report["derived_counts"]["fallback_surface_count"] == 3


def test_unknown_dependency_resolution_mode_blocks_full_closure():
    from standalone_tools.labutopia_poc.material_closure import (
        derive_material_closure_claims,
    )

    report = derive_material_closure_claims(
        asset_id="LabUtopia/DryingBox_01",
        dependency_records=[
            {
                "material_name": "UnexpectedMaterial",
                "resolution_mode": "typo_local_mirror",
            }
        ],
        fallback_surface_records=[],
        waiver_records=[],
    )

    assert report["closure_claim_allowed"] is False
    assert report["native_material_closure_claim_allowed"] is False
    assert report["full_native_material_closure_claim_allowed"] is False
    assert report["derived_counts"]["unsupported_dependency_resolution_mode_count"] == 1
    assert "unsupported_dependency_resolution_mode" in report["blockers"]
    assert report["native_material_closure_reason"] == (
        "unsupported_dependency_resolution_mode"
    )


def test_material_closure_report_does_not_retain_input_references():
    from standalone_tools.labutopia_poc.material_closure import (
        derive_material_closure_claims,
    )

    dependency_records = [_aluminum_dependency_record()]
    report = derive_material_closure_claims(
        asset_id="LabUtopia/DryingBox_01",
        dependency_records=dependency_records,
        fallback_surface_records=[],
        waiver_records=[],
    )

    dependency_records[0]["material_name"] = "MutatedAfterReport"

    assert (
        report["dependency_records"][0]["material_name"]
        == "Aluminum_Anodized_Charcoal"
    )


def test_rejects_full_closure_overclaim_with_fallback_surface():
    from standalone_tools.labutopia_poc.material_closure import (
        assert_material_claims_are_derived,
    )

    claimed = {
        "full_native_material_closure_claim_allowed": True,
        "derived_counts": {"fallback_surface_count": 1},
    }

    with pytest.raises(AssertionError, match="full material closure overclaim"):
        assert_material_claims_are_derived(claimed)


def test_rejects_full_closure_overclaim_with_remote_dependency():
    from standalone_tools.labutopia_poc.material_closure import (
        assert_material_claims_are_derived,
    )

    claimed = {
        "full_native_material_closure_claim_allowed": True,
        "derived_counts": {
            "remote_unmirrored_unwaived_count": 1,
            "remote_waiver_count": 0,
            "fallback_surface_count": 0,
        },
        "blockers": ["remote_dependency_unmirrored_unwaived"],
    }

    with pytest.raises(AssertionError, match="full material closure overclaim"):
        assert_material_claims_are_derived(claimed)


def test_rejects_full_closure_overclaim_with_stale_counts():
    from standalone_tools.labutopia_poc.material_closure import (
        assert_material_claims_are_derived,
    )

    claimed = {
        "closure_claim_allowed": True,
        "native_material_closure_claim_allowed": True,
        "full_native_material_closure_claim_allowed": True,
        "dependency_records": [
            {
                "material_name": "UnexpectedMaterial",
                "resolution_mode": "typo_local_mirror",
            }
        ],
        "fallback_surface_records": [],
        "waiver_records": [],
        "derived_counts": {
            "remote_unmirrored_unwaived_count": 0,
            "remote_waiver_count": 0,
            "local_mirror_count": 1,
            "unsupported_dependency_resolution_mode_count": 0,
            "fallback_surface_count": 0,
        },
        "blockers": [],
    }

    with pytest.raises(AssertionError, match="full material closure overclaim"):
        assert_material_claims_are_derived(claimed)


def test_derive_blockers_accepts_planned_positional_signature():
    from standalone_tools.labutopia_poc.material_closure import _derive_blockers

    assert _derive_blockers(1, 1, 1) == [
        "remote_dependency_unmirrored_unwaived",
        "explicit_material_waiver_open",
        "fallback_surfaces_remain_after_aluminum_local_mirror",
    ]


def test_rejects_remote_dependency_without_mirror_or_waiver():
    from standalone_tools.labutopia_poc.material_closure import (
        derive_material_closure_claims,
    )

    report = derive_material_closure_claims(
        asset_id="LabUtopia/DryingBox_01",
        dependency_records=[
            {
                "material_name": "ExampleRemote",
                "resolution_mode": "remote_unmirrored_unwaived",
            }
        ],
        fallback_surface_records=[],
        waiver_records=[],
    )

    assert report["derived_counts"]["remote_unmirrored_unwaived_count"] == 1
    assert report["native_material_closure_claim_allowed"] is False
    assert "remote_dependency_unmirrored_unwaived" in report["blockers"]
