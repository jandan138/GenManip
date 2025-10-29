"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from omni.isaac.core.robots.robot import Robot  # type: ignore

from genmanip.core.robot.embodiment.singlearm_embodiment import SingleArmEmbodiment
from genmanip.core.usd_utils import (
    set_drive_damping_and_stiffness,
    set_drive_max_force,
)


class FrankaNormalEmbodiment(SingleArmEmbodiment):
    def __init__(self, robot: Robot) -> None:
        super().__init__(robot)
        self.embodiment_name = "franka"
        self.gripper_name = "panda_hand"
        self.arm_dof_num = 7
        self.gripper_dof_num = 2
        self.gripper_open = [0.04, 0.04]
        self.gripper_close = [0.0, 0.0]
        self.robot_view.set_max_joint_velocities([2.0] * 9)
        self.default_arm_dof_indices = [0, 1, 2, 3, 4, 5, 6]
        self.default_gripper_dof_indices = [7, 8]


class FrankaRobotiqEmbodiment(SingleArmEmbodiment):
    def __init__(self, robot: Robot) -> None:
        super().__init__(robot)
        self.embodiment_name = "franka"
        self.gripper_name = "robotiq"
        self.arm_dof_num = 7
        self.gripper_dof_num = 6
        self.gripper_open = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.gripper_close = [0.7853, 0.7853, -0.7853, -0.7853, -0.7853, -0.7853]
        self.robot_view.set_max_joint_velocities([2.0] * 13)
        self.default_arm_dof_indices = [0, 1, 2, 3, 4, 5, 6]
        self.default_gripper_dof_indices = [7, 8, 9, 10, 11, 12]

    def _initialize(self, default_joint_positions=None):
        super()._initialize(default_joint_positions)
        joint_list = [
            "base_link/finger_joint",
            "base_link/right_outer_knuckle_joint",
            "base_link/left_inner_knuckle_joint",
            "base_link/right_inner_knuckle_joint",
            "right_outer_finger/right_inner_finger_joint",
            "left_outer_finger/left_inner_finger_joint",
        ]
        for joint in joint_list:
            set_drive_damping_and_stiffness(
                self.robot.prim_path + f"/Robotiq_2F_85/{joint}",
                damping=0.01,
                stiffness=0.1,
            )
            set_drive_max_force(
                self.robot.prim_path + f"/Robotiq_2F_85/{joint}",
                10000.0,
            )
        joint_list = [
            # "base_link/right_outer_knuckle_joint",
            "base_link/left_inner_knuckle_joint",
            "base_link/right_inner_knuckle_joint",
            "right_outer_finger/right_inner_finger_joint",
            "left_outer_finger/left_inner_finger_joint",
        ]
        for joint in joint_list:
            set_drive_max_force(
                self.robot.prim_path + f"/Robotiq_2F_85/{joint}",
                0.0,
            )
