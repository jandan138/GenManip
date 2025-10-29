"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from omni.isaac.core.prims import XFormPrim  # type: ignore
from omni.isaac.core.robots.robot import Robot  # type: ignore

from genmanip.core.robot.embodiment.dualarm_embodiment import DualArmEmbodiment


class AlohaSplitEmbodiment(DualArmEmbodiment):
    def __init__(self, robot: Robot) -> None:
        super().__init__(robot)
        self.embodiment_name = "aloha_split"
        self.gripper_name = "piper"
        self.arm_name = "piper"
        self.arm_dof_num = 6
        self.gripper_dof_num = 2
        self.gripper_open = [0.05, -0.05]
        self.gripper_close = [0.0, 0.0]
        self.robot_view.set_max_joint_velocities([2.0] * 28)
        self.robot_base_left = XFormPrim(
            self.robot.prim_path
            + "/split_aloha_mid_360_with_piper/split_aloha_mid_360_with_piper/fl/arm_base"
        )
        self.robot_base_right = XFormPrim(
            self.robot.prim_path
            + "/split_aloha_mid_360_with_piper/split_aloha_mid_360_with_piper/fr/arm_base"
        )
        self.left_arm_dof_indices = [
            12,
            14,
            16,
            18,
            20,
            22,
            24,
            25,
        ]
        self.right_arm_dof_indices = [
            13,
            15,
            17,
            19,
            21,
            23,
            26,
            27,
        ]
        self.body_dof_indices = [7]
        self.base_dof_indices = [0, 1, 2]
        self.default_arm_dof_indices = [0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13]
        self.default_gripper_dof_indices = [6, 7, 14, 15]
        self.default_lift_joint_position = -0.3
        self.default_lift_joint_path = "/split_aloha_mid_360_with_piper/split_aloha_mid_360_with_piper/box_link/lifting_joint"
