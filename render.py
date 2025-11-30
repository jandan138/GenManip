"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import argparse
from filelock import SoftFileLock
import gc
import os
import sys

from isaacsim import SimulationApp # type: ignore[import-untyped]
import numpy as np
from tqdm import tqdm

from genmanip.utils.standalone.file_utils import (
    load_default_config,
    load_dict_from_pkl,
    load_yaml,
    make_dir,
)
from genmanip.utils.standalone.utils import parse_demogen_config, setup_logger

current_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(current_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-cfg",
        "--config",
        default="configs/tasks/minimal.yml",
        type=str,
        help="Path to the YAML config file",
    )
    parser.add_argument(
        "--record",
        type=str,
        required=False,
        default="just for record",
        help="Helps to record user name for monitoring in htop/nvidia-smi/nvitop etc.",
    )
    parser.add_argument(
        "-l",
        "--local",
        action="store_true",
        help="Run in local mode, a quick command to enable Isaac Sim GUI",
    )
    parser.add_argument(
        "-r",
        "--render_first_frame",
        action="store_true",
        help="Only render the first frame",
    )
    parser.add_argument(
        "-wod",
        "--without_depth",
        action="store_true",
        help="Without render and save depth info",
    )
    parser.add_argument(
        "-a",
        "--add_random_position_camera",
        action="store_true",
        help="Add random position camera",
    )
    parser.add_argument(
        "-d",
        "--downsample",
        type=int,
        default=1,
        help="Downsample the rendering frame rate",
    )
    parser.add_argument(
        "-p",
        "--save_pointcloud",
        action="store_true",
        help="Save pointcloud",
    )
    parser.add_argument(
        "--high_quality", action="store_true", help="High quality rendering"
    )
    return parser.parse_args()


args = parse_args()
config = load_yaml(args.config)

simulation_app = SimulationApp({"headless": not args.local})

from genmanip.core.loader.domain_randomization import random_texture
from genmanip.core.loader.scene import (
    build_scene_from_config,
    clear_scene,
    collect_meta_infos,
    load_object_pool,
    preprocess_scene,
    recovery_scene_render,
    warmup_world,
)
from genmanip.utils.pointcloud.pointcloud import (
    meshDict2pointCloudDict,
    get_current_pointCloutList,
    objectList2meshList,
)
from genmanip.core.embodiment.utils import create_joint_xform_list
from genmanip.core.sensor.camera import set_camera_look_at
from genmanip.utils.usd_utils import remove_colliders
from genmanip.demogen.recoder.render_recorder import Logger
from genmanip.demogen.recoder.utils import parse_planning_result

# 0. Basic Setup
# 0-0. Isaac Sim hacking to avoid stuck in cooking, https://forums.developer.nvidia.com/t/gpu-memory-usage/300922/8
simulation_app._carb_settings.set("/physics/cooking/ujitsoCollisionCooking", False)

# 0-1. setup logger
logger = setup_logger()

# 0-2. load default config
default_config = load_default_config(
    current_dir, "__None__.json", "local" if args.local else "default"
)
default_config["current_dir"] = current_dir

# 0-3. parse generation config
demogen_config_list = parse_demogen_config(config)

# 1. Main Loop for rendering
for demogen_config in demogen_config_list:
    # 1-0. make directory for rendering
    make_dir(
        os.path.join(
            default_config["DEMONSTRATION_DIR"], demogen_config["task_name"], "render"
        )
    )

    # 1-1. build scene from config, include: load scene usda, create robot, create camera, define embodiment, etc.
    scene = build_scene_from_config(
        demogen_config,
        default_config,
        current_dir,
        physics_dt=1 / 600000.0,
        rendering_dt=1 / 600000.0,
        is_eval=True,
        is_render=True,
        save_pointcloud=args.save_pointcloud,
    )

    # 1-2. load object pool, preprocess scene, warmup world, collect meta infos
    load_object_pool(scene, demogen_config, current_dir)
    preprocess_scene(scene, demogen_config)
    warmup_world(scene)
    collect_meta_infos(scene)

    # 1-3. remove all colliders to speed up physics step
    for object in scene["object_list"].values():
        remove_colliders(object.prim_path)

    # 1-4. list all trajectory directories
    dir_list = os.listdir(
        os.path.join(
            default_config["DEMONSTRATION_DIR"],
            demogen_config["task_name"],
            "trajectory",
        )
    )
    logger.info(f"rendering {len(dir_list)} trajectories")

    # 2. Main Loop for rendering
    for dir in dir_list:
        # 2-0. check if the trajectory directory exists
        if not os.path.isdir(
            os.path.join(
                default_config["DEMONSTRATION_DIR"],
                demogen_config["task_name"],
                "trajectory",
                dir,
            )
        ):
            continue
        if os.path.isdir(
            os.path.join(
                default_config["DEMONSTRATION_DIR"],
                demogen_config["task_name"],
                "trajectory",
                dir,
            )
        ) and os.path.exists(
            os.path.join(
                default_config["DEMONSTRATION_DIR"],
                demogen_config["task_name"],
                "render",
                dir,
            )
        ):
            logger.info(f"skip {dir} because it is already rendered")
            continue

        # 2-1. create lock file for avoiding multiple rendering
        lock_file = os.path.join(
            default_config["DEMONSTRATION_DIR"],
            demogen_config["task_name"],
            "render",
            f"render_{dir}_soft.lock",
        )
        lock = SoftFileLock(lock_file, timeout=0)
        try:
            executed = False
            with lock:
                # if trajectory directory exists and render directory does not exist, then make render directory and load meta info
                if os.path.isdir(
                    os.path.join(
                        default_config["DEMONSTRATION_DIR"],
                        demogen_config["task_name"],
                        "trajectory",
                        dir,
                    )
                ) and not os.path.exists(
                    os.path.join(
                        default_config["DEMONSTRATION_DIR"],
                        demogen_config["task_name"],
                        "render",
                        dir,
                    )
                ):
                    make_dir(
                        os.path.join(
                            default_config["DEMONSTRATION_DIR"],
                            demogen_config["task_name"],
                            "render",
                            dir,
                        )
                    )
                else:
                    raise ValueError(f"render directory {dir} already exists")

                # 2-2. load meta info
                meta_info = load_dict_from_pkl(
                    os.path.join(
                        default_config["DEMONSTRATION_DIR"],
                        demogen_config["task_name"],
                        "trajectory",
                        dir,
                        "meta_info.pkl",
                    )
                )

                # 2-3. set camera, add random position camera if needed
                input_camera_dict = scene["camera_list"].copy()
                if args.add_random_position_camera:
                    # avoid the camera is in the back of the robot
                    random_azimuth = np.random.uniform(-150, 150)
                    random_elevation = np.random.uniform(30, 50)
                    distance = np.random.uniform(0.7, 1.2)
                    set_camera_look_at(
                        input_camera_dict["camera1"],
                        np.array([0, 0, 1.1]),
                        distance=distance,
                        azimuth=random_azimuth,
                        elevation=random_elevation,
                    )
                else:
                    input_camera_dict.pop("camera1")

                # 2-4. create recorder
                recorder = Logger(
                    input_camera_dict,
                    scene["robot_info"]["robot_list"][0],
                    meta_info["task_data"]["instruction"],
                    log_dir=os.path.join(
                        default_config["DEMONSTRATION_DIR"],
                        demogen_config["task_name"],
                        "render",
                        dir,
                    ),
                    task_data=meta_info["task_data"],
                    tcp_config=scene["tcp_configs"]["franka"],
                )

                # 2-5. recovery scene initial layout and joint state
                recovery_scene_render(
                    scene, meta_info["task_data"], demogen_config, default_config
                )

                # 2-6. random texture
                random_texture(
                    scene,
                    default_config,
                    demogen_config,
                    table_without_collider=True,
                )

                # 2-7. parse planning result, get object position, orientation, scale, joint world pose, etc.
                data_list = parse_planning_result(
                    dir, default_config, demogen_config, scene
                )

                # 2-8. New version of rendering enable using world.render instead of world.step, but need to record world pose of robot links
                has_joint_world_pose = "joint_world_pose" in data_list[0]
                if has_joint_world_pose:
                    joint_xform_list = create_joint_xform_list(
                        scene["robot_info"]["robot_list"][0].robot
                    )

                # 2-9. warmup world
                for _ in range(10):
                    if has_joint_world_pose:
                        for joint_name, joint_xform in joint_xform_list.items():  # type: ignore[attr-defined]
                            joint_xform.set_world_pose(
                                *data_list[0]["joint_world_pose"][joint_name]
                            )
                    else:
                        scene["robot_info"]["robot_list"][0].robot.set_joint_positions(
                            data_list[0]["qpos"]
                        )
                    for key in scene["object_list"]:
                        if key == "00000000000000000000000000000000":
                            continue
                        scene["object_list"][key].set_world_pose(
                            data_list[0]["obj_info"][key]["position"],
                            data_list[0]["obj_info"][key]["orientation"],
                        )
                        scene["object_list"][key].set_local_scale(
                            data_list[0]["obj_info"][key]["scale"]
                        )
                    if has_joint_world_pose:
                        scene["world"].step()
                    else:
                        scene["world"].render()

                if args.downsample > 1:
                    data_list = data_list[:: args.downsample]

                # 3. Main Loop for rendering single episode
                print(
                    "rendering data with length: ",
                    len(data_list),
                    "in",
                    "render" if has_joint_world_pose else "step",
                    "mode",
                )

                if args.save_pointcloud:
                    scene["cacheDict"]["meshDict"] = objectList2meshList(
                        scene["object_list"]
                    )
                    pointDict = meshDict2pointCloudDict(scene["cacheDict"]["meshDict"])
                    if has_joint_world_pose:
                        pointJointDict = meshDict2pointCloudDict
                for data in tqdm(data_list):
                    # 3-1. set robot state
                    if has_joint_world_pose:
                        for joint_name, joint_xform in joint_xform_list.items():  # type: ignore[attr-defined]
                            joint_xform.set_world_pose(
                                *data["joint_world_pose"][joint_name]
                            )
                    else:
                        scene["robot_info"]["robot_list"][0].robot.set_joint_positions(
                            data["qpos"]
                        )

                    # 3-2. set object state
                    for key in scene["object_list"]:
                        if key == "00000000000000000000000000000000":
                            continue
                        scene["object_list"][key].set_world_pose(
                            data["obj_info"][key]["position"],
                            data["obj_info"][key]["orientation"],
                        )
                        scene["object_list"][key].set_local_scale(
                            data["obj_info"][key]["scale"]
                        )

                    # 3-3. render or step
                    if has_joint_world_pose:
                        scene["world"].render()
                    else:
                        scene["world"].step()

                    if args.high_quality:
                        for _ in range(50):
                            scene["world"].render()
                            scene["world"].get_observations()

                    # 3-4. load dynamic info
                    if args.save_pointcloud:
                        pointcloud = get_current_pointCloutList(
                            scene["object_list"], pointDict  # type: ignore[attr-defined]
                        )
                        if has_joint_world_pose:
                            pointcloud.update(
                                {
                                    "robot": get_current_pointCloutList(
                                        joint_xform_list, pointJointDict  # type: ignore[attr-defined]
                                    )
                                }
                            )
                    else:
                        pointcloud = None
                    recorder.load_dynamic_info(
                        data["obj_info"],
                        data["action"],
                        data["qpos"],
                        data["qvel"],
                        data["gripper_close"],
                        data["name"],
                        pointcloud=pointcloud,
                    )

                    # if render first frame, then break
                    if args.render_first_frame:
                        break

                # 4. save render result after rendering
                recorder.save(without_depth=args.without_depth)
                gc.collect()
                executed = True

            # remove lock file after rendering
            if executed and os.path.exists(lock_file):
                os.remove(lock_file)
        except Exception as e:
            logger.info(f"error in rendering {dir}: {e}")

    # 5. clear scene after rendering single task and start next task
    clear_scene(scene, demogen_config, current_dir)

# 6. close Isaac Sim
simulation_app.close()
