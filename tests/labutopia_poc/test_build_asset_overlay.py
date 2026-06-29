import hashlib
import json
import subprocess
import sys

import pytest

import standalone_tools.labutopia_poc.build_asset_overlay as build_overlay
from standalone_tools.labutopia_poc.build_asset_overlay import build_asset_overlay


def _write_native_material_fixture(source_dir):
    materials_dir = source_dir / "SubUSDs" / "materials"
    textures_dir = source_dir / "SubUSDs" / "textures"
    materials_dir.mkdir(parents=True)
    textures_dir.mkdir(parents=True)
    helper_bytes = {
        "ad_3dsmax_materials.mdl": b"mdl 1.6;\n",
        "ad_3dsmax_maps.mdl": b"mdl 1.6;\n",
        "vray_materials.mdl": b"mdl 1.6;\n",
        "vray_maps.mdl": b"mdl 1.6;\n",
    }
    helper_hashes = {}
    for helper_name, helper_content in helper_bytes.items():
        (materials_dir / helper_name).write_bytes(helper_content)
        helper_hashes[helper_name] = hashlib.sha256(helper_content).hexdigest()
    texture_bytes = {
        "image4.jpg": b"fixture texture 4",
        "image1.JPG": b"fixture texture 1",
    }
    texture_hashes = {}
    for texture_name, texture_content in texture_bytes.items():
        (textures_dir / texture_name).write_bytes(texture_content)
        texture_hashes[texture_name] = hashlib.sha256(texture_content).hexdigest()
    shared_imports = """mdl 1.6;
import ad_3dsmax_materials::*;
import ad_3dsmax_maps::*;
import vray_materials::*;
import vray_maps::*;
"""
    (materials_dir / "material_11.mdl").write_text(
        shared_imports + "export material mdl_0007() = material();\n",
        encoding="utf-8",
    )
    (materials_dir / "material_08.mdl").write_text(
        shared_imports
        + 'export material mdl_0008() = material(surface: material_surface(scattering: df::diffuse_reflection_bsdf(tint: texture_2d("../textures/image4.jpg", ::tex::gamma_srgb))));\n',
        encoding="utf-8",
    )
    (materials_dir / "material_09.mdl").write_text(
        shared_imports
        + 'export material mdl_0009() = material(surface: material_surface(scattering: df::diffuse_reflection_bsdf(tint: texture_2d("../textures/image1.JPG", ::tex::gamma_srgb))));\n',
        encoding="utf-8",
    )
    return helper_bytes, helper_hashes, texture_hashes


def test_build_asset_overlay_writes_scene_wrapper_manifest_and_cleans_reruns(
    tmp_path,
):
    labutopia_root = tmp_path / "LabUtopia"
    source_dir = labutopia_root / "assets" / "chemistry_lab" / "lab_001"
    source_dir.mkdir(parents=True)
    scene_bytes = b"#usda 1.0\n\ndef Xform \"World\" {}\n"
    (source_dir / "lab_001.usd").write_bytes(scene_bytes)
    (source_dir / "SubUSDs").mkdir()
    (source_dir / "SubUSDs" / "prop.usd").write_text("prop", encoding="utf-8")

    overlay_root = tmp_path / "overlay" / "assets"
    build_asset_overlay(labutopia_root=labutopia_root, overlay_root=overlay_root)

    scene_dir = (
        overlay_root / "scene_usds" / "labutopia" / "level1_poc" / "lab_001"
    )
    assert (scene_dir / "scene.usd").exists()
    assert (scene_dir / "scene.usda").exists()
    scene_usda = (scene_dir / "scene.usda").read_text(encoding="utf-8")
    assert 'def Xform "World"' in scene_usda
    assert 'def Xform "labutopia_level1_poc"' in scene_usda
    assert 'def Xform "_scene"' not in scene_usda
    assert (
        'def Xform "obj_obj_conical_bottle02" (\n'
        '            prepend payload = @scene.usd@</World/conical_bottle02>'
    ) in scene_usda
    assert 'prepend payload = @scene.usd@</World/DryingBox_01>' not in scene_usda
    assert 'def Xform "obj_obj_DryingBox_01" (' in scene_usda
    assert 'prepend apiSchemas = ["PhysicsArticulationRootAPI"]' in scene_usda
    assert 'def Cube "body_link"' in scene_usda
    assert 'def Cube "door_link"' in scene_usda
    assert 'def Cube "handle"' in scene_usda
    assert 'def Scope "Looks"' in scene_usda
    assert 'def Material "door_panel_mat"' in scene_usda
    assert 'def Material "door_seam_mat"' in scene_usda
    assert 'def Material "handle_mount_mat"' in scene_usda
    assert 'def Material "handle_mat"' in scene_usda
    assert "outputs:mdl:surface.connect" in scene_usda
    assert "OmniPBR.mdl" in scene_usda
    assert "inputs:diffuse_color_constant = (1, 0.18, 0.04)" in scene_usda
    assert "color3f inputs:diffuseColor = (0.28, 0.34, 0.42)" in scene_usda
    assert "color3f inputs:diffuseColor = (1, 0.18, 0.04)" in scene_usda
    assert '"MaterialBindingAPI"' in scene_usda
    assert (
        'prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsCollisionAPI", '
        '"PhysicsMassAPI", "MaterialBindingAPI"]'
    ) in scene_usda
    assert (
        "rel material:binding = "
        "</World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/door_panel_mat>"
    ) in scene_usda
    assert (
        "rel material:binding = "
        "</World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/handle_mat>"
    ) in scene_usda
    assert 'def Cube "door_left_seam"' in scene_usda
    assert 'def Cube "door_right_seam"' in scene_usda
    assert 'def Cube "door_top_seam"' in scene_usda
    assert 'def Cube "door_bottom_seam"' in scene_usda
    assert "double3 xformOp:translate = (-0.255, -0.168, 0.01)" in scene_usda
    assert "double3 xformOp:scale = (0.012, 0.012, 0.43)" in scene_usda
    assert "color3f inputs:diffuseColor = (0.04, 0.05, 0.06)" in scene_usda
    assert 'def Cube "handle_mount_backplate"' in scene_usda
    assert "double3 xformOp:translate = (0.18, -0.174, 0.05)" in scene_usda
    assert "double3 xformOp:scale = (0.075, 0.014, 0.28)" in scene_usda
    assert "double3 xformOp:translate = (0.18, -0.22, 0.05)" in scene_usda
    assert "double3 xformOp:scale = (0.045, 0.075, 0.25)" in scene_usda
    assert "double3 xformOp:scale = (0.08, 0.06, 0.24)" not in scene_usda
    assert 'def Cube "handle_visual_marker"' not in scene_usda
    assert "double3 xformOp:translate = (0.18, -0.165, 0.05)" not in scene_usda
    assert "double3 xformOp:scale = (0.035, 0.06, 0.18)" not in scene_usda
    assert 'def PhysicsFixedJoint "BaseFixedJoint"' in scene_usda
    assert (
        "rel physics:body1 = "
        "</World/labutopia_level1_poc/obj_obj_DryingBox_01/body_link>"
    ) in scene_usda
    assert 'def PhysicsRevoluteJoint "RevoluteJoint"' in scene_usda
    assert "point3f physics:localPos0 = (-0.25, -0.2, 0.01)" in scene_usda
    assert "point3f physics:localPos1 = (-0.25, 0, 0)" in scene_usda
    assert "point3f physics:localPos0 = (0.18, -0.10, 0.04)" in scene_usda
    assert "double3 xformOp:translate = (-0.18, -0.22, 0.05)" not in scene_usda
    assert "double3 xformOp:translate = (-0.18, -0.165, 0.05)" not in scene_usda
    assert 'PhysicsPrismaticJoint' not in scene_usda
    assert 'def Xform "obj_obj_DryingBox_01_handle" (' not in scene_usda
    assert "primvars:displayColor" in scene_usda
    assert '"PhysicsMassAPI"' in scene_usda
    assert "float physics:mass = 0.5" in scene_usda
    assert "point3f physics:diagonalInertia = (0.01, 0.01, 0.01)" in scene_usda
    assert "point3f physics:centerOfMass = (0, 0, 0)" in scene_usda
    assert "quatf physics:principalAxes = (1, 0, 0, 0)" in scene_usda
    assert "double3 xformOp:translate = (0.28, 0, 0.8)" in scene_usda
    assert "double3 xformOp:translate = (0.75, 0.1, 0.78)" in scene_usda
    assert (
        'def Xform "obj_table" (\n'
        '            prepend payload = @scene.usd@</World/table>'
    ) in scene_usda
    assert 'def DomeLight "DeterministicDomeLight"' in scene_usda
    assert "float inputs:intensity = 1000" in scene_usda
    assert "inputs:texture:file" not in scene_usda

    manifest_path = overlay_root / "manifests" / "labutopia_level1_poc.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert (
        manifest["usd_name"]
        == "scene_usds/labutopia/level1_poc/lab_001/scene"
    )
    assert manifest["scene_uid"] == "labutopia_level1_poc"
    assert manifest["source_task_prims"] == {
        "level1_pick": ["/World/conical_bottle02"],
        "level1_place": ["/World/beaker2", "/World/target_plat"],
        "level1_open_door": [
            "/World/DryingBox_01",
            "/World/DryingBox_01/handle",
            "/World/DryingBox_01/RevoluteJoint",
        ],
    }
    assert manifest["source_to_runtime_object_key"] == {
        "/World/conical_bottle02": "obj_conical_bottle02",
        "/World/beaker2": "obj_beaker2",
        "/World/target_plat": "obj_target_plat",
        "/World/DryingBox_01": "obj_DryingBox_01",
        "/World/DryingBox_01/handle": "obj_DryingBox_01_handle",
        "/World/table": "table",
    }
    assert manifest["runtime_object_keys"] == [
        "obj_conical_bottle02",
        "obj_beaker2",
        "obj_target_plat",
        "obj_DryingBox_01",
        "obj_DryingBox_01_handle",
        "table",
    ]
    assert manifest["wrapper_prim_paths"] == {
        "obj_conical_bottle02": "/World/labutopia_level1_poc/obj_obj_conical_bottle02",
        "obj_beaker2": "/World/labutopia_level1_poc/obj_obj_beaker2",
        "obj_target_plat": "/World/labutopia_level1_poc/obj_obj_target_plat",
        "obj_DryingBox_01": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
        "obj_DryingBox_01_handle": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle",
        "table": "/World/labutopia_level1_poc/obj_table",
    }
    assert manifest["articulation_part_paths"] == {
        "obj_DryingBox_01_handle": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle"
    }
    contracts = manifest["render_object_contracts"]
    assert contracts["obj_conical_bottle02"]["desired_runtime_translation"] == [
        0.28,
        0.0,
        0.8,
    ]
    assert contracts["obj_DryingBox_01"]["desired_runtime_translation"] == [
        0.75,
        0.1,
        0.78,
    ]
    assert contracts["obj_DryingBox_01_handle"][
        "compose_nested_transform_with_parent"
    ] == "obj_DryingBox_01"
    for uid in (
        "obj_conical_bottle02",
        "obj_beaker2",
        "obj_target_plat",
        "obj_DryingBox_01",
        "obj_DryingBox_01_handle",
    ):
        color = contracts[uid]["display_color"]
        assert len(color) == 3
        assert all(0.0 <= channel <= 1.0 for channel in color)
        assert contracts[uid]["expected_world_bbox_lwh_m"]["min"]
        assert contracts[uid]["expected_world_bbox_lwh_m"]["max"]
    assert manifest["required_genmanip_object_uids"] == [
        "obj_conical_bottle02",
        "obj_beaker2",
        "obj_target_plat",
        "obj_DryingBox_01",
        "obj_DryingBox_01_handle",
        "obj_table",
    ]
    assert manifest["table_uid"] == "table"
    assert manifest["deterministic_lights"] == [
        {
            "prim_path": "/World/labutopia_level1_poc/DeterministicDomeLight",
            "type": "DomeLight",
            "intensity": 1000,
        }
    ]
    assert manifest["drying_box_runtime_asset"] == {
        "strategy": "sanitized_surrogate",
        "wrapper_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
        "base_joint_name": "BaseFixedJoint",
        "joint_name": "RevoluteJoint",
        "removed_source_joint_types": ["PhysicsPrismaticJoint"],
        "source_payload_used": False,
        "visual_affordances": [
            {
                "name": "high_contrast_door_panel",
                "display_color": [0.28, 0.34, 0.42],
            },
            {
                "name": "door_outline_seams",
                "display_color": [0.04, 0.05, 0.06],
            },
            {
                "name": "handle_mount_backplate",
                "display_color": [0.05, 0.07, 0.09],
            },
            {
                "name": "high_contrast_handle",
                "display_color": [1.0, 0.18, 0.04],
            },
        ],
    }
    assert manifest["notes"] == [
        "scene.usda exposes a single scene uid under /World for GenManip discovery.",
        "Immediate obj_* wrapper prims payload top-level LabUtopia source prims except DryingBox_01.",
        "DryingBox_01 uses a sanitized runtime surrogate with identity root scale and finite inertial attributes.",
        "The drying-box handle is exposed as an articulation part, not an independent payload.",
        "Task object wrapper translations normalize LabUtopia source coordinates into the robot/table workspace.",
        "A deterministic dome light is authored in the runtime wrapper scene.",
        "Runtime object keys strip one leading obj_ from wrapper prim names.",
    ]

    copied_scene = next(
        item
        for item in manifest["copied_files"]
        if item["relative_path"]
        == "scene_usds/labutopia/level1_poc/lab_001/scene.usd"
    )
    assert copied_scene["bytes"] == len(scene_bytes)
    assert copied_scene["sha256"] == hashlib.sha256(scene_bytes).hexdigest()

    stale_path = scene_dir / "stale.txt"
    stale_path.write_text("remove me", encoding="utf-8")
    build_asset_overlay(labutopia_root=labutopia_root, overlay_root=overlay_root)

    assert not stale_path.exists()


def test_build_asset_overlay_native_strategy_references_native_drying_box(
    tmp_path,
):
    labutopia_root = tmp_path / "LabUtopia"
    source_dir = labutopia_root / "assets" / "chemistry_lab" / "lab_001"
    source_dir.mkdir(parents=True)
    (source_dir / "lab_001.usd").write_text("#usda 1.0\n", encoding="utf-8")

    overlay_root = tmp_path / "overlay" / "assets"
    build_asset_overlay(
        labutopia_root=labutopia_root,
        overlay_root=overlay_root,
        drying_box_strategy="native_complex",
    )

    scene_usda = (
        overlay_root
        / "scene_usds"
        / "labutopia"
        / "level1_poc"
        / "lab_001"
        / "scene.usda"
    ).read_text(encoding="utf-8")
    assert 'def Xform "obj_obj_DryingBox_01" (' in scene_usda
    assert (
        "prepend payload = @scene.usd@</World/DryingBox_01>" in scene_usda
        or "prepend references = @scene.usd@</World/DryingBox_01>" in scene_usda
    )
    assert 'over "handle"' in scene_usda
    assert 'def Cube "body_link"' not in scene_usda
    assert 'def Cube "door_link"' not in scene_usda
    assert 'def Cube "handle"' not in scene_usda
    assert 'def Xform "obj_obj_DryingBox_01_handle" (' not in scene_usda

    manifest_path = overlay_root / "manifests" / "labutopia_level1_poc.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["articulation_part_paths"] == {
        "obj_DryingBox_01_handle": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle"
    }
    assert manifest["wrapper_prim_paths"]["obj_DryingBox_01"] == (
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01"
    )
    assert manifest["wrapper_prim_paths"]["obj_DryingBox_01_handle"] == (
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle"
    )
    drying_box_runtime_asset = manifest["drying_box_runtime_asset"]
    assert drying_box_runtime_asset["strategy"] == (
        "native_complex_with_additive_physics_override"
    )
    assert drying_box_runtime_asset["source_payload_used"] is True
    assert drying_box_runtime_asset["source_prim_path"] == "/World/DryingBox_01"
    assert drying_box_runtime_asset["wrapper_prim_path"] == (
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01"
    )
    assert drying_box_runtime_asset["handle_policy"] == "nested_native_handle"
    assert drying_box_runtime_asset["surrogate_kept_for_debug_baseline"] is True


def test_build_asset_overlay_native_strategy_preserves_drying_box_materials(
    tmp_path,
):
    labutopia_root = tmp_path / "LabUtopia"
    source_dir = labutopia_root / "assets" / "chemistry_lab" / "lab_001"
    source_dir.mkdir(parents=True)
    (source_dir / "lab_001.usd").write_text("#usda 1.0\n", encoding="utf-8")
    helper_bytes, helper_hashes, texture_hashes = _write_native_material_fixture(
        source_dir
    )

    overlay_root = tmp_path / "overlay" / "assets"
    build_asset_overlay(
        labutopia_root=labutopia_root,
        overlay_root=overlay_root,
        drying_box_strategy="native_complex",
    )

    scene_usda = (
        overlay_root
        / "scene_usds"
        / "labutopia"
        / "level1_poc"
        / "lab_001"
        / "scene.usda"
    ).read_text(encoding="utf-8")

    drying_box_block = scene_usda.split('def Xform "obj_obj_DryingBox_01" (', 1)[1]
    drying_box_block = drying_box_block.split('def Xform "obj_table" (', 1)[0]
    assert (
        'def Scope "Looks" (\n'
        "                prepend payload = @scene.usd@</World/Looks>"
    ) in drying_box_block
    assert scene_usda.index('def Xform "labutopia_level1_poc"') < scene_usda.index(
        'def Scope "Looks" ('
    )
    assert (
        "rel material:binding = "
        "</World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/mdl_0007>"
    ) in drying_box_block
    assert (
        "rel material:binding = "
        "</World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/mdl_0008>"
    ) in drying_box_block
    assert (
        "rel material:binding = "
        "</World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/mdl_0009>"
    ) in drying_box_block
    assert (
        "rel material:binding = "
        "</World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/Aluminum_Anodized_Charcoal>"
    ) in drying_box_block
    assert "rel material:binding = </World/Looks/" not in drying_box_block
    assert "primvars:displayColor" in drying_box_block
    assert 'over "_900_1"' in drying_box_block
    assert "float physics:mass = 2" in drying_box_block
    assert "float physics:mass = 0.5" in drying_box_block
    assert "float physics:mass = 0.1" in drying_box_block
    assert "float state:angular:physics:position = 0" in drying_box_block

    manifest_path = overlay_root / "manifests" / "labutopia_level1_poc.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    drying_box_runtime_asset = manifest["drying_box_runtime_asset"]
    assert drying_box_runtime_asset["material_policy"] == (
        "owned_world_looks_payload_with_wrapper_local_rebind"
    )
    assert (
        drying_box_runtime_asset["material_scope_policy"]
        == "preserve_owned_world_looks"
    )
    assert drying_box_runtime_asset["material_status"] == "mixed_native_and_fallback"

    root_path = "/World/labutopia_level1_poc/obj_obj_DryingBox_01"
    report = manifest["drying_box_wrapper_composition"]
    assert report["schema_version"] == 1
    assert report["wrapper_prim_path"] == root_path
    assert report["source_prim_path"] == "/World/DryingBox_01"
    assert report["material_scope_policy"] == "preserve_owned_world_looks"
    assert report["material_policy"] == (
        "owned_world_looks_payload_with_wrapper_local_rebind"
    )
    assert report["material_status"] == "mixed_native_and_fallback"
    assert report["source_material_scope"] == "/World/Looks"
    assert report["runtime_material_scope"] == f"{root_path}/Looks"
    assert report["material_scope_ownership"] == (
        "source_world_looks_payloaded_under_wrapper"
    )
    assert report["source_binding_record_count"] == len(
        build_overlay.DRYING_BOX_NATIVE_MATERIAL_BINDINGS
    )
    assert report["runtime_rebind_count"] == len(
        build_overlay.DRYING_BOX_NATIVE_MATERIAL_BINDINGS
    )
    assert report["stale_source_binding_count"] == 0
    assert report["unresolved_binding_target_count"] == 0
    assert report["compute_bound_material_summary"] == {
        "checked_with": "UsdShade.MaterialBindingAPI.ComputeBoundMaterial",
        "bound_material_count": len(build_overlay.DRYING_BOX_NATIVE_MATERIAL_BINDINGS),
        "unbound_fallback_count": 3,
        "status": "mixed_native_and_fallback",
    }
    expected_material_paths = {
        f"{root_path}/Looks/{material_name}"
        for material_name in set(build_overlay.DRYING_BOX_NATIVE_MATERIAL_BINDINGS.values())
    }
    assert set(report["owned_material_paths"]) == expected_material_paths
    assert {
        record["runtime_binding_target"]
        for record in report["source_binding_records"]
    } == expected_material_paths
    assert all(
        record["source_binding_target"].startswith("/World/Looks/")
        for record in report["source_binding_records"]
    )
    assert all(
        record["runtime_binding_target"].startswith(f"{root_path}/Looks/")
        for record in report["source_binding_records"]
    )
    fallback_policy = report["fallback_display_color_policy"]
    assert fallback_policy["material_status"] == "mixed_native_and_fallback"
    assert fallback_policy["policy"] == "stage3_task_visible_readability_overlay"
    assert {
        record["runtime_prim_path"]
        for record in fallback_policy["fallback_records"]
    } == {
        f"{root_path}/button",
        f"{root_path}/Group/_900_1",
        f"{root_path}/panel",
    }
    assert report["payload_dependency_report"] == {
        "native_payload": "scene.usd</World/DryingBox_01>",
        "owned_material_scope_payload": "scene.usd</World/Looks>",
    }
    assert report["wrapper_transform_report"] == {
        "source_scale": [0.001, 0.001, 0.001],
        "axis_policy": "preserve_source_up_axis_and_axes",
        "workspace_translation": [0.75, 0.1, 0.78],
    }
    assert report["camera_light_prerequisites"] == {
        "task_yaml_camera_names": ["camera1", "camera2"],
        "primary_evidence_camera": "camera2",
        "deterministic_light_prims": [
            "/World/labutopia_level1_poc/DeterministicDomeLight"
        ],
    }
    assert report["worker_mdl_system_path"] == (
        "/isaac-sim/materials/:"
        "{ASSETS_DIR}/scene_usds/labutopia/level1_poc/lab_001/SubUSDs/materials:"
        "{ASSETS_DIR}/miscs/mdl/labutopia/mdl"
    )

    material_dependencies = {
        item["material_name"]: item
        for item in report["material_dependency_report"]
    }
    assert material_dependencies["mdl_0007"]["helper_mdl_imports"] == [
        {
            "module": "ad_3dsmax_materials",
            "relative_path": "SubUSDs/materials/ad_3dsmax_materials.mdl",
            "dependency_location_status": "local_file_copied_with_source_scene",
            "sha256": helper_hashes["ad_3dsmax_materials.mdl"],
            "bytes": len(helper_bytes["ad_3dsmax_materials.mdl"]),
        },
        {
            "module": "ad_3dsmax_maps",
            "relative_path": "SubUSDs/materials/ad_3dsmax_maps.mdl",
            "dependency_location_status": "local_file_copied_with_source_scene",
            "sha256": helper_hashes["ad_3dsmax_maps.mdl"],
            "bytes": len(helper_bytes["ad_3dsmax_maps.mdl"]),
        },
        {
            "module": "vray_materials",
            "relative_path": "SubUSDs/materials/vray_materials.mdl",
            "dependency_location_status": "local_file_copied_with_source_scene",
            "sha256": helper_hashes["vray_materials.mdl"],
            "bytes": len(helper_bytes["vray_materials.mdl"]),
        },
        {
            "module": "vray_maps",
            "relative_path": "SubUSDs/materials/vray_maps.mdl",
            "dependency_location_status": "local_file_copied_with_source_scene",
            "sha256": helper_hashes["vray_maps.mdl"],
            "bytes": len(helper_bytes["vray_maps.mdl"]),
        },
    ]
    assert material_dependencies["mdl_0008"]["texture_paths"] == [
        "SubUSDs/textures/image4.jpg"
    ]
    assert material_dependencies["mdl_0008"]["texture_hashes"] == {
        "SubUSDs/textures/image4.jpg": texture_hashes["image4.jpg"]
    }
    assert material_dependencies["mdl_0009"]["texture_paths"] == [
        "SubUSDs/textures/image1.JPG"
    ]
    assert material_dependencies["mdl_0009"]["texture_hashes"] == {
        "SubUSDs/textures/image1.JPG": texture_hashes["image1.JPG"]
    }
    aluminum = material_dependencies["Aluminum_Anodized_Charcoal"]
    assert aluminum["dependency_location_status"] == "local_mirror_copied_with_package"
    assert aluminum["offline_material_closure_status"] == "resolved_local_mirror"
    assert aluminum["remote_aluminum_disposition"] == "local_mirror"
    assert aluminum["material_closure_kept_open"] is False
    assert aluminum["local_mirror_path"] == (
        "miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl"
    )
    assert aluminum["worker_resolved_path"] == (
        "{ASSETS_DIR}/miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl"
    )
    assert aluminum["worker_mdl_system_path_covered"] is True
    assert aluminum["sha256"] == (
        "640855d3890c6faaae6346a850ef9f366d4b397c0f4313e25c7ac0b9230c106a"
    )
    assert aluminum["bytes"] == 1600
    assert aluminum["texture_paths"] == [
        "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_BaseColor.png",
        "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_Normal.png",
        "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_ORM.png",
    ]


def test_manifest_contains_generic_asset_acceptance_material_closure(tmp_path):
    labutopia_root = tmp_path / "LabUtopia"
    source_dir = labutopia_root / "assets" / "chemistry_lab" / "lab_001"
    source_dir.mkdir(parents=True)
    (source_dir / "lab_001.usd").write_text("#usda 1.0\n", encoding="utf-8")
    _write_native_material_fixture(source_dir)

    overlay_root = tmp_path / "overlay" / "assets"
    build_asset_overlay(
        labutopia_root=labutopia_root,
        overlay_root=overlay_root,
        drying_box_strategy="native_complex",
    )

    manifest_path = overlay_root / "manifests" / "labutopia_level1_poc.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    material = manifest["asset_acceptance"]["material_closure"]
    assert material["asset_id"] == "LabUtopia/DryingBox_01"
    assert material["material_status"] == "mixed_native_and_fallback"
    assert material["derived_counts"] == {
        "remote_unmirrored_unwaived_count": 0,
        "remote_waiver_count": 0,
        "local_mirror_count": 1,
        "unsupported_dependency_resolution_mode_count": 0,
        "fallback_surface_count": 3,
    }
    assert material["blockers"] == [
        "fallback_surfaces_remain_after_aluminum_local_mirror"
    ]
    assert material["aluminum_material_closure_claim_allowed"] is True
    assert material["native_material_closure_claim_allowed"] is False
    assert material["full_native_material_closure_claim_allowed"] is False


def test_build_asset_overlay_native_strategy_writes_stage4_physics_override_report(
    tmp_path,
):
    labutopia_root = tmp_path / "LabUtopia"
    source_dir = labutopia_root / "assets" / "chemistry_lab" / "lab_001"
    source_dir.mkdir(parents=True)
    source_scene = source_dir / "lab_001.usd"
    source_scene.write_text("#usda 1.0\n", encoding="utf-8")
    _write_native_material_fixture(source_dir)

    overlay_root = tmp_path / "overlay" / "assets"
    diagnostics_root = (
        tmp_path
        / "saved"
        / "diagnostics"
        / "native_dryingbox_physics_override_20260629_000000"
    )
    build_asset_overlay(
        labutopia_root=labutopia_root,
        overlay_root=overlay_root,
        drying_box_strategy="native_complex",
        physics_override_output_root=diagnostics_root,
    )

    manifest_path = overlay_root / "manifests" / "labutopia_level1_poc.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = manifest["drying_box_physics_override"]
    report_path = build_overlay.Path(report["physics_override_json"])
    packaged_report_path = build_overlay.Path(report["packaged_physics_override_json"])
    assert report_path == diagnostics_root / "physics_override.json"
    assert report_path.exists()
    assert packaged_report_path.exists()
    assert report["stage"] == "acceptance_stage_4"
    assert report["status"] == "passed"
    assert report["override_layer_path"].endswith(
        "scene_usds/labutopia/level1_poc/lab_001/scene.usda"
    )
    assert report["generated_wrapper_stage_path"] == report["override_layer_path"]
    assert report["source_usd_path"] == str(source_scene)
    assert report["source_usd_sha256"] == build_overlay._sha256(source_scene)
    assert report["remote_aluminum_disposition"] == "local_mirror"
    assert report["material_closure_kept_open"] is True
    assert report["native_material_closure_reason"] == (
        "fallback_surfaces_remain_after_aluminum_local_mirror"
    )

    scene_text = (
        overlay_root
        / "scene_usds"
        / "labutopia"
        / "level1_poc"
        / "lab_001"
        / "scene.usda"
    ).read_text(encoding="utf-8")
    assert "https://omniverse-content-production.s3.us-west-2.amazonaws.com" not in scene_text
    assert (
        "asset info:mdl:sourceAsset = @Aluminum_Anodized_Charcoal.mdl@"
        in scene_text
    )
    assert (
        overlay_root
        / "miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl"
    ).exists()
    assert (
        overlay_root
        / "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_Normal.png"
    ).exists()
    copied_paths = {item["relative_path"] for item in manifest["copied_files"]}
    assert {
        "miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl",
        "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_BaseColor.png",
        "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_Normal.png",
        "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_ORM.png",
    }.issubset(copied_paths)

    gate = report["static_material_dependency_gate"]
    assert gate["status"] == "passed"
    assert gate["remote_unmirrored_unwaived_count"] == 0
    assert gate["remote_waiver_count"] == 0
    assert gate["local_mirror_count"] == 1
    assert gate["remote_dependency_records"] == [
        {
            "material_name": "Aluminum_Anodized_Charcoal",
            "source_material_path": "/World/Looks/Aluminum_Anodized_Charcoal",
            "runtime_material_path": (
                "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/"
                "Aluminum_Anodized_Charcoal"
            ),
            "source_url": (
                "https://omniverse-content-production.s3.us-west-2.amazonaws.com/"
                "Materials/Base/Metals/Aluminum_Anodized_Charcoal.mdl"
            ),
            "resolution_mode": "local_mirror",
            "local_mirror_path": (
                "miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl"
            ),
            "local_mirror_sha256": (
                "640855d3890c6faaae6346a850ef9f366d4b397c0f4313e25c7ac0b9230c106a"
            ),
            "local_mirror_bytes": 1600,
            "worker_resolved_path": (
                "{ASSETS_DIR}/miscs/mdl/labutopia/mdl/"
                "Aluminum_Anodized_Charcoal.mdl"
            ),
            "worker_mdl_system_path_covered": True,
            "waiver_id": None,
            "waiver_reason": None,
            "closure_claim_allowed": False,
            "aluminum_material_closure_claim_allowed": True,
            "native_material_closure_claim_allowed": False,
            "full_native_material_closure_claim_allowed": False,
        }
    ]

    saved_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved_report == report
    assert saved_report["dof_map"]["metric_dof"] == {
        "joint_name": "RevoluteJoint",
        "joint_type": "PhysicsRevoluteJoint",
        "metric": "open_door_angle_deg",
    }
    assert saved_report["dof_map"]["ignored_dofs"] == [
        {
            "joint_name": "PrismaticJoint",
            "joint_type": "PhysicsPrismaticJoint",
            "policy": "ignored_by_open_door_metric",
        }
    ]
    assert saved_report["material_validator_summary"] == {
        "unresolved_binding_target_count": 0,
        "remote_only_dependency_count": 0,
        "fallback_surface_count": 3,
        "waiver_count": 0,
        "remote_aluminum_disposition": "local_mirror",
        "native_material_closure_open": True,
        "native_material_closure_reason": (
            "fallback_surfaces_remain_after_aluminum_local_mirror"
        ),
    }


def test_parse_args_accepts_native_drying_box_strategy(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_asset_overlay.py", "--drying-box-strategy", "native_complex"],
    )

    args = build_overlay.parse_args()

    assert args.drying_box_strategy == "native_complex"


def test_build_asset_overlay_cli_runs_from_repo_root(tmp_path):
    labutopia_root = tmp_path / "LabUtopia"
    source_dir = labutopia_root / "assets" / "chemistry_lab" / "lab_001"
    source_dir.mkdir(parents=True)
    (source_dir / "lab_001.usd").write_text("#usda 1.0\n", encoding="utf-8")

    overlay_root = tmp_path / "overlay" / "assets"
    repo_root = build_overlay.Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "standalone_tools/labutopia_poc/build_asset_overlay.py",
            "--labutopia-root",
            str(labutopia_root),
            "--overlay-root",
            str(overlay_root),
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    output = json.loads(result.stdout)
    assert output["manifest"] == str(
        overlay_root / "manifests" / "labutopia_level1_poc.json"
    )


def test_build_asset_overlay_rejects_overlay_scene_inside_source_dir(
    tmp_path, monkeypatch
):
    labutopia_root = tmp_path / "LabUtopia"
    source_dir = labutopia_root / "assets" / "chemistry_lab" / "lab_001"
    source_dir.mkdir(parents=True)
    (source_dir / "lab_001.usd").write_text("#usda 1.0\n", encoding="utf-8")

    def fail_if_copytree_runs(source, destination):
        raise AssertionError(f"copytree should not run for {source} -> {destination}")

    monkeypatch.setattr(build_overlay.shutil, "copytree", fail_if_copytree_runs)

    with pytest.raises(ValueError, match="inside the LabUtopia source scene directory"):
        build_asset_overlay(labutopia_root=labutopia_root, overlay_root=source_dir)

    assert not (
        source_dir
        / "scene_usds"
        / "labutopia"
        / "level1_poc"
        / "lab_001"
        / "scene_usds"
    ).exists()


def test_metrics_manager_lazily_registers_labutopia_metrics_without_omni():
    script = """
import sys

assert 'omni' not in sys.modules
from genmanip.core.metrics.metrics_manager import MetricsManager

manager = MetricsManager([
    [[{
        'type': 'manip/labutopia/object_height_delta',
        'sub_goal_setting': {
            'obj_uid': 'obj_conical_bottle02',
            'axis': 'z',
            'min_delta': 0.1,
        },
    }]]
])
metric = manager.cur_union_metric[0][0]
assert metric.__class__.__name__ == 'ObjectHeightDelta'
assert 'omni' not in sys.modules
"""
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=build_overlay.Path(__file__).resolve().parents[2],
        check=True,
    )
