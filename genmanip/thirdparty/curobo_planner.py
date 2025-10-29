"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import os

from omni.isaac.core import World  # type: ignore
from omni.isaac.core.robots.robot import Robot  # type: ignore

from genmanip.thirdparty.curobo_planners.base import CuroboPlanner
from genmanip.thirdparty.curobo_planners.franka import CuroboFrankaPlanner
from genmanip.thirdparty.curobo_planners.piper import CuroboPiperPlanner
from genmanip.thirdparty.curobo_planners.lift2 import CuroboLift2Planner
from genmanip.utils.file_utils import load_yaml


def get_curobo_planner(
    robot: Robot, robot_type: str, world: World, current_dir: str
) -> CuroboPlanner:
    if robot_type == "franka":
        franka_cfg = load_yaml(
            os.path.join(current_dir, "assets/robots/configs/franka.yml")
        )
        planner = CuroboFrankaPlanner(franka_cfg, world, robot.prim_path)
    elif robot_type.startswith("piper_"):
        piper_cfg = load_yaml(
            os.path.join(
                current_dir, "saved/assets/miscs/curobo/piper100/piper100_left_arm.yml"
            )
        )
        piper_cfg["robot_cfg"]["kinematics"]["usd_path"] = piper_cfg["robot_cfg"][
            "kinematics"
        ]["usd_path"].replace("${ASSETS_DIR}", current_dir + "/saved/assets")
        piper_cfg["robot_cfg"]["kinematics"]["urdf_path"] = piper_cfg["robot_cfg"][
            "kinematics"
        ]["urdf_path"].replace("${ASSETS_DIR}", current_dir + "/saved/assets")
        planner = CuroboPiperPlanner(
            piper_cfg, world, robot.prim_path, robot_type.split("_")[1]
        )
    elif robot_type.startswith("R5a_"):
        lift2_cfg = load_yaml(
            os.path.join(
                current_dir, "saved/assets/miscs/curobo/R5a/r5a_left_arm.yml"
            )
        )
        lift2_cfg["robot_cfg"]["kinematics"]["usd_path"] = lift2_cfg["robot_cfg"][
            "kinematics"
        ]["usd_path"].replace("${ASSETS_DIR}", current_dir + "/saved/assets")
        lift2_cfg["robot_cfg"]["kinematics"]["urdf_path"] = lift2_cfg["robot_cfg"][
            "kinematics"
        ]["urdf_path"].replace("${ASSETS_DIR}", current_dir + "/saved/assets")
        planner = CuroboLift2Planner(
            lift2_cfg, world, robot.prim_path, robot_type.split("_")[1]
        )
    else:
        raise ValueError(f"Unsupported robot type: {robot_type}")
    return planner
