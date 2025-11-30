"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from abc import abstractmethod

from mplib.planner import Planner as MplibPlanner
import numpy as np
from scipy.spatial.transform import Rotation as R

from omni.isaac.core import World  # type: ignore
from omni.isaac.core.robots.robot import Robot  # type: ignore

from genmanip.core.embodiment.utils import get_all_joints, get_all_body_from_joint
from genmanip.utils.planner.curobo.utils import CuroboPlanner


class BaseEmbodiment:
    def __init__(self, robot: Robot) -> None:
        self.embodiment_name = "franka"
        self.gripper_name = "default"
        self.arm_dof_num = 7
        self.gripper_dof_num = 2
        self.gripper_open = [0.04, 0.04]
        self.gripper_close = [0.0, 0.0]
        self.robot = robot
        self.robot_view = robot._articulation_view
        self.planner: CuroboPlanner | None = None
        self.default_arm_dof_indices = [0, 1, 2, 3, 4, 5, 6]
        self.default_gripper_dof_indices = [7, 8]

    def _initialize(self, default_joint_positions: list[float] | None = None) -> None:
        self.robot.initialize()
        if default_joint_positions is not None:
            self.robot.set_joint_positions(default_joint_positions)
        else:
            if self.robot.get_joints_default_state() is not None:
                self.robot.set_joint_positions(
                    self.robot.get_joints_default_state().positions
                )
        self.default_dof_indices = [i for i in range(len(self.robot.dof_names))]
        self.joint_dict = {}
        get_all_joints(self.robot.prim, self.joint_dict)
        self.link_dict = {}
        get_all_body_from_joint(self.joint_dict, self.link_dict)

    def _post_initialize(self) -> None:
        self.robot.set_joints_default_state(
            positions=self.robot.get_joints_state().positions,
            velocities=self.robot.get_joints_state().velocities,
        )

    def initialize(self, default_joint_positions: list[float] | None = None) -> None:
        self._initialize(default_joint_positions)
        self._post_initialize()

    def set_joint_positions(
        self, joint_positions: list[float], joint_indices: list[int] | None = None
    ) -> None:
        if joint_indices is None:
            joint_indices = self.default_dof_indices
        self.robot.set_joint_positions(joint_positions, joint_indices=joint_indices)

    def get_joint_positions(
        self, joint_indices: list[int] | None = None
    ) -> list[float]:
        if joint_indices is None:
            joint_indices = self.default_dof_indices
        return self.robot.get_joint_positions(joint_indices=joint_indices)

    @abstractmethod
    def set_planner(self, world: World, current_dir: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def _plan_pose(
        self,
        goal_pose: tuple[np.ndarray, np.ndarray],
        joint_position: list[float],
        dof_name: list[str],
        grasp: bool = False,
        arm: str = "default",
    ) -> list[float] | None:
        raise NotImplementedError

    def _transform_goal_pose(
        self, goal_pose: tuple[np.ndarray, np.ndarray]
    ) -> tuple[np.ndarray, np.ndarray]:
        robot_p, robot_q = self.robot.get_world_pose()
        goal_matrix = np.eye(4)
        goal_matrix[:3, :3] = R.from_quat(goal_pose[1][[1, 2, 3, 0]]).as_matrix()
        goal_matrix[:3, 3] = goal_pose[0]
        robot_matrix = np.eye(4)
        robot_matrix[:3, :3] = R.from_quat(robot_q[[1, 2, 3, 0]]).as_matrix()
        robot_matrix[:3, 3] = robot_p
        goal_pose_matrix = np.linalg.inv(robot_matrix) @ goal_matrix
        return (
            goal_pose_matrix[:3, 3],
            R.from_matrix(goal_pose_matrix[:3, :3]).as_quat()[[3, 0, 1, 2]],
        )

    def plan_pose(
        self,
        goal_pose: tuple[np.ndarray, np.ndarray],
        joint_position: list[float],
        grasp: bool = False,
        arm: str = "default",
    ) -> list[float] | None:
        assert not isinstance(
            self.planner, MplibPlanner
        ), "mplib planner is not supported anymore"
        dof_name = self.robot.dof_names
        goal_pose = self._transform_goal_pose(goal_pose)
        return self._plan_pose(
            goal_pose, joint_position, dof_name, grasp=grasp, arm=arm
        )

    def convert_curobo_result_to_action(
        self, result: list[float], grasp: bool, arm: str = "default"
    ) -> np.ndarray:
        return np.concatenate(
            [
                result[: self.arm_dof_num],
                self.gripper_open if not grasp else self.gripper_close,
            ]
        )

    def convert_action_to_joint_state(
        self, action: list[float], arm: str = "default"
    ) -> list[float]:
        joint_positions = self.robot.get_joint_positions()
        joint_positions[self.default_dof_indices] = action
        return joint_positions

    def _fk_single(self, joint_positions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.planner is None:
            raise ValueError("Planner is not initialized")
        return self.planner.fk_single(joint_positions[: self.arm_dof_num])

    def fk_single(self, joint_positions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if len(joint_positions) == len(self.robot.get_joint_positions()):
            return self._fk_single(joint_positions[self.default_dof_indices])
        elif (
            len(joint_positions) == self.arm_dof_num
            or len(joint_positions) == self.arm_dof_num + self.gripper_dof_num
            or len(joint_positions) == len(self.default_dof_indices)
        ):
            return self._fk_single(joint_positions)
        else:
            raise ValueError(f"Invalid joint positions length: {len(joint_positions)}")

    def _ik_single(
        self, pose: np.ndarray, cur_joint_positions: np.ndarray
    ) -> np.ndarray | None:
        if self.planner is None:
            raise ValueError("Planner is not initialized")
        return self.planner.ik_single(pose, cur_joint_positions)

    def ik_single(
        self,
        pose: np.ndarray,
        cur_joint_positions: np.ndarray,
        in_world_frame: bool = False,
    ) -> np.ndarray | None:
        if in_world_frame:
            p = pose[:3]
            q = pose[3:]
            transformed_pose = self._transform_goal_pose((p, q))
            pose = np.concatenate([transformed_pose[0], transformed_pose[1]])
        return self._ik_single(pose, cur_joint_positions)

    def reference_arm_type(self, target: np.ndarray) -> str:
        return "default"


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
