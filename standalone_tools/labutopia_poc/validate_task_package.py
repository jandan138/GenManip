#!/usr/bin/env python3
"""Static validator for the LabUtopia EBench proof-of-concept task package."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
TASK_ROOT = ROOT / "configs/tasks"
PACKAGE_ROOT = TASK_ROOT / "ebench/labutopia_lab_poc"
TASK_PREFIX = "ebench/labutopia_lab_poc/"
SCENE_UID = "labutopia_level1_poc"
RUNTIME_USD_NAME = "scene_usds/labutopia/level1_poc/lab_001/scene"
EXPECTED_TASKS = {"level1_pick", "level1_place", "level1_open_door"}
EXPECTED_TASK_ORDER = ["level1_pick", "level1_place", "level1_open_door"]
EXPECTED_TOP_INDEX_ENTRIES = [
    "ebench/labutopia_lab_poc/franka_poc/franka_poc.json",
    "ebench/labutopia_lab_poc/lift2_candidate/lift2_candidate.json",
]
EXPECTED_PROFILE_INDEX_ENTRIES = {
    profile: [
        f"ebench/labutopia_lab_poc/{profile}/{task}.yml"
        for task in EXPECTED_TASK_ORDER
    ]
    for profile in ("franka_poc", "lift2_candidate")
}
EXPECTED_WRAPPER_PRIM_PATHS = {
    "obj_conical_bottle02": "/World/labutopia_level1_poc/obj_obj_conical_bottle02",
    "obj_beaker2": "/World/labutopia_level1_poc/obj_obj_beaker2",
    "obj_target_plat": "/World/labutopia_level1_poc/obj_obj_target_plat",
    "obj_DryingBox_01": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
    "obj_DryingBox_01_handle": "/World/labutopia_level1_poc/obj_obj_DryingBox_01_handle",
    "table": "/World/labutopia_level1_poc/obj_table",
}
PROFILE_EXPECTATIONS = {
    "franka_poc": {
        "robot_type": "manip/franka/panda_hand",
        "camera_config": "configs/cameras/labutopia_franka_poc.yml",
    },
    "lift2_candidate": {
        "robot_type": "manip/lift2/R5a",
        "camera_config": "configs/cameras/fixed_camera_lift2_simbox.yml",
    },
}
ALLOWED_METRICS = {
    "manip/labutopia/object_height_delta": {
        "obj_uid",
        "axis",
        "min_delta",
        "skip_steps",
        "succ_cnts",
    },
    "manip/labutopia/object_at_target": {
        "obj_uid",
        "target_uid",
        "xy_radius",
        "z_tolerance",
        "skip_steps",
        "succ_cnts",
    },
    "manip/labutopia/handle_displacement": {
        "obj_uid",
        "min_distance",
        "skip_steps",
        "succ_cnts",
    },
}


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _task_path(relative_path: str, index_path: Path) -> Path:
    path = TASK_ROOT / relative_path
    _assert(path.exists(), f"{index_path}: indexed task path does not exist: {path}")
    return path


def _load_index(path: Path) -> list[str]:
    data = _load_json(path)
    _assert(isinstance(data, list), f"{path}: expected JSON list index")
    _assert(
        all(isinstance(item, str) for item in data),
        f"{path}: expected every index entry to be a string",
    )
    return data


def _indexed_task_yaml_paths() -> list[Path]:
    top_index = PACKAGE_ROOT / "labutopia_lab_poc.json"
    top_entries = _load_index(top_index)
    _assert(
        top_entries == EXPECTED_TOP_INDEX_ENTRIES,
        f"{top_index}: expected profile indexes {EXPECTED_TOP_INDEX_ENTRIES!r}",
    )
    profile_indexes = [_task_path(item, top_index) for item in top_entries]
    _assert(
        {path.parent.name for path in profile_indexes}
        == {"franka_poc", "lift2_candidate"},
        f"{top_index}: expected franka_poc and lift2_candidate profile indexes",
    )

    task_paths: list[Path] = []
    for index_path in profile_indexes:
        profile = index_path.parent.name
        expected_entries = EXPECTED_PROFILE_INDEX_ENTRIES[profile]
        entries = _load_index(index_path)
        _assert(
            len(entries) == len(set(entries)) == 3,
            f"{index_path}: expected 3 distinct task YAML entries",
        )
        _assert(
            entries == expected_entries,
            f"{index_path}: expected task entries {expected_entries!r}",
        )
        basenames = {Path(item).stem for item in entries}
        _assert(
            basenames == EXPECTED_TASKS,
            f"{index_path}: expected task basenames {EXPECTED_TASKS!r}",
        )
        for item in entries:
            task_path = _task_path(item, index_path)
            _assert(task_path.suffix in {".yml", ".yaml"}, f"{task_path}: expected YAML")
            task_paths.append(task_path)

    _assert(len(task_paths) == 6, f"{top_index}: expected 6 task YAMLs")
    return sorted(task_paths)


def _validate_assets_manifest() -> None:
    path = PACKAGE_ROOT / "common/assets_manifest.json"
    _assert(path.exists(), f"{path}: missing LabUtopia assets manifest")
    manifest = _load_json(path)

    _assert(
        manifest.get("scene_uid") == SCENE_UID,
        f"{path}: scene_uid must be {SCENE_UID!r}",
    )
    _assert(
        manifest.get("runtime_usd_name") == RUNTIME_USD_NAME,
        f"{path}: runtime_usd_name must be {RUNTIME_USD_NAME!r}",
    )
    _assert(
        manifest.get("wrapper_prim_paths") == EXPECTED_WRAPPER_PRIM_PATHS,
        f"{path}: wrapper_prim_paths must preserve GenManip key stripping",
    )

    generated_manifest = manifest.get("generated_manifest")
    _assert(
        isinstance(generated_manifest, str) and generated_manifest,
        f"{path}: generated_manifest must be a non-empty path",
    )
    generated_path = Path(generated_manifest)
    _assert(
        generated_path.exists(),
        f"{path}: generated manifest path does not exist: {generated_path}",
    )
    generated = _load_json(generated_path)
    for common_key, generated_key in {
        "runtime_usd_name": "usd_name",
        "scene_uid": "scene_uid",
        "runtime_object_keys": "runtime_object_keys",
        "wrapper_prim_paths": "wrapper_prim_paths",
        "source_to_runtime_object_key": "source_to_runtime_object_key",
    }.items():
        _assert(
            manifest.get(common_key) == generated.get(generated_key),
            f"{path}: {common_key} differs from {generated_path}:{generated_key}",
        )


def _validate_task_semantics() -> None:
    path = PACKAGE_ROOT / "common/task_semantics.yml"
    data = _load_yaml(path)
    tasks = data.get("tasks") if isinstance(data, dict) else None
    _assert(isinstance(tasks, dict), f"{path}: expected top-level tasks mapping")
    _assert(set(tasks) == EXPECTED_TASKS, f"{path}: unexpected task keys: {set(tasks)}")

    open_door = tasks["level1_open_door"]
    preferred = open_door.get("metrics", {}).get("preferred")
    _assert(isinstance(preferred, dict), f"{path}: missing open_door preferred metric")
    _assert(
        preferred.get("type") == "manip/default/check_joint_angle",
        f"{path}: open_door preferred metric must be manip/default/check_joint_angle",
    )
    settings = preferred.get("sub_goal_setting")
    _assert(
        isinstance(settings, dict),
        f"{path}: open_door preferred metric missing sub_goal_setting",
    )
    for key in ("articulation_obj_uid", "joint_name", "angle_deg_range"):
        _assert(key in settings, f"{path}: open_door preferred metric missing {key}")


def _walk_goal_dicts(value: Any, path: Path) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        results: list[dict[str, Any]] = []
        for item in value:
            results.extend(_walk_goal_dicts(item, path))
        return results
    raise AssertionError(f"{path}: goal contains unsupported value {value!r}")


def _validate_metric(metric: dict[str, Any], path: Path) -> None:
    _assert("sub_goal_setting" not in metric, f"{path}: runtime goal uses sub_goal_setting")
    metric_type = metric.get("type")
    _assert(
        metric_type in ALLOWED_METRICS,
        f"{path}: unsupported LabUtopia metric type {metric_type!r}",
    )
    missing = ALLOWED_METRICS[metric_type] - set(metric)
    _assert(not missing, f"{path}: metric {metric_type} missing top-level params {missing}")


def _validate_runtime_task(path: Path) -> None:
    sys.path.insert(0, str(ROOT))
    from genmanip.core.scene.scene_config import SceneConfig

    data = _load_yaml(path)
    configs = data.get("evaluation_configs") if isinstance(data, dict) else None
    _assert(isinstance(configs, list), f"{path}: expected evaluation_configs list")
    _assert(len(configs) == 1, f"{path}: expected exactly one evaluation_configs item")
    cfg = configs[0]
    _assert(isinstance(cfg, dict), f"{path}: evaluation config must be a mapping")

    SceneConfig(**cfg)
    _assert(cfg.get("num_test") is not None, f"{path}: missing num_test")
    task_name = cfg.get("task_name")
    _assert(
        isinstance(task_name, str) and task_name.startswith(TASK_PREFIX),
        f"{path}: task_name must start with {TASK_PREFIX!r}",
    )
    _assert(cfg.get("table_uid") == "table", f"{path}: table_uid must be 'table'")

    profile = path.parent.name
    expected = PROFILE_EXPECTATIONS.get(profile)
    _assert(expected is not None, f"{path}: unknown LabUtopia task profile {profile!r}")
    robots = cfg.get("robots")
    _assert(isinstance(robots, list) and robots, f"{path}: robots must be non-empty")
    _assert(
        robots[0].get("type") == expected["robot_type"],
        f"{path}: {profile} robot type must be {expected['robot_type']!r}",
    )
    camera = cfg.get("domain_randomization", {}).get("cameras", {})
    _assert(
        camera.get("config_path") == expected["camera_config"],
        f"{path}: {profile} camera config must be {expected['camera_config']!r}",
    )

    goals = cfg.get("generation_config", {}).get("goal")
    _assert(goals is not None, f"{path}: missing generation_config.goal")
    metrics = _walk_goal_dicts(goals, path)
    _assert(metrics, f"{path}: generation_config.goal contains no metric dicts")
    for metric in metrics:
        _validate_metric(metric, path)


def _validate_metrics_manager_lazy_registration() -> None:
    sys.path.insert(0, str(ROOT))
    for module_name in list(sys.modules):
        if module_name == "genmanip.extensions.metrics" or module_name.startswith(
            "genmanip.extensions.metrics."
        ):
            del sys.modules[module_name]

    from genmanip.core.metrics.metrics_manager import MetricsManager

    with contextlib.redirect_stdout(io.StringIO()):
        manager = MetricsManager(
            [
                [
                    [
                        {
                            "type": "manip/labutopia/object_height_delta",
                            "sub_goal_setting": {
                                "obj_uid": "obj_conical_bottle02",
                                "axis": "z",
                                "min_delta": 0.1,
                            },
                        }
                    ]
                ]
            ]
        )
    metric = manager.cur_union_metric[0][0]
    _assert(
        metric.__class__.__name__ == "ObjectHeightDelta",
        "MetricsManager did not lazily register LabUtopia object_height_delta",
    )
    _assert(
        "genmanip.extensions.metrics" not in sys.modules,
        "MetricsManager imported the full genmanip.extensions.metrics package",
    )


def validate_task_package() -> None:
    _validate_assets_manifest()
    _validate_task_semantics()
    for path in _indexed_task_yaml_paths():
        _validate_runtime_task(path)
    _validate_metrics_manager_lazy_registration()


def main() -> None:
    validate_task_package()
    print("LabUtopia task package validation OK")


if __name__ == "__main__":
    main()
