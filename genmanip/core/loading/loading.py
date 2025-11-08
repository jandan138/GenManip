"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import copy
import os
import random

from mplib import Planner as MplibPlanner
import numpy as np
from scipy.spatial.transform import Rotation as R
from tqdm import tqdm

import omni.replicator.core as rep  # type: ignore
import omni.usd  # type: ignore
from omni.isaac.core import World  # type: ignore
from omni.isaac.core.articulations import Articulation  # type: ignore
from omni.isaac.core.materials.omni_pbr import OmniPBR  # type: ignore
from omni.isaac.core.prims import XFormPrim  # type: ignore
from omni.isaac.core.robots.robot import Robot  # type: ignore
from omni.isaac.core.utils.prims import delete_prim, is_prim_path_valid  # type: ignore
from omni.isaac.sensor import Camera  # type: ignore
from pxr import UsdGeom  # type: ignore

from genmanip.core.loading.preload_rules import (
    apply_rule,
    collect_all_colors,
    collect_all_materials,
    collect_all_shapes,
    generate_long_horizon_by_category,
    generate_long_horizon_by_color,
    generate_long_horizon_by_materials,
    generate_long_horizon_by_shape,
)
from genmanip.core.loading.robot import (
    relate_aloha_split_from_data,
    relate_franka_from_data,
    relate_franka_robotiq_from_data,
    relate_franka_robotiq_simbox_from_data,
    relate_lift2_from_data,
)
from genmanip.core.loading.utils import reset_object_xyz, collect_world_pose_list
from genmanip.core.pointcloud.pointcloud import (
    objectList2meshList,
    get_mesh_info_by_load,
)
from genmanip.core.robot.embodiment import (
    FrankaNormalEmbodiment,
    FrankaRobotiqEmbodiment,
    AlohaSplitEmbodiment,
    Lift2Embodiment,
)
from genmanip.core.robot.embodiment import BaseEmbodiment  # type: ignore
from genmanip.core.robot.franka import get_franka_PD_controller
from genmanip.core.sensor.camera import setup_camera, get_src
from genmanip.core.usd_utils import (
    add_physics_material,
    add_usd_to_world,
    create_omni_pbr,
    clean_prim_velocity,
    has_collision_api,
    remove_contact_offset,
    remove_colliders,
    set_colliders,
    set_contact_offset,
    set_gravity,
    set_mass,
    set_rigid_body,
    set_rigid_body_CCD,
    set_semantic_label,
    setup_physics_scene,
)
from genmanip.thirdparty.curobo_planner import get_curobo_planner, CuroboPlanner
from genmanip.thirdparty.mplib_planner import get_mplib_planner
from genmanip.utils.utils import generate_hash
from genmanip.utils.file_utils import load_yaml, load_json
from genmanip_bench.evaluate.evaluator import Evaluator
from object_utils.object_pool import ObjectPool


def setup_walls_and_materials(
    uuid: str, world: World, object_list: dict
) -> tuple[list[XFormPrim], list[OmniPBR]]:
    walls = []
    wall_position_list = [[0, -25, 10], [25, 0, 10], [0, 25, 10], [-25, 0, 10]]
    wall_textures = []
    for i in range(5):
        mat = create_omni_pbr(
            f"/World/{uuid}/obj_defaultGroundPlane/GroundPlane/Wall{i}_Material"
        )
        wall_textures.append(mat)
    for i in range(4):
        prim_path = f"/World/{uuid}/obj_defaultGroundPlane/GroundPlane/Wall{i}"
        plane_geom = UsdGeom.Plane.Define(world.stage, prim_path)
        plane_geom.CreateLengthAttr().Set(20)
        plane_geom.CreateWidthAttr().Set(50)
        plane_xform = XFormPrim(
            prim_path,
            scale=[1, 1, 1],
            translation=wall_position_list[i],
            orientation=R.from_euler("xyz", [90, 0, 90 * i], degrees=True).as_quat()[
                [3, 0, 1, 2]
            ],
        )
        walls.append(plane_xform)
        plane_xform.apply_visual_material(wall_textures[i])
    default_ground_plane_xform = XFormPrim(
        object_list["defaultGroundPlane"].prim_path + "/GroundPlane/CollisionMesh"
    )
    default_ground_plane_xform.apply_visual_material(wall_textures[4])
    return walls, wall_textures


def collect_articulation_list(
    scene: dict, articulation_list: dict[str, Articulation]
) -> dict[str, np.ndarray]:
    init_positions_list = {}
    for articulation_id, articulation in articulation_list.items():
        if scene["articulation_data"][articulation_id]["is_articulated"]:
            init_positions_list[articulation_id] = articulation.get_joint_positions()
    return init_positions_list


def create_camera_list(
    camera_data: dict[str, dict],
    uuid: str,
    rendering_dt: float = 1 / 60.0,
    only_depth_rep_for_camera: bool = False,
) -> dict[str, Camera]:
    camera_list = {}
    for key in camera_data:
        rp = rep.create.render_product(
            rep.create.camera(),
            (
                camera_data[key]["resolution"][0],
                camera_data[key]["resolution"][1],
            ),
        )
        if camera_data[key]["exists"]:
            camera_list[key] = Camera(
                prim_path=f'/World/{uuid}{camera_data[key]["prim_path"]}',
                name=camera_data[key]["name"],
                frequency=1 / rendering_dt,
                resolution=(
                    camera_data[key]["resolution"][0],
                    camera_data[key]["resolution"][1],
                ),
                render_product_path=rp.path,
            )
            if "position" in camera_data[key] and "orientation" in camera_data[key]:
                camera_list[key].set_local_pose(
                    camera_data[key]["position"], camera_data[key]["orientation"]
                )
        else:
            camera_list[key] = Camera(
                prim_path=f'/Camera{camera_data[key]["prim_path"]}',
                name=camera_data[key]["name"],
                frequency=1 / rendering_dt,
                resolution=(
                    camera_data[key]["resolution"][0],
                    camera_data[key]["resolution"][1],
                ),
                position=camera_data[key]["position"],
                orientation=camera_data[key]["orientation"],
                render_product_path=rp.path,
            )
        if "camera_params" not in camera_data[key]:
            camera_data[key]["camera_params"] = None
        setup_camera(
            camera_list[key],
            camera_cfg=camera_data[key],
            only_depth_rep_for_camera=only_depth_rep_for_camera,
        )
    return camera_list


def add_background_scene(
    scene: dict,
    usd_path: str,
    position: np.ndarray,
    scale: list[float] = [0.01, 0.01, 0.01],
) -> None:
    background_xform, background_uuid = load_world_xform_prim(
        os.path.join(usd_path),
        scene_prim_path=f"/World/background_{usd_path.split('/')[-1].split('.')[0]}",
    )
    background_xform.set_world_pose(position=position)
    background_xform.set_local_scale(scale)
    if (
        "defaultGroundPlane" in scene["object_list"]
        and scene["object_list"]["defaultGroundPlane"].prim.IsActive()
    ):
        scene["object_list"]["defaultGroundPlane"].prim.SetActive(False)


def get_object_list(
    uuid: str, scene_xform: XFormPrim, table_uid: str
) -> dict[str, XFormPrim]:
    object_list = {}
    for scene in scene_xform.prim.GetAllChildren():
        for object in scene.GetAllChildren():
            if str(object.GetPath()).split("/")[-1] == "franka":
                set_semantic_label(
                    str(object.GetPath()), str(object.GetPath()).split("/")[-1]
                )
                continue
            if "camera" in str(object.GetPath()).split("/")[-1]:
                continue
            if str(object.GetPath()).split("/")[-1][:4] != "obj_":
                pass
            elif str(object.GetPath()).split("/")[-1][4:] != table_uid:
                object_list[str(object.GetPath()).split("/")[-1][4:]] = (
                    relate_object_from_data(
                        scene_uid=uuid,
                        uid=str(object.GetPath()).split("/")[-1][4:],
                    )
                )
            else:
                object_list["00000000000000000000000000000000"] = (
                    relate_object_from_data(
                        scene_uid=uuid, uid=str(object.GetPath()).split("/")[-1][4:]
                    )
                )
            set_semantic_label(
                str(object.GetPath()), str(object.GetPath()).split("/")[-1][4:]
            )
    return object_list


def load_camera_from_data(camera_data: dict[str, dict], uuid: str) -> Camera:
    camera = Camera(
        prim_path=f"/World/{uuid}/" + camera_data["name"],
        name=camera_data["name"],
        position=camera_data["position"],
        frequency=camera_data["frequency"],
        resolution=(camera_data["resolution_width"], camera_data["resolution_height"]),
        orientation=camera_data["orientation"],
    )
    setup_camera(camera, camera_cfg=camera_data)
    return camera


def load_world_xform_prim(
    scene_path: str, scene_prim_path: str = "/World"
) -> tuple[XFormPrim, str]:
    scene_path = os.path.abspath(scene_path)
    omni.usd.get_context().new_stage()
    omni.usd.get_context().open_stage(scene_path)
    scene_xform = XFormPrim(
        "/World",
        name="World",
    )
    uuid = str(scene_xform.prim.GetAllChildren()[0].GetPath()).split("/")[-1]
    return scene_xform, uuid


def relate_object_from_data(scene_uid: str, uid: str) -> XFormPrim:
    return XFormPrim(f"/World/{scene_uid}/obj_{uid}")


def get_embodiment(robot_config: dict, robot: Robot) -> BaseEmbodiment:
    if robot_config["type"] == "franka":
        if robot_config["config"]["gripper_type"] == "panda_hand":
            return FrankaNormalEmbodiment(robot)
        elif robot_config["config"]["gripper_type"] == "robotiq":
            return FrankaRobotiqEmbodiment(robot)
    elif robot_config["type"] == "aloha_split":
        if robot_config["config"]["gripper_type"] == "aloha_split":
            return AlohaSplitEmbodiment(robot)
        else:
            raise ValueError(f"Unsupported robot config: {robot_config}")
    elif robot_config["type"] == "lift2":
        if robot_config["config"]["gripper_type"] == "lift2":
            return Lift2Embodiment(robot)
        else:
            raise ValueError(f"Unsupported robot config: {robot_config}")
    else:
        raise ValueError(f"Unsupported robot type: {robot_config['type']}")


def add_robot_to_scene(uuid: str, robot_config: dict, default_config: dict) -> Robot:
    if robot_config["type"] == "franka":
        if robot_config["config"]["gripper_type"] == "panda_hand":
            return relate_franka_from_data(uuid)
        elif robot_config["config"]["gripper_type"] == "robotiq":
            return relate_franka_robotiq_from_data(uuid, default_config)
        elif robot_config["config"]["gripper_type"] == "robotiq_simbox":
            robot_config["config"]["gripper_type"] = "robotiq"
            return relate_franka_robotiq_simbox_from_data(uuid, default_config)
        else:
            raise ValueError(f"Unsupported robot config: {robot_config}")
    elif robot_config["type"] == "aloha_split":
        if robot_config["config"]["gripper_type"] == "aloha_split":
            return relate_aloha_split_from_data(uuid, default_config)
        else:
            raise ValueError(f"Unsupported robot config: {robot_config}")
    elif robot_config["type"] == "lift2":
        if robot_config["config"]["gripper_type"] == "lift2":
            return relate_lift2_from_data(uuid, default_config)
        else:
            raise ValueError(f"Unsupported robot config: {robot_config}")
    else:
        raise ValueError(f"Unsupported robot type: {robot_config['type']}")


def add_robot_view(robot_config: dict, robot: Robot) -> Robot:
    if robot_config["type"] == "franka":
        if robot_config["config"]["gripper_type"] == "panda_hand":
            return get_franka_PD_controller(robot, max_joint_velocities=[2.0] * 9)
        elif robot_config["config"]["gripper_type"] == "robotiq":
            return get_franka_PD_controller(robot, max_joint_velocities=[2.0] * 13)
        else:
            raise ValueError(f"Unsupported robot config: {robot_config}")
    else:
        raise ValueError(f"Unsupported robot type: {robot_config['type']}")


def preload_object(
    object_path: str,
    uuid: str,
    uid: str,
    world: World,
    add_rigid_body: bool = True,
    add_colliders: bool = True,
    remove_collider: bool = False,
) -> XFormPrim:
    if not os.path.exists(object_path):
        raise ValueError(f"Object path {object_path} does not exist")
    print(f"Object {uid} loading")
    obj_xform = add_usd_to_world(
        asset_path=object_path,
        prim_path=f"/World/{uuid}/obj_{uid}",
        name=f"obj_{uid}",
        translation=[1000.0, 0.0, 0.0],
        orientation=[0.5, 0.5, 0.5, 0.5],
        scale=None,
        add_rigid_body=add_rigid_body,
        add_colliders=add_colliders,
        collision_approximation="convexDecomposition",
    )
    if remove_collider:
        remove_colliders(obj_xform.prim_path)
    if obj_xform is not None:
        world.step()
        if obj_xform.prim.IsActive():
            obj_xform.prim.SetActive(False)
        print(f"Object {uid} loaded")
    else:
        delete_prim(f"/World/{uuid}/obj_{uid}")
    return obj_xform


def process_long_horizon_replacement(
    scene: dict, default_config: dict, demogen_config: dict
) -> tuple[dict, dict]:
    replacement_config = demogen_config["domain_randomization"]["replace_object"][
        "replacement"
    ]
    folder_path = os.path.join(
        default_config["ASSETS_DIR"],
        replacement_config["random_long_horizon"]["folder_path"],
    )
    usd_list = os.listdir(folder_path)
    usd_list = [
        usd for usd in usd_list if not os.path.isdir(os.path.join(folder_path, usd))
    ]
    types = ["category", "materials", "color", "shape"]
    while True:
        type = random.choice(types)
        if type == "category":
            replacement_config, meta_info = generate_long_horizon_by_category(
                scene,
                usd_list,
                demogen_config["domain_randomization"]["replace_object"]["replacement"][
                    "random_long_horizon"
                ]["folder_path"],
            )
        elif type == "materials":
            replacement_config, meta_info = generate_long_horizon_by_materials(
                scene,
                usd_list,
                demogen_config["domain_randomization"]["replace_object"]["replacement"][
                    "random_long_horizon"
                ]["folder_path"],
            )
        elif type == "color":
            replacement_config, meta_info = generate_long_horizon_by_color(
                scene,
                usd_list,
                demogen_config["domain_randomization"]["replace_object"]["replacement"][
                    "random_long_horizon"
                ]["folder_path"],
            )
        elif type == "shape":
            replacement_config, meta_info = generate_long_horizon_by_shape(
                scene,
                usd_list,
                demogen_config["domain_randomization"]["replace_object"]["replacement"][
                    "random_long_horizon"
                ]["folder_path"],
            )
        if replacement_config is None:
            continue
        obj1_list = copy.deepcopy(usd_list)
        for rule in replacement_config["obj1"]["rule"]:
            obj1_list = apply_rule(rule, obj1_list, scene["object_pool"])
        obj2_list = copy.deepcopy(usd_list)
        for rule in replacement_config["obj2"]["rule"]:
            obj2_list = apply_rule(rule, obj2_list, scene["object_pool"])
        background_list = copy.deepcopy(usd_list)
        for rule in replacement_config["background"]["rule"]:
            background_list = apply_rule(rule, background_list, scene["object_pool"])
        if len(obj1_list) > 5 and len(obj2_list) > 5 and len(background_list) > 5:
            break
    return replacement_config, meta_info


def preprocess_object_config(
    scene: dict, default_config: dict, demogen_config: dict
) -> dict:
    object_config_backup = copy.deepcopy(demogen_config["object_config"])
    while True:
        object_config = copy.deepcopy(object_config_backup)
        color_list = collect_all_colors(scene["object_pool"])
        shape_list = collect_all_shapes(scene["object_pool"])
        material_list = collect_all_materials(scene["object_pool"])
        object_config_keys = list(object_config.keys())
        object_config_keys.sort()
        color_project_dict = {}
        shape_project_dict = {}
        material_project_dict = {}
        for key in object_config_keys:
            if object_config[key]["type"] == "rule":
                for rule in object_config[key]["filter_rule"]:
                    if "retrieve_color_[" in rule:
                        color_index = rule.split("retrieve_color_[")[1].split("]")[0]
                        if color_index not in color_project_dict:
                            color_project_dict[color_index] = random.choice(color_list)
                    elif "retrieve_shape_[" in rule:
                        shape_index = rule.split("retrieve_shape_[")[1].split("]")[0]
                        if shape_index not in shape_project_dict:
                            shape_project_dict[shape_index] = random.choice(shape_list)
                    elif "retrieve_material_[" in rule:
                        material_index = rule.split("retrieve_material_[")[1].split(
                            "]"
                        )[0]
                        if material_index not in material_project_dict:
                            material_project_dict[material_index] = random.choice(
                                material_list
                            )
                    elif "retrieve_not_color_[" in rule:
                        color_index = rule.split("retrieve_not_color_[")[1].split("]")[
                            0
                        ]
                        if color_index not in color_project_dict:
                            color_project_dict[color_index] = random.choice(color_list)
                    elif "retrieve_not_shape_[" in rule:
                        shape_index = rule.split("retrieve_not_shape_[")[1].split("]")[
                            0
                        ]
                        if shape_index not in shape_project_dict:
                            shape_project_dict[shape_index] = random.choice(shape_list)
                    elif "retrieve_not_material_[" in rule:
                        material_index = rule.split("retrieve_not_material_[")[1].split(
                            "]"
                        )[0]
                        if material_index not in material_project_dict:
                            material_project_dict[material_index] = random.choice(
                                material_list
                            )
        for key in object_config_keys:
            if object_config[key]["type"] == "rule":
                for rule_idx in range(len(object_config[key]["filter_rule"])):
                    rule = object_config[key]["filter_rule"][rule_idx]
                    if "retrieve_color_[" in rule:
                        color_index = rule.split("retrieve_color_[")[1].split("]")[0]
                        rule = f"retrieve_color_{color_project_dict[color_index]}"
                    elif "retrieve_shape_[" in rule:
                        shape_index = rule.split("retrieve_shape_[")[1].split("]")[0]
                        rule = f"retrieve_shape_{shape_project_dict[shape_index]}"
                    elif "retrieve_material_[" in rule:
                        material_index = rule.split("retrieve_material_[")[1].split(
                            "]"
                        )[0]
                        rule = (
                            f"retrieve_material_{material_project_dict[material_index]}"
                        )
                    elif "retrieve_not_color_[" in rule:
                        color_index = rule.split("retrieve_not_color_[")[1].split("]")[
                            0
                        ]
                        rule = f"retrieve_not_color_{color_project_dict[color_index]}"
                    elif "retrieve_not_shape_[" in rule:
                        shape_index = rule.split("retrieve_not_shape_[")[1].split("]")[
                            0
                        ]
                        rule = f"retrieve_not_shape_{shape_project_dict[shape_index]}"
                    elif "retrieve_not_material_[" in rule:
                        material_index = rule.split("retrieve_not_material_[")[1].split(
                            "]"
                        )[0]
                        rule = f"retrieve_not_material_{material_project_dict[material_index]}"
                    object_config[key]["filter_rule"][rule_idx] = rule
        is_vaild = True
        for key in object_config_keys:
            if object_config[key]["type"] == "load_object_from_path":
                folder_path = os.path.join(
                    default_config["ASSETS_DIR"],
                    object_config[key]["path"],
                )
                usd_list = os.listdir(folder_path)
                usd_list = [
                    usd
                    for usd in usd_list
                    if usd.endswith(".usd")
                    and not os.path.isdir(os.path.join(folder_path, usd))
                ]
                usd_list_len = len(usd_list)
                for rule in object_config[key]["filter_rule"]:
                    usd_list = apply_rule(rule, usd_list, scene["object_pool"])
                if len(usd_list) < 5 and len(usd_list) < usd_list_len:
                    is_vaild = False
                    break
        if is_vaild:
            break
    return object_config


def preload_objects(
    scene: dict,
    default_config: dict,
    demogen_config: dict,
    without_planning: bool = False,
) -> None:
    demogen_config["object_config"] = preprocess_object_config(
        scene, default_config, demogen_config
    )
    scene["cacheDict"]["replacement"] = {}
    scene["cacheDict"]["preloaded_object_list"] = {}
    scene["cacheDict"]["preloaded_object_path_list"] = {}
    scene["cacheDict"]["preloaded_object_uid_list"] = {}
    scene["cacheDict"]["preload_hash_feature"] = {}
    scene["cacheDict"]["preload_object_meta_info"] = {}
    object_config = demogen_config["object_config"]
    object_config_keys = list(object_config.keys())
    object_config_keys.sort()
    for key in object_config_keys:
        if object_config[key]["type"] == "load_object_from_path":
            origin_text = object_config[key]["path"]
            rules = object_config[key]["filter_rule"]
            rules.sort()
            for rule in rules:
                origin_text += rule
            scene["cacheDict"]["preload_hash_feature"][key] = generate_hash(origin_text)
        elif object_config[key]["type"] == "existed_object":
            origin_text = object_config[key]["uid_list"]
            if not isinstance(origin_text, list):
                origin_text = [origin_text]
            origin_text.sort()
            concat_text = ""
            for uid in origin_text:
                concat_text += uid
            scene["cacheDict"]["preload_hash_feature"][key] = generate_hash(concat_text)
        elif object_config[key]["type"] == "add_additional_object_from_path":
            scene["cacheDict"]["preload_hash_feature"][key] = generate_hash(
                object_config[key]["path"]
            )
            if not object_config[key]["path"].endswith(".usd"):
                object_config[key]["max_cached_num"] = len(
                    os.listdir(
                        os.path.join(
                            default_config["ASSETS_DIR"],
                            object_config[key]["path"],
                        )
                    )
                )
            else:
                object_config[key]["max_cached_num"] = 1
    max_cached_num_dict = {}
    for key in object_config_keys:
        if object_config[key]["type"] == "existed_object":
            continue
        if scene["cacheDict"]["preload_hash_feature"][key] not in max_cached_num_dict:
            max_cached_num_dict[scene["cacheDict"]["preload_hash_feature"][key]] = (
                object_config[key]["max_cached_num"]
            )
        else:
            max_cached_num_dict[scene["cacheDict"]["preload_hash_feature"][key]] = max(
                max_cached_num_dict[scene["cacheDict"]["preload_hash_feature"][key]],
                object_config[key]["max_cached_num"],
            )
    sorted_object_config_keys = sorted(
        object_config_keys,
        key=lambda x: object_config[x]["type"] == "add_additional_object_from_path",
        reverse=True,
    )
    for key in sorted_object_config_keys:
        if (
            scene["cacheDict"]["preload_hash_feature"][key]
            in scene["cacheDict"]["preloaded_object_uid_list"]
        ):
            continue
        else:
            if object_config[key]["type"] == "add_additional_object_from_path":
                folder_path = os.path.join(
                    default_config["ASSETS_DIR"],
                    object_config[key]["path"],
                )
                if folder_path.endswith(".usd"):
                    usd_list = [folder_path.split("/")[-1]]
                    folder_path = os.path.dirname(folder_path)
                    object_config[key]["uid"] = (
                        object_config[key]["path"].split("/")[-1].split(".")[0]
                    )
                    object_config[key]["path"] = os.path.dirname(
                        object_config[key]["path"]
                    )
                else:
                    usd_list = os.listdir(folder_path)
                    usd_list = [
                        usd
                        for usd in usd_list
                        if not os.path.isdir(os.path.join(folder_path, usd))
                    ]
                max_cached_num = np.clip(
                    max_cached_num_dict[
                        scene["cacheDict"]["preload_hash_feature"][key]
                    ],
                    0,
                    len(usd_list),
                )
                usd_list = random.sample(usd_list, max_cached_num)
                scene["cacheDict"]["preloaded_object_uid_list"][
                    scene["cacheDict"]["preload_hash_feature"][key]
                ] = []
                for obj in tqdm(usd_list):
                    uid = obj.split(".")[0]
                    if (
                        os.path.isdir(os.path.join(folder_path, obj))
                        or uid not in scene["object_pool"].uids
                    ):
                        continue
                    scene["cacheDict"]["preloaded_object_uid_list"][
                        scene["cacheDict"]["preload_hash_feature"][key]
                    ].append(uid)
                    if (
                        uid in scene["cacheDict"]["preloaded_object_list"]
                        or uid in scene["object_list"]
                    ):
                        continue
                    obj_xform = preload_object(
                        os.path.join(folder_path, obj),
                        scene["uuid"],
                        uid,
                        scene["world"],
                        add_colliders=not without_planning
                        and not object_config[key].get("without_colliders", False),
                        add_rigid_body=not without_planning
                        and not object_config[key].get("is_not_rigid", False),
                    )
                    scene["cacheDict"]["preload_object_meta_info"][uid] = {
                        "add_colliders": not without_planning
                        and not object_config[key].get("without_colliders", False),
                        "add_rigid_body": not without_planning
                        and not object_config[key].get("is_not_rigid", False),
                    }
                    joints_default_state = scene["robot_info"]["robot_list"][
                        0
                    ].robot.get_joints_default_state()
                    scene["robot_info"]["robot_list"][0].robot.set_joint_positions(
                        joints_default_state.positions
                    )
                    scene["robot_info"]["robot_list"][0].robot.set_joint_velocities(
                        joints_default_state.velocities
                    )
                    scene["cacheDict"]["preloaded_object_list"][uid] = obj_xform
                    scene["cacheDict"]["preloaded_object_path_list"][uid] = (
                        os.path.join(
                            object_config[key]["path"],
                            obj,
                        )
                    )
                    scene["object_list"][uid] = obj_xform
                    if not scene["object_list"][uid].prim.IsActive():
                        scene["object_list"][uid].prim.SetActive(True)
                    scene["cacheDict"]["meshDict"][uid] = get_mesh_info_by_load(
                        scene["object_list"][uid],
                        os.path.join(
                            default_config["ASSETS_DIR"],
                            "mesh_data",
                            demogen_config["task_name"],
                            os.path.dirname(
                                scene["cacheDict"]["preloaded_object_path_list"][uid]
                            ),
                            f"{uid}.obj",
                        ),
                    )
            elif object_config[key]["type"] == "existed_object":
                scene["cacheDict"]["preloaded_object_uid_list"][
                    scene["cacheDict"]["preload_hash_feature"][key]
                ] = object_config[key]["uid_list"]
                for uid in object_config[key]["uid_list"]:
                    if uid in scene["object_list"]:
                        scene["cacheDict"]["preloaded_object_list"][uid] = scene[
                            "object_list"
                        ][uid]
                    else:
                        scene["cacheDict"]["preloaded_object_list"][uid] = scene[
                            "articulation_list"
                        ][uid]
            elif object_config[key]["type"] == "load_object_from_path":
                folder_path = os.path.join(
                    default_config["ASSETS_DIR"],
                    object_config[key]["path"],
                )
                usd_list = os.listdir(folder_path)
                usd_list = [
                    usd
                    for usd in usd_list
                    if not os.path.isdir(os.path.join(folder_path, usd))
                    and str(usd).endswith(".usd")
                ]
                for rule in object_config[key]["filter_rule"]:
                    usd_list = apply_rule(rule, usd_list, scene["object_pool"])
                max_cached_num = np.clip(
                    max_cached_num_dict[
                        scene["cacheDict"]["preload_hash_feature"][key]
                    ],
                    0,
                    len(usd_list),
                )
                usd_list = random.sample(usd_list, max_cached_num)
                scene["cacheDict"]["preloaded_object_uid_list"][
                    scene["cacheDict"]["preload_hash_feature"][key]
                ] = []
                if "replace_existed_object" in object_config[key]:
                    for uid in object_config[key]["replace_existed_object"]:
                        # if not uid in scene["cacheDict"]["preloaded_object_list"]:
                        scene["cacheDict"]["preloaded_object_list"][uid] = scene[
                            "object_list"
                        ][uid]
                        if scene["object_list"][uid].prim.IsActive():
                            scene["object_list"][uid].prim.SetActive(False)
                        scene["cacheDict"]["meshDict"].pop(uid)
                        scene["object_list"].pop(uid)
                    if not (
                        "option" in object_config[key]
                        and "remove_existed_object" in object_config[key]["option"]
                    ):
                        scene["cacheDict"]["preloaded_object_uid_list"][
                            scene["cacheDict"]["preload_hash_feature"][key]
                        ].extend(object_config[key]["replace_existed_object"])
                for obj in tqdm(usd_list):
                    uid = obj.split(".")[0]
                    if (
                        os.path.isdir(os.path.join(folder_path, obj))
                        or uid not in scene["object_pool"].uids
                    ) and not (
                        "option" in object_config[key]
                        and "plain_replace" in object_config[key]["option"]
                    ):
                        continue
                    scene["cacheDict"]["preloaded_object_uid_list"][
                        scene["cacheDict"]["preload_hash_feature"][key]
                    ].append(uid)
                    if (
                        uid in scene["cacheDict"]["preloaded_object_list"]
                        or uid in scene["object_list"]
                    ):
                        continue
                    obj_xform = preload_object(
                        os.path.join(folder_path, obj),
                        scene["uuid"],
                        uid,
                        scene["world"],
                        add_colliders=not without_planning
                        and not object_config[key].get("without_colliders", False),
                        add_rigid_body=not without_planning
                        and not object_config[key].get("is_not_rigid", False),
                    )
                    scene["cacheDict"]["preload_object_meta_info"][uid] = {
                        "add_colliders": not without_planning
                        and not object_config[key].get("without_colliders", False),
                        "add_rigid_body": not without_planning
                        and not object_config[key].get("is_not_rigid", False),
                    }
                    joints_default_state = scene["robot_info"]["robot_list"][
                        0
                    ].robot.get_joints_default_state()
                    scene["robot_info"]["robot_list"][0].robot.set_joint_positions(
                        joints_default_state.positions
                    )
                    scene["robot_info"]["robot_list"][0].robot.set_joint_velocities(
                        joints_default_state.velocities
                    )
                    scene["cacheDict"]["preloaded_object_list"][uid] = obj_xform
                    scene["cacheDict"]["preloaded_object_path_list"][uid] = (
                        os.path.join(
                            object_config[key]["path"],
                            obj,
                        )
                    )


def create_planner(
    scene: dict, demogen_config: dict, current_dir: str
) -> list[CuroboPlanner | MplibPlanner]:
    planner_name = demogen_config["generation_config"]["planner"]
    if planner_name == "mplib":
        return [
            get_mplib_planner(robot.robot, robot_config["type"], current_dir)
            for robot, robot_config in zip(
                scene["robot_info"]["robot_list"],
                demogen_config["robots"],
            )
        ]
    elif planner_name == "curobo":
        return [
            get_curobo_planner(
                robot.robot, robot_config["type"], scene["world"], current_dir
            )
            for robot, robot_config in zip(
                scene["robot_info"]["robot_list"],
                demogen_config["robots"],
            )
        ]
    else:
        raise ValueError(f"Unsupported planner type: {planner_name}")


def add_articulation_to_scene(uid: str, uuid: str, world: World) -> Articulation:
    articulation = Articulation(
        prim_path=f"/World/{uuid}/obj_{uid}",
        name=f"obj_{uid}",
    )
    world.scene.add(articulation)
    return articulation


def load_articulation_data(scene: dict, demogen_config: dict, current_dir: str) -> None:
    if "articulation_data_path" in demogen_config["domain_randomization"]:
        scene["articulation_data"] = load_json(
            os.path.join(
                current_dir,
                "assets/objects",
                f"{demogen_config['domain_randomization']['articulation_data_path']}.json",
            )
        )
    else:
        scene["articulation_data"] = load_json(
            os.path.join(current_dir, "assets/objects/articulation_data.json")
        )


def load_object_pool(scene: dict, demogen_config: dict, current_dir: str) -> None:
    if "object_data_path" in demogen_config["domain_randomization"]:
        scene["object_pool"] = ObjectPool(
            os.path.join(
                current_dir,
                "assets/objects",
                f"{demogen_config['domain_randomization']['object_data_path']}.pickle",
            )
        )
    else:
        scene["object_pool"] = ObjectPool(
            os.path.join(current_dir, "assets/objects/object_v7.pickle")
        )


def set_articulation(scene: dict, demogen_config: dict, world: World) -> None:
    for key in demogen_config["generation_config"]["articulation"]:
        # todo: remove "pan" from "is_articulated", or change key to "have_joint"
        if scene["articulation_data"][key]["is_articulated"]:
            scene["articulation_list"][key] = add_articulation_to_scene(
                key, scene["uuid"], world
            )
        else:
            scene["articulation_list"][key] = scene["object_list"][key]
    world.reset()
    for articulation in scene["articulation_list"].values():
        if scene["articulation_data"][key]["is_articulated"]:
            articulation._articulation_view.initialize()
    world.initialize_physics()
    for _ in range(10):
        world.step()
    for arti_id, articulation in scene["articulation_list"].items():
        if scene["articulation_data"][key]["is_articulated"]:
            if (
                arti_id in demogen_config["generation_config"]["articulation"]
                and "target_positions"
                in demogen_config["generation_config"]["articulation"][arti_id]
            ):
                articulation._articulation_view.set_joint_positions(
                    demogen_config["generation_config"]["articulation"][arti_id][
                        "target_positions"
                    ]
                )
    for _ in range(10):
        world.step()


def parse_articulation(scene: dict, demogen_config: dict) -> None:
    for arti_id, articulation in scene["articulation_list"].items():
        arti_parts = scene["articulation_data"][arti_id]["part"]
        arti_prim = scene["object_list"][arti_id]
        arti_prim_path = arti_prim.prim_path
        for part_name, part_group in arti_parts.items():
            part_prim_path = arti_prim_path + f"/Instance/{part_group}"
            arti_part = f"{arti_id}_{part_name}"
            scene["object_list"][arti_part] = XFormPrim(part_prim_path)
            scene["articulation_part_list"][arti_part] = XFormPrim(part_prim_path)
        scene["object_list"].pop(arti_id)


def parse_articulation_from_object_config(demogen_config: dict) -> None:
    demogen_config["generation_config"]["articulation"] = {}
    for key in demogen_config["object_config"]:
        if demogen_config["object_config"][key][
            "type"
        ] == "existed_object" and demogen_config["object_config"][key].get(
            "is_articulated", False
        ):
            for uid in demogen_config["object_config"][key]["uid_list"]:
                info = {}
                info["target_positions"] = demogen_config["object_config"][key][
                    "target_positions"
                ]
                info["is_articulated"] = demogen_config["object_config"][key][
                    "is_articulated"
                ]
                demogen_config["generation_config"]["articulation"][uid] = info


def build_scene_from_config(
    demogen_config: dict,
    default_config: dict,
    current_dir: str,
    physics_dt: float = 1 / 60.0,
    rendering_dt=1 / 60.0,
    is_eval: bool = False,
    is_render: bool = False,
    only_depth_rep_for_camera: bool = False,
    save_pointcloud: bool = False,
) -> dict:
    """
    Build a complete 3D scene from configuration files for robotic manipulation tasks.

    This function creates and initializes a comprehensive scene environment including:
    - Physics world with configurable timesteps
    - USD scene loading and object management
    - Robot(s) with embodiment and joint configurations
    - Camera system with rendering capabilities
    - Articulated objects with joint positioning
    - Background elements (walls, lighting, textures)
    - Motion planning components (when not in evaluation mode)

    Args:
        demogen_config (dict): Main configuration dictionary containing scene generation
            parameters, object configurations, robot settings, and domain randomization options.
        default_config (dict): Default configuration containing asset directory paths and
            global settings.
        current_dir (str): Current working directory path used for resolving relative paths
            in configuration files.
        physics_dt (float, optional): Physics simulation timestep in seconds. Defaults to 1/60.0.
        rendering_dt (float, optional): Rendering timestep in seconds. Defaults to 1/60.0.
        is_eval (bool, optional): Whether running in evaluation mode. When True, planners
            are not created. Defaults to False.
        is_render (bool, optional): Whether rendering is enabled. When True, camera
            resolution is adjusted for display. Defaults to False.

    Returns:
        dict: A comprehensive scene dictionary containing:
            - 'world': Isaac Sim World instance with physics and rendering
            - 'object_list': Dictionary of XFormPrim objects representing scene objects
            - 'robot_info': Dictionary with robot instances and views
            - 'camera_list': Dictionary of camera objects for observation
            - 'articulation_list': Dictionary of articulated objects with joints
            - 'articulation_part_list': Dictionary of articulated object parts
            - 'background': Background elements (walls, textures)
            - 'assets_list': Available assets for domain randomization
            - 'planner_list': Motion planners (when not in evaluation mode)
            - 'tcp_configs': Tool center point configurations
            - 'cacheDict': Cached mesh data for collision detection
            - 'meta_infos': Scene metadata and pose information
    """
    scene = {}

    # Load the scene usd file
    usd_name = demogen_config["usd_name"]
    scene["scene_xform"], scene["uuid"] = load_world_xform_prim(
        os.path.join(default_config["ASSETS_DIR"], f"{usd_name}.usda")
    )
    world = World(physics_dt=physics_dt, rendering_dt=rendering_dt)

    # Set physics parameters
    setup_physics_scene()
    scene["world"] = world

    # Get object list
    scene["object_list"] = get_object_list(
        scene["uuid"], scene["scene_xform"], demogen_config["table_uid"]
    )
    world_pose_list = collect_world_pose_list(scene["object_list"])

    # Load articulation data
    load_articulation_data(scene, demogen_config, current_dir)
    scene["articulation_list"] = {}
    scene["articulation_part_list"] = {}
    parse_articulation_from_object_config(demogen_config)
    if demogen_config["generation_config"]["articulation"]:
        set_articulation(scene, demogen_config, world)
        parse_articulation(scene, demogen_config)

    # Create robot list
    scene["robot_info"] = {}
    scene["robot_info"]["robot_list"] = [
        get_embodiment(
            robot_config,
            add_robot_to_scene(scene["uuid"], robot_config, default_config),
        )
        for robot_config in demogen_config["robots"]
    ]
    for robot in scene["robot_info"]["robot_list"]:
        robot = world.scene.add(robot.robot)

    # Load camera information
    camera_info = demogen_config["domain_randomization"]["cameras"]
    if camera_info["type"] == "fixed":
        camera_data = load_yaml(os.path.join(current_dir, camera_info["config_path"]))
    else:
        raise ValueError(f"Unsupported camera type: {camera_info['type']}")
    if is_render:
        if "camera1" in camera_data:
            camera_data["camera1"]["resolution"] = [640, 480]

    # Create camera list
    scene["camera_list"] = create_camera_list(
        camera_data, scene["uuid"], rendering_dt, only_depth_rep_for_camera
    )

    world.reset()

    for robot, robot_cfg in zip(
        scene["robot_info"]["robot_list"], demogen_config["robots"]
    ):
        robot.initialize(
            default_joint_positions=robot_cfg.get("default_joint_positions", None)
        )
    for key, articulation in scene["articulation_list"].items():
        if scene["articulation_data"][key]["is_articulated"]:
            articulation._articulation_view.initialize()
    scene["cacheDict"] = {}
    if not is_render or save_pointcloud:
        scene["cacheDict"]["meshDict"] = objectList2meshList(
            scene["object_list"],
            os.path.join(
                default_config["ASSETS_DIR"],
                "mesh_data",
                demogen_config["task_name"],
            ),
        )
    scene["background"] = {}
    if demogen_config["domain_randomization"]["random_environment"]["has_wall"]:
        scene["background"]["wall"], scene["background"]["wall_textures"] = (
            setup_walls_and_materials(scene["uuid"], world, scene["object_list"])
        )
    else:
        scene["background"]["wall"] = None
        scene["background"]["wall_textures"] = None
    scene["assets_list"] = collect_assets(default_config["ASSETS_DIR"])
    # if not is_eval:
    for robot in scene["robot_info"]["robot_list"]:
        robot.set_planner(scene["world"], current_dir)
    scene["tcp_configs"] = {}
    if (
        scene["robot_info"]["robot_list"][0].embodiment_name == "franka"
        and scene["robot_info"]["robot_list"][0].gripper_name == "robotiq"
    ):
        scene["tcp_configs"]["franka"] = load_yaml(
            os.path.join(current_dir, "configs/robots/franka_robotiq_tcp.yaml")
        )
    else:
        scene["tcp_configs"]["franka"] = load_yaml(
            os.path.join(current_dir, "configs/robots/franka_tcp.yaml")
        )
    reset_object_xyz(scene["object_list"], world_pose_list)
    for key in scene["object_list"]:
        clean_prim_velocity(scene["object_list"][key].prim_path)
    return scene


def setup_robot_joint_positions(
    embodiment: BaseEmbodiment, demogen_config: dict
) -> BaseEmbodiment:
    if "default_joint_positions" in demogen_config["robots"][0]:
        embodiment.robot.set_joint_positions(
            np.array(demogen_config["robots"][0]["default_joint_positions"])
        )
    return embodiment


def collect_assets(assets_dir: str) -> dict:
    assets_list = {}
    if os.path.exists(os.path.join(assets_dir, "miscs/hdrs")):
        assets_list["domelight"] = os.listdir(f"{assets_dir}/miscs/hdrs")
    else:
        assets_list["domelight"] = []
    if os.path.exists(os.path.join(assets_dir, "miscs/textures")):
        assets_list["wall_texture"] = os.listdir(f"{assets_dir}/miscs/textures")
    else:
        assets_list["wall_texture"] = []
    if os.path.exists(
        os.path.join(assets_dir, "object_usds/grutopia_usd/Table/Materials")
    ):
        assets_list["table_mdl"] = os.listdir(
            f"{assets_dir}/object_usds/grutopia_usd/Table/Materials"
        )
    else:
        assets_list["table_mdl"] = []
    if os.path.exists(os.path.join(assets_dir, "object_usds/grutopia_usd/Table/table")):
        assets_list["table"] = os.listdir(
            f"{assets_dir}/object_usds/grutopia_usd/Table/table"
        )
        assets_list["table"] = [
            os.path.join(
                assets_dir,
                "object_usds/grutopia_usd/Table/table",
                table_path,
                "instance.usd",
            )
            for table_path in assets_list["table"]
        ]
    else:
        assets_list["table"] = []
    return assets_list


def preprocess_scene(scene: dict, demogen_config: dict) -> None:
    preprocess_config = demogen_config["preprocess_config"]
    for preprocess_info in preprocess_config:
        if preprocess_info["type"] == "disable_contact_offset":
            for object in scene["object_list"].values():
                remove_contact_offset(object.prim_path)
        if preprocess_info["type"] == "enable_contact_offset":
            for object in scene["object_list"].values():
                set_contact_offset(object.prim_path, 0.1)
        if preprocess_info["type"] == "disable_gravity":
            for name, object in scene["object_list"].items():
                if (
                    name != "defaultGroundPlane"
                    and name not in scene["articulation_part_list"].keys()
                    and name not in scene["articulation_list"]
                ):
                    set_gravity(object.prim_path, preprocess_info["config"]["value"])
        if preprocess_info["type"] == "ccd":
            for name, object in scene["object_list"].items():
                if (
                    name != "defaultGroundPlane"
                    and name != "00000000000000000000000000000000"
                    and name
                    not in demogen_config["layout_config"].get("ignored_objects", [])
                    and name not in scene["articulation_part_list"].keys()
                    and name not in scene["articulation_list"]
                ):
                    set_rigid_body_CCD(object.prim_path, True)
        if preprocess_info["type"] == "collider":
            for name, object in scene["object_list"].items():
                if (
                    name != "defaultGroundPlane"
                    and name not in scene["articulation_part_list"].keys()
                    and name not in scene["articulation_list"]
                ):
                    if name == "00000000000000000000000000000000":
                        set_colliders(
                            object.prim_path,
                            collision_approximation=preprocess_info["config"]["type"],
                            convex_hulls=2048,
                        )
                    else:
                        set_colliders(
                            object.prim_path,
                            collision_approximation=preprocess_info["config"]["type"],
                        )
        if preprocess_info["type"] == "remove_all_object":
            object_list_key = list(scene["object_list"].keys())
            for key in object_list_key:
                if (
                    key != "defaultGroundPlane"
                    and key != "00000000000000000000000000000000"
                ):
                    if scene["object_list"][key].prim.IsActive():
                        scene["object_list"][key].prim.SetActive(False)
                    scene["object_list"].pop(key)
                    if (
                        "meshDict" in scene["cacheDict"]
                        and key in scene["cacheDict"]["meshDict"]
                    ):
                        scene["cacheDict"]["meshDict"].pop(key)
        if preprocess_info["type"] == "apply_rigid_body_solution":
            for name, object in scene["object_list"].items():
                schema_list = object.prim.GetAppliedSchemas()
                if (
                    "PhysicsRigidBodyAPI" in schema_list
                    and "PhysxRigidBodyAPI" in schema_list
                ):
                    set_rigid_body(object.prim_path)
        if preprocess_info["type"] == "rigid_body":
            for name, object in scene["object_list"].items():
                if (
                    name != "defaultGroundPlane"
                    and name not in scene["articulation_part_list"].keys()
                    and name not in scene["articulation_list"]
                    and name != "00000000000000000000000000000000"
                ):
                    set_rigid_body(object.prim_path)
        if preprocess_info["type"] == "apply_default_physics_material":
            for name, object in scene["object_list"].items():
                if has_collision_api(object.prim):
                    add_physics_material(object.prim_path)


def cleanup_camera(camera_data: dict, camera: Camera) -> None:
    if camera_data["with_bbox2d"]:
        camera.remove_bounding_box_2d_tight_from_frame()
        camera.remove_bounding_box_2d_loose_from_frame()
    if camera_data["with_bbox3d"]:
        camera.remove_bounding_box_3d_from_frame()
    if camera_data["with_motion_vector"]:
        camera.remove_motion_vectors_from_frame()
    if camera_data["with_semantic"]:
        camera.remove_semantic_segmentation_from_frame()
    if camera_data["with_distance"]:
        camera.remove_distance_to_image_plane_from_frame()
    if camera._render_product is not None:
        camera._render_product.destroy()
    del camera
    # delete_prim(camera.prim_path)


def clear_scene(scene: dict, demogen_config: dict, current_dir: str) -> None:
    camera_info = demogen_config["domain_randomization"]["cameras"]
    if camera_info["type"] == "fixed":
        camera_data = load_yaml(os.path.join(current_dir, camera_info["config_path"]))
    else:
        raise ValueError(f"Unsupported camera type: {camera_info['type']}")
    for camera_name, camera_info in camera_data.items():
        cleanup_camera(camera_info, scene["camera_list"][camera_name])
    scene["world"].scene.clear()
    del scene
    delete_prim("/World")
    delete_prim("/Camera")
    delete_prim("/Replicator")
    omni.usd.get_context().close_stage()
    omni.usd.get_context().new_stage()
    # action_registry = omni.kit.actions.core.get_action_registry()
    # action = action_registry.get_action("omni.kit.viewport.menubar.lighting", "set_lighting_mode_stage")
    # action.execute()


def warmup_world(
    scene: dict,
    physics_steps: int = 100,
    without_depth: bool = False,
) -> None:
    if not without_depth:
        while any(
            camera._custom_annotators["distance_to_image_plane"] is not None
            and get_src(camera, "depth") is None
            for camera in scene["camera_list"].values()
        ):
            scene["world"].step()
    for _ in range(physics_steps):
        scene["world"].step(render=False)


def collect_meta_infos(scene: dict) -> None:
    scene["meta_infos"] = {}
    scene["meta_infos"]["world_pose_list"] = collect_world_pose_list(
        scene["object_list"]
    )
    scene["meta_infos"]["articulation_pose_list"] = collect_articulation_list(
        scene, scene["articulation_list"]
    )
    scene["meta_infos"]["robot_pose_list"] = [
        robot.robot.get_world_pose() for robot in scene["robot_info"]["robot_list"]
    ]
    scene["meta_infos"]["robot_tcp_list"] = [
        robot.fk_single(robot.robot.get_joint_positions())
        for robot in scene["robot_info"]["robot_list"]
    ]
    scene["meta_infos"]["joint_positions"] = [
        robot.robot.get_joint_positions() for robot in scene["robot_info"]["robot_list"]
    ]
    scene["meta_infos"]["joint_velocities"] = [
        robot.robot.get_joint_velocities()
        for robot in scene["robot_info"]["robot_list"]
    ]


def update_meta_infos(scene: dict) -> None:
    articulation_part_list = scene["articulation_part_list"]
    for part_id, part_xform in articulation_part_list.items():
        scene["meta_infos"]["world_pose_list"][part_id] = part_xform.get_world_pose()


def recovery_scene(
    scene: dict,
    evaluator: Evaluator,
    task_data: dict,
    eval_config: dict,
    default_config: dict,
) -> dict:
    layout = copy.deepcopy(task_data["initial_layout"])
    if scene["robot_info"]["robot_list"][0].robot.name in layout:
        layout.pop(scene["robot_info"]["robot_list"][0].robot.name)
    object_list_keys = list(scene["object_list"].keys())
    for key in object_list_keys:
        if key not in layout:
            if scene["object_list"][key].prim.IsActive():
                scene["object_list"][key].prim.SetActive(False)
            scene["object_list"].pop(key)
        else:
            if not scene["object_list"][key].prim.IsActive():
                scene["object_list"][key].prim.SetActive(True)
    for key in layout:
        if key not in scene["object_list"]:
            scene["object_list"][key] = preload_object(
                os.path.join(default_config["ASSETS_DIR"], layout[key]["path"]),
                scene["uuid"],
                layout[key]["prim_path"].split("/")[-1][4:],
                scene["world"],
                add_colliders=layout[key].get("add_colliders", True),
                add_rigid_body=layout[key].get("add_rigid_body", True),
            )
            if not scene["object_list"][key].prim.IsActive():
                scene["object_list"][key].prim.SetActive(True)
    for key, object_info in layout.items():
        if is_prim_path_valid(object_info["prim_path"]):
            scene["object_list"][key].set_world_pose(
                object_info["position"], object_info["orientation"]
            )
            scene["object_list"][key].set_local_scale(object_info["scale"])
            clean_prim_velocity(scene["object_list"][key].prim_path)
    scene["cacheDict"]["meshDict"] = objectList2meshList(
        scene["object_list"],
        os.path.join(
            default_config["ASSETS_DIR"],
            "mesh_data",
            eval_config["task_name"],
        ),
    )
    for goal in task_data["goal"]:
        for subgoal in goal:
            if "another_obj2_uid" in subgoal:
                set_mass(
                    scene["object_list"][subgoal["another_obj2_uid"]].prim_path, 10.0
                )
            if "status" in subgoal:
                continue
            if "obj1_uid" in subgoal:
                set_mass(scene["object_list"][subgoal["obj1_uid"]].prim_path, 0.1)
            if "obj2_uid" in subgoal:
                set_mass(scene["object_list"][subgoal["obj2_uid"]].prim_path, 10.0)
    if scene["robot_info"]["robot_list"][0].robot.name in task_data["initial_layout"]:
        scene["robot_info"]["robot_list"][0].robot.set_joint_positions(
            task_data["initial_layout"][
                scene["robot_info"]["robot_list"][0].robot.name
            ]["joint_positions"]
        )
    else:
        scene["robot_info"]["robot_list"][0].robot.set_joint_positions(
            np.array([0.012, -0.57, 0.0, -2.81, 0.0, 3.37, 0.741, 0.04, 0.04])
        )
    if evaluator is not None:
        evaluator.instruction = task_data["instruction"]
    return layout


def is_valid_object_path(path: str) -> bool:
    return (
        os.path.exists(path)
        and not os.path.isdir(path)
        and str(path).endswith(".usd")
        and str(path) != ""
    )


def is_valid_object_path(path: str) -> bool:
    return (
        os.path.exists(path)
        and not os.path.isdir(path)
        and str(path).endswith(".usd")
        and str(path) != ""
    )


def recovery_scene_render(
    scene: dict,
    task_data: dict,
    eval_config: dict,
    default_config: dict,
    remove_table: bool = False,
) -> dict:
    layout = copy.deepcopy(task_data["initial_layout"])
    scene["robot_info"]["robot_list"][0].robot.set_world_pose(
        layout[scene["robot_info"]["robot_list"][0].robot.name]["position"],
        layout[scene["robot_info"]["robot_list"][0].robot.name]["orientation"],
    )
    if scene["robot_info"]["robot_list"][0].robot.name in layout:
        scene["robot_info"]["robot_list"][0].robot.set_joint_positions(
            layout[scene["robot_info"]["robot_list"][0].robot.name]["joint_positions"]
        )
    else:
        scene["robot_info"]["robot_list"][0].robot.set_joint_positions(
            np.array([0.012, -0.57, 0.0, -2.81, 0.0, 3.37, 0.741, 0.04, 0.04])
        )
    if scene["robot_info"]["robot_list"][0].robot.name in layout:
        layout.pop(scene["robot_info"]["robot_list"][0].robot.name)
    object_list_keys = list(scene["object_list"].keys())
    for key in object_list_keys:
        if key not in layout:
            if scene["object_list"][key].prim.IsActive():
                scene["object_list"][key].prim.SetActive(False)
            scene["object_list"].pop(key)
        else:
            if not scene["object_list"][key].prim.IsActive():
                scene["object_list"][key].prim.SetActive(True)
    for key in layout:
        if key not in scene["object_list"]:
            if is_valid_object_path(
                os.path.join(default_config["ASSETS_DIR"], layout[key]["path"])
            ):
                scene["object_list"][key] = preload_object(
                    os.path.join(default_config["ASSETS_DIR"], layout[key]["path"]),
                    scene["uuid"],
                    layout[key]["prim_path"].split("/")[-1][4:],
                    scene["world"],
                    add_colliders=False,
                    add_rigid_body=False,
                    remove_collider=True,
                )
                if not scene["object_list"][key].prim.IsActive():
                    scene["object_list"][key].prim.SetActive(True)
    for key, object_info in layout.items():
        if is_prim_path_valid(object_info["prim_path"]):
            scene["object_list"][key].set_world_pose(
                object_info["position"], object_info["orientation"]
            )
            scene["object_list"][key].set_local_scale(object_info["scale"])
    # scene["cacheDict"]["meshDict"] = objectList2meshList(
    #     scene["object_list"],
    #     os.path.join(
    #         default_config["ASSETS_DIR"],
    #         "mesh_data",
    #         eval_config["task_name"],
    #     ),
    # )
    for goal in task_data["goal"]:
        for subgoal in goal:
            if "is_articulated" in subgoal:
                continue
            if "another_obj2_uid" in subgoal:
                set_mass(
                    scene["object_list"][subgoal["another_obj2_uid"]].prim_path, 10.0
                )
            if "obj1_uid" in subgoal:
                set_mass(scene["object_list"][subgoal["obj1_uid"]].prim_path, 0.1)
            if "obj2_uid" in subgoal:
                set_mass(scene["object_list"][subgoal["obj2_uid"]].prim_path, 10.0)
    if remove_table:
        if scene["object_list"]["00000000000000000000000000000000"].prim.IsActive():
            scene["object_list"]["00000000000000000000000000000000"].prim.SetActive(False)