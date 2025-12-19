from datetime import datetime
import os
import copy
import logging
import numpy as np
import sys
from tqdm import tqdm
import traceback
import uuid

from genmanip.core.scene.scene import Scene
from genmanip.core.skill.utils import SkillFactory
from genmanip.demogen.recoder.planning_recorder import PlanningRecorder, collect_task_data
from genmanip.demogen.workflow.utils import (
    check_evalgen_finished,
    check_planning_finished,
    corse_process_task_data,
    refine_task_data,
    rewrite_instruction,
)
from genmanip.utils.loader.domain_randomization import (
    build_up_scene,
    domain_randomization,
    reset_scene,
)
from genmanip.utils.loader.scene import (
    clear_scene,
    preload_objects,
    setup_robot_joint_positions,
    update_meta_infos,
)
from genmanip.utils.standalone.file_utils import (
    load_default_config,
    load_task_config,
    load_yaml,
    make_dir,
    record_log,
)
from genmanip.utils.standalone.utils import (
    check_proxy_exist,
    check_usda_exist,
    parse_demogen_config,
    parse_evalgen_config,
    parse_restart_per_failed,
    parse_restart_per_success,
    setup_logger,
)
from genmanip.utils.standalone.version_utils import process_archived_config
from genmanip.utils.standalone.utils import ColorFormatter
from genmanip.utils.usd_utils import remove_colliders



class DemoGenWorkflow:
    def __init__(
        self,
        args,
        simulation_app,
        current_dir,
    ):
        self.args = args
        self.simulation_app = simulation_app
        self.current_dir = current_dir
        self.is_local = args.local
        self.is_evalgen = args.eval
        self.is_wop = args.without_planning
        self.logger = setup_logger()
        log_dir = os.path.join(current_dir, "logs", "demogen")
        mac_addr = uuid.getnode()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H_%M_%S_%f")
        os.makedirs(log_dir, exist_ok=True)

        log_path = os.path.join(log_dir, f"{mac_addr}_{timestamp}.log")

        logger_name = "DemogenWorkflow"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)

        if not self.logger.handlers:
            # ---- file handler (no color) ----
            fh = logging.FileHandler(log_path)
            fh.setLevel(logging.INFO)
            file_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            fh.setFormatter(file_fmt)
            self.logger.addHandler(fh)

            # ---- console handler (color) ----
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(logging.INFO)
            color_fmt = ColorFormatter("%(asctime)s [%(levelname)s] %(message)s")
            ch.setFormatter(color_fmt)
            self.logger.addHandler(ch)

            self.logger.propagate = False

        self.logger.info("===== Demogen Workflow started =====")

        self.config = load_task_config(args.config)
        self.default_config = load_default_config(
            self.current_dir, "__None__.json", "local" if self.is_local else "default"
        )
        if not self.is_evalgen:
            self.demogen_config_list = parse_demogen_config(self.config)
        else:
            self.demogen_config_list = parse_evalgen_config(self.config)

    def run(self):
        for demogen_config in self.demogen_config_list:
            try:
                self._process_single_task(demogen_config)
            except Exception as e:
                self.logger.error(
                    f"Error processing task {demogen_config.get('task_name')}: {e}"
                )
                self.logger.error(traceback.format_exc())
                continue
        self.simulation_app.close()

    def _preprocess_single_task(self, demogen_config):
        process_archived_config(demogen_config)
        save_dir = self._get_save_dir(demogen_config)
        make_dir(save_dir)
        if self._check_global_finished(demogen_config):
            return
        if check_proxy_exist():
            self.logger.warning("Proxy exists, may cost disconnect anygrasp server...")
        if not check_usda_exist(self.default_config, demogen_config):
            self.logger.error(
                f"USD file does not exist. If the path is right, use `python standalone_tools/usda_gen.py -f saved/assets/scene_usds -r` to generate/re-generate the USDA file."
            )
            return
        else:
            self.logger.info(f"USD file exists")

    def _process_single_task(self, demogen_config):
        self._preprocess_single_task(demogen_config)
        demogen_config_task_backup = copy.deepcopy(demogen_config)
        restart_per_success = parse_restart_per_success(demogen_config)
        restart_per_failed = parse_restart_per_failed(demogen_config)

        while True:
            demogen_config = copy.deepcopy(demogen_config_task_backup)
            scene = self._initialize_scene(demogen_config)

            # Episode counters
            counters = {"success": 0, "failed": 0}
            is_task_finished = False

            demogen_config_episode_backup = copy.deepcopy(demogen_config)
            # 3. Episode loop
            while (
                self.simulation_app.is_running()
                and counters["success"] < restart_per_success
                and counters["failed"] < restart_per_failed
            ):
                demogen_config = copy.deepcopy(demogen_config_episode_backup)
                # 3-1. Check finish condition
                if self._check_global_finished(demogen_config):
                    is_task_finished = True
                    break

                counters["failed"] += 1

                episode_result = self._run_episode(scene, demogen_config)

                if episode_result == "success":
                    counters["success"] += 1
                    counters["failed"] -= 1
                elif episode_result == "retry":
                    counters["failed"] -= 1
                    continue
                elif episode_result == "failed":
                    pass  # Keep the incremented failed count

            clear_scene(scene, demogen_config, self.current_dir)

            if is_task_finished:
                break

    def _initialize_scene(self, demogen_config):
        scene = Scene(scene_config=demogen_config)
        scene.initialize(
            default_config=self.default_config,
            scene_config=demogen_config,
            physics_dt=1 / 30,
            rendering_dt=1 / 30,
            only_depth_rep_for_camera=True,
        )

        preload_objects(
            scene, self.default_config, demogen_config, without_planning=self.is_wop
        )

        if "defaultGroundPlane" in scene.object_list:
            remove_colliders(scene.object_list["defaultGroundPlane"].prim_path)

        setup_robot_joint_positions(scene.robot_list[0], demogen_config)
        scene.post_initialize()
        return scene

    def _run_episode(self, scene, demogen_config):
        self.logger.info("Reset scene to initial state")
        reset_scene(scene)

        self.task_data = corse_process_task_data(demogen_config)

        self.logger.info("Build up scene and activate/deactivate objects")
        build_up_scene(scene, demogen_config, self.default_config, self.task_data)

        self.task_data = refine_task_data(self.task_data, demogen_config)
        scene.build_metrics_manager(self.task_data["goal"])

        self.logger.info("Start domain randomization")
        if demogen_config["mode"] != "benchmark":
            if (
                domain_randomization(
                    scene,
                    self.default_config,
                    demogen_config,
                    self.task_data,
                    self.logger,
                )
                == -1
            ):
                self.logger.info("Domain randomization failed, retry")
                return "retry"
        self.logger.info("Domain randomization finished")

        update_meta_infos(scene)

        self.task_data = collect_task_data(
            scene.object_list,
            scene.robot_list,
            load_yaml(
                os.path.join(
                    self.current_dir,
                    demogen_config["domain_randomization"]["cameras"]["config_path"],
                )
            ),
            self.task_data,
            scene.cache_library.preloaded_object_path_list,
            scene.cache_library.preload_object_meta_info,
        )
        self.save_dir = self._get_save_dir(demogen_config)

        self.recorder = PlanningRecorder(
            scene.camera_list.copy(),
            scene.robot_list[0],
            scene.object_list,
            self.task_data["instruction"],
            log_dir=self.save_dir,
            task_data=self.task_data,
            tcp_config=scene.tcp_configs["franka"],
            logger=self.logger,
        )
        # Benchmark mode quick exit
        if demogen_config["mode"] == "benchmark":
            self.recorder.save(demogen_config["task_name"], self.args.config)
            return "retry"

        for _ in range(100):
            scene.world.step(render=False)

        if self.is_wop:
            self.recorder.load_dynamic_info(
                np.array([0.0] * 9), 1, name=f"0/cold_start"
            )
            self.recorder.save(demogen_config["task_name"], self.args.config)
            record_log(self.save_dir, "success")
            return "success"

        action_success = self._execute_actions(scene, demogen_config)

        if not action_success:
            return "failed"

        for _ in tqdm(range(30)):
            scene.world.step(render=False)

        finished = False
        if len(self.task_data["goal"]) == 0 or len(self.task_data["goal"][0]) == 0:
            finished = True
        else:
            sr = scene.metric_manager.step(scene)
            finished = sr == 1

        rewrite_instruction(self.task_data, demogen_config)

        if finished:
            self.recorder.save(demogen_config["task_name"], self.args.config)
            record_log(self.save_dir, "success")
            return "success"
        else:
            self.logger.error("Data generation failed")
            record_log(self.save_dir, "failed")
            return "failed"

    def _execute_actions(self, scene, demogen_config):
        save_dir = self._get_save_dir(demogen_config)

        for idx, action_info in enumerate(self.task_data["task_path"]):
            try:
                if "type" not in action_info:
                    action_info["type"] = "pick_and_place"
                skill = SkillFactory.get(action_info["type"])(
                    action_info, demogen_config
                )
                is_success, action_info["arm"] = skill.execute(
                    scene,
                    self.recorder,
                    str(idx),
                )
                if not is_success:
                    raise Exception("Subgoal not completed")
            except Exception as e:
                self.logger.error(str(e))
                self.logger.error(traceback.format_exc())
                record_log(save_dir, str(e))
                return False

        return True

    def _get_save_dir(self, demogen_config):
        if not self.is_evalgen:
            return os.path.join(
                self.default_config["DEMONSTRATION_DIR"],
                demogen_config["task_name"],
                "trajectory",
            )
        else:
            return os.path.join(
                self.default_config["TASKS_DIR"], demogen_config["task_name"]
            )

    def _check_global_finished(self, demogen_config):
        if self.is_evalgen:
            return check_evalgen_finished(demogen_config, self.default_config)
        else:
            return check_planning_finished(demogen_config, self.default_config)
