"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import os
import pickle
from typing import Any

import numpy as np

from genmanip.utils.usd_utils.camera_utils import get_eval_camera_data, get_src
from genmanip.utils.standalone.file_utils import make_dir, save_dict_to_json
from genmanip.utils.standalone.frame_utils import save_image
from genmanip.utils.standalone.robot_utils import (
    joint_position_to_end_effector_pose,
    joint_positions_to_ee_pose_translation_euler,
)
from genmanip.utils.standalone.transform_utils import (
    pose_to_transform,
    transform_to_pose,
)
from genmanip.utils.standalone.utils import tuple_to_list

try:
    # if mediapy is installed, use it to create video
    import mediapy as mp
    from genmanip.utils.standalone.frame_utils import (
        create_video_from_image_list_with_mediapy as create_video_from_image_list,
    )
except:
    # if mediapy is not installed, use the original function
    from genmanip.utils.standalone.frame_utils import (
        create_video_from_image_list as create_video_from_image_list,
    )

import json
import lmdb
import pickle
import shutil
import socket


from genmanip.utils.standalone.socket_utils import send_message, wait_message
from genmanip.core.robot.base import BaseEmbodiment
from genmanip.core.robot.dualarm_manip import DualArmEmbodiment

from omni.isaac.sensor import Camera  # type: ignore


def get_scalar_data_from_lmdb(data_path: str, key: str | bytes) -> dict:
    meta_info = pickle.load(open(f"{data_path}/meta_info.pkl", "rb"))
    lmdb_env = lmdb.open(
        f"{data_path}/lmdb", readonly=True, lock=False, readahead=False, meminit=False
    )
    key_index = meta_info["keys"]["scalar_data"].index(key)
    key_key = meta_info["keys"]["scalar_data"][key_index]
    with lmdb_env.begin(write=False) as txn:
        data = pickle.loads(txn.get(key_key))
    return data


def parse_lmdb_data(lmdb_path: str) -> dict:
    data = {}
    meta_info = pickle.load(open(f"{lmdb_path}/meta_info.pkl", "rb"))
    arm_action = get_scalar_data_from_lmdb(lmdb_path, b"arm_action")
    gripper_action = get_scalar_data_from_lmdb(lmdb_path, b"gripper_action")
    try:
        base_motion = get_scalar_data_from_lmdb(lmdb_path, b"base_motion")
    except:
        base_motion = [np.array([0.0, 0.0, 0.0])] * len(arm_action)
    key_action = []
    idx_dict = {}
    for frame_status in meta_info["task_data"]["frame_status"]:
        idx = int(frame_status.split("/")[0])
        if idx not in idx_dict:
            idx_dict[idx] = []
        idx_dict[idx].append(frame_status)
    for idx in idx_dict.keys():
        if (
            f"{idx}/pre_grasp" in meta_info["task_data"]["frame_status"]
            and f"{idx}/post_grasp" in meta_info["task_data"]["frame_status"]
            and f"{idx}/post_place" in meta_info["task_data"]["frame_status"]
        ):
            key_action.append(
                [
                    joint_position_to_end_effector_pose(
                        arm_action[
                            meta_info["task_data"]["frame_status"][f"{idx}/pre_grasp"]
                        ]
                    ),
                    joint_position_to_end_effector_pose(
                        arm_action[
                            meta_info["task_data"]["frame_status"][f"{idx}/post_grasp"]
                        ]
                    ),
                    joint_position_to_end_effector_pose(
                        arm_action[
                            meta_info["task_data"]["frame_status"][f"{idx}/post_place"]
                        ]
                    ),
                ]
            )
        else:
            for action_name in idx_dict[idx]:
                key_action.append(
                    [
                        joint_position_to_end_effector_pose(
                            arm_action[
                                meta_info["task_data"]["frame_status"][action_name]
                            ]
                        )
                    ]
                )
    data["key_action"] = key_action
    data["action"] = arm_action
    data["gripper_action"] = gripper_action
    data["base_motion"] = base_motion
    return data


class Evaluator:
    def __init__(
        self,
        camera_list: dict[str, Camera],
        robot: BaseEmbodiment,
        instruction: str,
        log_dir: str,
        is_relative_action: bool = False,
        send_port: socket.socket | None = None,
        receive_port: socket.socket | None = None,
        remove_log_dir: bool = False,
    ) -> None:
        if "camera1" in camera_list:
            camera_list.pop("camera1")
        self.camera_list = camera_list
        self.image_list = {}
        for camera_name in self.camera_list.keys():
            self.image_list[camera_name] = []
        self.embodiment = robot
        self.instruction = instruction
        self.success_cnt = 0
        self.total_cnt = 0
        self.log_dir = log_dir
        self.send_port = send_port
        self.receive_port = receive_port
        self.is_relative_action = is_relative_action
        self.current_joint_position = self.embodiment.robot.get_joint_positions()[:7]
        self.last_joint_position = self.embodiment.robot.get_joint_positions()[:7]
        self.meta_record = {}
        self.task_data = []
        self.planning_data = {}
        self.last_ee_pose = None
        self.remove_log_dir = remove_log_dir
        make_dir(self.log_dir)

    def update_task_data(self, task_data: dict, planning_data: dict) -> None:
        self.task_data = task_data
        self.instruction = task_data["instruction"]
        self.planning_data = planning_data

    def finish(self, success_rate: float) -> float:
        for camera_name in self.camera_list.keys():
            if len(os.listdir(os.path.join(self.traj_log_dir, camera_name))) > 0:
                create_video_from_image_list(
                    self.image_list[camera_name],
                    os.path.join(self.traj_log_dir, camera_name + ".mp4"),
                )
                self.image_list[camera_name] = []
                shutil.rmtree(os.path.join(self.traj_log_dir, camera_name))
        self.save_meta_record()
        new_traj_log_dir = self.traj_log_dir + (
            "_success" if success_rate != 0 else "_failure"
        )
        os.rename(self.traj_log_dir, new_traj_log_dir)
        sr_info = {"success_rate": success_rate}
        save_dict_to_json(sr_info, os.path.join(new_traj_log_dir, "sr_info.json"))
        if success_rate != 0:
            self.success_cnt += 1
        self.total_cnt += 1
        return success_rate

    def initialize(self, seed: str) -> None:
        self.steps = 0
        self.last_joint_position = self.embodiment.robot.get_joint_positions()[
            self.embodiment.default_dof_indices
        ]
        self.traj_log_dir = os.path.join(self.log_dir, str(seed))
        if self.remove_log_dir:
            if os.path.exists(self.traj_log_dir):
                shutil.rmtree(self.traj_log_dir)
            if os.path.exists(self.traj_log_dir + "_success"):
                shutil.rmtree(self.traj_log_dir + "_success")
            if os.path.exists(self.traj_log_dir + "_failure"):
                shutil.rmtree(self.traj_log_dir + "_failure")
        self.current_joint_position = self.embodiment.robot.get_joint_positions()[
            self.embodiment.default_dof_indices
        ]
        self.meta_record = {}
        self.meta_record["joint_positions"] = []
        self.meta_record["joint_velocities"] = []
        self.meta_record["tcp"] = []
        self.meta_record["instruction"] = self.instruction
        self.meta_record["model_output"] = []
        self.last_ee_pose = self.embodiment.fk_single(
            self.embodiment.robot.get_joint_positions()
        )
        if (
            len(self.last_ee_pose) == 2
            and len(self.last_ee_pose[0]) == 3
            and len(self.last_ee_pose[1]) == 4
        ):
            self.last_ee_pose = [self.last_ee_pose]
        else:
            self.last_ee_pose = list(self.last_ee_pose)
        make_dir(self.traj_log_dir)
        for camera_name in self.camera_list.keys():
            make_dir(os.path.join(self.traj_log_dir, camera_name))
        self.record_config()

    def record_config(self) -> None:
        with open(os.path.join(self.traj_log_dir, "config.json"), "w") as f:
            json.dump(
                {
                    "instruction": self.instruction,
                },
                f,
            )

    def record(self, is_save_image: bool = True) -> int:
        if is_save_image:
            for camera_name, camera in self.camera_list.items():
                self.image_list[camera_name].append(get_src(camera, "rgb"))
            if self.steps % 10 == 0:
                for camera_name in self.camera_list.keys():
                    save_image(
                        self.image_list[camera_name][-1],
                        os.path.join(
                            self.traj_log_dir,
                            camera_name,
                            f"{str(self.steps).zfill(5)}.png",
                        ),
                    )
        self.meta_record["joint_positions"].append(
            self.embodiment.robot.get_joint_positions()
        )
        self.meta_record["joint_velocities"].append(
            self.embodiment.robot.get_joint_velocities()
        )
        self.meta_record["tcp"].append(
            joint_positions_to_ee_pose_translation_euler(
                self.embodiment.robot.get_joint_positions()
            )
        )
        self.steps += 1
        return self.steps

    def apply_delta_pose(
        self,
        delta_pose: tuple[np.ndarray, np.ndarray],
        current_pose: tuple[np.ndarray, np.ndarray],
    ) -> tuple[np.ndarray, np.ndarray]:
        delta_position = np.array(delta_pose[0])
        delta_orientation = np.array(delta_pose[1])
        current_position = np.array(current_pose[0])
        current_orientation = np.array(current_pose[1])
        delta_pose_formatted = (delta_position, delta_orientation)
        current_pose_formatted = (current_position, current_orientation)
        delta_transform = pose_to_transform(delta_pose_formatted)
        current_transform = pose_to_transform(current_pose_formatted)
        new_transform = delta_transform @ current_transform
        return transform_to_pose(new_transform)

    def get_obs(self, without_render: bool = False) -> dict:
        self.current_joint_position = self.embodiment.robot.get_joint_positions()[
            self.embodiment.default_dof_indices
        ]
        if isinstance(self.embodiment, DualArmEmbodiment):
            self.current_base_position = self.embodiment.robot.get_joint_positions()[
                self.embodiment.base_dof_indices
            ]
        else:
            self.current_base_position = [0.0, 0.0, 0.0]
        self.current_arm_position = self.current_joint_position[self.embodiment.default_arm_dof_indices]
        self.current_gripper_position = self.current_joint_position[self.embodiment.default_gripper_dof_indices]

        camera_data = {}
        if not without_render:
            camera_data = get_eval_camera_data(self.camera_list)
        ee_pose = self.embodiment.fk_single(self.embodiment.robot.get_joint_positions())

        obs = {
            "instruction": self.instruction,
            "camera_data": camera_data,
            "state.joints": self.current_arm_position,
            "state.gripper": self.current_gripper_position,
            "state.base": self.current_base_position,
            "state.ee_pose": tuple_to_list(ee_pose),
            "timestep": self.steps,
            "reset": self.steps == 0,
        }

        for camera, img in camera_data.items():
            obs[f"video.{camera}_view"] = img['rgb']
        return obs

    def request_action(self, obs) -> dict[str, Any]:
        if self.send_port is None:
            raise ValueError("Send port is not set")
        if self.receive_port is None:
            raise ValueError("Receive port is not set")
        send_message(self.send_port, obs)
        action = wait_message(self.receive_port)
        return action

    def parse_action(self, action, control_type: str = "joint_position") -> np.ndarray:
        self.meta_record["model_output"].append(action)
        embodiment_joint_num = (
            self.embodiment.arm_dof_num + self.embodiment.gripper_dof_num
        )
        # Joint Position shouold be list, when dual arm, joint position should concatenate
        if control_type == "joint_position":
            action = np.array(action, dtype=np.float64)
            for i in range(len(action) // embodiment_joint_num):
                if self.is_relative_action:
                    sta_idx = i * embodiment_joint_num
                    end_idx = sta_idx + self.embodiment.arm_dof_num
                    action[sta_idx:end_idx] += self.last_joint_position[sta_idx:end_idx]
            self.last_joint_position = action

        # if shape is (3), (4), (X), its a single arm eepose, if shape is ((3), (4), (X)), ((3), (4), (X)), its a dual arm eepose
        elif control_type == "ee_pose":
            if len(action) == 3 and len(action[0]) == 3 and len(action[1]) == 4:
                actions = [(action[0], action[1], action[2])]
            else:
                actions = list(action)
            action = np.array([])
            for i, act in enumerate(actions):
                position, orientation, gripper_width = act
                if self.is_relative_action:
                    delta_pose = (position, orientation)
                    abs_pose = self.apply_delta_pose(delta_pose, self.last_ee_pose[i])  # type: ignore
                    position = abs_pose[0].tolist()
                    orientation = abs_pose[1].tolist()
                    self.last_ee_pose[i] = abs_pose  # type: ignore
                else:
                    self.last_ee_pose[i] = (position, orientation)  # type: ignore

                if len(actions) == 1:
                    planner = self.embodiment.planner
                elif i == 0:
                    planner = self.embodiment.left_planner  # type: ignore
                elif i == 1:
                    planner = self.embodiment.left_planner  # type: ignore
                else:
                    raise ValueError("Invalid action")

                sta_idx = i * embodiment_joint_num
                end_idx = sta_idx + self.embodiment.arm_dof_num
                ik_result = planner.ik_single(  # type: ignore
                    position + orientation,
                    self.embodiment.robot.get_joint_positions()[
                        self.embodiment.default_dof_indices
                    ][sta_idx:end_idx],
                )

                if ik_result is None:
                    print("IK failed")
                    ik_result = self.embodiment.robot.get_joint_positions()[
                        self.embodiment.default_dof_indices
                    ][sta_idx:end_idx]

                action = np.concatenate(
                    [action, ik_result[: self.embodiment.arm_dof_num], gripper_width]
                )
        else:
            raise ValueError("Action is not a list or tuple")

        self.last_joint_position = action
        return action

    def set_permissions(self, path: str) -> None:
        os.chmod(path, 0o777)
        for root, dirs, files in os.walk(path):
            for dir_name in dirs:
                os.chmod(os.path.join(root, dir_name), 0o777)
            for file_name in files:
                os.chmod(os.path.join(root, file_name), 0o777)

    def save_meta_record(self) -> None:
        with open(os.path.join(self.traj_log_dir, "meta_record.pkl"), "wb") as f:
            pickle.dump(self.meta_record, f)
