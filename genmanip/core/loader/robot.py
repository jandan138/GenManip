"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import os

import numpy as np

from omni.isaac.core.robots.robot import Robot  # type: ignore
from omni.isaac.core.utils.prims import create_prim, get_prim_at_path  # type: ignore
from omni.isaac.franka import Franka  # type: ignore

from genmanip.utils.usd_utils import get_world_pose_by_prim_path


def relate_aloha_from_data(
    scene_uid: str,
    default_config: dict,
    position: np.ndarray = np.array([-0.5, 0.0, 0.0]),
    orientation: np.ndarray = np.array([1.0, 0.0, 0.0, 0.0]),
) -> Robot:
    # Deactivate the franka robot
    prim = get_prim_at_path(f"/World/{scene_uid}/franka")
    if prim.IsActive():
        prim.SetActive(False)
    # Create the aloha robot
    prim = create_prim(
        prim_path=f"/World/{scene_uid}/aloha",
        prim_type="Xform",
        usd_path=os.path.join(
            default_config["ASSETS_DIR"],
            "robot_usds/arx5_description_isaac/arx5_description_isaac.usd",
        ),
        position=position,
        orientation=orientation,
    )
    # Create the aloha robot object
    aloha = Robot(
        prim_path=f"/World/{scene_uid}/aloha",
        name="aloha",
    )
    return aloha


def relate_aloha_split_from_data(
    scene_uid: str,
    default_config: dict,
    position: np.ndarray = np.array([-0.65, 0.0, 0.3]),
    orientation: np.ndarray = np.array([1.0, 0.0, 0.0, 0.0]),
) -> Robot:
    # Deactivate the franka robot
    prim = get_prim_at_path(f"/World/{scene_uid}/franka")
    if prim.IsValid() and prim.IsActive():
        prim.SetActive(False)
    # Create the aloha_split robot
    prim = create_prim(
        prim_path=f"/World/{scene_uid}/aloha_split",
        prim_type="Xform",
        usd_path=os.path.join(
            default_config["ASSETS_DIR"],
            "robot_usds/split_aloha_mid_360/robot.usd",
        ),
        position=position,
        orientation=orientation,
    )
    # Create the aloha_split robot object
    aloha_split = Robot(
        prim_path=f"/World/{scene_uid}/aloha_split",
        name="aloha_split",
    )
    # Set default parameters for the aloha_split robot
    aloha_split.set_solver_position_iteration_count(128)
    aloha_split.set_stabilization_threshold(0.005)
    aloha_split.set_solver_velocity_iteration_count(4)
    return aloha_split


def relate_piper_from_data(
    scene_uid: str,
    default_config: dict,
    position: np.ndarray | None = None,
    orientation: np.ndarray | None = None,
) -> Robot:
    # Get the position and orientation of the franka robot
    if position is None:
        position = get_world_pose_by_prim_path(f"/World/{scene_uid}/franka")[0]
    if orientation is None:
        orientation = get_world_pose_by_prim_path(f"/World/{scene_uid}/franka")[1]
    # Deactivate the franka robot
    prim = get_prim_at_path(f"/World/{scene_uid}/franka")
    if prim.IsValid() and prim.IsActive():
        prim.SetActive(False)
    # Create the piper robot with same position and orientation as the franka robot
    prim = create_prim(
        prim_path=f"/World/{scene_uid}/piper",
        prim_type="Xform",
        usd_path=os.path.join(
            default_config["ASSETS_DIR"],
            "robot_usds/piper/piper_description.usd",
        ),
        position=position,
        orientation=orientation,
    )
    # Create the piper robot object
    piper = Robot(
        prim_path=f"/World/{scene_uid}/piper",
        name="piper",
    )
    return piper


def relate_piper100_from_data(
    scene_uid: str,
    default_config: dict,
    position: np.ndarray | None = None,
    orientation: np.ndarray | None = None,
) -> Robot:
    # Get the position and orientation of the franka robot
    if position is None:
        position = get_world_pose_by_prim_path(f"/World/{scene_uid}/franka")[0]
    if orientation is None:
        orientation = get_world_pose_by_prim_path(f"/World/{scene_uid}/franka")[1]
    # Deactivate the franka robot
    prim = get_prim_at_path(f"/World/{scene_uid}/franka")
    if prim.IsValid() and prim.IsActive():
        prim.SetActive(False)
    # Create the piper100 robot
    prim = create_prim(
        prim_path=f"/World/{scene_uid}/piper100",
        prim_type="Xform",
        usd_path=os.path.join(
            default_config["ASSETS_DIR"],
            "robot_usds/piper100/piper100.usd",
        ),
        position=position,
        orientation=orientation,
    )
    # Create the piper100 robot object
    piper100 = Robot(
        prim_path=f"/World/{scene_uid}/piper100",
        name="piper100",
    )
    # Set default parameters for the piper100 robot
    piper100.set_solver_position_iteration_count(128)
    piper100.set_stabilization_threshold(0.005)
    piper100.set_solver_velocity_iteration_count(4)
    return piper100


def relate_AXRX5_from_data(
    scene_uid: str,
    default_config: dict,
    position: np.ndarray | None = None,
    orientation: np.ndarray | None = None,
) -> Robot:
    # Get the position and orientation of the franka robot
    if position is None:
        position = get_world_pose_by_prim_path(f"/World/{scene_uid}/franka")[0]
    if orientation is None:
        orientation = get_world_pose_by_prim_path(f"/World/{scene_uid}/franka")[1]
    # Deactivate the franka robot
    prim = get_prim_at_path(f"/World/{scene_uid}/franka")
    if prim.IsActive() and prim.IsValid():
        prim.SetActive(False)
    # Create the AXRX5 robot
    prim = create_prim(
        prim_path=f"/World/{scene_uid}/AXRX5",
        prim_type="Xform",
        usd_path=os.path.join(
            default_config["ASSETS_DIR"],
            "robot_usds/X5A/X5A.usd",
        ),
        position=position,
        orientation=orientation,
    )
    # Create the AXRX5 robot object
    AXRX5 = Robot(
        prim_path=f"/World/{scene_uid}/AXRX5",
        name="AXRX5",
    )
    # Set default parameters for the AXRX5 robot
    AXRX5.set_solver_position_iteration_count(128)
    AXRX5.set_stabilization_threshold(0.005)
    AXRX5.set_solver_velocity_iteration_count(4)
    return AXRX5


def relate_franka_from_data(scene_uid: str) -> Franka:
    # Create the franka robot
    robot = Franka(
        prim_path=f"/World/{scene_uid}/franka",
    )
    # Set default parameters for the franka robot
    robot.set_solver_position_iteration_count(128)
    robot.set_enabled_self_collisions(True)
    robot.set_stabilization_threshold(0.005)
    robot.set_solver_velocity_iteration_count(16)
    return robot


def relate_franka_robotiq_from_data(scene_uid: str, default_config: dict) -> Robot:
    # Get the position and orientation of the franka robot
    position, orientation = get_world_pose_by_prim_path(f"/World/{scene_uid}/franka")
    # Deactivate the franka robot
    prim = get_prim_at_path(f"/World/{scene_uid}/franka")
    if prim.IsActive() and prim.IsValid():
        prim.SetActive(False)
    # Create the franka_robotiq robot
    prim = create_prim(
        prim_path=f"/World/{scene_uid}/robotiq",
        prim_type="Xform",
        usd_path=os.path.join(
            default_config["ASSETS_DIR"], "robot_usds/robotiq/robot_mimic.usd"
        ),
    )
    # Create the franka_robotiq robot object
    franka_robotiq = Robot(
        prim_path=f"/World/{scene_uid}/robotiq",
        name="franka_robotiq",
    )
    # Set default parameters for the franka_robotiq robot
    franka_robotiq.set_solver_position_iteration_count(124)
    franka_robotiq.set_stabilization_threshold(0.005)
    franka_robotiq.set_solver_velocity_iteration_count(4)
    franka_robotiq.set_world_pose(position, orientation)
    return franka_robotiq


def relate_lift2_from_data(
    scene_uid: str,
    default_config: dict,
    position: np.ndarray = np.array([-0.45, 0.0, 0.5]),
    orientation: np.ndarray = np.array([1.0, 0.0, 0.0, 0.0]),
) -> Robot:
    # Deactivate the franka robot
    prim = get_prim_at_path(f"/World/{scene_uid}/franka")
    if prim.IsValid() and prim.IsActive():
        prim.SetActive(False)
    # Create the lift2 robot
    prim = create_prim(
        prim_path=f"/World/{scene_uid}/lift2",
        prim_type="Xform",
        usd_path=os.path.join(
            default_config["ASSETS_DIR"], "robot_usds/lift2/robot.usd"
        ),
        position=position,
        orientation=orientation,
    )
    # Create the lift2 robot object
    lift2 = Robot(
        prim_path=f"/World/{scene_uid}/lift2",
        name="lift2",
    )
    # Set default parameters for the lift2 robot
    lift2.set_solver_position_iteration_count(128)
    lift2.set_stabilization_threshold(0.005)
    lift2.set_solver_velocity_iteration_count(4)
    return lift2


def relate_franka_robotiq_simbox_from_data(
    scene_uid: str, default_config: dict
) -> Robot:
    # Get the position and orientation of the franka robot
    position, orientation = get_world_pose_by_prim_path(f"/World/{scene_uid}/franka")
    # Deactivate the franka robot
    prim = get_prim_at_path(f"/World/{scene_uid}/franka")
    if prim.IsValid() and prim.IsActive():
        prim.SetActive(False)
    # Create the franka_robotiq robot
    prim = create_prim(
        prim_path=f"/World/{scene_uid}/robotiq",
        prim_type="Xform",
        usd_path=os.path.join(
            default_config["ASSETS_DIR"], "robot_usds/robotiq_simbox/robot.usd"
        ),
    )
    # Create the franka_robotiq robot object
    franka_robotiq = Robot(
        prim_path=f"/World/{scene_uid}/robotiq",
        name="franka_robotiq",
    )
    # Set default parameters for the franka_robotiq robot
    franka_robotiq.set_solver_position_iteration_count(124)
    franka_robotiq.set_stabilization_threshold(0.005)
    franka_robotiq.set_solver_velocity_iteration_count(4)
    franka_robotiq.set_world_pose(position, orientation)
    return franka_robotiq
