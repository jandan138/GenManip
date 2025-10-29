"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import numpy as np
from scipy.spatial.transform import Rotation as R

from omni.isaac.core.prims import XFormPrim  # type: ignore


def grasp_local_to_world_sparse(
    grasp_list: np.ndarray, object: XFormPrim
) -> list[dict]:
    world_grasp_list = []
    T_world_object = np.eye(4)
    T_world_object[:3, :3] = R.from_quat(
        object.get_world_pose()[1][[1, 2, 3, 0]]
    ).as_matrix()
    T_world_object[:3, 3] = object.get_world_pose()[0]
    T_correction = np.eye(4)
    T_correction[:3, :3] = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])
    for grasp in grasp_list:
        T_object_grasp = np.eye(4)
        T_object_grasp[:3, :3] = grasp[4:13].reshape(3, 3)
        T_object_grasp[:3, 3] = grasp[13:16]
        T_world_grasp = T_world_object @ T_object_grasp @ T_correction
        world_grasp_list.append(
            {
                "translation": T_world_grasp[:3, 3],
                "orientation": R.from_matrix(T_world_grasp[:3, :3]).as_quat()[
                    [3, 0, 1, 2]
                ],
                "score": grasp[0],
                "fall_time": grasp[17],
            }
        )
    return world_grasp_list


def get_graspnet_pose(object: XFormPrim, pose_npy_path: str) -> list[dict]:
    """
    Get grasp pose from graspnet pose npy file.
    Args:
        object: xform prim of the object
        pose_npy_path: path to the graspnet pose npy file
    Returns:
        world_grasps: list of graspnet pose in world frame
    """
    local_grasps = np.load(pose_npy_path)
    local_grasps = local_grasps[0].reshape(1, -1)
    world_grasps = grasp_local_to_world_sparse(local_grasps, object)
    return world_grasps
