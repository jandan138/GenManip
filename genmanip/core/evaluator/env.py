from datetime import datetime
import numpy as np
import os
from typing import Any

from genmanip.core.robot.dualarm_manip import DualArmEmbodiment
from genmanip.core.scene.scene import Scene
from genmanip.core.scene.scene_config import SceneConfig
from genmanip.core.evaluator.utils import EpisodeRecorder, parse_embodiment_action
from genmanip.utils.loader.domain_randomization import random_texture_for_eval
from genmanip.utils.loader.scene import (
    clear_scene,
    recovery_scene,
)
from genmanip.utils.standalone.file_utils import (
    load_dict_from_pkl,
    make_dir,
)
from genmanip.utils.standalone.io_utils import serialize_data
from genmanip.utils.standalone.utils import setup_logger, tuple_to_list
from genmanip.utils.standalone.version_utils import process_archived_config
from genmanip.utils.usd_utils import get_eval_camera_data, remove_colliders


class IsaacEvalEnvRay:
    def __init__(self, args, simulation_app, default_config, current_dir):
        self.args = args
        self.simulation_app = simulation_app
        self.default_config = default_config
        self.current_dir = current_dir

        self.logger = setup_logger()

        self.current_eval_config = None
        self.scene_config = None
        self.current_seed = None

        self.scene = None

        self._step_cnt = 0
        self.num_steps = args.num_steps
        self.done = False

        self.current_joint_position = None
        self.last_joint_position: np.ndarray | None = None
        self.last_ee_pose: list[tuple[np.ndarray, np.ndarray]] | None = None
        self.instruction = None
        self._recorder: EpisodeRecorder | None = None
        self.traj_log_dir = None

        self.run_id = args.run_id

        self.success_cnt = 0
        self.total_cnt = 0

    def _require_scene(self) -> Scene:
        if self.scene is None:
            raise ValueError("Scene not initialized")
        return self.scene

    def _require_scene_config(self) -> SceneConfig:
        if self.scene_config is None:
            raise ValueError("Current eval config not initialized")
        return self.scene_config

    def _require_seed(self) -> str:
        if self.current_seed is None:
            raise ValueError("Current seed not initialized")
        return self.current_seed

    def _require_recorder(self) -> EpisodeRecorder:
        if self._recorder is None:
            raise ValueError("Episode recorder not initialized")
        return self._recorder

    def _get_embodiment(self):
        scene = self._require_scene()
        if len(scene.robot_list) == 0:
            raise ValueError("No robot in scene")
        return scene.robot_list[0]

    def _maybe_initialize_task(self, current_eval_config: dict) -> None:
        processed = process_archived_config(current_eval_config)
        if (
            self.current_eval_config is not None
            and processed["task_name"] == self.current_eval_config["task_name"]
        ):
            return

        if self.scene_config is not None and self.scene is not None:
            clear_scene(self.scene, self.scene_config, self.current_dir)
            self.scene = None

        self.current_eval_config = processed
        self.logger.info(f"Starting new task: {self.current_eval_config['task_name']}")

        self.scene_config = SceneConfig(**processed)
        self.num_steps = (
            self.scene_config.num_steps
            if self.args.num_steps is None
            else self.args.num_steps
        )

        make_dir(
            os.path.join(
                self.default_config["EVAL_RESULT_DIR"],
                self.scene_config.task_name,
            )
        )

        self.scene = Scene(scene_config=self.scene_config)
        self.scene.initialize(
            self.default_config,
            physics_dt=1 / 30,
            rendering_dt=1 / 30,
            only_depth_rep_for_camera=True,
            only_color_rep_for_camera=True,
        )
        self.scene.post_initialize()

        if "camera1" in self.scene.camera_list:
            self.scene.camera_list.pop("camera1")

    def reset(self, seed, current_eval_config, default_config: dict | None = None):
        if default_config is not None:
            self.default_config = default_config
        self._maybe_initialize_task(current_eval_config)

        self.current_seed = seed
        self.logger.info(f"Resetting episode: {self.current_seed}")

        self._setup_episode_layout()

        self._step_cnt = 0
        scene = self._require_scene()
        _ = self._require_scene_config()

        self.done = False
        embodiment = scene.robot_list[0]
        self.current_joint_position = embodiment.robot.get_joint_positions()[
            embodiment.default_dof_indices
        ]
        self.last_joint_position = self.current_joint_position.copy()
        self.last_ee_pose = self._init_last_ee_pose()

        obs = self.get_obs()
        info = {
            "task": self._require_scene_config().task_name,
            "seed": self.current_seed,
        }
        return obs, info

    def _init_last_ee_pose(self) -> list[tuple[np.ndarray, np.ndarray]]:
        embodiment = self._get_embodiment()
        joint_positions = embodiment.robot.get_joint_positions()
        if isinstance(embodiment, DualArmEmbodiment):
            left_pose, right_pose = embodiment.fk_single(joint_positions)
            return [left_pose, right_pose]  # type: ignore
        return [embodiment.fk_single(joint_positions)]

    def get_obs(self):
        scene = self._require_scene()
        embodiment = scene.robot_list[0]
        recorder = self._require_recorder()
        timestep = recorder.steps
        scene_config = self._require_scene_config()
        seed = self._require_seed()
        task_name = scene_config.task_name

        self.current_joint_position = embodiment.robot.get_joint_positions()[
            embodiment.default_dof_indices
        ]
        if isinstance(embodiment, DualArmEmbodiment):
            current_base_position = embodiment.robot.get_joint_positions()[
                embodiment.base_dof_indices
            ]
        else:
            current_base_position = [0.0, 0.0, 0.0]
        current_arm_position = self.current_joint_position[
            embodiment.default_arm_dof_indices
        ]
        current_gripper_position = self.current_joint_position[
            embodiment.default_gripper_dof_indices
        ]

        camera_data = {}
        if not self.args.without_render:
            camera_data = get_eval_camera_data(scene.camera_list)
        ee_pose = embodiment.fk_single(embodiment.robot.get_joint_positions())

        if self.instruction is None:
            raise ValueError("Instruction not initialized")
        obs = {
            "instruction": self.instruction,
            "camera_data": camera_data,
            "state.joints": current_arm_position,
            "state.gripper": current_gripper_position,
            "state.base": current_base_position,
            "state.ee_pose": tuple_to_list(ee_pose),
            "timestep": timestep,
            "reset": timestep == 0,
            "episode_id": str(os.path.join(self.run_id, task_name, seed)),
        }

        for camera, img in camera_data.items():
            obs[f"video.{camera}_view"] = img["rgb"]
        recorder.record_obs(obs)
        return serialize_data(obs)

    def step(self, action: dict[str, Any]):
        if not self.simulation_app.is_running():
            return None, 0, True, {"error": "Sim closed"}
        if self.scene is None:
            return None, 0, True, {"error": "Scene not initialized"}
        if self.scene_config is None:
            return None, 0, True, {"error": "Current eval config not initialized"}
        if self._recorder is None:
            return None, 0, True, {"error": "Episode recorder not initialized"}

        # Done
        if self.done:
            return None, 0, True, {"info": "Done"}

        # 3-1. Set joint targets
        base_motion = action.get("base_motion", [0.0, 0.0, 0.0])
        arm_action = self.parse_action(
            action["action"], control_type=action["control_type"]
        )
        self._recorder.record_model_output(
            arm_action=arm_action, base_motion=base_motion
        )
        self.scene.robot_list[0].robot_view.set_joint_position_targets(
            arm_action,
            joint_indices=self.scene.robot_list[0].default_dof_indices,
        )
        if isinstance(self.scene.robot_list[0], DualArmEmbodiment):
            self.scene.robot_list[0].delta_move_to(*base_motion)

        # 3-2. Step Physics
        self.scene.world.step(render=not self.args.without_render)

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
            {"info": sr},
        )

    def post_episode_process(self, done_info):
        if self.done:
            return None
        if self.scene is None:
            return None
        if self.scene_config is None:
            return None

        episode_sr = self.scene.metric_manager.calc_overall_sr()

        self.done = True
        self.finish(episode_sr)
        return episode_sr

    def close(self):
        self.simulation_app.close()

    def _setup_episode_layout(self):
        scene = self._require_scene()
        scene_config = self._require_scene_config()
        seed = self._require_seed()
        task_dir = self.default_config["TASKS_DIR"]
        task_name = scene_config.task_name
        # Load data
        meta_info = load_dict_from_pkl(
            os.path.join(task_dir, task_name, f"{seed}/meta_info.pkl")
        )

        # Recovery Scene
        recovery_scene(
            scene,
            None,
            meta_info["task_data"],
            task_name,
            self.default_config,
        )

        # Randomization
        if self.args.random_randomization:
            random_texture_for_eval(scene, self.default_config, scene_config)

        # Update Config & Evaluator
        self.instruction = meta_info["task_data"]["instruction"]

        # Remove Ground Plane Colliders
        if "defaultGroundPlane" in scene.object_list:
            remove_colliders(scene.object_list["defaultGroundPlane"].prim_path)

        # Warmup
        for _ in range(50):
            scene.world.step()

        self.traj_log_dir = os.path.join(
            self.default_config["EVAL_RESULT_DIR"], self.run_id, task_name, seed
        )
        self._recorder = EpisodeRecorder.create(
            traj_log_dir=self.traj_log_dir,
            camera_names=list(scene.camera_list.keys()),
            instruction=self.instruction,
            save_every=10,
            with_render=not self.args.without_render,
        )

        scene.build_metrics_manager(
            meta_info["task_data"]["goal"], skip_steps=10, succ_cnts=50
        )

    def parse_action(self, action, control_type: str = "joint_position") -> np.ndarray:
        embodiment = self._get_embodiment()
        if self.last_joint_position is None:
            raise ValueError("Last joint position not initialized")
        action_arr, last_joint_position, last_ee_pose = parse_embodiment_action(
            action,
            control_type=control_type,
            embodiment=embodiment,
            is_relative_action=self.args.is_relative_action,
            last_joint_position=self.last_joint_position,
            last_ee_pose=self.last_ee_pose,
        )
        self.last_joint_position = last_joint_position
        self.last_ee_pose = last_ee_pose
        return action_arr

    def finish(self, success_rate: float) -> float:
        recorder = self._require_recorder()
        recorder.finalize(success_rate)
        if success_rate != 0:
            self.success_cnt += 1
        self.total_cnt += 1
        return success_rate
