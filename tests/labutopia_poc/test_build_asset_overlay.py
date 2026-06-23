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
    assert (
        'def Xform "obj_obj_DryingBox_01_handle" (\n'
        '            prepend payload = @scene.usd@</World/DryingBox_01/handle>'
    ) in scene_usda
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
        "obj_DryingBox_01_handle": "/World/labutopia_level1_poc/obj_obj_DryingBox_01_handle",
        "table": "/World/labutopia_level1_poc/obj_table",
    }
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
    assert manifest["notes"] == [
        "scene.usda exposes a single scene uid under /World for GenManip discovery.",
        "Immediate obj_* wrapper prims payload the selected LabUtopia source prims.",
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
