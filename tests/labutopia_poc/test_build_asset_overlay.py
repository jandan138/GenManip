import hashlib
import json
import subprocess
import sys

import pytest

import standalone_tools.labutopia_poc.build_asset_overlay as build_overlay
from standalone_tools.labutopia_poc.build_asset_overlay import build_asset_overlay


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
