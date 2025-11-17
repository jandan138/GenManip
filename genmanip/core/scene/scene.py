"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from dataclasses import dataclass
from typing import Any

from omni.isaac.core import World  # type: ignore
from omni.isaac.core.prims import XFormPrim  # type: ignore
from omni.isaac.core.robots.robot import Robot  # type: ignore
from omni.isaac.core.articulations import Articulation  # type: ignore
from omni.isaac.core.materials.omni_pbr import OmniPBR  # type: ignore
from omni.isaac.core.utils.prims import delete_prim, is_prim_path_valid  # type: ignore
from omni.isaac.sensor import Camera  # type: ignore
from pxr import UsdGeom  # type: ignore

from genmanip.core.robot.embodiment import BaseEmbodiment
from genmanip.thirdparty.curobo_planner import CuroboPlanner


@dataclass
class Assets:
    wall_texture: list[str]
    domelight: list[str]
    table: list[str]
    table_mdl: list[str]
    scene: list[str]
    misc: list[str]


@dataclass
class Background:
    wall: dict[str, XFormPrim] | None
    wall_textures: list[OmniPBR] | None

@dataclass
class CacheDict:
    meshDict: dict[str, Any]
    pointcloudDict: dict[str, Any]
    
@dataclass
class Scene:
    world: World
    object_list: dict[str, XFormPrim]
    robot_info: dict[str, BaseEmbodiment]
    camera_list: dict[str, Camera]
    articulation_list: dict[str, Articulation]
    articulation_part_list: dict[str, XFormPrim]
    background: Background
    assets_list: Assets
    planner_list: list[CuroboPlanner]
    tcp_configs: dict[str, dict[str, float]]
    cacheDict: dict[str, Any]
