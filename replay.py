import os
from tqdm import tqdm
import sys
from isaacsim import SimulationApp

current_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(current_dir)

from argparse import ArgumentParser
from genmanip.utils.file_utils import load_yaml

parser = ArgumentParser()
parser.add_argument(
    "-cfg",
    "--config",
    type=str,
    default="/closedlooptest/configs/sandwich_plate_all_none.yaml",
    required=True,
    help="Path to the YAML config file",
)
parser.add_argument("-l", "--local", action="store_true")
args = parser.parse_args()
config = load_yaml(args.config)

simulation_app = SimulationApp({"headless": not args.local})

from genmanip.utils.file_utils import load_default_config
from genmanip.utils.utils import setup_logger
from genmanip_bench.evaluate.evaluator import parse_lmdb_data
from genmanip.utils.file_utils import load_dict_from_pkl, make_dir
from genmanip.utils.utils import parse_eval_config
from genmanip.demogen.planning.utils import (
    check_eval_finished,
    adjust_arm_gripper_action_by_embodiment,
)
from genmanip.core.loading.loading import (
    build_scene_from_config,
    clear_scene,
    warmup_world,
    preprocess_scene,
    collect_meta_infos,
    load_object_pool,
)
from genmanip.core.loading.loading import recovery_scene
from genmanip.core.usd_utils import remove_colliders

simulation_app._carb_settings.set("/physics/cooking/ujitsoCollisionCooking", False)
logger = setup_logger()
default_config = load_default_config(current_dir, "default.json")
eval_config_list = parse_eval_config(config)
for eval_config in eval_config_list:
    make_dir(os.path.join(default_config["EVAL_RESULT_DIR"], eval_config["task_name"]))
    seed = check_eval_finished(eval_config, default_config)
    if seed == -1:
        continue
    seed = str(seed).zfill(3)
    make_dir(
        os.path.join(default_config["EVAL_RESULT_DIR"], eval_config["task_name"], seed)
    )
    scene = build_scene_from_config(
        eval_config,
        default_config,
        current_dir,
        is_eval=True,
        physics_dt=1 / 30,
        rendering_dt=1 / 30,
        only_depth_rep_for_camera=True,
    )
    load_object_pool(scene, eval_config, current_dir)
    preprocess_scene(scene, eval_config)
    warmup_world(scene)
    collect_meta_infos(scene)
    while simulation_app.is_running():
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
        layout = recovery_scene(
            scene, None, meta_info["task_data"], eval_config, default_config
        )
        eval_config["generation_config"]["goal"] = meta_info["task_data"]["goal"]
        remove_colliders(scene["object_list"]["defaultGroundPlane"].prim_path)
        for _ in range(50):
            scene["world"].step()
        for i in range(len(planning_data["action"])):
            arm_action = planning_data["action"][i]
            gripper_action = planning_data["gripper_action"][i]
            action = adjust_arm_gripper_action_by_embodiment(
                arm_action,
                gripper_action,
                scene["robot_info"]["robot_list"][0].embodiment_name,
            )
            scene["robot_info"]["robot_list"][0].robot_view.set_joint_position_targets(
                action,
                joint_indices=scene["robot_info"]["robot_list"][0].default_dof_indices,
            )
            scene["world"].step(render=True)
        seed = check_eval_finished(eval_config, default_config)
        if seed == -1:
            break
        seed = str(seed).zfill(3)
        make_dir(
            os.path.join(
                default_config["EVAL_RESULT_DIR"], eval_config["task_name"], seed
            )
        )
    clear_scene(scene, eval_config, current_dir)
simulation_app.close()
