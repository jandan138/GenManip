def test_native_dryingbox_audit_schema():
    from standalone_tools.labutopia_poc.audit_native_dryingbox import (
        audit_native_dryingbox,
    )

    report = audit_native_dryingbox(
        labutopia_root="/cpfs/shared/simulation/zhuzihou/dev/LabUtopia",
        source_prim_path="/World/DryingBox_01",
    )

    assert report["source_prim_path"] == "/World/DryingBox_01"
    assert "stage_path" in report
    assert "stage_sha256" in report
    assert "articulation_roots" in report
    assert "rigid_bodies" in report
    assert "joints" in report
    assert "handle_candidates" in report
    assert "risk_flags" in report
    assert all("xformOps" in prim for prim in report["prims"])
    assert all("xform_ops" not in prim for prim in report["prims"])
    for joint in report["joints"]:
        assert "physics:body0" in joint
        assert "physics:body1" in joint
        assert "body0" not in joint
        assert "body1" not in joint
        assert "axis" in joint
        assert "limits" in joint


def test_native_dryingbox_audit_captures_known_native_risks():
    from standalone_tools.labutopia_poc.audit_native_dryingbox import (
        audit_native_dryingbox,
    )

    report = audit_native_dryingbox(
        labutopia_root="/cpfs/shared/simulation/zhuzihou/dev/LabUtopia",
        source_prim_path="/World/DryingBox_01",
    )

    prim_paths = {prim["path"] for prim in report["prims"]}
    assert "/World/DryingBox_01" in prim_paths
    assert "/World/DryingBox_01/handle" in prim_paths

    risk_flags = report["risk_flags"]
    assert set(risk_flags) == {
        "non_identity_root_scale",
        "zero_mass",
        "zero_inertia",
        "invalid_com",
        "invalid_principal_axes",
        "invalid_joint_body_target",
        "unexpected_joint_type",
        "multiple_active_dofs",
    }
    assert risk_flags["non_identity_root_scale"]
    assert risk_flags["zero_mass"]
    assert risk_flags["zero_inertia"]
    assert risk_flags["invalid_com"]
    assert risk_flags["invalid_principal_axes"]
    assert risk_flags["invalid_joint_body_target"]
    assert risk_flags["unexpected_joint_type"] == [
        {
            "path": "/World/DryingBox_01/button/PrismaticJoint",
            "type": "PhysicsPrismaticJoint",
        }
    ]
    assert risk_flags["multiple_active_dofs"][0]["count"] == 2
