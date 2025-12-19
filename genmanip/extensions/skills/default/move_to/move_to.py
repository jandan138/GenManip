"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import os
from typing import TYPE_CHECKING

import numpy as np
from pydantic import Field

from genmanip.core.skill.base import BaseSkill, SkillConfig
from genmanip.core.skill.utils import SkillFactory
from genmanip.demogen.recoder.planning_recorder import PlanningRecorder

if TYPE_CHECKING:
    from genmanip.core.scene.scene import Scene


class MoveToConfig(SkillConfig):
    name: str = "pick_and_place"
    type: str = Field(..., description="Type of the move to skill")
    rel_object_uid: str = Field(
        default="00000000000000000000000000000000",
        description="UID of the relative object",
    )
    rel_position: dict = Field(
        default={"x": 0.0, "y": 0.0, "yaw": 0.0},
        description="Position of the relative object",
    )
    delta_position: dict = Field(
        default={"x": 0.0, "y": 0.0, "yaw": 0.0},
        description="Delta position of the relative object",
    )


@SkillFactory.register("move_to")
class MoveToSkill(BaseSkill):
    def __init__(self, config_dict: dict, demogen_config: dict):
        self.config = MoveToConfig(**config_dict)
        self.demogen_config = demogen_config

    def execute(
        self, scene: "Scene", recorder: PlanningRecorder, idx: str
    ) -> tuple[bool, str]:
        if self.config.type == "delta":
            self._handle_dual_arm_base_move(
                scene,
                recorder,
                scene.robot_list[0],
                idx_name=str(idx),
                delta_move_config=self.config.delta_position,
            )
        return True, "default"

    def _handle_dual_arm_base_move(
        self,
        scene,
        recorder,
        embodiment,
        idx_name,
        delta_move_config: dict = {"x": 0.0, "y": 0.0, "yaw": 0.0},
    ):
        max_xy = max(abs(delta_move_config["x"]), abs(delta_move_config["y"]))
        x_step = delta_move_config["x"] / max_xy * 0.01
        y_step = delta_move_config["y"] / max_xy * 0.01
        x_remaining = delta_move_config["x"]
        y_remaining = delta_move_config["y"]
        while x_remaining != 0.0 or y_remaining != 0.0:
            if abs(x_step) > abs(x_remaining):
                x_step = x_remaining
            if abs(y_step) > abs(y_remaining):
                y_step = y_remaining
            x_remaining -= x_step
            y_remaining -= y_step
            embodiment.delta_move_to(x_step, y_step, 0.0)
            recorder.load_dynamic_info(
                None,
                None,
                arm=None,
                base_motion=np.array([x_step, y_step, 0.0]),
                name=f"{idx_name}/move",
            )
            scene.world.step(render=False)
            if os.environ.get("GENMANIP_DEBUG", "0") == "1":
                scene.world.render()
