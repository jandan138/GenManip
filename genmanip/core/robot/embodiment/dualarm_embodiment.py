"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import numpy as np

from curobo.types.state import JointState
from omni.isaac.core import World  # type: ignore
from omni.isaac.core.prims import XFormPrim  # type: ignore
from omni.isaac.core.robots.robot import Robot  # type: ignore

from genmanip.core.robot.embodiment.base_embodiment import BaseEmbodiment
from genmanip.core.usd_utils import (
    set_drive_damping_and_stiffness,
    set_drive_max_force,
)
from genmanip.thirdparty.curobo_planner import get_curobo_planner


class DualArmEmbodiment(BaseEmbodiment):
    def __init__(self, robot: Robot) -> None:
        super().__init__(robot)
        self.embodiment_name = "abstract_dual_arm"
        self.gripper_name = "default"
        self.arm_name = "default"
        self.arm_dof_num = 6
        self.gripper_dof_num = 2
        self.gripper_open = [0.05, 0.05]
        self.gripper_close = [0.0, 0.0]
        self.robot_view.set_max_joint_velocities([2.0] * 28)
        self.robot_base_left = XFormPrim(self.robot.prim_path + "/fl/arm_base")
        self.robot_base_right = XFormPrim(self.robot.prim_path + "/fr/arm_base")
        self.left_arm_dof_indices = [
            i for i in range(self.arm_dof_num + self.gripper_dof_num)
        ]
        self.right_arm_dof_indices = [
            i
            for i in range(
                self.arm_dof_num + self.gripper_dof_num,
                2 * self.arm_dof_num + self.gripper_dof_num,
            )
        ]
        self.body_dof_indices = [3]
        self.base_dof_indices = [0, 1, 2]
        self.default_arm_dof_indices = [i for i in range(self.arm_dof_num * 2)]
        self.default_gripper_dof_indices = [
            i
            for i in range(
                self.arm_dof_num * 2, self.arm_dof_num * 2 + self.gripper_dof_num * 2
            )
        ]
        self.default_lift_joint_position = -0.3
        self.default_lift_joint_path = "/box_link/lifting_joint"

    def _initialize(self, default_joint_positions: list[float] | None = None) -> None:
        super()._initialize(default_joint_positions)
        single_arm_joint_position = [0.0] * 6 + self.gripper_open
        self.robot.set_joint_positions(
            [self.default_lift_joint_position] + single_arm_joint_position * 2,
            joint_indices=self.body_dof_indices
            + self.left_arm_dof_indices
            + self.right_arm_dof_indices,
        )
        self.robot_view.set_joint_positions(
            [self.default_lift_joint_position] + single_arm_joint_position * 2,
            joint_indices=self.body_dof_indices
            + self.left_arm_dof_indices
            + self.right_arm_dof_indices,
        )
        self.default_dof_indices = (
            self.left_arm_dof_indices + self.right_arm_dof_indices
        )
        set_drive_damping_and_stiffness(
            self.robot.prim_path + self.default_lift_joint_path,
            damping=10000,
            stiffness=1000000,
        )
        set_drive_max_force(
            self.robot.prim_path + self.default_lift_joint_path,
            1000000,
        )

    def set_planner(self, world: World, current_dir: str) -> None:
        self.left_planner = get_curobo_planner(
            self.robot, f"{self.arm_name}_left", world, current_dir
        )
        self.right_planner = get_curobo_planner(
            self.robot, f"{self.arm_name}_right", world, current_dir
        )

    def _fk_single(  # type: ignore[override]
        self, joint_positions: np.ndarray
    ) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]]:
        if self.left_planner is None or self.right_planner is None:
            raise ValueError("Planner is not initialized")
        return (
            self.left_planner.fk_single(joint_positions[: self.arm_dof_num]),
            self.right_planner.fk_single(
                joint_positions[
                    self.arm_dof_num + self.gripper_dof_num : -self.gripper_dof_num
                ]
            ),
        )

    def _plan_pose(  # type: ignore[override]
        self,
        goal_pose: tuple[np.ndarray, np.ndarray],
        joint_position: JointState,
        dof_name: list[str],
        grasp: bool = False,
        arm: str = "default",
    ) -> list[np.ndarray] | None:
        if arm == "left":
            goal_pose = (
                goal_pose[0]
                - self.robot_base_left.get_world_pose()[0]
                + self.robot.get_world_pose()[0],
                goal_pose[1],
            )
            return self.left_planner.plan(
                goal_pose[0],
                goal_pose[1],
                joint_position,
                self.robot.dof_names,
                grasp=grasp,
            )
        elif arm == "right":
            goal_pose = (
                goal_pose[0]
                - self.robot_base_right.get_world_pose()[0]
                + self.robot.get_world_pose()[0],
                goal_pose[1],
            )
            return self.right_planner.plan(
                goal_pose[0],
                goal_pose[1],
                joint_position,
                self.robot.dof_names,
                grasp=grasp,
            )
        else:
            raise ValueError(f"Invalid arm: {arm}")

    def convert_curobo_result_to_action(
        self, result: list[float], grasp: bool, arm: str = "default"
    ) -> np.ndarray:
        joint_positions = self.robot.get_joint_positions()
        if arm == "left":
            if (
                len(result) == self.arm_dof_num
                or len(result) == self.arm_dof_num + self.gripper_dof_num
            ):
                return np.concatenate(
                    [
                        result[: self.arm_dof_num],
                        self.gripper_open if not grasp else self.gripper_close,
                        joint_positions[self.right_arm_dof_indices],
                    ]
                )
            elif len(result) == len(self.default_dof_indices):
                return np.concatenate(
                    [
                        result[: self.arm_dof_num],
                        self.gripper_open if not grasp else self.gripper_close,
                        result[self.arm_dof_num + self.gripper_dof_num :],
                    ]
                )
            else:
                raise ValueError(f"Invalid result length: {len(result)}")
        elif arm == "right":
            if (
                len(result) == self.arm_dof_num
                or len(result) == self.arm_dof_num + self.gripper_dof_num
            ):
                return np.concatenate(
                    [
                        joint_positions[self.left_arm_dof_indices],
                        result[: self.arm_dof_num],
                        self.gripper_open if not grasp else self.gripper_close,
                    ]
                )
            elif len(result) == len(self.default_dof_indices):
                return np.concatenate(
                    [
                        result[: self.arm_dof_num + self.gripper_dof_num],
                        result[
                            self.arm_dof_num
                            + self.gripper_dof_num : self.arm_dof_num
                            + self.gripper_dof_num
                            + self.arm_dof_num
                        ],
                        self.gripper_open if not grasp else self.gripper_close,
                    ]
                )
            else:
                raise ValueError(f"Invalid result length: {len(result)}")
        else:
            raise ValueError(f"Invalid arm: {arm}")

    def reference_arm_type(self, target: np.ndarray) -> str:
        target2left = np.linalg.norm(target - self.robot_base_left.get_world_pose()[0])
        target2right = np.linalg.norm(
            target - self.robot_base_right.get_world_pose()[0]
        )
        if target2left < target2right:
            return "left"
        else:
            return "right"
