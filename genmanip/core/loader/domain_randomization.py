"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import os
import random

import cv2
from mplib.pymp import Pose
import numpy as np
import random
from scipy.spatial.transform import Rotation as R

from omni.isaac.core.prims import XFormPrim  # type: ignore
from omni.isaac.core.robots.robot import Robot  # type: ignore
from omni.isaac.core.utils.prims import get_prim_at_path, delete_prim  # type: ignore
from omni.isaac.sensor import Camera  # type: ignore
from pxr import Usd  # type: ignore

from genmanip.core.loader.hardcode_rule import verify_cup_and_plate
from genmanip.core.loader.utils import (
    add_object_to_scene_from_preload_list,
    adjust_object_scale_by_thickness,
    get_object_scale,
    remove_object_from_scene_by_preload,
    reset_object_xyz,
    reset_articulation_positions,
    resize_object_in_scene_by_uid,
)
from genmanip.utils.pointcloud.pointcloud import (
    get_current_pcList_by_meshList,
    get_mesh_info_by_load,
)
from genmanip.demogen.random_place.random_place import (
    setup_random_all_range,
    setup_random_all_range_buffered,
    setup_random_custom_tableset,
    setup_random_obj1_range,
    setup_random_tableset,
    setup_random_tableset_buffered,
    setup_random_tableset_by_centric_range,
    setup_scene_graph_placement,
    verify_placement,
)
from genmanip.core.sensor.camera import get_src
from genmanip.utils.usd_utils import (
    add_usd_to_world,
    change_material_info,
    change_table_mdl,
    clean_prim_velocity,
    create_dome_light,
    get_prim_bbox,
    resize_object_by_lwh,
    set_colliders,
)
from genmanip.core.embodiment import BaseEmbodiment
from genmanip.core.metrics.metrics import check_finished
from genmanip.utils.planner.mplib.utils import get_mplib_planner
from genmanip.utils.standalone.file_utils import load_yaml
from genmanip.utils.standalone.robot_utils import (
    joint_positions_to_position_and_orientation,
)


def random_camera_pose(
    camera: Camera,
    camera_cfg: dict,
    max_translation_noise: float = 0.05,
    max_orientation_noise: float = 10.0,
) -> None:
    translation = np.array(camera_cfg["position"])
    orientation = np.array(camera_cfg["orientation"])

    random_direction = np.random.randn(3)
    random_direction /= np.linalg.norm(random_direction)
    random_distance = np.random.uniform(0, max_translation_noise)
    perturbed_translation = translation + random_direction * random_distance

    original_rot = R.from_quat(orientation, scalar_first=True)
    random_axis = np.random.randn(3)
    random_axis /= np.linalg.norm(random_axis)
    random_angle_deg = np.random.uniform(-max_orientation_noise, max_orientation_noise)
    random_angle_rad = np.radians(random_angle_deg)
    perturbation_rot = R.from_rotvec(random_axis * random_angle_rad)
    perturbed_rot = perturbation_rot * original_rot
    perturbed_orientation = perturbed_rot.as_quat(scalar_first=True)

    camera.set_local_pose(
        translation=perturbed_translation,
        orientation=perturbed_orientation,
        camera_axes=camera_cfg["camera_axes"],
    )


def random_camera_list_pose(
    camera_list: dict[str, Camera],
    camera_cfg: dict[str, dict],
    camera_randomization_cfg: dict,
) -> None:
    for camera_name in camera_randomization_cfg.keys():
        random_camera_pose(
            camera_list[camera_name],
            camera_cfg[camera_name],
            max_translation_noise=camera_randomization_cfg[camera_name][
                "max_translation_noise"
            ],
            max_orientation_noise=camera_randomization_cfg[camera_name][
                "max_orientation_noise"
            ],
        )


def random_robot_pose(robot: Robot, random_range: float | dict) -> None:
    position, _ = robot.get_world_pose()
    if isinstance(random_range, (int, float)):
        new_position = (
            random.uniform(position[0] - random_range, position[0] + random_range),
            random.uniform(position[1] - random_range, position[1] + random_range),
            position[2],
        )
    elif isinstance(random_range, dict) and all(
        key in random_range for key in ["x", "y", "z"]
    ):
        new_position = (
            random.uniform(
                position[0] - random_range["x"], position[0] + random_range["x"]
            ),
            random.uniform(
                position[1] - random_range["y"], position[1] + random_range["y"]
            ),
            random.uniform(
                position[2] - random_range["z"], position[2] + random_range["z"]
            ),
        )
    else:
        raise ValueError(
            "random_range must be a number or a dict with 'x', 'y', 'z' keys"
        )

    robot.set_world_pose(position=new_position)


def random_robot_eepose(robot: BaseEmbodiment, current_dir: str) -> int:
    assert (
        robot.embodiment_name == "franka"
    ), "Only franka robot is supported for random robot eepose"
    franka_robot = robot.robot
    planner = get_mplib_planner(
        franka_robot, robot_type=robot.embodiment_name, current_dir=current_dir
    )
    position, orientation = joint_positions_to_position_and_orientation(
        franka_robot.get_joint_positions()
    )
    position += np.array(
        [
            random.uniform(-0.1, 0.1),
            random.uniform(-0.1, 0.1),
            random.uniform(-0.1, 0.1),
        ]
    )
    rot = R.from_quat(orientation[[1, 2, 3, 0]])
    rot = rot * R.from_euler(
        "zyx",
        [
            random.uniform(-np.pi / 6, np.pi / 6),
            random.uniform(-np.pi / 6, np.pi / 6),
            random.uniform(-np.pi / 6, np.pi / 6),
        ],
        degrees=False,
    )
    orientation = rot.as_quat()[[3, 0, 1, 2]]
    joint_positions = planner.IK(
        Pose(p=position.astype(float), q=orientation.astype(float)),
        franka_robot.get_joint_positions()[:9],
        return_closest=True,
    )
    if joint_positions[0] != "Success":
        return -1
    elif joint_positions is None:
        return -1
    else:
        joint_positions = joint_positions[1]
        if joint_positions is None:
            return -1
        franka_robot.set_joint_positions(
            np.concatenate([joint_positions[1][:7], robot.gripper_open]),
        )
        return 0


def replace_table(
    object_list: dict,
    table_path: str,
    uuid: str,
    without_collider: bool = False,
) -> None:
    # "00000000000000000000000000000000" is the default table key
    object = object_list["00000000000000000000000000000000"]
    # Disable the default table
    try:
        object_list["00000000000000000000000000000000"].prim.SetActive(False)
    except:
        pass
    # Get the new table uid from table path, table path is like "/path/to/folder/table_uid/instance.usd"
    table_uid = table_path.split("/")[-2]
    # If the new table is already in the scene, use the existing prim
    if get_prim_at_path(f"/World/{uuid}/obj_{table_uid}").IsValid():
        object_list["00000000000000000000000000000000"] = XFormPrim(
            prim_path=f"/World/{uuid}/obj_{table_uid}",
            name=f"obj_{table_uid}",
        )
        object_list["00000000000000000000000000000000"].prim.SetActive(True)
    # If the new table is not in the scene, add it to the scene
    else:
        object_list["00000000000000000000000000000000"] = add_usd_to_world(
            asset_path=table_path,
            prim_path=f"/World/{uuid}/obj_{table_uid}",
            name=f"obj_{table_uid}",
            orientation=R.from_euler("xyz", [0, 0, 90], degrees=True).as_quat()[
                [3, 0, 1, 2]
            ],
        )
    # Resize the table and set the position
    try:
        resize_object_by_lwh(
            object_list["00000000000000000000000000000000"], l=1.0, w=1.50, h=1.002
        )
        aabb = get_prim_bbox(object_list["00000000000000000000000000000000"].prim)
        position, _ = object_list["00000000000000000000000000000000"].get_world_pose()
        position[2] -= aabb.get_min_bound()[2]
        object_list["00000000000000000000000000000000"].set_world_pose(
            position=position
        )
        if not without_collider:
            set_colliders(object_list["00000000000000000000000000000000"].prim_path)
    except:
        delete_prim(object_list["00000000000000000000000000000000"].prim_path)
        object_list["00000000000000000000000000000000"] = object
        object_list["00000000000000000000000000000000"].prim.SetActive(True)


def replace_table_for_eval(
    object_list: dict,
    table_path: str,
    uuid: str,
    real_table_uid: str,
    without_collider: bool = False,
) -> None:
    # "00000000000000000000000000000000" is the default table key
    object = object_list["00000000000000000000000000000000"]
    # Disable the default table
    try:
        # If the new table is not the real table, disable the default table
        if (
            str(object_list["00000000000000000000000000000000"].prim_path).split(
                "obj_"
            )[-1]
            != real_table_uid
        ):
            object_list["00000000000000000000000000000000"].prim.SetActive(False)
        else:
            object_list["00000000000000000000000000000000"].prim.GetAttribute(
                "visibility"
            ).Set("invisible")
    except:
        pass
    # Get the new table uid from table path, table path is like "/path/to/folder/table_uid/instance.usd"
    table_uid = table_path.split("/")[-2]
    # If the new table is already in the scene, use the existing prim
    if get_prim_at_path(f"/World/{uuid}/obj_{table_uid}").IsValid():
        object_list["00000000000000000000000000000000"] = XFormPrim(
            prim_path=f"/World/{uuid}/obj_{table_uid}",
            name=f"obj_{table_uid}",
        )
        object_list["00000000000000000000000000000000"].prim.SetActive(True)
    else:
        object_list["00000000000000000000000000000000"] = add_usd_to_world(
            asset_path=table_path,
            prim_path=f"/World/{uuid}/obj_{table_uid}",
            name=f"obj_{table_uid}",
            orientation=R.from_euler("xyz", [0, 0, 90], degrees=True).as_quat()[
                [3, 0, 1, 2]
            ],
        )
    # Resize the table and set the position
    try:
        resize_object_by_lwh(
            object_list["00000000000000000000000000000000"], l=1.0, w=1.50, h=1.002
        )
        aabb = get_prim_bbox(object_list["00000000000000000000000000000000"].prim)
        position, _ = object_list["00000000000000000000000000000000"].get_world_pose()
        position[2] -= aabb.get_min_bound()[2]
        object_list["00000000000000000000000000000000"].set_world_pose(
            position=position
        )
        if not without_collider:
            set_colliders(object_list["00000000000000000000000000000000"].prim_path)
    except:
        delete_prim(object_list["00000000000000000000000000000000"].prim_path)
        object_list["00000000000000000000000000000000"] = object
        object_list["00000000000000000000000000000000"].prim.SetActive(True)
        object_list["00000000000000000000000000000000"].prim.GetAttribute(
            "visibility"
        ).Set("invisible")


def load_scene_as_background(
    scene_info: dict,
    assets_dir: str,
    uuid: str,
    table_uid: str,
) -> tuple[XFormPrim, XFormPrim]:
    def deactivate_selected_prims(
        prim: Usd.Prim, selected_names: list[str], random_names: list[str]
    ):

        for child_prim in prim.GetAllChildren():
            prim_name = child_prim.GetName().lower()
            for name in selected_names:
                if name.lower() in prim_name:
                    child_prim.SetActive(False)

            for name in random_names:
                if name.lower() in prim_name:
                    flag = True if random.random() > 0.5 else False
                    child_prim.SetActive(flag)

            deactivate_selected_prims(child_prim, selected_names, random_names)

    FIXED_HEIGHT = 0.99931

    original_table_prim = get_prim_at_path(f"/World/{uuid}/obj_{table_uid}")
    if original_table_prim.IsActive():
        original_table_prim.SetActive(False)

    ground_plane_prim = get_prim_at_path(f"/World/{uuid}/obj_defaultGroundPlane")
    deactivate_selected_prims(ground_plane_prim, ["collision"], [])

    room = add_usd_to_world(
        asset_path=os.path.join(
            assets_dir,
            "miscs",
            scene_info["scene"]["path"],
        ),
        prim_path=f"/World/{uuid}/room",
        name="room",
        translation=[
            scene_info["scene"]["translation"][1],
            -scene_info["scene"]["translation"][0],
            FIXED_HEIGHT
            - scene_info["scene"]["translation"][2]
            - 2 * scene_info["table"]["translation"][2],
        ],
        orientation=R.from_euler(
            "xyz", [0, 0, scene_info["scene"]["euler"][2] - 90], degrees=True
        ).as_quat()[[3, 0, 1, 2]],
        scale=scene_info["scene"]["scale"],
    )
    deactivate_selected_prims(
        room.prim,
        ["pan", "hearth", "ceiling", "__default_setting", "other", "microwave"],
        ["light"],
    )
    table = add_usd_to_world(
        asset_path=os.path.join(
            assets_dir,
            "miscs",
            scene_info["table"]["path"],
        ),
        prim_path=f"/World/{uuid}/table",
        name="table",
        translation=[
            0,
            0,
            FIXED_HEIGHT
            - scene_info["scene"]["translation"][2]
            - scene_info["table"]["translation"][2],
        ],
        orientation=R.from_euler("xyz", [0, 0, -90], degrees=True).as_quat()[
            [3, 0, 1, 2]
        ],
        scale=scene_info["table"]["scale"],
    )
    return room, table


def random_objaverse_table_texture(scene: dict, default_config: dict) -> None:
    light_intensity = 0
    texture_path = None
    while light_intensity < 80:
        texture_path = random.choice(scene["assets_list"]["wall_texture"])
        image = cv2.imread(
            os.path.abspath(
                f"{default_config['ASSETS_DIR']}/miscs/textures/{texture_path}"
            )
        )
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        light_intensity = np.mean(np.array(image))
    if texture_path is None:
        raise ValueError("No texture path found")
    change_material_info(
        f"{scene['object_list']['00000000000000000000000000000000'].prim_path}",
        texture_path=os.path.abspath(
            f"{default_config['ASSETS_DIR']}/miscs/textures/{texture_path}"
        ),
        translation=(random.uniform(-1.0, 1.0), random.uniform(-1.0, 1.0)),
        rotation=0,
        scale=(0.4, 0.4),
    )


def random_wall_texture(scene: dict, default_config: dict) -> None:
    # randomize 5 walls' texture, [left, right, front, back, top]
    for i in range(5):
        light_intensity = 0
        texture_path = None
        while light_intensity < 80:
            texture_path = random.choice(scene["assets_list"]["wall_texture"])
            image = cv2.imread(
                os.path.abspath(
                    f"{default_config['ASSETS_DIR']}/miscs/textures/{texture_path}"
                )
            )
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            light_intensity = np.mean(np.array(image))
        if texture_path is None:
            raise ValueError("No texture path found")
        scene["background"]["wall_textures"][i].set_texture(
            os.path.abspath(
                f"{default_config['ASSETS_DIR']}/miscs/textures/{texture_path}"
            )
        )


def random_texture_once(
    scene: dict,
    default_config: dict,
    demogen_config: dict,
    table_without_collider: bool = False,
) -> float:
    # randomize the dome light
    if demogen_config["domain_randomization"]["random_environment"]["hdr"]:
        light_path = random.choice(scene["assets_list"]["domelight"])
        create_dome_light(
            f"/World/{scene['uuid']}/obj_defaultGroundPlane/GroundPlane/DomeLight",
            f"{default_config['ASSETS_DIR']}/miscs/hdrs/{light_path}",
        )
    # randomize table texture for the default table, table prim tree is under objaverse format
    if demogen_config["domain_randomization"]["random_environment"][
        "table_texture"
    ] and not (
        "table_type" in demogen_config["domain_randomization"]["random_environment"]
        and demogen_config["domain_randomization"]["random_environment"]["table_type"]
    ):
        random_objaverse_table_texture(scene, default_config)
    # randomize wall texture
    if demogen_config["domain_randomization"]["random_environment"]["wall_texture"]:
        random_wall_texture(scene, default_config)
    # randomize table and table texture for grutopia format table, table prim tree is under grutopia format
    if (
        "table_type" in demogen_config["domain_randomization"]["random_environment"]
        and demogen_config["domain_randomization"]["random_environment"]["table_type"]
    ):
        table_path = random.choice(scene["assets_list"]["table"])
        replace_table(
            scene["object_list"],
            table_path,
            scene["uuid"],
            without_collider=table_without_collider,
        )
        if demogen_config["domain_randomization"]["random_environment"][
            "table_texture"
        ]:
            change_table_mdl(
                scene["object_list"]["00000000000000000000000000000000"].prim_path,
                texture_path_list=[
                    os.path.abspath(
                        f"{default_config['ASSETS_DIR']}/object_usds/grutopia_usd/Table/Materials/{table_mdl_path}"
                    )
                    for table_mdl_path in scene["assets_list"]["table_mdl"]
                ],
            )
    # randomize camera pose
    if (
        "camera_randomization"
        in demogen_config["domain_randomization"]["random_environment"]
    ):
        current_dir = default_config["current_dir"]
        camera_data = load_yaml(
            os.path.join(
                current_dir,
                demogen_config["domain_randomization"]["cameras"]["config_path"],
            )
        )
        random_camera_list_pose(
            scene["camera_list"],
            camera_data,
            demogen_config["domain_randomization"]["random_environment"][
                "camera_randomization"
            ],
        )
    # render the scene and get the light intensity
    for _ in range(10):
        scene["world"].render()
    if "obs_camera" in scene["camera_list"]:
        image = get_src(scene["camera_list"]["obs_camera"], "rgb")
    elif "top_camera" in scene["camera_list"]:
        image = get_src(scene["camera_list"]["top_camera"], "rgb")
    else:
        raise ValueError("No main camera found")
    if image is None:
        raise ValueError("No image found")
    # get the light intensity
    light_intensity = np.mean(np.array(image))
    return float(light_intensity)


def random_texture_once_for_eval(
    scene: dict,
    default_config: dict,
    demogen_config: dict,
    table_without_collider: bool = True,
) -> float:
    # randomize the dome light
    if demogen_config["domain_randomization"]["random_environment"]["hdr"]:
        light_path = random.choice(scene["assets_list"]["domelight"])
        create_dome_light(
            f"/World/{scene['uuid']}/obj_defaultGroundPlane/GroundPlane/DomeLight",
            f"{default_config['ASSETS_DIR']}/miscs/hdrs/{light_path}",
        )
    # randomize table texture for the default table, table prim tree is under objaverse format
    if demogen_config["domain_randomization"]["random_environment"][
        "table_texture"
    ] and not (
        "table_type" in demogen_config["domain_randomization"]["random_environment"]
        and demogen_config["domain_randomization"]["random_environment"]["table_type"]
    ):
        random_objaverse_table_texture(scene, default_config)
    # randomize wall texture
    if demogen_config["domain_randomization"]["random_environment"]["wall_texture"]:
        random_wall_texture(scene, default_config)
    # randomize table and table texture for grutopia format table, table prim tree is under grutopia format
    if (
        "table_type" in demogen_config["domain_randomization"]["random_environment"]
        and demogen_config["domain_randomization"]["random_environment"]["table_type"]
    ):
        table_path = random.choice(scene["assets_list"]["table"])
        replace_table_for_eval(
            scene["object_list"],
            table_path,
            scene["uuid"],
            real_table_uid=demogen_config["table_uid"],
            without_collider=table_without_collider,
        )
        if demogen_config["domain_randomization"]["random_environment"][
            "table_texture"
        ]:
            change_table_mdl(
                scene["object_list"]["00000000000000000000000000000000"].prim_path,
                texture_path_list=[
                    os.path.abspath(
                        f"{default_config['ASSETS_DIR']}/object_usds/grutopia_usd/Table/Materials/{table_mdl_path}"
                    )
                    for table_mdl_path in scene["assets_list"]["table_mdl"]
                ],
            )
    # render the scene and get the light intensity
    for _ in range(10):
        scene["world"].render()
    if "obs_camera" in scene["camera_list"]:
        image = get_src(scene["camera_list"]["obs_camera"], "rgb")
    elif "top_camera" in scene["camera_list"]:
        image = get_src(scene["camera_list"]["top_camera"], "rgb")
    else:
        raise ValueError("No main camera found")
    if image is None:
        raise ValueError("No image found")
    light_intensity = np.mean(np.array(image))
    return float(light_intensity)


def random_texture(
    scene: dict,
    default_config: dict,
    demogen_config: dict,
    table_without_collider: bool = False,
) -> int:
    cnt = 0
    while cnt < 10:
        # randomize the texture of the scene
        light_intensity = random_texture_once(
            scene,
            default_config,
            demogen_config,
            table_without_collider=table_without_collider,
        )
        # if the light intensity is >= 80, break the loop
        if light_intensity >= 80:
            break
        cnt += 1
    # if the light intensity is < 80 after 10 times, print error message and return -1
    if cnt == 10:
        print("random texture failed")
        return -1
    return 0


def random_texture_for_eval(
    scene: dict,
    default_config: dict,
    demogen_config: dict,
) -> int:
    cnt = 0
    while cnt < 10:
        # randomize the texture of the scene
        light_intensity = random_texture_once_for_eval(
            scene,
            default_config,
            demogen_config,
        )
        if light_intensity >= 80:
            break
        cnt += 1
    if cnt == 10:
        print("random texture failed")
        return -1
    return 0


def domain_randomization(
    scene: dict,
    default_config: dict,
    demogen_config: dict,
    task_data: dict,
    mode: str = "demogen",
) -> dict | int:
    # randomize robot base position
    if demogen_config["domain_randomization"]["random_environment"][
        "robot_base_position"
    ]:
        for robot in scene["robot_info"]["robot_list"]:
            if isinstance(
                demogen_config["domain_randomization"]["random_environment"][
                    "robot_base_position"
                ],
                dict,
            ):
                random_robot_pose(
                    robot.robot,
                    demogen_config["domain_randomization"]["random_environment"][
                        "robot_base_position"
                    ]["random_range"],
                )
            else:
                random_robot_pose(robot.robot, 0.1)
    # randomize robot eepose
    if demogen_config["domain_randomization"]["random_environment"].get(
        "robot_eepose", False
    ):
        for robot in scene["robot_info"]["robot_list"]:
            random_robot_eepose(
                robot,
                default_config["current_dir"],
            )
    # setup random table layout
    print("setup random position")
    if demogen_config["layout_config"]["type"] == "random_all":
        IS_OK = setup_random_tableset(
            scene["object_list"],
            scene["cacheDict"]["meshDict"],
            demogen_config["layout_config"]["ignored_objects"],
        )
    elif demogen_config["layout_config"]["type"] == "random_all_buffered":
        IS_OK = setup_random_tableset_buffered(
            scene["object_list"],
            scene["cacheDict"]["meshDict"],
            demogen_config["layout_config"]["ignored_objects"],
            task_data["goal"][0][0]["obj1_uid"],
            task_data["goal"][0][0]["obj2_uid"],
        )
    elif demogen_config["layout_config"]["type"] == "centric_random_range":
        IS_OK = setup_random_tableset_by_centric_range(
            scene["object_list"],
            scene["cacheDict"]["meshDict"],
            demogen_config["layout_config"],
            demogen_config["layout_config"]["ignored_objects"],
            demogen_config["layout_config"].get("partial_ignore", {}),
        )
    elif demogen_config["layout_config"]["type"] == "random_obj1_range":
        IS_OK = setup_random_obj1_range(
            scene["object_list"],
            scene["cacheDict"]["meshDict"],
            task_data,
            demogen_config["layout_config"],
            scene["meta_infos"]["world_pose_list"],
        )
    elif demogen_config["layout_config"]["type"] == "random_custom_tableset":
        IS_OK = setup_random_custom_tableset(
            scene["object_list"],
            scene["articulation_list"],
            scene["cacheDict"]["meshDict"],
            demogen_config["layout_config"]["custom_tableset"],
            in_order=demogen_config["layout_config"].get("in_order", False),
        )
    elif demogen_config["layout_config"]["type"] == "random_all_range":
        IS_OK = setup_random_all_range(
            scene["object_list"],
            scene["cacheDict"]["meshDict"],
            demogen_config["layout_config"],
            demogen_config["layout_config"]["ignored_objects"],
        )
    elif demogen_config["layout_config"]["type"] == "random_all_range_buffered":
        IS_OK = setup_random_all_range_buffered(
            scene["object_list"],
            scene["cacheDict"]["meshDict"],
            demogen_config["layout_config"],
            demogen_config["layout_config"]["ignored_objects"],
            task_data,
        )
    elif demogen_config["layout_config"]["type"] == "scene_graph_placement":
        IS_OK = setup_scene_graph_placement(
            scene["object_list"],
            scene["cacheDict"]["meshDict"],
            demogen_config,
        )
    else:
        IS_OK = 0
    if IS_OK == -1:
        print("random position failed")
        return IS_OK
    # clean prim velocity because the prim velocity may not zero from the previous scene
    for key in scene["object_list"]:
        clean_prim_velocity(scene["object_list"][key].prim_path)
    print("verify placement")
    # verify if the placement is stable
    if (
        len(task_data["goal"]) > 0
        and len(task_data["goal"][0]) > 0
        and "obj1_uid" in task_data["goal"][0][0]
    ):
        if task_data["goal"][0][0]["obj1_uid"] in scene["object_list"].keys():
            IS_OK = verify_placement(
                scene["object_list"][task_data["goal"][0][0]["obj1_uid"]],
                scene["world"],
            )
            if not IS_OK:
                print("verify placement failed")
                return -1
    # clean prim velocity because the prim velocity may not zero from the previous scene
    for key in scene["object_list"]:
        clean_prim_velocity(scene["object_list"][key].prim_path)
    # task should not be finished after randomization
    finished = (
        check_finished(
            task_data["goal"],
            pclist=get_current_pcList_by_meshList(
                scene["object_list"], scene["cacheDict"]["meshDict"]
            ),
            articulation_list=scene["articulation_list"],
        )
        == 1
    )
    if finished:
        print("check finished failed")
        return -1
    return 0


def reset_scene(scene: dict) -> None:
    reset_object_xyz(scene["object_list"], scene["meta_infos"]["world_pose_list"])
    reset_articulation_positions(scene)
    for robot, joint_positions, joint_velocities, robot_pose in zip(
        scene["robot_info"]["robot_list"],
        scene["meta_infos"]["joint_positions"],
        scene["meta_infos"]["joint_velocities"],
        scene["meta_infos"]["robot_pose_list"],
    ):
        robot.robot.set_joint_positions(joint_positions)
        robot.robot.set_joint_velocities(joint_velocities)
        robot.robot.set_world_pose(*robot_pose)


def satisfy_replace_existed_object(
    replace_object_config: dict,
    key: str,
    replaced_uid: str,
    added_uid_list: list[str],
    object_config_key_list: list[str],
) -> bool:
    if (
        "option" in replace_object_config[key]
        and "cup_plate_replace" in replace_object_config[key]["option"]
    ):
        if verify_cup_and_plate(
            object_config_key_list,
            key,
            object_config_key_list.index(key),
            replaced_uid,
            added_uid_list,
        ):
            return True
        return False
    else:
        return True


def build_up_scene(
    scene: dict,
    demogen_config: dict,
    default_config: dict,
    task_data: dict,
) -> dict:
    """
    initialize meta_to_fine_projection
    for config:
    object1:
        type: load_object_from_path
        ...
    `object1` is called meta key, which may represent a set of objects in the scene, each time for one object. The uid of the object is called fine key.
    meta_to_fine_projection is a dict, the key is the meta key, the value is the fine key.
    by recording it, we can disactivate last added object and add new object to the scene.
    """
    # 1. initialize meta_to_fine_projection
    if "meta_to_fine_projection" not in scene["cacheDict"]:
        scene["cacheDict"]["meta_to_fine_projection"] = {}
        for key in scene["cacheDict"]["preload_hash_feature"]:
            scene["cacheDict"]["meta_to_fine_projection"][key] = ""

    # 2. initialize configs
    replace_object_config = demogen_config["object_config"]
    added_uid_list = []
    object_config_key_list = list(replace_object_config.keys())
    object_config_key_list.sort()

    # 3. choose new object to replace for each object in the object_config
    for key in object_config_key_list:
        while True:
            replaced_uid = random.choice(
                scene["cacheDict"]["preloaded_object_uid_list"][
                    scene["cacheDict"]["preload_hash_feature"][key]
                ]
            )
            if replaced_uid not in added_uid_list and satisfy_replace_existed_object(
                replace_object_config,
                key,
                replaced_uid,
                added_uid_list,
                object_config_key_list,
            ):
                break
        added_uid_list.append(replaced_uid)

    # 4. remove the old object
    for key, replaced_uid in scene["cacheDict"]["meta_to_fine_projection"].items():
        if (
            replaced_uid in scene["object_list"]
            and replace_object_config[key]["type"] == "load_object_from_path"
        ):
            remove_object_from_scene_by_preload(replaced_uid, scene)

    # 5. add new object and resize it
    for key, replaced_uid in zip(object_config_key_list, added_uid_list):
        # 5-1. existed object
        if replace_object_config[key]["type"] == "existed_object":
            # 5-1-1. activate object if it is not active
            if not scene["cacheDict"]["preloaded_object_list"][
                replaced_uid
            ].prim.IsActive():
                scene["cacheDict"]["preloaded_object_list"][
                    replaced_uid
                ].prim.SetActive(True)

            # 5-1-2. add object to object_list and compute mesh cache for the object
            if replaced_uid not in scene["object_list"]:
                scene["object_list"][replaced_uid] = scene["cacheDict"][
                    "preloaded_object_list"
                ][replaced_uid]
                scene["cacheDict"]["meshDict"][replaced_uid] = get_mesh_info_by_load(
                    scene["object_list"][replaced_uid],
                    os.path.join(
                        default_config["ASSETS_DIR"],
                        "mesh_data",
                        demogen_config["task_name"],
                        f"{replaced_uid}.obj",
                    ),
                )

            if "fixed_size" in replace_object_config[key]:
                resize_object_in_scene_by_uid(
                    replaced_uid,
                    scene,
                    default_config,
                    replace_object_config[key]["fixed_size"],
                    demogen_config,
                )

            # 5-1-3. record the meta_to_fine_projection
            scene["cacheDict"]["meta_to_fine_projection"][key] = replaced_uid

        # 5-2. load_object_from_path
        elif replace_object_config[key]["type"] == "load_object_from_path":
            # 5-2-1. add object to the scene
            add_object_to_scene_from_preload_list(
                replaced_uid, scene, default_config, demogen_config
            )

            # 5-2-2. get the scale of the object
            scale = get_object_scale(
                replace_object_config, key, replaced_uid, scene["object_pool"]
            )

            # 5-2-3. resize the object by scale
            # 5-2-3-1. if scale is in meter, and is float or list[float]
            if scale is not None and "fixed_scale" not in replace_object_config[key]:
                resize_object_in_scene_by_uid(
                    replaced_uid, scene, default_config, scale, demogen_config
                )

            # 5-2-3-2. if scale is relative to the original object, and is float or list[float]
            elif "fixed_scale" in replace_object_config[key]:
                if not isinstance(replace_object_config[key]["fixed_scale"], list):
                    scene["object_list"][replaced_uid].set_local_scale(
                        [replace_object_config[key]["fixed_scale"]] * 3
                    )
                else:
                    scene["object_list"][replaced_uid].set_local_scale(
                        replace_object_config[key]["fixed_scale"]
                    )
                scene["cacheDict"]["meshDict"][replaced_uid] = get_mesh_info_by_load(
                    scene["object_list"][replaced_uid],
                    os.path.join(
                        default_config["ASSETS_DIR"],
                        "mesh_data",
                        demogen_config["task_name"],
                        os.path.dirname(
                            scene["cacheDict"]["preloaded_object_path_list"][
                                replaced_uid
                            ]
                        ),
                        f"{replaced_uid}.obj",
                    ),
                )

            # 5-2-3-3. if scale is not defined, raise error
            else:
                raise ValueError(
                    f"Object {replaced_uid} has no scale information, previous logic is archived, please add `fixed_scale: 1.0` to object config to keep object to its original scale"
                )

            # 5-2-3-4. adjust object scale by thickness if needed
            if (
                "option" in replace_object_config[key]
                and "adjust_thickness" in replace_object_config[key]["option"]
            ):
                adjust_object_scale_by_thickness(
                    scene,
                    replaced_uid,
                    default_config,
                    demogen_config,
                    0.06,
                )

            # 5-2-4. record the meta_to_fine_projection
            scene["cacheDict"]["meta_to_fine_projection"][key] = replaced_uid

        # 5-3. add_additional_object_from_path
        elif replace_object_config[key]["type"] == "add_additional_object_from_path":
            # 5-3-0. get real uid of the object
            if "uid" in replace_object_config[key]:
                replaced_uid = replace_object_config[key]["uid"]
            else:
                replaced_uid = (
                    replace_object_config[key]["path"].split("/")[-1].split(".")[0]
                )

            # 5-3-1. add object to the scene
            add_object_to_scene_from_preload_list(
                replaced_uid, scene, default_config, demogen_config
            )

            # 5-3-2. get the scale of the object
            scale = get_object_scale(
                replace_object_config, key, replaced_uid, scene["object_pool"]
            )

            # 5-3-3. resize the object by scale
            # 5-3-3-1. if scale is in meter, and is float or list[float]
            if scale is not None and "fixed_scale" not in replace_object_config[key]:
                resize_object_in_scene_by_uid(
                    replaced_uid, scene, default_config, scale, demogen_config
                )

            # 5-3-3-2. if scale is relative to the original object, and is float or list[float]
            elif "fixed_scale" in replace_object_config[key]:
                if not isinstance(replace_object_config[key]["fixed_scale"], list):
                    scene["object_list"][replaced_uid].set_local_scale(
                        [replace_object_config[key]["fixed_scale"]] * 3
                    )
                else:
                    scene["object_list"][replaced_uid].set_local_scale(
                        replace_object_config[key]["fixed_scale"]
                    )
                scene["cacheDict"]["meshDict"][replaced_uid] = get_mesh_info_by_load(
                    scene["object_list"][replaced_uid],
                    os.path.join(
                        default_config["ASSETS_DIR"],
                        "mesh_data",
                        demogen_config["task_name"],
                        os.path.dirname(
                            scene["cacheDict"]["preloaded_object_path_list"][
                                replaced_uid
                            ]
                        ),
                        f"{replaced_uid}.obj",
                    ),
                )

            # 5-3-3-3. if scale is not defined, raise error
            else:
                raise ValueError(
                    f"Object {replaced_uid} has no scale information, previous logic is archived, please add `fixed_scale: 1.0` to object config to keep object to its original scale"
                )

            # 5-3-3-4. adjust object scale by thickness if needed
            if (
                "option" in replace_object_config[key]
                and "adjust_thickness" in replace_object_config[key]["option"]
            ):
                adjust_object_scale_by_thickness(
                    scene,
                    replaced_uid,
                    default_config,
                    demogen_config,
                    0.06,
                )

            # 5-3-4. record the meta_to_fine_projection
            scene["cacheDict"]["meta_to_fine_projection"][key] = replaced_uid

    # 6. replace the uid in the goal
    for i in range(len(task_data["goal"])):
        for j in range(len(task_data["goal"][i])):
            if (
                "obj1_uid" in task_data["goal"][i][j]
                and task_data["goal"][i][j]["obj1_uid"]
                in scene["cacheDict"]["meta_to_fine_projection"]
            ):
                task_data["goal"][i][j]["obj1_uid"] = scene["cacheDict"][
                    "meta_to_fine_projection"
                ][task_data["goal"][i][j]["obj1_uid"]]
            if (
                "obj2_uid" in task_data["goal"][i][j]
                and task_data["goal"][i][j]["obj2_uid"]
                in scene["cacheDict"]["meta_to_fine_projection"]
            ):
                task_data["goal"][i][j]["obj2_uid"] = scene["cacheDict"][
                    "meta_to_fine_projection"
                ][task_data["goal"][i][j]["obj2_uid"]]
            if "ignored_uid" in task_data["goal"][i][j]:
                for k in range(len(task_data["goal"][i][j]["ignored_uid"])):
                    if (
                        task_data["goal"][i][j]["ignored_uid"][k]
                        in scene["cacheDict"]["meta_to_fine_projection"]
                    ):
                        task_data["goal"][i][j]["ignored_uid"][k] = scene["cacheDict"][
                            "meta_to_fine_projection"
                        ][task_data["goal"][i][j]["ignored_uid"][k]]

    # 7. replace uid in layout config
    if "layout_config" in demogen_config:
        if demogen_config["layout_config"]["type"] == "random_custom_tableset":
            custom_dict = {}
            if isinstance(demogen_config["layout_config"]["custom_tableset"], list):
                demogen_config["layout_config"]["custom_tableset"] = random.choice(
                    demogen_config["layout_config"]["custom_tableset"]
                )
            for key in demogen_config["layout_config"]["custom_tableset"]:
                custom_dict[scene["cacheDict"]["meta_to_fine_projection"][key]] = (
                    demogen_config["layout_config"]["custom_tableset"][key]
                )
                if (
                    demogen_config["layout_config"]["custom_tableset"][key]["type"]
                    == "scene_graph"
                ):
                    custom_dict[scene["cacheDict"]["meta_to_fine_projection"][key]][
                        "obj2_uid"
                    ] = scene["cacheDict"]["meta_to_fine_projection"][
                        demogen_config["layout_config"]["custom_tableset"][key][
                            "obj2_uid"
                        ]
                    ]
            demogen_config["layout_config"]["custom_tableset"] = custom_dict

    # 8. add object_infos to task_data
    task_data["object_infos"] = {}
    for obj_uid in scene["object_list"]:
        obj_info = scene["object_pool"].get_object_info(obj_uid)
        if obj_info is not None and obj_uid not in task_data["object_infos"]:
            task_data["object_infos"][obj_uid] = obj_info
    for obj_uid in scene["articulation_list"]:
        obj_info = scene["object_pool"].get_object_info(obj_uid)
        if obj_info is not None and obj_uid not in task_data["object_infos"]:
            task_data["object_infos"][obj_uid] = obj_info
    for obj_uid in scene["cacheDict"]["preloaded_object_list"]:
        obj_info = scene["object_pool"].get_object_info(obj_uid)
        if obj_info is not None and obj_uid not in task_data["object_infos"]:
            task_data["object_infos"][obj_uid] = obj_info
    return scene
