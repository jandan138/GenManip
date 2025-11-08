"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import argparse
import os
import sys

from isaacsim import SimulationApp
from tqdm import tqdm

from genmanip.utils.file_utils import (
    load_default_config,
    load_dict_from_pkl,
    load_yaml,
    make_dir,
)
from genmanip.utils.utils import parse_eval_config, setup_logger

current_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(current_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-r",
        "--receive_port",
        type=int,
        default=10000,
        help="Receive port for the evaluator",
    )
    parser.add_argument(
        "-s",
        "--send_port",
        type=int,
        default=10001,
        help="Send port for the evaluator",
    )
    parser.add_argument(
        "-cfg",
        "--config",
        type=str,
        default="configs/tasks/minimal.yml",
        help="Path to the YAML config file",
    )
    parser.add_argument(
        "-l",
        "--local",
        action="store_true",
        help="Run in local mode, a quick command to enable Isaac Sim GUI",
    )
    parser.add_argument(
        "-n",
        "--num_steps",
        type=int,
        default=600,
        help="Number of steps to run the evaluation",
    )
    parser.add_argument(
        "-wor",
        "--without_render",
        action="store_true",
        help="Run in without render mode, only record the data",
    )
    parser.add_argument(
        "-rr",
        "--random_randomization",
        action="store_true",
        help="Run in random randomization mode, enable randomization configs in eval config",
    )
    return parser.parse_args()


args = parse_args()
config = load_yaml(args.config)

simulation_app = SimulationApp({"headless": not args.local})

from genmanip.core.loading.domain_randomization import random_texture_for_eval
from genmanip.core.loading.loading import (
    build_scene_from_config,
    clear_scene,
    collect_meta_infos,
    load_object_pool,
    preprocess_scene,
    recovery_scene,
    warmup_world,
)
from genmanip.core.pointcloud.pointcloud import get_current_pcList_by_meshList
from genmanip.core.usd_utils import remove_colliders
from genmanip.demogen.evaluate.evaluate import check_finished
from genmanip.demogen.planning.utils import check_eval_finished
from genmanip_bench.evaluate.evaluator import Evaluator, parse_lmdb_data
from genmanip_bench.request_model.socket_utils import (
    create_receive_port_and_attach,
    create_send_port_and_wait,
)

# 0. Basic Setup
# 0-0. Isaac Sim hacking to avoid stuck in cooking, https://forums.developer.nvidia.com/t/gpu-memory-usage/300922/8
simulation_app._carb_settings.set("/physics/cooking/ujitsoCollisionCooking", False)

# 0-1. setup logger
logger = setup_logger()

# 0-2. load default config
default_config = load_default_config(
    current_dir, "__None__.json", "local" if args.local else "default"
)
eval_config_list = parse_eval_config(config)

# 0-3. create receive and send ports, need to launch model client before running this script
receive_port = create_receive_port_and_attach(args.receive_port)
send_port = create_send_port_and_wait(args.send_port)

# 1. Evaluate
for eval_config in eval_config_list:
    # 1-0. make directory for the evaluation
    make_dir(os.path.join(default_config["EVAL_RESULT_DIR"], eval_config["task_name"]))

    # 1-1. check if the evaluation is finished
    seed = check_eval_finished(eval_config, default_config)
    if seed == -1:
        continue
    seed = str(seed).zfill(3)
    make_dir(
        os.path.join(default_config["EVAL_RESULT_DIR"], eval_config["task_name"], seed)
    )

    # 1-2. build scene from config, include: load scene usda, create robot, create camera, define embodiment, etc.
    scene = build_scene_from_config(
        eval_config,
        default_config,
        current_dir,
        is_eval=True,
        physics_dt=1 / 30,
        rendering_dt=1 / 30,
        only_depth_rep_for_camera=True,
    )

    # 1-3. load object pool, preprocess scene, warmup world, collect meta infos
    load_object_pool(scene, eval_config, current_dir)
    preprocess_scene(scene, eval_config)
    warmup_world(scene)
    collect_meta_infos(scene)

    # 1-4. create evaluator
    evaluator = Evaluator(
        scene,
        eval_config["instruction"],
        os.path.join(default_config["EVAL_RESULT_DIR"], eval_config["task_name"]),
        current_dir,
        send_port=send_port,
        receive_port=receive_port,
        is_relative_action=True,
    )

    # 2. Main Loop for evaluation one task for several times
    while simulation_app.is_running():
        # 2-0. load meta info and planning data for objects and layout information
        meta_info = load_dict_from_pkl(
            os.path.join(
                default_config["TASKS_DIR"],
                eval_config["task_name"],
                f"{seed}/meta_info.pkl",
            )
        )
        planning_data = parse_lmdb_data(
            os.path.join(
                default_config["TASKS_DIR"],
                eval_config["task_name"],
                f"{seed}",
            )
        )

        # 2-1. recovery scene in layout, including load objects and setup layout
        layout = recovery_scene(
            scene, evaluator, meta_info["task_data"], eval_config, default_config
        )

        # 2-2. randomize the texture / other randomization if needed
        if args.random_randomization:
            random_texture_for_eval(
                scene,
                default_config,
                eval_config,
            )

        # 2-3. update task data
        eval_config["generation_config"]["goal"] = meta_info["task_data"]["goal"]
        evaluator.update_task_data(meta_info["task_data"], planning_data)

        # 2-4. remove colliders for default ground plane, TODO: remove this after make sure all scene assets' ground plane has no colliders
        remove_colliders(scene["object_list"]["defaultGroundPlane"].prim_path)

        # 2-5. warmup physics
        for _ in range(50):
            scene["world"].step()

        # 2-6. initialize evaluator
        evaluator.initialize(seed)

        # 3. main loop for singleevaluation
        step_cnt = 0
        for _ in tqdm(range(args.num_steps)):
            # 3-0. request action from model client
            action = evaluator.request_action(without_render=args.without_render)

            # 3-1. set joint position targets
            scene["robot_info"]["robot_list"][0].robot_view.set_joint_position_targets(
                action,
                joint_indices=scene["robot_info"]["robot_list"][0].default_dof_indices,
            )

            # 3-2. step the world
            scene["world"].step(render=not args.without_render)

            # 3-3. record the data
            evaluator.record(is_save_image=not args.without_render)

            # 3-4. check if the task goal is finished every 10 steps
            if step_cnt % 10 == 0:
                finished = (
                    finished + 10
                    if (
                        check_finished(
                            eval_config["generation_config"]["goal"],
                            pclist=get_current_pcList_by_meshList(
                                scene["object_list"], scene["cacheDict"]["meshDict"]
                            ),
                            articulation_list=scene["articulation_list"],
                        )
                        == 1
                    )
                    else 0
                )

                # 3-5. if the task goal is finished 100 times, break the loop
                if finished != 0:
                    print(f"finished {finished} times")
                if finished >= 100:
                    break
            step_cnt += 1

        # 3-6. finish the evaluation
        evaluator.finish(
            finished,
            check_finished(
                eval_config["generation_config"]["goal"],
                pclist=get_current_pcList_by_meshList(
                    scene["object_list"], scene["cacheDict"]["meshDict"]
                ),
                articulation_list=scene["articulation_list"],
            ),
        )

        # 3-7. get next seed
        seed = check_eval_finished(eval_config, default_config)
        if seed == -1:
            break
        seed = str(seed).zfill(3)
        make_dir(
            os.path.join(
                default_config["EVAL_RESULT_DIR"], eval_config["task_name"], seed
            )
        )

    # 3-8. clear the scene
    clear_scene(scene, eval_config, current_dir)

# 4. close the simulation app
simulation_app.close()
