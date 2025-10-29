"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import argparse
import copy
import os
import sys

from isaacsim import SimulationApp
from tqdm import tqdm

from genmanip.utils.file_utils import (
    load_default_config,
    load_task_config,
    load_yaml,
    make_dir,
    record_log,
)
from genmanip.utils.utils import (
    check_proxy_exist,
    check_usda_exist,
    parse_demogen_config,
    parse_evalgen_config,
    parse_restart_per_failed,
    parse_restart_per_success,
    setup_logger,
)

current_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(current_dir)


def parse_args() -> argparse.Namespace:
    """Parse the arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-cfg",
        "--config",
        type=str,
        default="configs/tasks/minimal.yml",
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
        default=False,
        action="store_true",
        help="Run in local mode, a quick command to enable Isaac Sim GUI and use local anygrasp server",
    )
    parser.add_argument(
        "--eval",
        default=False,
        action="store_true",
        help="Run in eval mode, generate tasks in 'evaluation_configs' and save to 'tasks' folder",
    )
    parser.add_argument(
        "-wop",
        "--without_planning",
        default=False,
        action="store_true",
        help="Run in without planning mode, only generate layout and save first frame results, for vlm data generation",
    )
    args = parser.parse_args()
    return args


args = parse_args()
config = load_task_config(args.config)
is_local = args.local
is_evalgen = args.eval
is_wop = args.without_planning


simulation_app = SimulationApp({"headless": not is_local})

from genmanip.core.loading.domain_randomization import (
    build_up_scene,
    domain_randomization,
    reset_scene,
)
from genmanip.core.loading.loading import (
    build_scene_from_config,
    clear_scene,
    collect_meta_infos,
    load_object_pool,
    preload_objects,
    preprocess_scene,
    setup_robot_joint_positions,
    update_meta_infos,
    warmup_world,
)
from genmanip.core.pointcloud.pointcloud import get_current_pcList_by_meshList
from genmanip.core.usd_utils import remove_colliders
from genmanip.demogen.evaluate.evaluate import check_finished
from genmanip.demogen.planning.planning import apply_action_by_config
from genmanip.demogen.planning.utils import (
    check_evalgen_finished,
    check_planning_finished,
    corse_process_task_data,
    refine_task_data,
    rewrite_instruction,
)
from genmanip.demogen.recoder.planning_recorder import Logger, collect_task_data

# 0. Basic setup
# 0-0. Isaac Sim hacking to avoid stuck in cooking, https://forums.developer.nvidia.com/t/gpu-memory-usage/300922/8
simulation_app._carb_settings.set("/physics/cooking/ujitsoCollisionCooking", False)

# 0-1. setup logger
logger = setup_logger()

# 0-2. load default config
default_config = load_default_config(
    current_dir, "__None__.json", "local" if is_local else "default"
)
default_config["current_dir"] = current_dir

# 0-3. parse generation config
if not is_evalgen:
    demogen_config_list = parse_demogen_config(config)
else:
    demogen_config_list = parse_evalgen_config(config)

# Main loop
for demogen_config in demogen_config_list:
    # 1. validation check
    # 1-0. check config out of date
    assert (
        "layout_config" in demogen_config
    ), "Your config is out of date, please update it."

    # 1-1. make directory for trajectory
    if not is_evalgen:
        make_dir(
            os.path.join(
                default_config["DEMONSTRATION_DIR"],
                demogen_config["task_name"],
                "trajectory",
            )
        )
    else:
        make_dir(os.path.join(default_config["TASKS_DIR"], demogen_config["task_name"]))

    # 1-2. check if the task is finished
    if is_evalgen:
        if check_evalgen_finished(demogen_config, default_config):
            continue
    else:
        if check_planning_finished(demogen_config, default_config):
            continue

    # 1-3. if proxy exists, warn the user
    if check_proxy_exist():
        logger.warning("Proxy exists, may cost disconnect anygrasp server...")

    # 1-4. if scene usda file does not exist, error and exit
    if not check_usda_exist(default_config, demogen_config):
        logger.error(
            f"USD file does not exist. If the path is right, use `python standalone_tools/usda_gen.py -f saved/assets/scene_usds -r` to generate/re-generate the USDA file."
        )
        continue
    else:
        logger.info(f"USD file exists")

    # 1-5. backup demogen config
    demogen_config_task_backup = copy.deepcopy(demogen_config)

    # 1-6. parse restart per success
    restart_per_success = parse_restart_per_success(demogen_config)
    restart_per_failed = parse_restart_per_failed(demogen_config)

    # Demogen Main Loop
    while True:
        # 2. scene setup
        # 2-0. copy demogen config to keep consistency between different runs
        demogen_config = copy.deepcopy(demogen_config_task_backup)

        # 2-1. build scene from config, include: load scene usda, create robot, create camera, define embodiment, etc.
        scene = build_scene_from_config(
            demogen_config,
            default_config,
            current_dir,
            physics_dt=1 / 30,
            rendering_dt=1 / 30,
            only_depth_rep_for_camera=True,
        )

        # 2-2. load object annotation
        load_object_pool(scene, demogen_config, current_dir)

        # 2-3. preprocess scene by config, function called when config requires
        preprocess_scene(scene, demogen_config)

        # 2-4. preload scaling objects to simulator for better performance, used when generating scaling data
        preload_objects(scene, default_config, demogen_config, without_planning=is_wop)

        # 2-5. remove colliders for default ground plane, TODO: remove this after make sure all scene assets' ground plane has no colliders
        remove_colliders(scene["object_list"]["defaultGroundPlane"].prim_path)

        # 2-6. setup robot joint positions
        setup_robot_joint_positions(
            scene["robot_info"]["robot_list"][0], demogen_config
        )

        # 2-7. warmup physics and camera
        warmup_world(scene, without_depth=demogen_config["mode"] == "benchmark")

        # 2-8. collect object position and robot joint positions
        collect_meta_infos(scene)

        # 2-9. backup demogen config for episode
        demogen_config_episode_backup = copy.deepcopy(demogen_config)

        is_finished = False
        total_success = 0
        total_failed = 0

        # 3. episode loop
        while (
            simulation_app.is_running()
            and total_success < restart_per_success
            and total_failed < restart_per_failed
        ):
            # 3-0. reset demogen config for episode
            demogen_config = copy.deepcopy(demogen_config_episode_backup)

            # 3-1. check if the episode is finished, if finished, break the episode loop
            if not is_evalgen:
                if check_planning_finished(demogen_config, default_config):
                    is_finished = True
                    break
            else:
                if check_evalgen_finished(demogen_config, default_config):
                    is_finished = True
                    break
            total_failed += 1

            # 3-2. reset objects, robots and articulations status to initial state
            print("reset scene")
            reset_scene(scene)

            # TODO: removed line of remove_colliders for default ground plane here, make sure nothing goes wrong

            # 3-3. corse process task data, translate meta task data to fine grained task data
            task_data = corse_process_task_data(demogen_config)

            # 3-4. activate / deactivate objects from preloaded objects
            print("build up scene")
            build_up_scene(scene, demogen_config, default_config, task_data)

            # 3-5. rewrite instruction and get action info list
            task_data = refine_task_data(task_data, demogen_config)

            # 3-6. domain randomization
            print("domain randomization")
            if demogen_config["mode"] != "benchmark":
                if (
                    domain_randomization(
                        scene, default_config, demogen_config, task_data, mode="demogen"
                    )
                    == -1
                ):
                    continue

            # 3-7 update information for articulations, TODO: is this necessary and should it be here?
            update_meta_infos(scene)

            # 3-8. set planner for robots, TODO: should it be here?
            for robot in scene["robot_info"]["robot_list"]:
                robot.set_planner(scene["world"], current_dir)

            # 3-9. collect meta info for recording
            task_data = collect_task_data(
                scene["object_list"],
                scene["robot_info"]["robot_list"],
                load_yaml(
                    os.path.join(
                        current_dir,
                        demogen_config["domain_randomization"]["cameras"][
                            "config_path"
                        ],
                    )
                ),
                task_data,
                scene["cacheDict"]["preloaded_object_path_list"],
                scene["cacheDict"]["preload_object_meta_info"],
            )

            # 3-10. create recorder
            recorder = Logger(
                scene["camera_list"].copy(),
                scene["robot_info"]["robot_list"][0],
                scene["object_list"],
                task_data["instruction"],
                log_dir=(
                    os.path.join(
                        default_config["DEMONSTRATION_DIR"],
                        demogen_config["task_name"],
                        "trajectory",
                    )
                    if not is_evalgen
                    else os.path.join(
                        default_config["TASKS_DIR"],
                        demogen_config["task_name"],
                    )
                ),
                task_data=task_data,
                tcp_config=scene["tcp_configs"]["franka"],
            )

            # if in benchmark mode, only layout is needed, so save and continue
            if demogen_config["mode"] == "benchmark":
                recorder.save(demogen_config["task_name"], args.config)
                continue

            # 3-11. warmup physics after domain randomization
            for _ in range(100):
                scene["world"].step(render=False)

            # if in without planning mode, only first frame is needed, so save and continue
            if is_wop:
                recorder.load_dynamic_info(
                    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                    1,
                    name=f"0/cold_start",
                )
                recorder.save(demogen_config["task_name"], args.config)
                if not is_evalgen:
                    record_log(
                        os.path.join(
                            default_config["DEMONSTRATION_DIR"],
                            demogen_config["task_name"],
                            "trajectory",
                        ),
                        "success",
                    )
                    total_success += 1
                    total_failed -= 1
                else:
                    record_log(
                        os.path.join(
                            default_config["TASKS_DIR"],
                            demogen_config["task_name"],
                        ),
                        "success",
                    )
                continue

            # 4. action loop
            for idx, action_info in enumerate(task_data["task_path"]):
                try:
                    # 4-1. for config action, apply the action and record data
                    is_success = apply_action_by_config(
                        scene,
                        action_info,
                        default_config,
                        demogen_config,
                        recorder,
                        idx,
                    )
                    if not is_success:
                        raise Exception("Subgoal not completed")
                except Exception as e:
                    # 4-2. if action failed, record the failure
                    del recorder
                    logger.error(str(e))
                    if not is_evalgen:
                        record_log(
                            os.path.join(
                                default_config["DEMONSTRATION_DIR"],
                                demogen_config["task_name"],
                                "trajectory",
                            ),
                            str(e),
                        )
                    else:
                        record_log(
                            os.path.join(
                                default_config["TASKS_DIR"],
                                demogen_config["task_name"],
                            ),
                            str(e),
                        )
                    break

            # if recorder is deleted, continue the episode loop
            if "recorder" not in locals() or "recorder" not in globals():
                logger.error("Task not completed, retry......")
                continue

            # 4-3. step physics and later check if the task is finished
            for _ in tqdm(range(30)):
                scene["world"].step(render=False)
            if len(task_data["goal"]) == 0 or len(task_data["goal"][0]) == 0:
                finished = True
            else:
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
            rewrite_instruction(task_data, demogen_config)

            # 4-4. if the task is finished, save the recorder and record the success
            if finished:
                recorder.save(demogen_config["task_name"], args.config)
                if not is_evalgen:
                    record_log(
                        os.path.join(
                            default_config["DEMONSTRATION_DIR"],
                            demogen_config["task_name"],
                            "trajectory",
                        ),
                        "success",
                    )
                    total_success += 1
                    total_failed -= 1
                else:
                    record_log(
                        os.path.join(
                            default_config["TASKS_DIR"],
                            demogen_config["task_name"],
                        ),
                        "success",
                    )
            # else, record the failure
            else:
                print("Failed")
                if not is_evalgen:
                    record_log(
                        os.path.join(
                            default_config["DEMONSTRATION_DIR"],
                            demogen_config["task_name"],
                            "trajectory",
                        ),
                        "failed",
                    )
                else:
                    record_log(
                        os.path.join(
                            default_config["TASKS_DIR"],
                            demogen_config["task_name"],
                        ),
                        "failed",
                    )
            # back to episode loop, reset, randomize and record again

        # 5. clear scene when achieving restart_per_success or reached expected episode number
        clear_scene(scene, demogen_config, current_dir)

        # 5-1. if reached expected episode number, break the task loop
        if is_finished:
            break
    # then process next task in demogen_config_list

# 6. close simulation
simulation_app.close()
