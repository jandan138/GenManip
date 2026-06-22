import pytest

from genmanip.core.evaluator.labutopia_layout import (
    build_labutopia_poc_meta_info,
    load_or_build_labutopia_poc_meta_info,
)


class _Prim:
    def __init__(self, active=True):
        self._active = active

    def IsActive(self):
        return self._active


class _Object:
    def __init__(self, prim_path, position, orientation, scale, active=True):
        self.prim_path = prim_path
        self.prim = _Prim(active)
        self._position = position
        self._orientation = orientation
        self._scale = scale

    def get_world_pose(self):
        return self._position, self._orientation

    def get_local_scale(self):
        return self._scale


class _RobotHandle:
    def __init__(self):
        self.name = "franka"

    def get_world_pose(self):
        return [0.0, 0.0, 0.71], [1.0, 0.0, 0.0, 0.0]

    def get_joint_positions(self):
        return [0.1, 0.2, 0.3]


class _Robot:
    def __init__(self):
        self.robot = _RobotHandle()


class _GenerationConfig:
    goal = [[{"type": "manip/labutopia/object_height_delta", "obj_uid": "obj"}]]


class _SceneConfig:
    task_name = "ebench/labutopia_lab_poc/franka_poc/level1_pick"
    instruction = "Pick up the object."
    generation_config = _GenerationConfig()


class _CacheLibrary:
    preloaded_object_path_list = {"obj": "objects/obj.usd"}
    preload_object_meta_info = {
        "obj": {"add_colliders": False, "add_rigid_body": True}
    }


class _Scene:
    object_list = {
        "obj": _Object(
            "/World/labutopia_level1_poc/obj_obj",
            [1.0, 2.0, 3.0],
            [1.0, 0.0, 0.0, 0.0],
            [1.0, 1.0, 1.0],
        ),
        "inactive": _Object(
            "/World/labutopia_level1_poc/obj_inactive",
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0, 0.0],
            [1.0, 1.0, 1.0],
            active=False,
        ),
    }
    articulation_list = {}
    articulation_part_list = {"obj": object()}
    robot_list = [_Robot()]
    cache_library = _CacheLibrary()


def test_build_labutopia_poc_meta_info_from_current_scene():
    meta_info = build_labutopia_poc_meta_info(_Scene(), _SceneConfig(), "000")

    task_data = meta_info["task_data"]
    assert meta_info["task_name"] == _SceneConfig.task_name
    assert meta_info["episode_name"] == "000"
    assert task_data["instruction"] == "Pick up the object."
    assert task_data["goal"] == _GenerationConfig.goal
    assert set(task_data["initial_layout"]) == {"obj", "franka"}
    assert task_data["initial_layout"]["obj"]["is_articulation_part"] is True
    assert task_data["initial_layout"]["obj"]["path"] == "objects/obj.usd"
    assert task_data["initial_layout"]["obj"]["add_colliders"] is False
    assert task_data["initial_layout"]["franka"]["joint_positions"] == [0.1, 0.2, 0.3]


def test_load_or_build_rejects_missing_non_labutopia_meta_info(tmp_path):
    with pytest.raises(FileNotFoundError, match="meta_info.pkl"):
        load_or_build_labutopia_poc_meta_info(
            tmp_path / "meta_info.pkl",
            "ebench/official_task/level1_pick",
            "000",
            _Scene(),
            _SceneConfig(),
        )
