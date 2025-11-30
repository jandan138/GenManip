import os
import sys
from isaacsim import SimulationApp
current_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(current_dir)

from argparse import ArgumentParser
from genmanip.utils.standalone.file_utils import load_json, load_yaml

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

from omni.isaac.core.utils.prims import delete_prim, get_prim_at_path  # type: ignore
from genmanip.core.metrics.metrics import check_finished
from genmanip.utils.standalone.file_utils import load_default_config
from genmanip.utils.standalone.utils import setup_logger
from genmanip.core.evaluator.evaluator import Evaluator, parse_lmdb_data
from genmanip.utils.usd_utils.export_utils import export
from genmanip.utils.standalone.file_utils import load_dict_from_pkl, make_dir
from genmanip.utils.standalone.utils import parse_eval_config
from genmanip.core.loader.scene import (
    build_scene_from_config,
    clear_scene,
    warmup_world,
    preprocess_scene,
    collect_meta_infos,
    load_object_pool,
)
from genmanip.core.loader.scene import recovery_scene
from genmanip.utils.usd_utils import remove_colliders
from filelock import SoftFileLock

def check_eval_finished(eval_config, default_config):
    lock_file = os.path.join(
        default_config["EVAL_RESULT_DIR"], eval_config["task_name"], "eval_soft.lock"
    )
    try:
        with SoftFileLock(lock_file, timeout=600.0):
            task_dir = os.path.join(
                default_config["EVAL_RESULT_DIR"],
                eval_config["task_name"],
            )
            if os.path.exists(task_dir):
                evaluation_num = len(os.listdir(task_dir)) - 1
                if evaluation_num >= eval_config["num_test"]:
                    if os.path.exists(lock_file):
                        os.remove(lock_file)
                    return -1
                else:
                    return evaluation_num
            return 0
    except:
        raise Exception(
            f"Filelock timeout, try to delete the lock file by python standalone_tools/cleanup_lockfiles.py"
        )

simulation_app._carb_settings.set("/physics/cooking/ujitsoCollisionCooking", False)
logger = setup_logger()
if args.local:
    default_config = load_default_config(current_dir, "__None__.json", "local")
else:
    default_config = load_default_config(current_dir, "default.json")
eval_config_list = parse_eval_config(config)
default_config["EVAL_RESULT_DIR"] = "saved/eval_usd"
for eval_config in eval_config_list:
    make_dir(os.path.join(default_config["EVAL_RESULT_DIR"], eval_config["task_name"]))
    seed = check_eval_finished(eval_config, default_config)
    if seed == -1:
        continue
    seed = str(seed).zfill(3)
    scene = build_scene_from_config(
        eval_config,
        default_config,
        current_dir,
        is_eval=True,
        physics_dt=1 / 60,
        rendering_dt=1 / 60,
        only_depth_rep_for_camera=True,
    )
    load_object_pool(scene, eval_config, current_dir)
    preprocess_scene(scene, eval_config)
    warmup_world(scene)
    collect_meta_infos(scene)
    evaluator = Evaluator(
        scene,
        eval_config["instruction"],
        os.path.join(default_config["EVAL_RESULT_DIR"], eval_config["task_name"]),
        current_dir,
        is_relative_action=True,
    )
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
            scene, evaluator, meta_info["task_data"], eval_config, default_config
        )
        eval_config["generation_config"]["goal"] = meta_info["task_data"]["goal"]
        evaluator.update_task_data(meta_info["task_data"], planning_data)
        remove_colliders(scene["object_list"]["defaultGroundPlane"].prim_path)
        for _ in range(50):
            scene["world"].step()
        export(
            os.path.join(
                default_config["EVAL_RESULT_DIR"],
                eval_config["task_name"],
                f"{seed}.usd",
            ),
            [get_prim_at_path(f"/World/{scene['uuid']}")],
        )
        seed = check_eval_finished(eval_config, default_config)
        if seed == -1:
            break
        seed = str(seed).zfill(3)
    clear_scene(scene, eval_config, current_dir)
simulation_app.close()
