"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import copy
import os
import pathlib
import pickle
import shutil
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from huggingface_hub import snapshot_download
from pydantic import BaseModel

from genmanip.utils.rerun.rerun_utils import log_episode_to_rerun
from genmanip.utils.standalone.file_utils import load_yaml, check_benchmark_version
from genmanip.utils.standalone.frame_utils import save_image
from genmanip.utils.standalone.file_utils import make_dir, save_dict_to_json
from genmanip.utils.standalone.transform_utils import (
    pose_to_transform,
    transform_to_pose,
)

try:
    # if mediapy is installed, use it to create video
    import mediapy as mp
    from genmanip.utils.standalone.frame_utils import (
        create_video_from_image_list_with_mediapy as create_video_from_image_list,
    )
except:
    # if mediapy is not installed, use the original function
    from genmanip.utils.standalone.frame_utils import (
        create_video_from_image_list as create_video_from_image_list,
    )


def parse_config_and_benchmark_id(
    config_or_benchmark_id: str, current_dir: str
) -> tuple[dict, str | None]:
    if str(config_or_benchmark_id).endswith(".yml") or str(
        config_or_benchmark_id
    ).endswith(".yaml"):
        config = load_yaml(config_or_benchmark_id)
        benchmark_id = None
    elif os.path.exists(
        os.path.join(
            current_dir,
            "saved/assets/collected_packages",
            str(config_or_benchmark_id).split("/")[-1],
            "tasks",
            "config.yaml",
        )
    ):
        print("Loading benchmark from local directory...")
        config = load_yaml(
            os.path.join(
                current_dir,
                "saved/assets/collected_packages",
                str(config_or_benchmark_id).split("/")[-1],
                "tasks",
                "config.yaml",
            )
        )
        benchmark_id = config_or_benchmark_id
    else:
        print("Downloading benchmark from HuggingFace...")
        if check_benchmark_version(config_or_benchmark_id):
            pathlib.Path("saved/assets/collected_packages").mkdir(
                parents=True, exist_ok=True
            )
            pathlib.Path("saved/tasks").mkdir(parents=True, exist_ok=True)
            snapshot_download(
                repo_id=config_or_benchmark_id,
                repo_type="dataset",
                local_dir=f"saved/assets/collected_packages/{config_or_benchmark_id.split('/')[-1]}",
            )
            if os.path.exists(
                os.path.join(
                    current_dir,
                    "saved/assets/collected_packages",
                    str(config_or_benchmark_id).split("/")[-1],
                    "tasks",
                    "config.yaml",
                )
            ):
                config = load_yaml(
                    os.path.join(
                        current_dir,
                        "saved/assets/collected_packages",
                        str(config_or_benchmark_id).split("/")[-1],
                        "tasks",
                        "config.yaml",
                    )
                )
                benchmark_id = config_or_benchmark_id
            else:
                raise ValueError(f"Config file {config_or_benchmark_id} not found")
        else:
            raise ValueError(f"Config file {config_or_benchmark_id} not found")
    return config, benchmark_id


class ActionRequest(BaseModel):
    data: dict


class ObsResponse(BaseModel):
    data: dict


def ensure_empty_dir(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)
    make_dir(path)


def apply_delta_pose(
    delta_pose: tuple[np.ndarray, np.ndarray],
    current_pose: tuple[np.ndarray, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    delta_position = np.array(delta_pose[0])
    delta_orientation = np.array(delta_pose[1])
    current_position = np.array(current_pose[0])
    current_orientation = np.array(current_pose[1])
    delta_transform = pose_to_transform((delta_position, delta_orientation))
    current_transform = pose_to_transform((current_position, current_orientation))
    new_transform = delta_transform @ current_transform
    return transform_to_pose(new_transform)


def _normalize_ee_pose_actions(action: Any) -> list[tuple[Any, Any, Any]]:
    if len(action) == 3 and len(action[0]) == 3 and len(action[1]) == 4:
        return [(action[0], action[1], action[2])]
    return list(action)


def parse_embodiment_action(
    action: Any,
    *,
    control_type: str,
    embodiment: Any,
    is_relative_action: bool,
    last_joint_position: np.ndarray,
    last_ee_pose: list[tuple[np.ndarray, np.ndarray]] | None,
) -> tuple[np.ndarray, np.ndarray, list[tuple[np.ndarray, np.ndarray]] | None]:
    embodiment_joint_num = embodiment.arm_dof_num + embodiment.gripper_dof_num

    if control_type == "joint_position":
        action_arr = np.array(action, dtype=np.float64)
        for i in range(len(action_arr) // embodiment_joint_num):
            if is_relative_action:
                start_idx = i * embodiment_joint_num
                end_idx = start_idx + embodiment.arm_dof_num
                action_arr[start_idx:end_idx] += last_joint_position[start_idx:end_idx]
        return action_arr, action_arr, last_ee_pose

    if control_type != "ee_pose":
        raise ValueError(f"Unsupported control_type: {control_type}")

    if last_ee_pose is None:
        raise ValueError("last_ee_pose is required for ee_pose control")

    actions = _normalize_ee_pose_actions(action)
    action_arr = np.array([])
    for i, act in enumerate(actions):
        position, orientation, gripper_width = act

        if is_relative_action:
            abs_pose = apply_delta_pose((position, orientation), last_ee_pose[i])
            position = abs_pose[0].tolist()
            orientation = abs_pose[1].tolist()
            last_ee_pose[i] = abs_pose
        else:
            last_ee_pose[i] = (np.asarray(position), np.asarray(orientation))

        if len(actions) == 1:
            planner = embodiment.planner
        elif i == 0:
            planner = embodiment.left_planner  # type: ignore[attr-defined]
        elif i == 1:
            planner = embodiment.right_planner  # type: ignore[attr-defined]
        else:
            raise ValueError("Invalid ee_pose action")

        if planner is None:
            raise ValueError("Planner is not initialized")

        start_idx = i * embodiment_joint_num
        end_idx = start_idx + embodiment.arm_dof_num
        cur_joint = embodiment.robot.get_joint_positions()[
            embodiment.default_dof_indices
        ][start_idx:end_idx]
        ik_result = planner.ik_single(position + orientation, cur_joint)
        if ik_result is None:
            ik_result = cur_joint

        action_arr = np.concatenate(
            [action_arr, ik_result[: embodiment.arm_dof_num], gripper_width]
        )

    return action_arr, action_arr, last_ee_pose


@dataclass
class EpisodeRecorder:
    traj_log_dir: str
    camera_names: list[str]
    instruction: str
    save_every: int = 10
    image_list: dict[str, list[Any]] = field(default_factory=dict)
    meta_record: dict[str, Any] = field(default_factory=dict)
    steps: int = 0

    @classmethod
    def create(
        cls,
        *,
        traj_log_dir: str,
        camera_names: Sequence[str],
        instruction: str,
        save_every: int = 10,
        with_render: bool = True,
    ) -> "EpisodeRecorder":
        ensure_empty_dir(traj_log_dir)
        if with_render:
            for camera_name in camera_names:
                make_dir(os.path.join(traj_log_dir, camera_name))
        image_list = {name: [] for name in camera_names}
        meta_record = {
            "joint_positions": [],
            "gripper_positions": [],
            "instruction": instruction,
            "model_output": [],
        }
        return cls(
            traj_log_dir=traj_log_dir,
            camera_names=list(camera_names),
            instruction=instruction,
            save_every=save_every,
            image_list=image_list,
            meta_record=meta_record,
        )

    def record_model_output(self, *, arm_action: Any, base_motion: Any) -> None:
        self.meta_record["model_output"].append(
            {"arm_action": arm_action, "base_motion": base_motion}
        )

    def record_obs(self, _obs: dict) -> int:
        obs = copy.deepcopy(_obs)
        for camera_name in self.camera_names:
            key = f"video.{camera_name}_view"
            if key not in obs:
                continue
            self.image_list[camera_name].append(obs[key])

            if self.steps % self.save_every == 0:
                camera_dir = os.path.join(self.traj_log_dir, camera_name)
                if os.path.exists(camera_dir):
                    save_image(
                        self.image_list[camera_name][-1],
                        os.path.join(camera_dir, f"{str(self.steps).zfill(5)}.png"),
                    )

        if "state.joints" in obs:
            self.meta_record["joint_positions"].append(obs["state.joints"])
        if "state.gripper" in obs:
            self.meta_record["gripper_positions"].append(obs["state.gripper"])
        self.steps += 1
        return self.steps

    def save_meta_record(self) -> None:
        with open(os.path.join(self.traj_log_dir, "meta_record.pkl"), "wb") as f:
            pickle.dump(self.meta_record, f)

    def finalize(self, success_rate: float) -> None:
        state_list = []
        action_list = []
        for item in self.meta_record["model_output"]:
            action_list.append(item["arm_action"])
        for item1, item2 in zip(
            self.meta_record["joint_positions"], self.meta_record["gripper_positions"]
        ):
            state_list.append(np.concatenate([item1, item2]).tolist())
        action_list = np.array(action_list)
        state_list = np.array(state_list)
        log_episode_to_rerun(
            self.image_list,
            action_list,
            state_list,
            rrd_path=os.path.join(self.traj_log_dir, "episode.rrd"),
        )

        for camera_name in self.camera_names:
            camera_dir = os.path.join(self.traj_log_dir, camera_name)
            if not os.path.exists(camera_dir):
                continue
            if (
                len(os.listdir(camera_dir)) > 0
                and len(self.image_list[camera_name]) > 0
            ):
                create_video_from_image_list(
                    self.image_list[camera_name],
                    os.path.join(self.traj_log_dir, camera_name + ".mp4"),
                )
                self.image_list[camera_name] = []
                shutil.rmtree(camera_dir)

        self.save_meta_record()

        save_dict_to_json(
            {"success_rate": success_rate},
            os.path.join(self.traj_log_dir, "sr_info.json"),
        )
