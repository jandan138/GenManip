"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import os
import pickle
from typing import Any

import lmdb
import numpy as np


def get_scalar_data_from_lmdb(data_path: str, key: bytes) -> list[Any]:
    meta_info = pickle.load(open(f"{data_path}/meta_info.pkl", "rb"))
    lmdb_env = lmdb.open(
        f"{data_path}/lmdb", readonly=True, lock=False, readahead=False, meminit=False
    )
    key_index = meta_info["keys"]["scalar_data"].index(key)
    key_key = meta_info["keys"]["scalar_data"][key_index]
    with lmdb_env.begin(write=False) as txn:
        data = pickle.loads(txn.get(key_key))
    return data


def parse_planning_result(
    dir: str,
    default_config: dict,
    demogen_config: dict,
    scene: dict,
) -> list[dict]:
    data_list = []
    data_dir = os.path.join(
        default_config["DEMONSTRATION_DIR"],
        demogen_config["task_name"],
        "trajectory",
        dir,
    )
    qpos_data = get_scalar_data_from_lmdb(data_dir, b"observation/robot/qpos")
    qvel_data = get_scalar_data_from_lmdb(data_dir, b"observation/robot/qvel")
    arm_action_data = get_scalar_data_from_lmdb(data_dir, b"arm_action")
    gripper_action_data = get_scalar_data_from_lmdb(data_dir, b"gripper_action")
    gripper_close_data = get_scalar_data_from_lmdb(data_dir, b"gripper_close")
    name_data = get_scalar_data_from_lmdb(data_dir, b"name")
    try:
        joint_world_pose_data = get_scalar_data_from_lmdb(
            data_dir, b"observation/robot/joint_world_pose"
        )
    except:
        joint_world_pose_data = None
    for (
        qpos,
        qvel,
        arm_action,
        gripper_action,
        gripper_close,
        name,
        joint_world_pose,
    ) in zip(
        qpos_data,
        qvel_data,
        arm_action_data,
        gripper_action_data,
        gripper_close_data,
        name_data,
        (
            joint_world_pose_data
            if joint_world_pose_data is not None
            else [None] * len(qpos_data)
        ),
    ):
        data = {}
        data["qpos"] = qpos
        data["qvel"] = qvel
        data["action"] = np.concatenate([arm_action, gripper_action])
        data["gripper_close"] = gripper_close
        data["name"] = name
        data["obj_info"] = {}
        if joint_world_pose is not None:
            data["joint_world_pose"] = joint_world_pose
        data_list.append(data)
    for key in scene["object_list"]:
        position_data = get_scalar_data_from_lmdb(
            data_dir, f"observation/obj_pose/{key}/position".encode("utf-8")
        )
        for data, position in zip(data_list, position_data):
            data["obj_info"][key] = {}
            data["obj_info"][key]["position"] = position
        orientation_data = get_scalar_data_from_lmdb(
            data_dir, f"observation/obj_pose/{key}/orientation".encode("utf-8")
        )
        for data, orientation in zip(data_list, orientation_data):
            data["obj_info"][key]["orientation"] = orientation
        scale_data = get_scalar_data_from_lmdb(
            data_dir, f"observation/obj_pose/{key}/scale".encode("utf-8")
        )
        for data, scale in zip(data_list, scale_data):
            data["obj_info"][key]["scale"] = scale
    return data_list
