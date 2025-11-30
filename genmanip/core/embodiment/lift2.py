"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from omni.isaac.core.prims import XFormPrim  # type: ignore
from omni.isaac.core.robots.robot import Robot  # type: ignore

from genmanip.core.embodiment.dualarm import DualArmEmbodiment

class Lift2Embodiment(DualArmEmbodiment):
    def __init__(self, robot: Robot) -> None:
        super().__init__(robot)
        self.embodiment_name = "lift2"
        self.gripper_name = "lift2"
        self.arm_name = "R5a"
        self.arm_dof_num = 6
        self.gripper_dof_num = 2
        self.gripper_open = [0.044, 0.044]
        self.gripper_close = [0.0, 0.0]
        self.robot_view.set_max_joint_velocities([2.0] * 26)
        self.robot_base_left = XFormPrim(
            self.robot.prim_path + "/lift2/lift2/fl/base_link"
        )
        self.robot_base_right = XFormPrim(
            self.robot.prim_path + "/lift2/lift2/fr/base_link"
        )
        self.left_arm_dof_indices = [10, 12, 14, 16, 18, 20, 23, 24]
        self.right_arm_dof_indices = [9, 11, 13, 15, 17, 19, 21, 22]
        self.body_dof_indices = [6]
        self.base_dof_indices = [0, 1, 2]
        self.default_arm_dof_indices = [0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13]
        self.default_gripper_dof_indices = [6, 7, 14, 15]
        self.default_lift_joint_position = 0.46
        self.default_lift_joint_path = "/lift2/lift2/base_link/joint4"