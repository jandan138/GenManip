"""
This script is used to create a LeRobot dataset from a directory of LMDB files.
It supports both single-arm and dual-arm robots.

Dependencies:
pip install "lerobot @ git+https://github.com/huggingface/lerobot.git@2b71789e15c35418b1ccecbceb81f4a598bfd883"

Usage:
python genmanip2lerobot.py --data_path /path/to/data --robot franka_robotiq --overwrite
"""

import pickle
import os
from tqdm import tqdm
import lmdb
import cv2
import argparse
import numpy as np
from lerobot.common.datasets.lerobot_dataset import HF_LEROBOT_HOME, LeRobotDataset  # type: ignore
from typing import Literal
from pathlib import Path
import shutil

ROBOT = "lift2"
ROBOT_CONFIGS = {
    "aloha_split": {
        "robot_type": "aloha_split",
        "is_dual_arm": True,
        "motors_state": [
            "joint_0",
            "joint_1",
            "joint_2",
            "joint_3",
            "joint_4",
            "joint_5",
            "joint_6",
            "joint_7",
            "joint_8",
            "joint_9",
            "joint_10",
            "joint_11",
            "gripper_1_left",
            "gripper_1_right",
            "gripper_2_left",
            "gripper_2_right",
        ],
        "motors_action": [
            "joint_0",
            "joint_1",
            "joint_2",
            "joint_3",
            "joint_4",
            "joint_5",
            "joint_6",
            "joint_7",
            "joint_8",
            "joint_9",
            "joint_10",
            "joint_11",
            "gripper_1",
            "gripper_2",
        ],
        "joint_indices": [
            12,
            14,
            16,
            18,
            20,
            22,
            13,
            15,
            17,
            19,
            21,
            23,
            24,
            25,
            26,
            27,
        ],
        "base_indices": [0, 1, 2],
        "cameras": [
            "top_camera",
            "left_camera",
            "right_camera",
        ],
    },
    "lift2": {
        "robot_type": "lift2",
        "is_dual_arm": True,
        "motors_state": [
            "joint_0",
            "joint_1",
            "joint_2",
            "joint_3",
            "joint_4",
            "joint_5",
            "joint_6",
            "joint_7",
            "joint_8",
            "joint_9",
            "joint_10",
            "joint_11",
        ],
        "motors_action": [
            "joint_0",
            "joint_1",
            "joint_2",
            "joint_3",
            "joint_4",
            "joint_5",
            "joint_6",
            "joint_7",
            "joint_8",
            "joint_9",
            "joint_10",
            "joint_11",
        ],
        "motors_state_gripper": [
            "gripper_1_left",
            "gripper_1_right",
            "gripper_2_left",
            "gripper_2_right",
        ],
        "motors_action_gripper": [
            "gripper_1",
            "gripper_2",
        ],
        "joint_indices": [10, 12, 14, 16, 18, 20, 9, 11, 13, 15, 17, 19],
        "gripper_indices": [23, 24, 21, 22],
        "base_indices": [0, 1, 2],
        "cameras": [
            "top_camera",
            "left_camera",
            "right_camera",
        ],
    },
    "franka_robotiq": {
        "robot_type": "franka_robotiq",
        "is_dual_arm": False,
        "motors_state": [
            "joint_0",
            "joint_1",
            "joint_2",
            "joint_3",
            "joint_4",
            "joint_5",
            "joint_6",
        ],
        "motors_action": [
            "joint_0",
            "joint_1",
            "joint_2",
            "joint_3",
            "joint_4",
            "joint_5",
            "joint_6",
        ],
        "motors_state_gripper": [
            "gripper_1",
            "gripper_2",
            "gripper_3",
            "gripper_4",
            "gripper_5",
            "gripper_6",
        ],
        "motors_action_gripper": [
            "gripper",
        ],
        "joint_indices": [0, 1, 2, 3, 4, 5, 6],
        "gripper_indices": [7, 8, 9, 10, 11, 12],
        "base_indices": [],
        "cameras": [
            "realsense",
            "obs_camera",
            "obs_camera_2",
        ],
    },
    "franka_pandahand": {
        "robot_type": "franka_pandahand",
        "is_dual_arm": False,
        "motors_state": [
            "joint_0",
            "joint_1",
            "joint_2",
            "joint_3",
            "joint_4",
            "joint_5",
            "joint_6",
        ],
        "motors_action": [
            "joint_0",
            "joint_1",
            "joint_2",
            "joint_3",
            "joint_4",
            "joint_5",
            "joint_6",
        ],
        "motors_state_gripper": [
            "gripper_1",
            "gripper_2",
        ],
        "motors_action_gripper": [
            "gripper",
        ],
        "joint_indices": [0, 1, 2, 3, 4, 5, 6],
        "gripper_indices": [7, 8],
        "base_indices": [],
        "cameras": [
            "realsense",
            "obs_camera",
            "obs_camera_2",
        ],
    },
}


def create_dataset(
    repo_id: str,
    robot_type: str,
    is_dual_arm: bool,
    mode: Literal["video", "image"] = "video",
    overwrite: bool = False,
) -> LeRobotDataset:
    cfg = ROBOT_CONFIGS[robot_type]
    motors_state = cfg["motors_state"]
    motors_action = cfg["motors_action"]
    motors_state_gripper = cfg["motors_state_gripper"]
    motors_action_gripper = cfg["motors_action_gripper"]
    base_motion = cfg["base_indices"]
    cameras = cfg["cameras"]

    features = {
        "state.joints": {
            "dtype": "float32",
            "shape": (len(motors_state),),
            "names": [
                motors_state,
            ],
        },
        "action.joints": {
            "dtype": "float32",
            "shape": (len(motors_action),),
            "names": [
                motors_action,
            ],
        },
        "action.joints_delta": {
            "dtype": "float32",
            "shape": (len(motors_state),),
            "names": [
                motors_action,
            ],
        },
        "state.gripper": {
            "dtype": "float32",
            "shape": (len(motors_state_gripper),),
            "names": [
                motors_state_gripper,
            ],
        },
        "action.gripper": {
            "dtype": "float32",
            "shape": (len(motors_action_gripper),),
            "names": [
                motors_action_gripper,
            ],
        },
        "state.ee_pose": {
            "dtype": "float32",
            "shape": (14,) if is_dual_arm else (7,),
            "names": [
                (
                    [
                        "ee0_x",
                        "ee0_y",
                        "ee0_z",
                        "ee0_qw",
                        "ee0_qx",
                        "ee0_qy",
                        "ee0_qz",
                        "ee1_x",
                        "ee1_y",
                        "ee1_z",
                        "ee1_qw",
                        "ee1_qx",
                        "ee1_qy",
                        "ee1_qz",
                    ]
                    if is_dual_arm
                    else [
                        "ee0_x",
                        "ee0_y",
                        "ee0_z",
                        "ee0_qw",
                        "ee0_qx",
                        "ee0_qy",
                        "ee0_qz",
                    ]
                )
            ],
        },
        "action.ee_pose": {
            "dtype": "float32",
            "shape": (14,) if is_dual_arm else (7,),
            "names": [
                (
                    [
                        "ee0_x",
                        "ee0_y",
                        "ee0_z",
                        "ee0_qw",
                        "ee0_qx",
                        "ee0_qy",
                        "ee0_qz",
                        "ee1_x",
                        "ee1_y",
                        "ee1_z",
                        "ee1_qw",
                        "ee1_qx",
                        "ee1_qy",
                        "ee1_qz",
                    ]
                    if is_dual_arm
                    else [
                        "ee0_x",
                        "ee0_y",
                        "ee0_z",
                        "ee0_qw",
                        "ee0_qx",
                        "ee0_qy",
                        "ee0_qz",
                    ]
                )
            ],
        },
        "action.ee_pose_delta": {
            "dtype": "float32",
            "shape": (14,) if is_dual_arm else (7,),
            "names": [
                (
                    [
                        "ee0_x",
                        "ee0_y",
                        "ee0_z",
                        "ee0_qw",
                        "ee0_qx",
                        "ee0_qy",
                        "ee0_qz",
                        "ee1_x",
                        "ee1_y",
                        "ee1_z",
                        "ee1_qw",
                        "ee1_qx",
                        "ee1_qy",
                        "ee1_qz",
                    ]
                    if is_dual_arm
                    else [
                        "ee0_x",
                        "ee0_y",
                        "ee0_z",
                        "ee0_qw",
                        "ee0_qx",
                        "ee0_qy",
                        "ee0_qz",
                    ]
                )
            ],
        },
    }

    if len(base_motion) > 0:
        features["state.base"] = {  # current base position
            "dtype": "float32",
            "shape": (len(base_motion),),
            "names": [
                ["base_x", "base_y", "base_theta"],
            ],
        }
        features["action.base"] = {
            "dtype": "float32",
            "shape": (len(base_motion),),
            "names": [
                ["base_x", "base_y", "base_theta"],
            ],
        }
        features["action.base_delta"] = {  # base motion delta value
            "dtype": "float32",
            "shape": (len(base_motion),),
            "names": [
                ["base_x", "base_y", "base_theta"],
            ],
        }

    for cam in cameras:
        features[f"video.{cam}_view"] = {
            "dtype": mode,
            "shape": (3, 480, 640),  # (channels, height, width)
            "names": [
                "channels",
                "height",
                "width",
            ],
        }
    print(HF_LEROBOT_HOME)  # /root/.cache/huggingface/lerobot
    if Path(HF_LEROBOT_HOME / repo_id).exists():
        if not overwrite:
            raise FileExistsError(
                f"Dataset already exists at {HF_LEROBOT_HOME / repo_id}. "
                "Use --overwrite to delete it."
            )
        shutil.rmtree(HF_LEROBOT_HOME / repo_id)

    return LeRobotDataset.create(
        repo_id=repo_id,
        fps=15,
        robot_type=robot_type,
        features=features,
        use_videos=True,
        tolerance_s=0.0001,
        image_writer_processes=10,
        image_writer_threads=5,
        video_backend="ffmpeg",
    )


def process_single_dataset(
    dataset: LeRobotDataset,
    state_joints: np.ndarray,
    action_joints: np.ndarray,
    action_joints_delta: np.ndarray,
    state_gripper: np.ndarray,
    action_gripper: np.ndarray,
    state_base: np.ndarray | list[None],
    action_base_delta: np.ndarray | list[None],
    state_ee_pose: np.ndarray,
    action_ee_pose: np.ndarray,
    action_ee_pose_delta: np.ndarray,
    video_dict: dict[str, np.ndarray],
    instruction: str,
) -> LeRobotDataset:
    num_frames = state_joints.shape[0]
    abs_base_motion = np.array([0.0, 0.0, 0.0]) if state_base[0] is not None else None

    for i in tqdm(range(num_frames), desc="Processing frames"):
        frame = {
            "state.joints": state_joints[i].astype(np.float32),
            "action.joints": action_joints[i].astype(np.float32),
            "action.joints_delta": action_joints_delta[i].astype(np.float32),
            "state.gripper": state_gripper[i].astype(np.float32),
            "action.gripper": np.atleast_1d(action_gripper[i]).astype(np.float32),
            "state.ee_pose": state_ee_pose[i].astype(np.float32),
            "action.ee_pose": action_ee_pose[i].astype(np.float32),
            "action.ee_pose_delta": action_ee_pose_delta[i].astype(np.float32),
        }
        if state_base[i] is not None:
            frame["state.base"] = state_base[i].astype(np.float32)  # type: ignore
        if action_base_delta[i] is not None:
            frame["action.base_delta"] = action_base_delta[i].astype(np.float32)  # type: ignore
        if abs_base_motion is not None:
            frame["action.base"] = abs_base_motion.astype(np.float32)
        for camera, img_array in video_dict.items():
            frame[f"video.{camera}_view"] = img_array[i]
        dataset.add_frame(frame, task=instruction)
        if abs_base_motion is not None and action_base_delta[i] is not None:
            abs_base_motion += action_base_delta[i].astype(np.float32)  # type: ignore
    dataset.save_episode()

    return dataset


def get_scalar_data_from_lmdb(data_path, key):
    """Retrieve scalar data from LMDB database.

    Loads and deserializes scalar data (e.g., joint positions, actions) from
    the LMDB storage format used in robotics datasets.

    Args:
        data_path (str): Path to dataset directory containing LMDB files
        key (bytes): LMDB key for the desired data

    Returns:
        Any: Deserialized data object (typically numpy arrays or lists)
    """
    meta_info = pickle.load(open(f"{data_path}/meta_info.pkl", "rb"))
    lmdb_env = lmdb.open(
        f"{data_path}/lmdb", readonly=True, lock=False, readahead=False, meminit=False
    )
    key_index = meta_info["keys"]["scalar_data"].index(key)
    key_key = meta_info["keys"]["scalar_data"][key_index]
    with lmdb_env.begin(write=False) as txn:
        data = pickle.loads(txn.get(key_key))
    return data


def get_json_data_from_lmdb(data_path):
    """Retrieve JSON metadata from LMDB database.

    Loads camera parameters and other metadata stored as JSON in the dataset.

    Args:
        data_path (str): Path to dataset directory containing LMDB files

    Returns:
        dict: Deserialized JSON data containing camera parameters and metadata
    """
    lmdb_env = lmdb.open(
        f"{data_path}/lmdb", readonly=True, lock=False, readahead=False, meminit=False
    )
    with lmdb_env.begin(write=False) as txn:
        data = pickle.loads(txn.get(b"json_data"))
    return data


def get_color_image_from_lmdb(data_path, key):
    """Load all color images from LMDB database (deprecated - memory intensive).

    Warning: This function loads all images into memory at once and should be
    avoided for large datasets. Use get_frame_data() instead.

    Args:
        data_path (str): Path to dataset directory
        key (str): Key pattern for color images

    Returns:
        list: List of color images as numpy arrays
    """
    meta_info = pickle.load(open(f"{data_path}/meta_info.pkl", "rb"))
    lmdb_env = lmdb.open(
        f"{data_path}/lmdb", readonly=True, lock=False, readahead=False, meminit=False
    )
    key_index = meta_info["keys"][key]
    color_image = []
    target_size = (640, 480)
    with lmdb_env.begin(write=False) as txn:
        for key in key_index:
            # Decode the compressed image bytes to numpy array (BGR color)
            img = cv2.imdecode(pickle.loads(txn.get(key)), cv2.IMREAD_COLOR)

            # Rescale to exactly 480x640 (stretches if aspect ratio differs)
            img_resized = cv2.resize(img, target_size, interpolation=cv2.INTER_LINEAR)

            color_image.append(img_resized)
    return color_image


def ee_pose_list_to_np(ee_pose_action_list) -> np.ndarray:
    # ee_pose_action_list: length T
    out = []
    for ee in ee_pose_action_list:
        if len(ee[0]) == 3 and len(ee[1]) == 4:
            p0 = np.asarray(ee[0], dtype=np.float32).reshape(
                3,
            )
            q0 = np.asarray(ee[1], dtype=np.float32).reshape(
                4,
            )
            out.append(np.concatenate([p0, q0], axis=0))  # (7,)
        elif len(ee) == 2:
            # ee = ((pos0, quat0), (pos1, quat1))
            (p0, q0), (p1, q1) = ee

            p0 = np.asarray(p0, dtype=np.float32).reshape(
                3,
            )
            q0 = np.asarray(q0, dtype=np.float32).reshape(
                4,
            )
            p1 = np.asarray(p1, dtype=np.float32).reshape(
                3,
            )
            q1 = np.asarray(q1, dtype=np.float32).reshape(
                4,
            )
            out.append(np.concatenate([p0, q0, p1, q1], axis=0))  # (14,)
    return np.stack(out, axis=0).astype(np.float32)  # (T, 14)


def get_all_data_from_lmdb(data_path: str, cameras: list[str]):
    state_joints_all = get_scalar_data_from_lmdb(data_path, b"observation/robot/qpos")

    action_joints = get_scalar_data_from_lmdb(data_path, b"arm_action")
    action_joints_delta = get_scalar_data_from_lmdb(data_path, b"delta_arm_action")

    action_gripper = get_scalar_data_from_lmdb(data_path, b"gripper_close")

    try:
        action_base_delta = get_scalar_data_from_lmdb(data_path, b"base_motion")
    except:
        action_base_delta = [None] * len(action_joints)

    state_ee_pose = get_scalar_data_from_lmdb(
        data_path, b"observation/robot/ee_pose_state"
    )
    action_ee_pose = get_scalar_data_from_lmdb(data_path, b"ee_pose_action")
    action_ee_pose_delta = get_scalar_data_from_lmdb(data_path, b"delta_ee_pose_action")
    camera_dict = {}
    for camera_name in cameras:
        camera_dict[camera_name] = get_color_image_from_lmdb(
            data_path, f"observation/{camera_name}/color_image"
        )
    return (
        state_joints_all,
        action_joints,
        action_joints_delta,
        action_gripper,
        action_base_delta,
        state_ee_pose,
        action_ee_pose,
        action_ee_pose_delta,
        camera_dict,
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_path", type=str, required=True)
    parser.add_argument(
        "--robot", type=str, default="lift2", choices=list(ROBOT_CONFIGS.keys())
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete existing LeRobot dataset output if present.",
    )
    return parser.parse_args()


def _validate_episode_data(
    *,
    state_joints: np.ndarray,
    action_joints: np.ndarray,
    action_joints_delta: np.ndarray,
    state_gripper: np.ndarray,
    action_gripper: np.ndarray,
    state_base: np.ndarray | list[None],
    action_base_delta: np.ndarray | list[None],
    state_ee_pose: np.ndarray,
    action_ee_pose: np.ndarray,
    action_ee_pose_delta: np.ndarray,
    video_dict: dict[str, np.ndarray],
) -> None:
    num_frames = state_joints.shape[0]
    series = {
        "action_joints": action_joints,
        "action_joints_delta": action_joints_delta,
        "state_gripper": state_gripper,
        "action_gripper": action_gripper,
        "state_base": state_base,
        "action_base_delta": action_base_delta,
        "state_ee_pose": state_ee_pose,
        "action_ee_pose": action_ee_pose,
        "action_ee_pose_delta": action_ee_pose_delta,
    }
    for name, arr in series.items():
        if isinstance(arr, list):
            if len(arr) != num_frames:
                raise ValueError(
                    f"Frame count mismatch: {name} has {len(arr)}, expected {num_frames}."
                )
        elif isinstance(arr, np.ndarray):
            if arr.shape[0] != num_frames:
                raise ValueError(
                    f"Frame count mismatch: state_joints has {num_frames}, "
                    f"{name} has {arr.shape[0]}."
                )
    for camera_name, frames in video_dict.items():
        if len(frames) != num_frames:
            raise ValueError(
                f"Video frame count mismatch for {camera_name}: "
                f"expected {num_frames}, got {len(frames)}."
            )


def add_single_episode_to_dataset(
    dataset: LeRobotDataset,
    lmdb_path: str,
    robot_type: str,
):
    cameras = ROBOT_CONFIGS[robot_type]["cameras"]
    (
        state_joints_all,
        action_joints,
        action_joints_delta,
        action_gripper,
        action_base_delta,
        state_ee_pose,
        action_ee_pose,
        action_ee_pose_delta,
        camera_dict,
    ) = get_all_data_from_lmdb(lmdb_path, cameras)
    joint_indices = ROBOT_CONFIGS[robot_type]["joint_indices"]
    gripper_indices = ROBOT_CONFIGS[robot_type]["gripper_indices"]
    base_indices = ROBOT_CONFIGS[robot_type]["base_indices"]

    instruction = pickle.load(open(f"{lmdb_path}/meta_info.pkl", "rb"))["task_data"][
        "instruction"
    ]

    state_joints = np.array(
        [state_joints_all[i][joint_indices] for i in range(len(state_joints_all))]
    )
    action_joints = np.array(action_joints)
    action_joints_delta = np.array(action_joints_delta)
    state_gripper = np.array(
        [state_joints_all[i][gripper_indices] for i in range(len(state_joints_all))]
    )
    action_gripper = np.array(action_gripper)
    state_base = (
        np.array(
            [state_joints_all[i][base_indices] for i in range(len(state_joints_all))]
        )
        if len(base_indices) > 0
        else [None] * len(state_joints_all)
    )
    action_base_delta = (
        np.array(action_base_delta)
        if len(base_indices) > 0
        else [None] * len(action_joints)
    )
    state_ee_pose = ee_pose_list_to_np(state_ee_pose)
    action_ee_pose = ee_pose_list_to_np(action_ee_pose)
    action_ee_pose_delta = ee_pose_list_to_np(action_ee_pose_delta)

    _validate_episode_data(
        state_joints=state_joints,
        action_joints=action_joints,
        action_joints_delta=action_joints_delta,
        state_gripper=state_gripper,
        action_gripper=action_gripper,
        state_base=state_base,
        action_base_delta=action_base_delta,
        state_ee_pose=state_ee_pose,
        action_ee_pose=action_ee_pose,
        action_ee_pose_delta=action_ee_pose_delta,
        video_dict=camera_dict,
    )

    process_single_dataset(
        dataset,
        state_joints=state_joints,
        action_joints=action_joints,
        action_joints_delta=action_joints_delta,
        state_gripper=state_gripper,
        action_gripper=action_gripper,
        state_base=state_base,
        action_base_delta=action_base_delta,
        state_ee_pose=state_ee_pose,
        action_ee_pose=action_ee_pose,
        action_ee_pose_delta=action_ee_pose_delta,
        video_dict=camera_dict,
        instruction=instruction,
    )


if __name__ == "__main__":
    args = parse_args()
    ROBOT = args.robot
    is_dual_arm = ROBOT_CONFIGS[args.robot]["is_dual_arm"]
    dataset = create_dataset(
        repo_id=f"genmanip2lerobot/{args.data_path.split('/')[-2]}",
        robot_type=args.robot,
        is_dual_arm=is_dual_arm,
        mode="video",
        overwrite=args.overwrite,
    )
    for lmdb_path in tqdm(os.listdir(args.data_path)):
        if os.path.isdir(os.path.join(args.data_path, lmdb_path)):
            add_single_episode_to_dataset(
                dataset,
                os.path.join(args.data_path, lmdb_path),
                robot_type=args.robot,
            )
