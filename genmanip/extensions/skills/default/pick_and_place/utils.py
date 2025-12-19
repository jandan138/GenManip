"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from genmanip.core.robot.base import BaseEmbodiment
from genmanip.utils.standalone.transform_utils import (
    adjust_orientation,
    adjust_translation_along_quaternion,
    rot_orientation_by_z_axis,
    rot_orientation_by_axis,
)

def adjust_grasp_by_embodiment(
    grasp: dict,
    embodiment: BaseEmbodiment,
) -> dict:
    grasp["orientation"] = adjust_orientation(grasp["orientation"])
    if embodiment.embodiment_name == "franka":
        if embodiment.gripper_name == "panda_hand":
            grasp["translation"] = adjust_translation_along_quaternion(
                grasp["translation"],
                grasp["orientation"],
                0.08,
                aug_distance=0.0,
            )
        elif embodiment.gripper_name == "robotiq":
            # robotiq 的 grasp pose 需要绕 z 轴旋转 45 度
            grasp["orientation"] = rot_orientation_by_z_axis(grasp["orientation"], -45)
            grasp["translation"] = adjust_translation_along_quaternion(
                grasp["translation"],
                grasp["orientation"],
                0.15,
                aug_distance=0.0,
            )
    elif embodiment.embodiment_name == "aloha_split":
        if embodiment.gripper_name == "piper":
            grasp["orientation"] = rot_orientation_by_z_axis(grasp["orientation"], -90)
            grasp["translation"] = adjust_translation_along_quaternion(
                grasp["translation"],
                grasp["orientation"],
                0.11,
                aug_distance=0.0,
            )
    elif embodiment.embodiment_name == "lift2":
        if embodiment.gripper_name == "lift2":
            grasp["translation"] = adjust_translation_along_quaternion(
                grasp["translation"],
                grasp["orientation"],
                0.135,
                aug_distance=0.0,
            )
            grasp["orientation"] = rot_orientation_by_axis(
                grasp["orientation"], "y", 90
            )
            grasp["orientation"] = rot_orientation_by_axis(
                grasp["orientation"], "z", 180
            )
    return grasp
