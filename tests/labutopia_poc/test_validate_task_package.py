import copy
import json
import math
import subprocess
import sys
import types

import pytest
import yaml

from standalone_tools.labutopia_poc import validate_task_package


EXPECTED_TOP_INDEX = [
    "ebench/labutopia_lab_poc/franka_poc/franka_poc.json",
    "ebench/labutopia_lab_poc/lift2_candidate/lift2_candidate.json",
]
EXPECTED_TASKS = ["level1_pick", "level1_place", "level1_open_door"]
EXPECTED_RENDER_OBJECTS = {
    "level1_pick": ["obj_conical_bottle02"],
    "level1_place": ["obj_beaker2", "obj_target_plat"],
    "level1_open_door": ["obj_DryingBox_01", "obj_DryingBox_01_handle"],
}
EXPECTED_TASK_CAMERA_CONFIGS = {
    "level1_pick": "configs/cameras/labutopia_franka_poc_pick.yml",
    "level1_place": "configs/cameras/labutopia_franka_poc_place.yml",
    "level1_open_door": "configs/cameras/labutopia_franka_poc_open_door.yml",
}
CAMERA_CLEANUP_FLAGS = {
    "with_bbox2d",
    "with_bbox3d",
    "with_motion_vector",
    "with_semantic",
    "with_distance",
}
BASE_FRANKA_CAMERAS = {
    "camera1": {
        "position": [2.0, 0.0, 2.0],
        "orientation": [0.61237, 0.35355, 0.35355, 0.61237],
        "camera_axes": "usd",
        **{flag: False for flag in CAMERA_CLEANUP_FLAGS},
    },
    "camera2": {
        "position": [0.45, -1.1, 1.55],
        "orientation": [0.87184, 0.4898, 0.0, 0.0],
        "camera_axes": "usd",
        **{flag: False for flag in CAMERA_CLEANUP_FLAGS},
    },
}
BASE_LIFT2_CAMERAS = {
    "camera1": {
        "position": [0.0, 0.0, 0.0],
        "orientation": [1.0, 0.0, 0.0, 0.0],
        **{flag: False for flag in CAMERA_CLEANUP_FLAGS},
    }
}


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_yaml(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def _write_task_files(task_root):
    for profile in ("franka_poc", "lift2_candidate"):
        profile_root = task_root / "ebench/labutopia_lab_poc" / profile
        profile_root.mkdir(parents=True, exist_ok=True)
        for task_name in EXPECTED_TASKS:
            (profile_root / f"{task_name}.yml").write_text("{}", encoding="utf-8")


def _write_valid_indexes(task_root):
    package_root = task_root / "ebench/labutopia_lab_poc"
    _write_json(package_root / "labutopia_lab_poc.json", EXPECTED_TOP_INDEX)
    for profile in ("franka_poc", "lift2_candidate"):
        _write_json(
            package_root / profile / f"{profile}.json",
            [
                f"ebench/labutopia_lab_poc/{profile}/{task}.yml"
                for task in EXPECTED_TASKS
            ],
        )


def _write_camera_config_fixture(tmp_root, franka_cameras):
    _write_yaml(tmp_root / "configs/cameras/labutopia_franka_poc.yml", franka_cameras)
    _write_yaml(
        tmp_root / "configs/cameras/fixed_camera_lift2_simbox.yml",
        BASE_LIFT2_CAMERAS,
    )
    for (
        task_name,
        config_path,
    ) in validate_task_package.EXPECTED_FRANKA_TASK_CAMERA_CONFIGS.items():
        task_cameras = {
            camera_name: dict(camera)
            for camera_name, camera in BASE_FRANKA_CAMERAS.items()
        }
        task_cameras["camera2"].update(
            validate_task_package.EXPECTED_FRANKA_TASK_CAMERA2_CONTRACTS[task_name]
        )
        task_cameras["camera2"]["task_view"] = task_name
        _write_yaml(tmp_root / config_path, task_cameras)


def test_indexed_task_yaml_paths_rejects_duplicate_profile_entries(tmp_path, monkeypatch):
    task_root = tmp_path / "tasks"
    _write_task_files(task_root)
    _write_valid_indexes(task_root)
    package_root = task_root / "ebench/labutopia_lab_poc"
    _write_json(
        package_root / "franka_poc/franka_poc.json",
        [
            "ebench/labutopia_lab_poc/franka_poc/level1_pick.yml",
            "ebench/labutopia_lab_poc/franka_poc/level1_pick.yml",
            "ebench/labutopia_lab_poc/franka_poc/level1_place.yml",
        ],
    )
    monkeypatch.setattr(validate_task_package, "TASK_ROOT", task_root)
    monkeypatch.setattr(validate_task_package, "PACKAGE_ROOT", package_root)

    with pytest.raises(AssertionError, match="franka_poc.json"):
        validate_task_package._indexed_task_yaml_paths()


def test_metrics_manager_lazy_registration_does_not_keep_metrics_package_imported():
    sys.modules["genmanip.extensions.metrics"] = types.ModuleType(
        "genmanip.extensions.metrics"
    )
    try:
        validate_task_package._validate_metrics_manager_lazy_registration()
        assert "genmanip.extensions.metrics" not in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "genmanip.extensions.metrics" or module_name.startswith(
                "genmanip.extensions.metrics."
            ):
                del sys.modules[module_name]


def test_validate_task_package_cli_reports_success():
    result = subprocess.run(
        [sys.executable, "standalone_tools/labutopia_poc/validate_task_package.py"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "LabUtopia task package validation OK" in result.stdout


def test_assets_manifest_rejects_missing_overlay_runtime_scene(tmp_path, monkeypatch):
    package_root = tmp_path / "tasks/ebench/labutopia_lab_poc"
    common_root = package_root / "common"
    common_root.mkdir(parents=True)
    overlay_root = tmp_path / "overlay/assets"
    generated_manifest = tmp_path / "generated_manifest.json"
    generated_manifest.write_text(
        json.dumps(
            {
                "usd_name": validate_task_package.RUNTIME_USD_NAME,
                "scene_uid": validate_task_package.SCENE_UID,
                "runtime_object_keys": [],
                "wrapper_prim_paths": validate_task_package.EXPECTED_WRAPPER_PRIM_PATHS,
                "source_to_runtime_object_key": {},
            }
        ),
        encoding="utf-8",
    )
    _write_json(
        common_root / "assets_manifest.json",
        {
            "overlay_root": str(overlay_root),
            "runtime_usd_name": validate_task_package.RUNTIME_USD_NAME,
            "generated_manifest": str(generated_manifest),
            "scene_uid": validate_task_package.SCENE_UID,
            "runtime_object_keys": [],
            "wrapper_prim_paths": validate_task_package.EXPECTED_WRAPPER_PRIM_PATHS,
            "source_to_runtime_object_key": {},
        },
    )
    monkeypatch.setattr(validate_task_package, "PACKAGE_ROOT", package_root)

    with pytest.raises(FileNotFoundError, match="runtime scene"):
        validate_task_package._validate_assets_manifest()


def test_assets_manifest_rejects_missing_drying_box_visual_affordance_geometry(
    tmp_path,
    monkeypatch,
):
    package_root = tmp_path / "tasks/ebench/labutopia_lab_poc"
    common_root = package_root / "common"
    common_root.mkdir(parents=True)
    overlay_root = tmp_path / "overlay/assets"
    runtime_scene = overlay_root / f"{validate_task_package.RUNTIME_USD_NAME}.usda"
    runtime_scene.parent.mkdir(parents=True)
    runtime_scene.write_text(
        """
#usda 1.0
def Xform "World"
{
    def Xform "labutopia_level1_poc"
    {
        def Cube "handle_visual_marker" (
            prepend apiSchemas = ["MaterialBindingAPI"]
        )
        {
            color3f[] primvars:displayColor = [(1, 0.18, 0.04)]
        }
        def DomeLight "DeterministicDomeLight"
        {
            float inputs:intensity = 1000
        }
    }
}
""",
        encoding="utf-8",
    )
    real_manifest = validate_task_package._load_json(
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = copy.deepcopy(real_manifest)
    manifest["overlay_root"] = str(overlay_root)
    manifest["generated_manifest"] = str(tmp_path / "generated_manifest.json")
    generated = {
        "usd_name": manifest["runtime_usd_name"],
        "scene_uid": manifest["scene_uid"],
        "runtime_object_keys": manifest["runtime_object_keys"],
        "wrapper_prim_paths": manifest["wrapper_prim_paths"],
        "source_to_runtime_object_key": manifest["source_to_runtime_object_key"],
        "deterministic_lights": manifest["deterministic_lights"],
        "articulation_part_paths": manifest["articulation_part_paths"],
        "render_object_contracts": manifest["render_object_contracts"],
        "drying_box_runtime_asset": manifest["drying_box_runtime_asset"],
    }
    _write_json(validate_task_package.Path(manifest["generated_manifest"]), generated)
    _write_json(common_root / "assets_manifest.json", manifest)
    monkeypatch.setattr(validate_task_package, "PACKAGE_ROOT", package_root)
    monkeypatch.setattr(
        validate_task_package,
        "EXPECTED_DRYING_BOX_RUNTIME_ASSET",
        manifest["drying_box_runtime_asset"],
    )

    with pytest.raises(AssertionError, match="drying-box door visual affordance"):
        validate_task_package._validate_assets_manifest()


def test_labutopia_tasks_define_runtime_articulation_contract():
    for path in validate_task_package._indexed_task_yaml_paths():
        data = validate_task_package._load_yaml(path)
        cfg = data["evaluation_configs"][0]

        assert "articulation" in cfg["generation_config"], str(path)


def test_labutopia_assets_manifest_declares_p1_render_object_contracts():
    manifest_path = (
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = validate_task_package._load_json(manifest_path)

    contracts = manifest["render_object_contracts"]
    for uid in {
        uid
        for required in EXPECTED_RENDER_OBJECTS.values()
        for uid in required
    }:
        contract = contracts[uid]
        assert contract["wrapper_prim_path"] == manifest["wrapper_prim_paths"][uid]
        assert contract["display_color"] != [0.5, 0.5, 0.5]
        assert contract["expected_world_bbox_lwh_m"]["min"]
        assert contract["expected_world_bbox_lwh_m"]["max"]

    assert manifest["wrapper_prim_paths"]["obj_DryingBox_01_handle"] == (
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle"
    )
    assert manifest["articulation_part_paths"] == {
        "obj_DryingBox_01_handle": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle"
    }
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

    runtime_scene = (
        validate_task_package.Path(manifest["overlay_root"])
        / f"{manifest['runtime_usd_name']}.usda"
    )
    scene_text = runtime_scene.read_text(encoding="utf-8")
    assert 'def Xform "obj_obj_DryingBox_01_handle" (' not in scene_text
    assert "double3 xformOp:translate = (0.18, -0.22, 0.05)" in scene_text
    assert 'def Cube "handle_visual_marker"' not in scene_text
    assert "double3 xformOp:translate = (0.18, -0.165, 0.05)" not in scene_text
    assert "double3 xformOp:translate = (-0.18, -0.22, 0.05)" not in scene_text
    assert "double3 xformOp:translate = (-0.18, -0.165, 0.05)" not in scene_text


def test_franka_tasks_define_render_validation_contract():
    for task_name, required_objects in EXPECTED_RENDER_OBJECTS.items():
        path = (
            validate_task_package.PACKAGE_ROOT
            / "franka_poc"
            / f"{task_name}.yml"
        )
        cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]
        validation = cfg["labutopia_render_validation"]
        camera_config_path = cfg["domain_randomization"]["cameras"]["config_path"]
        camera_path = validate_task_package.ROOT / camera_config_path
        cameras = validate_task_package._load_yaml(camera_path)

        assert validation["schema_version"] == 1
        assert validation["primary_camera"] == "camera2"
        assert validation["required_visible_objects"] == required_objects
        assert validation["evidence_policy"] == {"direct_render": False}
        assert set(validation["required_camera_names"]).issubset(cameras)
        assert {
            "black_frame",
            "low_texture",
            "required_object_missing",
            "severe_clipping",
        }.issubset(set(validation["reject_frame_if"]))


def test_franka_tasks_use_task_specific_evidence_camera_configs():
    seen_configs = set()
    for task_name, expected_config in EXPECTED_TASK_CAMERA_CONFIGS.items():
        path = (
            validate_task_package.PACKAGE_ROOT
            / "franka_poc"
            / f"{task_name}.yml"
        )
        cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]
        camera_config_path = cfg["domain_randomization"]["cameras"]["config_path"]
        validation = cfg["labutopia_render_validation"]

        assert camera_config_path == expected_config
        seen_configs.add(camera_config_path)
        assert validation["primary_camera"] == "camera2"
        assert validation["evidence_camera_config"] == expected_config

        cameras = validate_task_package._load_yaml(
            validate_task_package.ROOT / camera_config_path
        )
        assert cameras["camera2"]["camera_axes"] == "usd"
        assert cameras["camera2"]["resolution"] == [512, 512]
        assert cameras["camera2"]["task_view"] == task_name

    assert len(seen_configs) == len(EXPECTED_TASK_CAMERA_CONFIGS)


def test_open_door_evidence_camera_is_close_to_handle_for_visual_qa():
    camera_path = (
        validate_task_package.ROOT
        / "configs/cameras/labutopia_franka_poc_open_door.yml"
    )
    cameras = validate_task_package._load_yaml(camera_path)
    camera2 = cameras["camera2"]

    position = camera2["position"]
    handle_anchor = [0.77, -0.02, 0.80]

    distance_to_handle = math.dist(position, handle_anchor)

    assert 0.54 <= distance_to_handle <= 0.64
    assert 0.72 <= position[0] <= 0.78
    assert -0.60 <= position[1] <= -0.52
    assert 0.99 <= position[2] <= 1.05
    assert 4.5 <= camera2["focal_length"] <= 5.5
    assert 9.0 <= camera2["horizontal_aperture"] <= 11.0


def test_franka_render_validation_declares_object_pixel_readability_thresholds():
    expected_minimums = {
        "level1_pick": {
            "obj_conical_bottle02": {"min_width_px": 36, "min_height_px": 48},
        },
        "level1_place": {
            "obj_beaker2": {"min_width_px": 34, "min_height_px": 34},
            "obj_target_plat": {"min_width_px": 42, "min_height_px": 24},
        },
        "level1_open_door": {
            "obj_DryingBox_01": {"min_width_px": 160, "min_height_px": 150},
            "obj_DryingBox_01_handle": {
                "min_width_px": 18,
                "min_height_px": 64,
            },
        },
    }

    for task_name, object_thresholds in expected_minimums.items():
        path = (
            validate_task_package.PACKAGE_ROOT
            / "franka_poc"
            / f"{task_name}.yml"
        )
        cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]
        thresholds = cfg["labutopia_render_validation"]["object_pixel_thresholds"]

        for uid, minimums in object_thresholds.items():
            actual = thresholds[uid]
            assert actual["min_width_px"] >= minimums["min_width_px"]
            assert actual["min_height_px"] >= minimums["min_height_px"]
            assert actual["min_area_fraction"] > 0.0


def test_franka_tasks_hide_non_task_objects_for_evidence_readability():
    expected_hidden = {
        "level1_pick": [
            "obj_beaker2",
            "obj_target_plat",
            "obj_DryingBox_01",
        ],
        "level1_place": ["obj_conical_bottle02", "obj_DryingBox_01"],
        "level1_open_door": [
            "obj_conical_bottle02",
            "obj_beaker2",
            "obj_target_plat",
        ],
    }

    for task_name, hidden_uids in expected_hidden.items():
        path = (
            validate_task_package.PACKAGE_ROOT
            / "franka_poc"
            / f"{task_name}.yml"
        )
        cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]
        active_rules = [
            item
            for item in cfg["preprocess_config"]
            if item.get("type") == "set_object_active"
        ]

        assert active_rules == [
            {"type": "set_object_active", "config": {"active": False, "uids": hidden_uids}}
        ]
        assert cfg["labutopia_render_validation"]["hidden_non_task_objects"] == hidden_uids


def test_open_door_uses_nested_handle_articulation_part_contract():
    path = (
        validate_task_package.PACKAGE_ROOT
        / "franka_poc"
        / "level1_open_door.yml"
    )
    cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]

    drying_box = cfg["object_config"]["obj_DryingBox_01"]
    assert drying_box["type"] == "existed_object"
    assert drying_box["uid_list"] == ["obj_DryingBox_01"]
    assert drying_box["is_articulated"] is True
    assert drying_box["articulation_info"]["is_articulated"] is True
    assert drying_box["articulation_info"]["part"]["handle"] == "/handle"

    metric = cfg["generation_config"]["goal"][0][0][0]
    assert metric["type"] == "manip/default/check_joint_angle"
    assert metric["articulation_obj_uid"] == "obj_DryingBox_01"
    assert metric["joint_name"] == "RevoluteJoint"


def test_open_door_initializes_drying_box_closed_for_eval_start():
    for profile in ("franka_poc", "lift2_candidate"):
        path = validate_task_package.PACKAGE_ROOT / profile / "level1_open_door.yml"
        cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]
        drying_box = cfg["object_config"]["obj_DryingBox_01"]

        assert drying_box["target_positions"] == [0.0], str(path)


def test_drying_box_articulation_physics_is_sanitized_for_runtime():
    manifest_path = (
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = validate_task_package._load_json(manifest_path)
    runtime_scene = (
        validate_task_package.Path(manifest["overlay_root"])
        / f"{manifest['runtime_usd_name']}.usda"
    )

    report = validate_task_package._inspect_drying_box_articulation_physics(
        runtime_scene
    )

    assert report["root_path"] == manifest["wrapper_prim_paths"]["obj_DryingBox_01"]
    assert report["zero_mass_links"] == []
    assert report["zero_inertia_links"] == []
    assert report["sanitized_for_physx"] is True


def test_drying_box_articulation_topology_is_ready_for_runtime():
    manifest_path = (
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = validate_task_package._load_json(manifest_path)
    runtime_scene = (
        validate_task_package.Path(manifest["overlay_root"])
        / f"{manifest['runtime_usd_name']}.usda"
    )

    report = validate_task_package._inspect_drying_box_articulation_physics(
        runtime_scene
    )

    assert report["root_scale"] in ([], [1.0, 1.0, 1.0])
    assert report["non_identity_root_scale"] is False
    assert report["duplicate_rigid_link_names"] == {}
    assert report["invalid_center_of_mass_links"] == []
    assert report["invalid_principal_axes_links"] == []
    assert report["invalid_joint_body_targets"] == []
    assert report["world_fixed_base_joint_paths"] == [
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/BaseFixedJoint"
    ]
    assert report["unexpected_joint_types"] == []
    assert report["runtime_topology_ready"] is True


def test_labutopia_camera_configs_define_cleanup_flags():
    for expectation in validate_task_package.PROFILE_EXPECTATIONS.values():
        camera_path = validate_task_package.ROOT / expectation["camera_config"]
        cameras = validate_task_package._load_yaml(camera_path)
        for camera_name, camera in cameras.items():
            missing = CAMERA_CLEANUP_FLAGS - set(camera)
            assert not missing, f"{camera_path}:{camera_name} missing {missing}"


def test_labutopia_franka_camera_config_declares_axes_and_task_view():
    camera_path = validate_task_package.ROOT / "configs/cameras/labutopia_franka_poc.yml"
    cameras = validate_task_package._load_yaml(camera_path)

    for camera_name, expected_axes in (
        validate_task_package.EXPECTED_FRANKA_CAMERA_AXES.items()
    ):
        assert cameras[camera_name]["camera_axes"] == expected_axes

    assert (
        cameras["camera2"]["position"]
        == validate_task_package.EXPECTED_FRANKA_CAMERA2_POSITION
    )
    assert (
        cameras["camera2"]["orientation"]
        == validate_task_package.EXPECTED_FRANKA_CAMERA2_ORIENTATION
    )


def test_labutopia_franka_primary_camera_is_over_runtime_workspace():
    camera_path = validate_task_package.ROOT / "configs/cameras/labutopia_franka_poc.yml"
    cameras = validate_task_package._load_yaml(camera_path)

    x, y, z = cameras["camera2"]["position"]
    assert 0.0 <= x <= 1.2
    assert -1.3 <= y <= 0.8
    assert 1.2 <= z <= 2.0
    assert cameras["camera2"]["position"] != [9.6, 0.0, 2.5]
    assert cameras["camera2"]["orientation"] == [0.87184, 0.4898, 0.0, 0.0]


def test_validate_camera_configs_rejects_franka_camera_axes_regression(
    tmp_path, monkeypatch
):
    franka_cameras = {
        camera_name: dict(camera)
        for camera_name, camera in BASE_FRANKA_CAMERAS.items()
    }
    franka_cameras["camera2"]["camera_axes"] = "world"
    _write_camera_config_fixture(tmp_path, franka_cameras)
    monkeypatch.setattr(validate_task_package, "ROOT", tmp_path)

    with pytest.raises(AssertionError, match="camera2: camera_axes must remain 'usd'"):
        validate_task_package._validate_camera_configs()


def test_validate_camera_configs_rejects_franka_camera2_position_regression(
    tmp_path, monkeypatch
):
    franka_cameras = {
        camera_name: dict(camera)
        for camera_name, camera in BASE_FRANKA_CAMERAS.items()
    }
    franka_cameras["camera2"]["position"] = [0.1, 0.0, 2.5]
    _write_camera_config_fixture(tmp_path, franka_cameras)
    monkeypatch.setattr(validate_task_package, "ROOT", tmp_path)

    with pytest.raises(AssertionError, match="camera2 position must remain"):
        validate_task_package._validate_camera_configs()


def test_validate_camera_configs_rejects_franka_camera2_orientation_regression(
    tmp_path, monkeypatch
):
    franka_cameras = {
        camera_name: dict(camera)
        for camera_name, camera in BASE_FRANKA_CAMERAS.items()
    }
    franka_cameras["camera2"]["orientation"] = [0.70711, 0.0, 0.0, -0.70711]
    _write_camera_config_fixture(tmp_path, franka_cameras)
    monkeypatch.setattr(validate_task_package, "ROOT", tmp_path)

    with pytest.raises(AssertionError, match="camera2 orientation must remain"):
        validate_task_package._validate_camera_configs()


def test_validate_camera_configs_rejects_open_door_lens_regression(
    tmp_path, monkeypatch
):
    franka_cameras = {
        camera_name: dict(camera)
        for camera_name, camera in BASE_FRANKA_CAMERAS.items()
    }
    _write_camera_config_fixture(tmp_path, franka_cameras)
    open_door_camera_path = (
        tmp_path / "configs/cameras/labutopia_franka_poc_open_door.yml"
    )
    open_door_cameras = yaml.safe_load(
        open_door_camera_path.read_text(encoding="utf-8")
    )
    del open_door_cameras["camera2"]["focal_length"]
    _write_yaml(open_door_camera_path, open_door_cameras)
    monkeypatch.setattr(validate_task_package, "ROOT", tmp_path)

    with pytest.raises(AssertionError, match="camera2 focal_length must be 5.0"):
        validate_task_package._validate_camera_configs()


def test_assets_manifest_declares_deterministic_runtime_light():
    manifest_path = (
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = validate_task_package._load_json(manifest_path)

    assert manifest["deterministic_lights"] == [
        {
            "prim_path": "/World/labutopia_level1_poc/DeterministicDomeLight",
            "type": "DomeLight",
            "intensity": 1000,
        }
    ]

    runtime_scene = (
        validate_task_package.Path(manifest["overlay_root"])
        / f"{manifest['runtime_usd_name']}.usda"
    )
    scene_text = runtime_scene.read_text(encoding="utf-8")
    assert 'def DomeLight "DeterministicDomeLight"' in scene_text
    assert "float inputs:intensity = 1000" in scene_text
