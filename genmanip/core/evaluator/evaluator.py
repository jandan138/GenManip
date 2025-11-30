"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import os
import pickle

import numpy as np

from genmanip.core.sensor.camera import get_eval_camera_data, get_src
from genmanip.utils.usd_utils import get_world_pose_by_prim_path
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


def request_action(
    camera_data: dict,
    instruction: str,
    joint_position_state: list,
    ee_pose_state: list,
    step: int,
    send_port: socket.socket,
    receive_port: socket.socket,
    # archived
    obj_is_grasped: bool | None = None,
    franka_hand_pose: tuple[np.ndarray, np.ndarray] | None = None,
    franka_pose: tuple[np.ndarray, np.ndarray] | None = None,
    key_action: bool | None = None,
) -> np.ndarray:
    reset = step == 0
    data = {
        "camera_data": camera_data,
        "instruction": instruction,
        "joint_position_state": joint_position_state,
        "ee_pose_state": ee_pose_state,
        "timestep": step,
        "reset": reset,
        # archived
        "key_action": key_action,
        "franka_hand_pose": franka_hand_pose,
        "franka_pose": franka_pose,
        "obj_is_grasped": obj_is_grasped,
    }
    send_message(send_port, data)
    response = wait_message(receive_port)
    return response["action"]


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
    return data


class Evaluator:
    def __init__(
        self,
        scene: dict,
        instruction: str,
        log_dir: str,
        current_dir: str,
        is_relative_action: bool = False,
        send_port: socket.socket | None = None,
        receive_port: socket.socket | None = None,
    ) -> None:
        self.scene = scene
        camera_list = scene["camera_list"].copy()
        if "camera1" in camera_list:
            camera_list.pop("camera1")
        self.camera_list = camera_list
        self.image_list = {}
        for camera_name in self.camera_list.keys():
            self.image_list[camera_name] = []
        self.embodiment = scene["robot_info"]["robot_list"][0]
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
        self.oracle_camera_data = {}
        self.grasp_cnt = 0
        self.planning_data = {}
        self.last_ee_pose = None
        make_dir(self.log_dir)

    def update_task_data(self, task_data: dict, planning_data: dict) -> None:
        self.task_data = task_data
        self.instruction = task_data["instruction"]
        self.planning_data = planning_data

    # def update_oracle_camera_data(self) -> None:
    #     is_grasped = self.grasp_cnt != 0
    #     self.oracle_camera_data = {}
    #     if is_grasped:
    #         world_pose_list = collect_world_pose_list(self.scene["object_list"])
    #         place_object_to_object_by_relation(
    #             self.task_data["goal"][0][0]["obj1_uid"],
    #             self.task_data["goal"][0][0]["obj2_uid"],
    #             self.scene["object_list"],
    #             self.scene["cacheDict"]["meshDict"],
    #             self.task_data["goal"][0][0]["position"],
    #             platform_uid="00000000000000000000000000000000",
    #         )
    #         for _ in range(10):
    #             self.scene["world"].render()
    #     for camera_name, camera in self.camera_list.items():
    #         self.oracle_camera_data[camera_name] = {}
    #         camera_info = collect_camera_info(camera)
    #         self.oracle_camera_data[camera_name]["bbox2d"] = np.zeros(4)
    #         self.oracle_camera_data[camera_name]["obj_mask"] = np.zeros_like(
    #             camera_info["obj_mask"]
    #         )
    #         for key, value in camera_info["obj_mask_id2labels"].items():
    #             if value["class"] == self.task_data["goal"][0][0]["obj1_uid"]:
    #                 wanted_mask = camera_info["obj_mask"] == int(key)
    #                 self.oracle_camera_data[camera_name]["obj_mask"][wanted_mask] = 1
    #                 break
    #         for key, value in camera_info["bbox2d_tight_id2labels"].items():
    #             if value["class"] == self.task_data["goal"][0][0]["obj1_uid"]:
    #                 for bbox in camera_info["bbox2d_tight"]:
    #                     if bbox[0] == int(key):
    #                         self.oracle_camera_data[camera_name]["bbox2d"] = [
    #                             bbox[1],
    #                             bbox[2],
    #                             bbox[3],
    #                             bbox[4],
    #                         ]
    #                         break
    #                 break
    #     if is_grasped:
    #         for _ in range(5):
    #             self.scene["world"].step()
    #             reset_object_xyz(self.scene["object_list"], world_pose_list)

    def finish(self, success: int, success_rate: float) -> None:
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
            "_success" if success != 0 else "_failure"
        )
        os.rename(self.traj_log_dir, new_traj_log_dir)
        sr_info = {"success_rate": success_rate}
        save_dict_to_json(sr_info, os.path.join(new_traj_log_dir, "sr_info.json"))
        if success != 0:
            self.success_cnt += 1
        self.total_cnt += 1

    def initialize(self, seed: str) -> None:
        self.grasp_cnt = 0
        self.steps = 0
        self.oracle_camera_data = {}
        self.last_joint_position = self.embodiment.robot.get_joint_positions()[
            self.embodiment.default_dof_indices
        ]
        self.traj_log_dir = os.path.join(self.log_dir, str(seed))
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

    def request_action(self, without_render: bool = False) -> np.ndarray:
        franka_hand_pose = get_world_pose_by_prim_path(
            self.embodiment.robot.prim_path + "/panda_hand"
        )
        franka_pose = self.embodiment.robot.get_world_pose()
        self.current_joint_position = self.embodiment.robot.get_joint_positions()[
            self.embodiment.default_dof_indices
        ]
        # meshlist = get_current_meshList(
        #     self.scene["object_list"], self.scene["cacheDict"]["meshDict"]
        # )
        # is_grasped = detect_target_is_grasped(
        #     self.embodiment.robot, meshlist[self.task_data["goal"][0][0]["obj1_uid"]]
        # )
        # if is_grasped:
        #     self.grasp_cnt = 10
        # else:
        #     if self.grasp_cnt > 0:
        #         self.grasp_cnt -= 1
        #     else:
        #         self.grasp_cnt = 0
        camera_data = {}
        if not without_render:
            # if self.steps % 50 == 0:
            #     self.update_oracle_camera_data()
            camera_data = get_eval_camera_data(self.camera_list)
            # for key in camera_data.keys():
            #     camera_data[key]["obj_mask"] = self.oracle_camera_data[key]["obj_mask"]
            #     camera_data[key]["bbox2d"] = self.oracle_camera_data[key]["bbox2d"]
        ee_pose = self.embodiment.fk_single(self.embodiment.robot.get_joint_positions())
        if self.send_port is None or self.receive_port is None:
            raise ValueError("Send port or receive port is not set")
        action = request_action(
            camera_data,
            self.instruction,
            self.current_joint_position,
            tuple_to_list(ee_pose),
            self.steps,
            send_port=self.send_port,
            receive_port=self.receive_port,
            # archived
            # franka_hand_pose=franka_hand_pose,
            # franka_pose=franka_pose,
            # key_action=self.planning_data["key_action"][0],
            # obj_is_grasped=self.grasp_cnt != 0,
        )
        self.meta_record["model_output"].append(action)
        # if isinstance(action, list):
        #     if self.is_relative_action:
        #         action[:7] += self.last_joint_position[:7]
        #     self.last_joint_position = np.array(action[:7])
        # elif isinstance(action, tuple):
        #     position = action[0]
        #     orientation = action[1]
        #     gripper_width = action[2]
        #     if self.is_relative_action:
        #         delta_pose = (position, orientation)
        #         abs_pose = self.apply_delta_pose(delta_pose, self.last_ee_pose)
        #         position = abs_pose[0].tolist()
        #         orientation = abs_pose[1].tolist()
        #         self.last_ee_pose = abs_pose
        #     else:
        #         self.last_ee_pose = (position, orientation)
        #     # pose = Pose(p=position, q=orientation)
        #     ik_result = self.embodiment.planner.ik_single(
        #         position + orientation,
        #         self.embodiment.robot.get_joint_positions()[:7],
        #     )
        #     if ik_result is None:
        #         print("IK failed")
        #         action = self.embodiment.robot.get_joint_positions()
        #     else:
        #         action = ik_result
        #     action = np.concatenate([action[:7], gripper_width])
        #     self.last_joint_position = np.array(action[:7])
        # return action

        # Joint Position shouold be list, when dual arm, joint position should concatenate
        if isinstance(action, list):
            action = np.array(action, dtype=np.float64)
            for i in range(
                len(action)
                // (self.embodiment.arm_dof_num + self.embodiment.gripper_dof_num)
            ):
                if self.is_relative_action:
                    action[
                        i
                        * (
                            self.embodiment.arm_dof_num
                            + self.embodiment.gripper_dof_num
                        ) : i
                        * (
                            self.embodiment.arm_dof_num
                            + self.embodiment.gripper_dof_num
                        )
                        + self.embodiment.arm_dof_num
                    ] += self.last_joint_position[
                        i
                        * (
                            self.embodiment.arm_dof_num
                            + self.embodiment.gripper_dof_num
                        ) : i
                        * (
                            self.embodiment.arm_dof_num
                            + self.embodiment.gripper_dof_num
                        )
                        + self.embodiment.arm_dof_num
                    ]
            self.last_joint_position = action
        # if shape is (3), (4), (X), its a single arm eepose, if shape is ((3), (4), (X)), ((3), (4), (X)), its a dual arm eepose
        elif isinstance(action, tuple):
            if len(action) == 3 and len(action[0]) == 3 and len(action[1]) == 4:
                actions = [(action[0], action[1], action[2])]
            else:
                actions = list(action)
            action = np.array([])
            for i, act in enumerate(actions):
                position = act[0]
                orientation = act[1]
                gripper_width = act[2]
                if self.is_relative_action:
                    delta_pose = (position, orientation)
                    abs_pose = self.apply_delta_pose(delta_pose, self.last_ee_pose[i])  # type: ignore
                    position = abs_pose[0].tolist()
                    orientation = abs_pose[1].tolist()
                    self.last_ee_pose[i] = abs_pose  # type: ignore
                else:
                    self.last_ee_pose[i] = (position, orientation)  # type: ignore
                if len(actions) == 1:
                    ik_result = self.embodiment.planner.ik_single(
                        position + orientation,
                        self.embodiment.robot.get_joint_positions()[
                            self.embodiment.default_dof_indices
                        ][
                            i
                            * (
                                self.embodiment.arm_dof_num
                                + self.embodiment.gripper_dof_num
                            ) : i
                            * (
                                self.embodiment.arm_dof_num
                                + self.embodiment.gripper_dof_num
                            )
                            + self.embodiment.arm_dof_num
                        ],
                    )
                else:
                    if i == 0:
                        ik_result = self.embodiment.left_planner.ik_single(
                            position + orientation,
                            self.embodiment.robot.get_joint_positions()[
                                self.embodiment.default_dof_indices
                            ][
                                i
                                * (
                                    self.embodiment.arm_dof_num
                                    + self.embodiment.gripper_dof_num
                                ) : i
                                * (
                                    self.embodiment.arm_dof_num
                                    + self.embodiment.gripper_dof_num
                                )
                                + self.embodiment.arm_dof_num
                            ],
                        )
                    elif i == 1:
                        ik_result = self.embodiment.right_planner.ik_single(
                            position + orientation,
                            self.embodiment.robot.get_joint_positions()[
                                self.embodiment.default_dof_indices
                            ][
                                i
                                * (
                                    self.embodiment.arm_dof_num
                                    + self.embodiment.gripper_dof_num
                                ) : i
                                * (
                                    self.embodiment.arm_dof_num
                                    + self.embodiment.gripper_dof_num
                                )
                                + self.embodiment.arm_dof_num
                            ],
                        )
                    else:
                        raise ValueError("Invalid action")
                if ik_result is None:
                    print("IK failed")
                    ik_result = self.embodiment.robot.get_joint_positions()[
                        self.embodiment.default_dof_indices
                    ][
                        i
                        * (
                            self.embodiment.arm_dof_num
                            + self.embodiment.gripper_dof_num
                        ) : i
                        * (
                            self.embodiment.arm_dof_num
                            + self.embodiment.gripper_dof_num
                        )
                        + self.embodiment.arm_dof_num
                    ]
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
