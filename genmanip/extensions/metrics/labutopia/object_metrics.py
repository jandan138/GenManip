from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field, field_validator

from genmanip.core.metrics.base import BaseMetric
from genmanip.core.metrics.utils import MetricFactory


AxisName = Literal["x", "y", "z"]


def _position(scene, obj_uid: str) -> np.ndarray:
    if obj_uid not in scene.object_list:
        raise KeyError(f"Object '{obj_uid}' not found in scene.object_list")
    pose = scene.object_list[obj_uid].get_world_pose()
    return np.asarray(pose[0], dtype=float)


class ObjectHeightDeltaConfig(BaseModel):
    obj_uid: str = Field(..., description="UID of the object to track")
    axis: AxisName = Field(default="z", description="Axis to measure")
    min_delta: float = Field(..., description="Minimum positive displacement")

    @field_validator("min_delta")
    @classmethod
    def validate_min_delta(cls, value):
        if value <= 0:
            raise ValueError("min_delta must be positive")
        return value


class ObjectAtTargetConfig(BaseModel):
    obj_uid: str = Field(..., description="UID of the object to track")
    target_uid: str = Field(..., description="UID of the target object")
    xy_radius: float = Field(..., description="Maximum radial XY distance")
    z_tolerance: float = Field(..., description="Maximum distance from initial z")

    @field_validator("xy_radius", "z_tolerance")
    @classmethod
    def validate_positive_threshold(cls, value):
        if value <= 0:
            raise ValueError("thresholds must be positive")
        return value


class HandleDisplacementConfig(BaseModel):
    obj_uid: str = Field(..., description="UID of the handle object to track")
    min_distance: float = Field(..., description="Minimum positive displacement")

    @field_validator("min_distance")
    @classmethod
    def validate_min_distance(cls, value):
        if value <= 0:
            raise ValueError("min_distance must be positive")
        return value


@MetricFactory.register("manip/labutopia/object_height_delta")
class ObjectHeightDelta(BaseMetric):
    def __init__(
        self,
        skip_steps: int = 1,
        succ_cnts: int = 0,
        sub_goal_setting: dict[str, Any] = {},
        **kwargs,
    ):
        super().__init__(skip_steps, succ_cnts, sub_goal_setting, **kwargs)
        self.setting = ObjectHeightDeltaConfig(**sub_goal_setting)
        self._initial_position = None

    def check_status(self, scene) -> bool:
        current = _position(scene, self.setting.obj_uid)
        if self._initial_position is None:
            self._initial_position = current.copy()

        axis_idx = {"x": 0, "y": 1, "z": 2}[self.setting.axis]
        delta = current[axis_idx] - self._initial_position[axis_idx]
        return bool(delta > self.setting.min_delta)

    def get_info(self):
        return {
            "setting": self.setting.model_dump(),
            "initial_position": (
                None
                if self._initial_position is None
                else self._initial_position.tolist()
            ),
        }


@MetricFactory.register("manip/labutopia/object_at_target")
class ObjectAtTarget(BaseMetric):
    def __init__(
        self,
        skip_steps: int = 1,
        succ_cnts: int = 0,
        sub_goal_setting: dict[str, Any] = {},
        **kwargs,
    ):
        super().__init__(skip_steps, succ_cnts, sub_goal_setting, **kwargs)
        self.setting = ObjectAtTargetConfig(**sub_goal_setting)
        self._initial_z = None

    def check_status(self, scene) -> bool:
        current = _position(scene, self.setting.obj_uid)
        target = _position(scene, self.setting.target_uid)
        if self._initial_z is None:
            self._initial_z = float(current[2])

        xy_dist = np.linalg.norm(current[:2] - target[:2])
        z_dist = abs(current[2] - self._initial_z)
        return bool(
            xy_dist < self.setting.xy_radius
            and z_dist < self.setting.z_tolerance
        )

    def get_info(self):
        return {
            "setting": self.setting.model_dump(),
            "initial_z": self._initial_z,
        }


@MetricFactory.register("manip/labutopia/handle_displacement")
class HandleDisplacement(BaseMetric):
    def __init__(
        self,
        skip_steps: int = 1,
        succ_cnts: int = 0,
        sub_goal_setting: dict[str, Any] = {},
        **kwargs,
    ):
        super().__init__(skip_steps, succ_cnts, sub_goal_setting, **kwargs)
        self.setting = HandleDisplacementConfig(**sub_goal_setting)
        self._initial_position = None

    def check_status(self, scene) -> bool:
        current = _position(scene, self.setting.obj_uid)
        if self._initial_position is None:
            self._initial_position = current.copy()

        return bool(
            np.linalg.norm(current - self._initial_position)
            > self.setting.min_distance
        )

    def get_info(self):
        return {
            "setting": self.setting.model_dump(),
            "initial_position": (
                None
                if self._initial_position is None
                else self._initial_position.tolist()
            ),
        }
