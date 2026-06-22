import hashlib
import json

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
    assert '@scene.usd@</World>' in (scene_dir / "scene.usda").read_text(
        encoding="utf-8"
    )

    manifest_path = overlay_root / "manifests" / "labutopia_level1_poc.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert (
        manifest["usd_name"]
        == "scene_usds/labutopia/level1_poc/lab_001/scene"
    )
    assert set(manifest["task_prims"]) == {
        "level1_pick",
        "level1_place",
        "level1_open_door",
    }
    assert manifest["prim_rename_map"]["conical_bottle02"] == "obj_conical_bottle02"
    assert "obj_conical_bottle02" in manifest["required_genmanip_object_uids"]

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
