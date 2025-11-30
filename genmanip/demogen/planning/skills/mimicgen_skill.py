"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import numpy as np
from scipy.spatial.transform import Rotation as R

from omni.isaac.core.utils.prims import get_prim_at_path  # type: ignore
from omni.isaac.core.utils.transformations import get_relative_transform  # type: ignore

from genmanip.utils.usd_utils import get_world_pose_by_prim_path
from genmanip.demogen.recoder.planning_recorder import Logger as PlanningLogger
from genmanip.utils.planner.mplib.utils import relate_planner_with_franka

from typing import Optional, Sequence  # type: ignore

from mplib.planner import Planner
from mplib.pymp import Pose
import numpy as np
from scipy.spatial.transform import Rotation as R

from omni.isaac.core.articulations import ArticulationView  # type: ignore
from omni.isaac.core.prims import XFormPrim  # type: ignore
from omni.isaac.core.robots.robot import Robot  # type: ignore
from omni.isaac.core.utils.prims import get_prim_at_path  # type: ignore
from omni.isaac.franka import Franka  # type: ignore

from genmanip.utils.usd_utils import get_robot_all_links
from genmanip.utils.planner.curobo.base import CuroboPlanner
from genmanip.utils.planner.mplib.utils import relate_planner_with_franka

def replay_skill(
    object_to_franka: np.ndarray,
    franka: Franka,
    planner: Planner,
    skill_data: list[dict],
) -> list[np.ndarray]:
    pose_data = []
    gripper_data = []
    # set planner base to [0, 0, 0] in robot frame
    planner.set_base_pose(Pose(p=np.array([0, 0, 0]), q=np.array([1, 0, 0, 0])))
    for action in skill_data:
        hand_to_franka = np.dot(object_to_franka, action["hand_to_object"])
        p_transformed, rot_mat = hand_to_franka[:3, 3], hand_to_franka[:3, :3]
        q_transformed = R.from_matrix(rot_mat).as_quat()[[3, 0, 1, 2]]
        pose_data.append(Pose(p=p_transformed, q=q_transformed))
        gripper_data.append(action["gripper_open"])

    paths = planner.plan_pose(
        pose_data[0], franka.get_joint_positions(), time_step=1 / 30.0, rrt_range=0.01
    )

    position_array = np.array(paths["position"])
    actions = [
        np.array(position_array[i].tolist() + [0.04, 0.04])
        for i in range(position_array.shape[0])
    ]

    start_joint_positions = actions[-1]

    # actions = []
    # start_joint_positions = franka.get_joint_positions()

    for pose, gripper in zip(pose_data, gripper_data):
        ik_result = planner.IK(
            pose,
            np.array(start_joint_positions),
            return_closest=True,
        )
        if ik_result[0] != "Success":
            continue
        start_joint_positions = ik_result[1]
        start_joint_positions = np.array(start_joint_positions)
        gripper_positions = [0.04, 0.04] if gripper else [0.0, 0.0]
        actions.append(np.array(start_joint_positions.tolist()[:7] + gripper_positions))
    # set planner back to robot pose in world frame
    planner = relate_planner_with_franka(franka, planner)
    return actions


def replay_skill_curobo(
    object_to_franka: np.ndarray,
    franka: Franka,
    curobo_planner: CuroboPlanner,
    skill_data: list[dict],
) -> list[np.ndarray]:
    pose_data = []
    gripper_data = []
    actions = []

    for action in skill_data:
        hand_to_franka = np.dot(object_to_franka, action["hand_to_object"])
        p_transformed, rot_mat = hand_to_franka[:3, 3], hand_to_franka[:3, :3]
        q_transformed = R.from_matrix(rot_mat).as_quat()[[3, 0, 1, 2]]
        pose_data.append(p_transformed.tolist() + q_transformed.tolist())
        gripper_data.append(action["gripper_open"])
    cur_joint_positions = pose_data[0]
    for pose, gripper in zip(pose_data, gripper_data):
        ik_result = curobo_planner.ik_single(pose, np.array(cur_joint_positions))
        if ik_result is None:
            continue
        gripper_positions = [0.04, 0.04] if gripper else [0.0, 0.0]
        actions.append(np.concatenate([ik_result[:7], gripper_positions]).tolist())
        cur_joint_positions = actions[-1][:7]

    print("action len: ", len(actions))
    return actions


def get_pose_matrix(pose: np.ndarray) -> np.ndarray:
    translation = pose[0]
    rotation = R.from_quat(pose[1][[1, 2, 3, 0]]).as_matrix()
    prim_matrix = np.eye(4)
    prim_matrix[:3, :3] = rotation
    prim_matrix[:3, 3] = translation
    return prim_matrix


def get_relative_transform_matrix(
    object_pose: np.ndarray, franka_pose: np.ndarray
) -> np.ndarray:
    object_matrix = get_pose_matrix(object_pose)
    franka_matrix = get_pose_matrix(franka_pose)
    return np.linalg.inv(franka_matrix) @ object_matrix


def replay_mimicgen_skill(
    scene: dict,
    recorder: PlanningLogger,
    demogen_config: dict,
    action_info: dict,
    idx: str,
) -> bool:
    franka = scene["robot_info"]["robot_list"][0].robot
    franka_prim = franka.prim
    object_prim_path = scene["articulation_list"][action_info["obj1_uid"]].prim_path
    object_prim = get_prim_at_path(object_prim_path)
    object_to_franka = get_relative_transform(object_prim, franka_prim)
    skill_data = scene["articulation_data"][action_info["obj1_uid"]]["skills"][
        action_info["skill_name"]
    ]["skill_trajectory"]
    # todo: support mplib and curobo
    if demogen_config["generation_config"]["planner"] == "mplib":
        actions = replay_skill(
            object_to_franka, franka, scene["planner_list"][0], skill_data
        )
        scene["planner_list"][0] = relate_planner_with_franka(
            franka, scene["planner_list"][0]
        )
    elif demogen_config["generation_config"]["planner"] == "curobo":
        # scene["planner_list"][0].update()
        actions = replay_skill_curobo(
            object_to_franka, franka, scene["planner_list"][0], skill_data
        )
    else:
        raise ValueError(f"Unsupported planner: {demogen_config['generation_config']['planner']}")
    print("mimicgen skill actions: ", len(actions))
    if len(actions) == 0:
        return False
    while actions:
        action = actions.pop(0)
        scene["robot_info"]["robot_view_list"][0].set_joint_position_targets(action)
        if np.allclose(action[7:], [0.04, 0.04]):
            grasp = 1
        elif np.allclose(action[7:], [0, 0]):
            grasp = -1
        else:
            raise ValueError("mimicgen skill action gripper invalid.")
        recorder.load_dynamic_info(
            action, grasp, name=f"{idx}/{action_info['skill_name']}"
        )
        scene["world"].step(render=True)
        if (
            get_world_pose_by_prim_path(franka.prim_path + "/panda_hand")[0][0] + 0.1
            < get_world_pose_by_prim_path(franka.prim_path + "/panda_link0")[0][0]
        ):
            return False
    return True
