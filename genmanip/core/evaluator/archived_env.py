import os
from typing import Any

from genmanip.core.evaluator.evaluator import Evaluator, parse_lmdb_data
from genmanip.core.robot.dualarm_manip import DualArmEmbodiment
from genmanip.core.scene.scene import Scene
from genmanip.core.scene.scene_config import SceneConfig
from genmanip.demogen.workflow.utils import check_eval_finished
from genmanip.utils.loader.domain_randomization import random_texture_for_eval
from genmanip.utils.loader.scene import (
    clear_scene,
    recovery_scene,
)
from genmanip.utils.standalone.file_utils import (
    load_default_config,
    load_dict_from_pkl,
    make_dir,
)
from genmanip.utils.standalone.socket_utils import (
    create_receive_port_and_attach,
    create_send_port_and_wait,
)
from genmanip.utils.standalone.version_utils import process_archived_config
from genmanip.utils.standalone.utils import (
    parse_eval_config,
    setup_logger,
)
from genmanip.utils.usd_utils import remove_colliders


class IsaacEvalEnv:
    """
    Docstring for IsaacEvalEnv

    Args: Description

    Including:
        get_obs(): get current observation from world

        reset(): reset

        step(action):
    """

    def __init__(self, args, simulation_app, current_dir, config, benchmark_id=None):
        self.args = args
        self.simulation_app = simulation_app
        self.current_dir = current_dir

        def red(text):
            return f"\033[1;31m{text}\033[0m"

        print(red("=" * 100))
        print(red("Using Archived Env, MAY COST UNEXPECTED RESULTS"))
        print(red("=" * 100))

        self.logger = setup_logger()
        self.default_config = load_default_config(
            self.current_dir, "__None__.json", "local" if self.args.local else "default"
        )
        if benchmark_id is not None:
            self.default_config["TASKS_DIR"] = os.path.join(
                self.current_dir,
                "saved/assets/collected_packages",
                benchmark_id.split("/")[-1],
                "tasks",
            )

        self.eval_config_list = parse_eval_config(config)
        self.task_queue = list(self.eval_config_list)
        self.current_eval_config = None
        self.scene_config = None
        self.current_seed = None
        self.num_steps = args.num_steps
        self.scene = None
        self.evaluator = None

        if hasattr(self.args, "receive_port") and hasattr(self.args, "send_port"):
            self.logger.info("Waiting for model client connection...")
            if self.args.receive_port is not None:
                self.receive_port = create_receive_port_and_attach(
                    self.args.receive_port
                )
            else:
                self.receive_port = None
            if hasattr(self.args, "send_port") and self.args.send_port is not None:
                self.send_port = create_send_port_and_wait(self.args.send_port)
            else:
                self.send_port = None
            self.logger.info("Connected.")
        else:
            self.receive_port = None
            self.send_port = None
            self.logger.info("No model client connection.")

        self._step_cnt = 0

    def reset(self):
        """
        Reset the environment to start a new episode.

        This function prepares the simulator for the next evaluation seed or next task in the queue.
        It performs the minimal necessary reset operations under the same `World` instance:
        - Clears the previous scene prims if present
        - Loads the next task configuration if the current one is exhausted
        - Retrieves the next valid randomization/evaluation seed
        - Recovers the scene layout and robot state for the new episode
        - Resets internal success and step counters

        Args:
            seed (int | None, optional): External seed to set for reproducibility. If not provided,
                the evaluator assigns the next seed automatically.
            options (dict | None, optional): Additional reset options (e.g., randomization flags,
                sensor overrides). Defaults to None.

        Returns:
            tuple[np.ndarray, dict] | None:
                - The initial observation after reset (usually depth or state representation)
                - Episode metadata including:
                    {"task": str, "seed": str}
                If no tasks or valid seeds remain, returns None.
        """
        obs = None
        info = None

        next_seed = self._get_next_episode_id()

        if next_seed is None:
            if self.scene is not None:
                if self.scene_config is None:
                    return None, None
                clear_scene(self.scene, self.scene_config, self.current_dir)
                self.scene = None

            if not self.task_queue:
                self.logger.info("All tasks finished.")
                return None, None

            demogen_config = process_archived_config(self.task_queue.pop(0))
            self.scene_config = SceneConfig(**demogen_config)
            self.num_steps = (
                self.scene_config.num_steps
                if self.args.num_steps is None
                else self.args.num_steps
            )
            self.logger.info(f"Starting new task: {self.scene_config.task_name}")

            make_dir(
                os.path.join(
                    self.default_config["EVAL_RESULT_DIR"],
                    self.scene_config.task_name,
                )
            )

            next_seed = self._get_next_episode_id()
            if next_seed is None:
                self.logger.warning(
                    f"Task {self.scene_config.task_name} has no valid seeds. Skipping."
                )
                return self.reset()

            self.scene = Scene(scene_config=self.scene_config)
            self.scene.initialize(
                self.default_config,
                physics_dt=1 / 30,
                rendering_dt=1 / 30,
                only_depth_rep_for_camera=True,
                only_color_rep_for_camera=True,
            )
            self.scene.post_initialize()

            self.evaluator = Evaluator(
                camera_list=self.scene.camera_list,
                robot=self.scene.robot_list[0],
                instruction=self.scene_config.instruction,
                log_dir=os.path.join(
                    self.default_config["EVAL_RESULT_DIR"],
                    self.scene_config.task_name,
                ),
                send_port=self.send_port,
                receive_port=self.receive_port,
                is_relative_action=True,
            )

        self.current_seed = next_seed
        self.logger.info(f"Resetting episode: {self.current_seed}")

        self._setup_episode_layout()

        self._step_cnt = 0
        if self.scene is None:
            raise ValueError("Scene not initialized")
        if self.scene_config is None:
            raise ValueError("Current eval config not initialized")

        obs = self.get_obs()
        info = {
            "task": self.scene_config.task_name,
            "seed": self.current_seed,
        }
        return obs, info

    def get_obs(self):
        """
        Retrieve the current observation from the environment.

        This function queries the active Evaluator instance to return the latest sensory
        observation from Isaac Sim. It does not modify the simulator state.

        Args:

        Returns:
            dict | None:
                camera_data (np.ndarray)
                instruction
                joint_position_state
                ee_pose_state
                timestep
                reset
        """
        if self.evaluator is None:
            return None
        return self.evaluator.get_obs(without_render=self.args.without_render)

    def step(self, action: dict[str, Any]):
        """
        Apply an action to the simulator and advance the environment by one timestep.

        This function interacts with Isaac Sim in real-time evaluation context:
        - Parses and validates the incoming action (local or remote-inference joint targets)
        - Sends the action to the robot articulation via joint position targets
        - Steps the physics and evaluator logging at the same frequency defined by the world
        - Checks success conditions over a sliding window (e.g., every 10 steps)
        - Computes a binary success reward without resetting the world

        Note:
            This API does not return the observation directly if the simulator uses
            request-response sockets externally. Use `get_remote_action` or `get_obs`
            outside if needed.

        Args:
            action (np.ndarray | list[float] | None): Target joint position/action vector.
                It can be absolute or relative depending on scene/evaluator configuration.

        Returns:
            tuple[np.ndarray, float, bool, bool, dict]:
                obs (np.ndarray | None): Observation at next state. If None (common in
                    socket-driven eval), call `get_obs()` explicitly.
                reward (float): 1.0 if success criteria is met at this check interval, else 0.0
                terminated (bool): True if the episode success is consistently met or max steps hit
                info (dict): Extra episode state info such as successful counter values or errors
        """
        if not self.simulation_app.is_running():
            return None, 0, True, {"error": "Sim closed"}
        if self.scene is None:
            return None, 0, True, {"error": "Scene not initialized"}
        if self.evaluator is None:
            return None, 0, True, {"error": "Evaluator not initialized"}
        if self.scene_config is None:
            return None, 0, True, {"error": "Current eval config not initialized"}

        # 3-1. Set joint targets
        def guess_control_type(action):
            if isinstance(action, list):
                return "joint_position"
            elif isinstance(action, tuple):
                return "ee_pose"
            else:
                raise ValueError("Invalid action")

        base_motion = action.get("base_motion", [0.0, 0.0, 0.0])
        control_type = guess_control_type(action["action"])
        arm_action = self.evaluator.parse_action(
            action["action"], control_type=control_type
        )
        self.scene.robot_list[0].robot_view.set_joint_position_targets(
            arm_action,
            joint_indices=self.scene.robot_list[0].default_dof_indices,
        )
        if isinstance(self.scene.robot_list[0], DualArmEmbodiment):
            self.scene.robot_list[0].delta_move_to(*base_motion)

        # 3-2. Step Physics
        self.scene.world.step(render=not self.args.without_render)

        # 3-3. Record data (Evaluator handles internal logging)
        self.evaluator.record(is_save_image=not self.args.without_render)

        # 3-4 & 3-5. Check Success Logic
        sr = self.scene.metric_manager.step(self.scene)
        self._step_cnt += 1

        # Check Termination
        done = False
        if sr == 1:
            self.logger.info("Goal reached consistently. Done.")
            done = True
        elif self._step_cnt >= self.num_steps:
            done = True

        return (
            self.get_obs(),
            sr,
            done,
            {"sr": sr},
        )

    def get_remote_action(self, obs) -> dict[str, Any] | None:
        if self.evaluator is None:
            return None
        return self.evaluator.request_action(obs)

    def post_episode_process(self, done_info):
        if self.scene is None:
            return
        if self.evaluator is None:
            return
        if self.scene_config is None:
            return

        episode_sr = self.scene.metric_manager.calc_overall_sr()

        self.evaluator.finish(episode_sr)

    def close(self):
        self.simulation_app.close()

    def _get_next_episode_id(self):
        if self.scene_config is None:
            return None

        seed_int = check_eval_finished(self.scene_config, self.default_config)
        if seed_int == -1:
            return None

        seed_str = str(seed_int).zfill(3)
        make_dir(
            os.path.join(
                self.default_config["EVAL_RESULT_DIR"],
                self.scene_config.task_name,
                seed_str,
            )
        )
        return seed_str

    def _setup_episode_layout(self):
        if self.scene is None:
            return
        if self.evaluator is None:
            return
        if self.scene_config is None:
            return
        if self.current_seed is None:
            return
        task_dir = self.default_config["TASKS_DIR"]
        task_name = self.scene_config.task_name
        seed = self.current_seed

        # Load data
        meta_info = load_dict_from_pkl(
            os.path.join(task_dir, task_name, f"{seed}/meta_info.pkl")
        )
        planning_data = parse_lmdb_data(os.path.join(task_dir, task_name, f"{seed}"))

        # Recovery Scene
        recovery_scene(
            self.scene,
            self.evaluator,
            meta_info["task_data"],
            self.scene_config.task_name,
            self.default_config,
        )

        # Randomization
        if self.args.random_randomization:
            random_texture_for_eval(self.scene, self.default_config, self.scene_config)

        # Update Config & Evaluator
        self.evaluator.update_task_data(meta_info["task_data"], planning_data)

        # Remove Ground Plane Colliders
        if "defaultGroundPlane" in self.scene.object_list:
            remove_colliders(self.scene.object_list["defaultGroundPlane"].prim_path)

        # Warmup
        for _ in range(50):
            self.scene.world.step()

        # Init Evaluator
        self.evaluator.initialize(seed)
        self.scene.build_metrics_manager(
            meta_info["task_data"]["goal"], skip_steps=10, succ_cnts=50
        )
