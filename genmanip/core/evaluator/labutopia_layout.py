from __future__ import annotations

import copy
import pickle
from pathlib import Path
from typing import Any


LABUTOPIA_POC_TASK_PREFIX = "ebench/labutopia_lab_poc/"


def is_labutopia_poc_task_name(task_name: str) -> bool:
    return isinstance(task_name, str) and task_name.startswith(LABUTOPIA_POC_TASK_PREFIX)


def _object_world_pose(obj: Any) -> tuple[Any, Any]:
    position, orientation = obj.get_world_pose()
    return position, orientation


def _build_initial_layout(scene: Any) -> dict[str, dict[str, Any]]:
    layout: dict[str, dict[str, Any]] = {}
    cache_library = getattr(scene, "cache_library", None)
    usd_path_list = getattr(cache_library, "preloaded_object_path_list", {}) or {}
    preload_object_meta_info = (
        getattr(cache_library, "preload_object_meta_info", {}) or {}
    )

    for key, obj in scene.object_list.items():
        prim = getattr(obj, "prim", None)
        if prim is not None and hasattr(prim, "IsActive") and not prim.IsActive():
            continue
        position, orientation = _object_world_pose(obj)
        object_meta = preload_object_meta_info.get(key, {})
        layout[key] = {
            "type": "object",
            "position": position,
            "orientation": orientation,
            "scale": obj.get_local_scale(),
            "path": usd_path_list.get(key, ""),
            "add_colliders": object_meta.get("add_colliders", True),
            "add_rigid_body": object_meta.get("add_rigid_body", True),
            "prim_path": obj.prim_path,
            "is_articulation_part": key in scene.articulation_part_list,
        }

    for key, articulation in scene.articulation_list.items():
        position, orientation = articulation.get_world_pose()
        layout[key] = {
            "type": "articulation",
            "position": position,
            "orientation": orientation,
            "scale": articulation.get_local_scale(),
            "joint_positions": articulation.get_joint_positions(),
            "prim_path": articulation.prim_path,
        }

    for embodiment in scene.robot_list:
        robot = embodiment.robot
        position, orientation = robot.get_world_pose()
        layout[robot.name] = {
            "type": "robot",
            "position": position,
            "orientation": orientation,
            "joint_positions": robot.get_joint_positions(),
        }

    return layout


def build_labutopia_poc_meta_info(
    scene: Any, scene_config: Any, seed: str
) -> dict[str, Any]:
    """Build minimal eval metadata for LabUtopia POC tasks from the live scene."""
    task_data = {
        "initial_scene_graph": None,
        "initial_layout": _build_initial_layout(scene),
        "goal": copy.deepcopy(scene_config.generation_config.goal),
        "instruction": scene_config.instruction,
        "frame_status": {},
    }
    return {
        "max_size": 0,
        "num_steps": 0,
        "language_instruction": scene_config.instruction,
        "task_data": task_data,
        "keys": {},
        "task_name": scene_config.task_name,
        "episode_name": seed,
    }


def load_or_build_labutopia_poc_meta_info(
    meta_info_path: str | Path,
    task_name: str,
    seed: str,
    scene: Any,
    scene_config: Any,
) -> dict[str, Any]:
    path = Path(meta_info_path)
    if path.exists():
        with path.open("rb") as handle:
            return pickle.load(handle)
    if not is_labutopia_poc_task_name(task_name):
        raise FileNotFoundError(f"meta_info.pkl does not exist: {path}")
    return build_labutopia_poc_meta_info(scene, scene_config, seed)
