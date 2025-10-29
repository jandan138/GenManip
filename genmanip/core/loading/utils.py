"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import os
import random

import numpy as np

from omni.isaac.core.prims import XFormPrim  # type: ignore

from genmanip.core.pointcloud.pointcloud import (
    get_current_meshList,
    get_mesh_info_by_load,
)
from genmanip.core.usd_utils.prim_utils import resize_object, resize_object_by_lwh
from genmanip.utils.pc_utils import compute_aabb_lwh, compute_mesh_bbox
from object_utils.object_pool import ObjectPool


def reset_object_xyz(
    object_list: dict[str, XFormPrim], xyz: dict[str, tuple[np.ndarray, np.ndarray]]
) -> None:
    for key in object_list:
        if key == "00000000000000000000000000000000" or key == "defaultGroundPlane":
            continue
        if key in xyz:
            object_list[key].set_world_pose(*xyz[key])


def collect_world_pose_list(
    object_list: dict[str, XFormPrim],
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    world_pose_list = {}
    for key in object_list:
        if key == "00000000000000000000000000000000" or key == "defaultGroundPlane":
            continue
        world_pose_list[key] = object_list[key].get_world_pose()
    return world_pose_list


def reset_articulation_positions(scene: dict) -> None:
    if (
        "meta_infos" not in scene
        or "articulation_pose_list" not in scene["meta_infos"]
        or "articulation_list" not in scene
        or "articulation_data" not in scene
    ):
        print("No articulation data found")
        return
    articulation_list = scene["articulation_list"]
    articulation_pose_list = scene["meta_infos"]["articulation_pose_list"]
    for articulation_id, articulation in articulation_list.items():
        if scene["articulation_data"][articulation_id]["is_articulated"]:
            articulation.set_joint_positions(articulation_pose_list[articulation_id])


def remove_object_from_scene_by_preload(uid: str, scene: dict) -> None:
    # Disactivate the object in object list
    if scene["object_list"][uid].prim.IsActive():
        scene["object_list"][uid].prim.SetActive(False)
    # Remove the object from mesh cache
    scene["cacheDict"]["meshDict"].pop(uid)
    # Remove the object from object list
    scene["object_list"].pop(uid)


def add_object_to_scene_from_preload_list(
    uid: str,
    scene: dict,
    default_config: dict,
    demogen_config: dict,
) -> None:
    # Add the object from preloaded object list to object list
    scene["object_list"][uid] = scene["cacheDict"]["preloaded_object_list"][uid]
    # Activate the object in object list
    if not scene["object_list"][uid].prim.IsActive():
        scene["object_list"][uid].prim.SetActive(True)
    # Compute the object's mesh information
    if uid in scene["cacheDict"]["preloaded_object_path_list"]:
        # if object is in preloaded object path list, object mesh path should be in the same folder as the object path in `mesh_data`, like `mesh_data/task_name/folder_name/uid.obj` while usd is in `object_usd/folder_name/uid.usd`
        scene["cacheDict"]["meshDict"][uid] = get_mesh_info_by_load(
            scene["object_list"][uid],
            os.path.join(
                default_config["ASSETS_DIR"],
                "mesh_data",
                demogen_config["task_name"],
                os.path.dirname(scene["cacheDict"]["preloaded_object_path_list"][uid]),
                f"{uid}.obj",
            ),
        )
    else:
        # else, object mesh path should be `mesh_data/task_name/uid.obj`
        scene["cacheDict"]["meshDict"][uid] = get_mesh_info_by_load(
            scene["object_list"][uid],
            os.path.join(
                default_config["ASSETS_DIR"],
                "mesh_data",
                demogen_config["task_name"],
                f"{uid}.obj",
            ),
        )


def replace_object_in_scene_by_uid(
    previous_uid: str,
    replaced_uid: str,
    scene: dict,
    default_config: dict,
    demogen_config: dict,
) -> None:
    # Remove the previous object from scene dict
    if previous_uid in scene["object_list"]:
        remove_object_from_scene_by_preload(previous_uid, scene)
    # Add the replaced object to scene dict
    add_object_to_scene_from_preload_list(
        replaced_uid, scene, default_config, demogen_config
    )


def resize_object_in_scene_by_uid(
    uid: str,
    scene: dict,
    default_config: dict,
    scale: float | list[float],
    demogen_config: dict,
) -> None:
    # 1. Get the current mesh list from scene dict
    meshlist = get_current_meshList(
        scene["object_list"], scene["cacheDict"]["meshDict"]
    )

    # 2. Resize the object in scene dict by scale factor and mesh information
    if isinstance(scale, float):
        resize_object(
            scene["object_list"][uid],
            scale,
            meshlist[uid],
        )
    elif isinstance(scale, list):
        print(f"resize object {uid} by {scale}")
        resize_object_by_lwh(
            scene["object_list"][uid],
            l=scale[0],
            w=scale[1],
            h=scale[2],
            mesh=meshlist[uid],
        )
    else:
        raise ValueError(f"Invalid scale type: {type(scale)}")

    # 3. Update the object's mesh information
    if uid in scene["cacheDict"]["preloaded_object_path_list"]:
        scene["cacheDict"]["meshDict"][uid] = get_mesh_info_by_load(
            scene["object_list"][uid],
            os.path.join(
                default_config["ASSETS_DIR"],
                "mesh_data",
                demogen_config["task_name"],
                os.path.dirname(scene["cacheDict"]["preloaded_object_path_list"][uid]),
                f"{uid}.obj",
            ),
        )
    else:
        scene["cacheDict"]["meshDict"][uid] = get_mesh_info_by_load(
            scene["object_list"][uid],
            os.path.join(
                default_config["ASSETS_DIR"],
                "mesh_data",
                demogen_config["task_name"],
                f"{uid}.obj",
            ),
        )


def adjust_object_scale_by_thickness(
    scene: dict,
    uid: str,
    default_config: dict,
    demogen_config: dict,
    object_scale: float,
    min_thickness: float,
) -> None:
    meshlist = get_current_meshList(
        scene["object_list"], scene["cacheDict"]["meshDict"]
    )
    mesh = meshlist[uid]
    aabb = compute_mesh_bbox(mesh)
    if np.min(compute_aabb_lwh(aabb)) > min_thickness:
        l, w, h = compute_aabb_lwh(aabb)
        min_thickness_ratio = min_thickness / np.min([l, w])
        min_thickness_ratio = max(min_thickness_ratio, min_thickness / np.min([l, w]))
        l *= min_thickness_ratio
        w *= min_thickness_ratio
        h *= min_thickness_ratio
        resize_object_by_lwh(
            scene["object_list"][uid],
            l=l,
            w=w,
            h=h,
            mesh=mesh,
        )
        scene["cacheDict"]["meshDict"][uid] = get_mesh_info_by_load(
            scene["object_list"][uid],
            os.path.join(
                default_config["ASSETS_DIR"],
                "mesh_data",
                demogen_config["task_name"],
                os.path.dirname(scene["cacheDict"]["preloaded_object_path_list"][uid]),
                f"{uid}.obj",
            ),
        )


def get_object_scale(
    replace_object_config: dict,
    key: str,
    replaced_uid: str,
    object_pool: ObjectPool,
) -> float:
    if (
        "option" in replace_object_config[key]
        and "plain_replace" in replace_object_config[key]["option"]
    ):
        scale = None
    else:
        object_info = object_pool.get_object_info(replaced_uid)
        if object_info is None:
            scale = random.uniform(0.08, 0.12)
        elif (
            "option" in replace_object_config[key]
            and "grep_min_scale" in replace_object_config[key]["option"]
        ):
            scale = object_info["scale"][0]
        else:
            scale = random.uniform(
                object_info["scale"][0],
                object_info["scale"][1],
            )
    if "clip_range" in replace_object_config[key]:
        scale = np.clip(
            scale,
            replace_object_config[key]["clip_range"]["min"],
            replace_object_config[key]["clip_range"]["max"],
        )
    if "fixed_size" in replace_object_config[key]:
        scale = replace_object_config[key]["fixed_size"]
    return scale
