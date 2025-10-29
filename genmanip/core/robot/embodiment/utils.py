"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from omni.isaac.core.prims import XFormPrim  # type: ignore
from omni.isaac.core.utils.prims import get_prim_at_path  # type: ignore
from pxr import UsdPhysics  # type: ignore


def get_all_joints(robot_prim: XFormPrim, joint_dict: dict) -> dict:
    for child in robot_prim.GetChildren():
        if child.IsA(UsdPhysics.Joint):
            joint_dict[child.GetName()] = UsdPhysics.Joint(child)
        else:
            get_all_joints(child, joint_dict)
    return joint_dict


def get_all_body_from_joint(
    joint_dict: dict[str, UsdPhysics.Joint], body_dict: dict[str, XFormPrim]
) -> dict[str, XFormPrim]:
    for value in joint_dict.values():
        body0_rel = value.GetBody0Rel()
        body0_path = body0_rel.GetTargets()
        if len(body0_path) > 0:
            body0_prim = get_prim_at_path(str(body0_path[0]))
            if body0_prim.IsValid():
                body_dict[body0_prim.GetName()] = body0_prim
        body1_rel = value.GetBody1Rel()
        body1_path = body1_rel.GetTargets()
        if len(body1_path) > 0:
            body1_prim = get_prim_at_path(str(body1_path[0]))
            if body1_prim.IsValid():
                body_dict[body1_prim.GetName()] = body1_prim
