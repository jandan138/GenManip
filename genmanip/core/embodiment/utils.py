"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from omni.isaac.core.prims import XFormPrim  # type: ignore
from omni.isaac.core.robots.robot import Robot  # type: ignore
from omni.isaac.core.utils.prims import get_prim_at_path  # type: ignore
from pxr import UsdPhysics  # type: ignore

from genmanip.utils.usd_utils import get_robot_all_links

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
    return body_dict

def create_joint_xform_list(robot: Robot) -> dict[str, XFormPrim]:
    robot_prim = get_prim_at_path(robot.prim_path)
    joint_prim_dict = get_robot_all_links(robot_prim)
    blacklist = ["Defeatured_2F_85_PAD_OPEN_basestep"]
    joint_xform_list = {
        joint_name: XFormPrim(str(joint_prim.GetPath()))
        for joint_name, joint_prim in joint_prim_dict.items()
        if all([black not in joint_name for black in blacklist])
    }
    return joint_xform_list


def create_tcp_xform_list(robot: Robot, tcp_config: list[dict]) -> list[XFormPrim]:
    tcp_xform_list = []
    for tcp_info in tcp_config:
        tcp = XFormPrim(
            f"{robot.prim_path}/{tcp_info['parent_prim_path']}/{tcp_info['name']}"
        )
        tcp.set_local_pose(tcp_info["position"], tcp_info["orientation"])
        tcp_xform_list.append(tcp)
    return tcp_xform_list
