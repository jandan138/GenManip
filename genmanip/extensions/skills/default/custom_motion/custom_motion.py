"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import os
from typing import TYPE_CHECKING

from curobo.util.trajectory import get_smooth_trajectory
import numpy as np
from pydantic import Field, BaseModel
import torch
from tqdm import tqdm

from omni.isaac.core.utils.types import JointsState  # type: ignore

from genmanip.core.robot.base import BaseEmbodiment
from genmanip.core.robot.dualarm_manip import DualArmEmbodiment
from genmanip.core.skill.base import BaseSkill, SkillConfig
from genmanip.core.skill.utils import SkillFactory
from genmanip.demogen.recoder.planning_recorder import PlanningRecorder
from genmanip.utils.standalone.transform_utils import (
    pose_frame_to_world,
    pose_world_to_frame,
)

if TYPE_CHECKING:
    from genmanip.core.scene.scene import Scene


class SingleArmMotion(BaseModel):
    name: str = Field(..., description="Name of the skill")
    translation: list[float] = Field([0.0, 0.0, 0.0], description="Translation")
    orientation: list[float] = Field(
        [0.707, 0.0, 0.707, 0.0], description="Orientation"
    )
    grasp: bool = Field(..., description="Grasp")
    type: str = Field(..., description="Type")
    rel_object_uid: str | None = Field(None, description="Relative object UID")
    rel_arm: str | None = Field(None, description="Relative arm")
    cnt: int = Field(1, description="Count")


class CustomMotionConfig(SkillConfig):
    name: str = "custom_motion"
    motion_list: dict[str, list[SingleArmMotion]] = Field(
        ..., description="Motion list"
    )


@SkillFactory.register("custom_motion")
class CustomMotionSkill(BaseSkill):
    def __init__(self, config_dict: dict, demogen_config: dict):
        self.config = CustomMotionConfig(**config_dict)
        self.demogen_config = demogen_config

    def _plan(self, embodiment: BaseEmbodiment, arm: str) -> list[dict]:
        action_list = []
        sim_js = embodiment.robot.get_joints_state()
        for motion in self.config.motion_list[arm]:
            if motion.type == "pending":
                action_list.extend(
                    self._create_pending_data(
                        embodiment, motion, sim_js, motion.grasp, arm, cnt=motion.cnt
                    )
                )
            else:
                action_list.extend(self._plan_pose(embodiment, motion, sim_js, arm))
        return action_list

    def _plan_pose(
        self,
        embodiment: BaseEmbodiment,
        target: SingleArmMotion,
        sim_js: JointsState,
        arm: str,
    ) -> list[dict]:
        action_list = []
        trajectory_points = self._plan_step(
            embodiment,
            target,
            arm,
            sim_js,
            smooth=False,
        )
        for point in trajectory_points:
            action_data = self._create_action_data(
                embodiment,
                point,
                target,
                target.grasp,
                arm,
            )
            action_list.append(action_data)
            sim_js.positions = embodiment.convert_action_to_joint_state(
                action_data["action"], arm
            )
        return action_list

    def _merge_dual_arm_action_list(
        self,
        embodiment: BaseEmbodiment,
        action_list_left: list[dict],
        action_list_right: list[dict],
    ) -> list[dict]:
        if len(action_list_left) > len(action_list_right):
            for _ in range(len(action_list_left) - len(action_list_right)):
                action_list_right.append(action_list_right[-1])
        elif len(action_list_left) < len(action_list_right):
            for _ in range(len(action_list_right) - len(action_list_left)):
                action_list_left.append(action_list_left[-1])
        action_list = []
        for left_action, right_action in zip(action_list_left, action_list_right):
            action_list.append(
                {
                    "action": left_action["action"][
                        : (embodiment.arm_dof_num + embodiment.gripper_dof_num)
                    ]
                    + right_action["action"][
                        (embodiment.arm_dof_num + embodiment.gripper_dof_num) :
                    ],
                    "name": "default",
                    "grasp": [left_action["grasp"], right_action["grasp"]],
                },
            )
        return action_list

    def _process_motion_target(self, scene: "Scene"):
        embodiment = scene.robot_list[0]
        if not isinstance(embodiment, DualArmEmbodiment):
            raise ValueError(
                f"Embodiment {embodiment.embodiment_name} is not a dual arm robot"
            )
        for arm in self.config.motion_list.keys():
            for info in self.config.motion_list[arm]:
                if info.type == "world_frame":
                    info.translation = info.translation
                    info.orientation = info.orientation
                elif info.type == "object_frame":
                    if info.rel_object_uid is not None:
                        rel_object = scene.object_list[info.rel_object_uid]
                        frame_in_world = rel_object.get_world_pose()
                        translation, orientation = pose_frame_to_world(
                            (np.array(info.translation), np.array(info.orientation)),
                            frame_in_world,
                        )
                        info.translation = translation.tolist()
                        info.orientation = orientation.tolist()
                    else:
                        raise ValueError(
                            f"Relative object is not provided: {info.rel_object_uid}"
                        )
                elif info.type == "robot_frame":
                    if info.rel_arm is not None:
                        if info.rel_arm == "left":
                            frame_in_world = embodiment.robot_base_left.get_world_pose()
                        elif info.rel_arm == "right":
                            frame_in_world = (
                                embodiment.robot_base_right.get_world_pose()
                            )
                        elif info.rel_arm == "default":
                            frame_in_world = embodiment.robot.get_world_pose()
                        else:
                            raise ValueError(f"Invalid relative arm: {info.rel_arm}")
                        translation, orientation = pose_frame_to_world(
                            (np.array(info.translation), np.array(info.orientation)),
                            frame_in_world,
                        )
                        info.translation = translation.tolist()
                        info.orientation = orientation.tolist()
                    else:
                        raise ValueError(
                            f"Relative arm is not provided: {info.rel_arm}"
                        )
                elif info.type == "pending":
                    pass
                else:
                    raise ValueError(f"Invalid motion type: {info.type}")

    def execute(
        self, scene: "Scene", recorder: PlanningRecorder, idx: str
    ) -> tuple[bool, str]:
        self._process_motion_target(scene)

        embodiment = scene.robot_list[0]
        if not isinstance(embodiment, DualArmEmbodiment):
            raise ValueError(
                f"Embodiment {embodiment.embodiment_name} is not a dual arm robot"
            )

        if "left" in self.config.motion_list and "right" not in self.config.motion_list:
            action_list = self._plan(embodiment, "left")
            self._excute_and_record(
                scene, recorder, embodiment, action_list, idx, "left"
            )
        elif (
            "right" in self.config.motion_list and "left" not in self.config.motion_list
        ):
            action_list = self._plan(embodiment, "right")
            self._excute_and_record(
                scene, recorder, embodiment, action_list, idx, "right"
            )
        elif "left" in self.config.motion_list and "right" in self.config.motion_list:
            action_list_left = self._plan(embodiment, "left")
            action_list_right = self._plan(embodiment, "right")
            action_list = self._merge_dual_arm_action_list(
                embodiment, action_list_left, action_list_right
            )
            self._excute_and_record(
                scene, recorder, embodiment, action_list, idx, "default"
            )
        else:
            raise ValueError(f"Invalid motion list: {self.config.motion_list}")

        return True, "default"

    def _plan_step(
        self, embodiment, target: SingleArmMotion, arm, sim_js, smooth: bool
    ) -> list[list[float]]:
        results = embodiment.plan_pose(
            (np.array(target.translation), np.array(target.orientation)),
            sim_js,
            arm=arm,
        )
        if results is None:
            eepose = embodiment._transform_goal_pose(
                (np.array(target.translation), np.array(target.orientation)), arm
            )
            raise RuntimeError(
                f"Motion planning failed for target: {target.name}, target pose might be out of reach: {eepose}"
            )

        if smooth:
            results = get_smooth_trajectory(
                torch.from_numpy(np.array(results)), 5
            ).numpy()

        return [np.asarray(res).tolist() for res in results]

    def _create_pending_data(
        self,
        embodiment: BaseEmbodiment,
        target: SingleArmMotion,
        sim_js: JointsState,
        grasp_state: bool,
        arm: str,
        cnt: int = 1,
    ) -> list[dict]:
        if not isinstance(embodiment, DualArmEmbodiment):
            raise ValueError(
                f"Embodiment {embodiment.embodiment_name} is not a dual arm robot"
            )
        joint_pos = sim_js.positions
        if arm == "left":
            joint_pos = joint_pos[embodiment.left_arm_dof_indices]
        elif arm == "right":
            joint_pos = joint_pos[embodiment.right_arm_dof_indices]
        elif arm == "default":
            joint_pos = joint_pos[
                embodiment.left_arm_dof_indices + embodiment.right_arm_dof_indices
            ]
        else:
            raise ValueError(f"Invalid arm: {arm}")
        joint_pos = joint_pos[: embodiment.arm_dof_num]
        return [
            {
                "action": embodiment.convert_curobo_result_to_action(
                    joint_pos, grasp_state, arm
                ).tolist(),
                "name": target.name,
                "grasp": grasp_state,
            }
            for _ in range(cnt)
        ]

    def _create_action_data(
        self,
        embodiment: BaseEmbodiment,
        joint_pos: list[float],
        target_info: SingleArmMotion,
        grasp_state: bool,
        arm: str,
    ) -> dict:
        return {
            "action": embodiment.convert_curobo_result_to_action(
                joint_pos, grasp_state, arm
            ).tolist(),
            "name": target_info.name,
            "grasp": grasp_state,
        }

    def _excute_and_record(
        self,
        scene: "Scene",
        recorder: PlanningRecorder,
        embodiment: BaseEmbodiment,
        data_list: list[dict],
        idx_name: str,
        arm: str,
    ) -> None:
        for action in tqdm(data_list, desc=f"Arm action executing {idx_name}"):
            embodiment.robot_view.set_joint_position_targets(
                action["action"], joint_indices=embodiment.default_dof_indices
            )
            if isinstance(action["grasp"], list):
                grasp_val = [1.0 if grasp else -1.0 for grasp in action["grasp"]]
            else:
                grasp_val = 1.0 if action["grasp"] else -1.0
            recorder.load_dynamic_info(
                action["action"],
                grasp_val,
                arm=arm,
                name=f"{idx_name}/{action['name']}",
            )
            scene.step(render=False)
            if os.environ.get("GENMANIP_DEBUG", "0") == "1":
                scene.world.render()
        data_list.clear()
