"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import numpy as np
import socket

from genmanip_bench.request_model.socket_utils import send_message, wait_message


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
