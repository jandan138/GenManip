import json
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
        "position": [9.6, 0.0, 2.5],
        "orientation": [0.70711, 0.0, 0.0, -0.70711],
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


def test_labutopia_tasks_define_runtime_articulation_contract():
    for path in validate_task_package._indexed_task_yaml_paths():
        data = validate_task_package._load_yaml(path)
        cfg = data["evaluation_configs"][0]

        assert "articulation" in cfg["generation_config"], str(path)


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
