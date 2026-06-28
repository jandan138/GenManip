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
    assert "material_closure" in report
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


def test_native_dryingbox_audit_material_closure_schema():
    from standalone_tools.labutopia_poc.audit_native_dryingbox import (
        audit_native_dryingbox,
    )

    report = audit_native_dryingbox(
        labutopia_root="/cpfs/shared/simulation/zhuzihou/dev/LabUtopia",
        source_prim_path="/World/DryingBox_01",
    )

    material_closure = report["material_closure"]
    assert material_closure["source_prim_path"] == "/World/DryingBox_01"
    assert material_closure["mesh_count"] > 0
    assert material_closure["bound_mesh_count"] > 0
    assert material_closure["out_of_scope_binding_count"] > 0

    mesh_materials = material_closure["mesh_materials"]
    assert mesh_materials
    assert all("mesh_path" in item for item in mesh_materials)
    assert all("source_binding_target" in item for item in mesh_materials)
    assert all("composed_binding_target" in item for item in mesh_materials)
    assert all("compute_bound_material" in item for item in mesh_materials)
    assert all("binding_scope_status" in item for item in mesh_materials)
    assert all("material_prim_valid" in item for item in mesh_materials)
    assert all("mdl" in item for item in mesh_materials)
    assert all("textures" in item for item in mesh_materials)
    assert all("displayColor" in item for item in mesh_materials)

    bound_items = [item for item in mesh_materials if item["source_binding_target"]]
    binding_targets = {item["source_binding_target"] for item in bound_items}
    composed_targets = {
        item["composed_binding_target"]
        for item in mesh_materials
        if item["composed_binding_target"]
    }
    assert "/World/Looks/mdl_0007" in binding_targets
    assert "/World/Looks/mdl_0009" in composed_targets
    inherited_body_mesh = next(
        item
        for item in mesh_materials
        if item["mesh_path"] == "/World/DryingBox_01/body/body/mesh"
    )
    assert inherited_body_mesh["source_binding_target"] == "/World/Looks/mdl_0009"
    assert (
        inherited_body_mesh["source_binding_relationship_path"]
        == "/World/DryingBox_01/body/body.material:binding"
    )
    assert all(item["material_prim_valid"] for item in bound_items)
    assert all(
        item["compute_bound_material"]["success"]
        and item["compute_bound_material"]["material_path"]
        for item in bound_items
    )
    assert any(
        item["binding_scope_status"] == "out_of_source_subtree"
        for item in bound_items
    )

    mdl_items = [item["mdl"] for item in bound_items if item["mdl"]["source_asset"]]
    assert mdl_items
    assert any(item["sub_identifier"] == "mdl_0007" for item in mdl_items)
    assert any(item["source_asset"].endswith("material_11.mdl") for item in mdl_items)
    assert all("asset_location" in item for item in mdl_items)
    assert all("resolved_path" in item for item in mdl_items)
    assert all("sha256" in item for item in mdl_items)
    assert any(item["asset_location"] == "local" for item in mdl_items)
    assert any(
        item["asset_location"] in {"missing", "remote", "unresolved"}
        for item in mdl_items
    )

    local_mdl_items = [item for item in mdl_items if item["asset_location"] == "local"]
    assert local_mdl_items
    assert all(len(item["sha256"]) == 64 for item in local_mdl_items)
    assert any(item["helper_imports"] for item in local_mdl_items)

    helper_mdl_dependencies = material_closure["helper_mdl_dependencies"]
    helper_names = {item["asset_path"] for item in helper_mdl_dependencies}
    assert "vray_materials.mdl" in helper_names
    assert "ad_3dsmax_maps.mdl" in helper_names
    assert all(
        item["asset_location"] in {"builtin", "local", "missing", "remote"}
        for item in helper_mdl_dependencies
    )
    local_helper_items = [
        item for item in helper_mdl_dependencies if item["asset_location"] == "local"
    ]
    assert local_helper_items
    assert all(len(item["sha256"]) == 64 for item in local_helper_items)

    assert isinstance(material_closure["texture_dependencies"], list)
    assert material_closure["texture_dependencies"]
    assert all(
        {"attribute_path", "asset_path", "resolved_path", "asset_location", "sha256"}
        <= set(item)
        for item in material_closure["texture_dependencies"]
    )
    assert any(
        item["asset_path"] == "../textures/image1.JPG"
        and item["asset_location"] == "local"
        and len(item["sha256"]) == 64
        for item in material_closure["texture_dependencies"]
    )


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
        "out_of_scope_material_binding",
        "missing_mdl",
        "missing_texture",
        "remote_only_mdl",
        "remote_only_texture",
        "black_or_low_contrast_fallback",
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
    assert risk_flags["out_of_scope_material_binding"]
