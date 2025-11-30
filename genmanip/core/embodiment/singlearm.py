"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import numpy as np

from omni.isaac.core.robots.robot import Robot  # type: ignore
from omni.isaac.core import World  # type: ignore

from genmanip.core.embodiment.base import BaseEmbodiment
from genmanip.utils.planner.curobo.utils import get_curobo_planner


class SingleArmEmbodiment(BaseEmbodiment):
    def __init__(self, robot: Robot) -> None:
        super().__init__(robot)
        self.embodiment_name = "abstract_single_arm"
        self.gripper_name = "default"
        self.arm_dof_num = 7
        self.gripper_dof_num = 2
        self.gripper_open = [0.04, 0.04]
        self.gripper_close = [0.0, 0.0]
        self.robot_view.set_max_joint_velocities([2.0] * 9)
        self.default_arm_dof_indices = [i for i in range(self.arm_dof_num)]
        self.default_gripper_dof_indices = [
            i for i in range(self.arm_dof_num, self.arm_dof_num + self.gripper_dof_num)
        ]

    def _plan_pose(  # type: ignore[override]
        self,
        goal_pose: tuple[np.ndarray, np.ndarray],
        joint_position: list[float],
        dof_name: list[str],
        grasp: bool = False,
        arm: str = "default",
    ) -> list[np.ndarray] | None:
        if self.planner is None:
            return None
        return self.planner.plan(
            goal_pose[0], goal_pose[1], joint_position, grasp=grasp
        )

    def set_planner(self, world: World, current_dir: str) -> None:
        self.planner = get_curobo_planner(
            self.robot, self.embodiment_name, world, current_dir
        )
