import argparse
import base64
import io
import os
from pathlib import Path
import pickle
import time
from typing import Any

import cv2
from importlib import import_module
import numpy as np
import requests


def _optional_import(name: str):
    try:
        module = import_module(name)
    except Exception as exc:
        raise RuntimeError(
            f"Missing optional dependency '{name}'. "
            f"Install with: pip install -e '.[full]' (or install '{name}' directly)."
        ) from exc
    return module


def decode_numpy(metadata: dict) -> "Any":
    np = _optional_import("numpy")
    decoded_bytes = base64.b64decode(metadata["data"])
    numpy_array = np.frombuffer(decoded_bytes, dtype=np.dtype(metadata["dtype"]))
    numpy_array = numpy_array.reshape(metadata["shape"])
    return numpy_array


def decode_tensor(metadata: dict) -> "Any":
    torch = _optional_import("torch")
    decoded_bytes = base64.b64decode(metadata["data"])
    tensor = torch.frombuffer(
        bytearray(decoded_bytes), dtype=getattr(torch, metadata["dtype"])
    )
    tensor = tensor.reshape(eval(metadata["shape"]))
    return tensor.to(metadata["device"])


def decode_image(metadata: dict) -> "Any":
    try:
        Image = _optional_import("PIL.Image")
        decoded_bytes = base64.b64decode(metadata["data"])
        image = Image.open(io.BytesIO(decoded_bytes))

        if "size" in metadata and image.size != metadata["size"]:
            image = image.resize(metadata["size"], Image.Resampling.LANCZOS)

        if "mode" in metadata and image.mode != metadata["mode"]:
            image = image.convert(metadata["mode"])

        return image
    except Exception as exc:
        raise RuntimeError(f"Image decoding failed: {exc}") from exc


def deserialize_data(data: Any):
    if isinstance(data, dict) and "type" in data:
        if data["type"] == "numpy_array":
            return decode_numpy(data)
        if data["type"] == "tensor":
            return decode_tensor(data)
        if data["type"] == "image":
            return decode_image(data)
    if isinstance(data, (list, tuple)):
        return [deserialize_data(item) for item in data]
    if isinstance(data, dict):
        return {key: deserialize_data(value) for key, value in data.items()}
    return data


class EvalClient:
    """
    EvalClient in binary mode:
    - /step:  pickled action_dict <-> pickled response_dict
    - /reset: pickled {"worker_ids": [...]} <-> pickled obs_dict
    - /kill: kill all workers
    - /load_config: load a new task config, restart server
    The rest APIs are still in JSON.
    """

    def __init__(
        self,
        base_url: str,
        worker_ids: list[str] | None = None,
        config: str = "",
        save_path: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        genmanip_dir = os.path.join(current_dir, "..", "..", "..", "..", "..")
        log_dir = os.path.join(genmanip_dir, "saved/client_results")
        self.log_dir = os.environ.get("GENMANIP_RESULT_DIR", log_dir)
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        self.worker_ids = worker_ids or ["0"]

        self.kill_workers()

        if config:
            print(f"loading config {config}")
            self.load_config(config)
        self.loggers = {}
        self._create_loggers()
        self._create_workers()

    def _create_loggers(self):
        self.loggers = {}
        for worker_id in self.worker_ids:
            self.loggers[str(worker_id)] = []

    def _append_logger(self, obs: dict, action_dict: dict):
        for worker_id in self.worker_ids:
            wid = str(worker_id)
            if (obs[wid]["metric"] is not None or obs[wid]["obs"]["reset"]) and len(
                self.loggers[wid]
            ) > 0:
                self._save_logger(self.loggers[wid])
                self.loggers[wid].clear()
                self.loggers[wid] = []
            else:
                _obs = obs[wid].copy()
                _obs["action"] = action_dict[wid]
                self.loggers[wid].append(_obs)

    def _save_logger(self, logger):
        save_dir = logger[0]["obs"]["episode_id"]
        save_path = os.path.join(self.log_dir, save_dir)
        Path(save_path).mkdir(parents=True, exist_ok=True)
        camera_images = {}
        keys = list(logger[0]["obs"].keys())
        for key in keys:
            if key.startswith("video."):
                camera_images[key.split(".")[1]] = [
                    image["obs"].pop(key) for image in logger
                ]
        for image in logger:
            image["obs"].pop("camera_data")
        for camera_name, image_list in camera_images.items():
            self._save_video_to_path(
                image_list, os.path.join(save_path, camera_name + ".mp4")
            )
        with open(os.path.join(save_path, "meta_record.pkl"), "wb") as f:
            pickle.dump(logger, f)

    def _save_video_to_path(self, image_list: list[np.ndarray], save_path: str):
        height, width, _ = image_list[0].shape
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
        video = cv2.VideoWriter(save_path, fourcc, 30, (width, height))
        for image in image_list:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            video.write(image)
        video.release()

    def _create_workers(self):
        resp = requests.post(
            f"{self.base_url}/create_workers",
            json={"data": {"worker_ids": self.worker_ids}},
            timeout=300,
        )
        if resp.status_code != 200:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(
                f"HTTP error when create_workers: {resp.status_code} - {detail}"
            )

    def reset(self):
        payload = pickle.dumps(
            {"worker_ids": self.worker_ids}, protocol=pickle.HIGHEST_PROTOCOL
        )
        resp = requests.post(
            f"{self.base_url}/reset",
            data=payload,
            headers={"Content-Type": "application/octet-stream"},
        )
        if resp.status_code != 200:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(f"HTTP error on reset: {resp.status_code} - {detail}")

        obs_dict = pickle.loads(resp.content)
        return deserialize_data(obs_dict)

    def step(self, action_dict: dict):
        payload = pickle.dumps(action_dict, protocol=pickle.HIGHEST_PROTOCOL)
        try:
            resp = requests.post(
                f"{self.base_url}/step",
                data=payload,
                headers={"Content-Type": "application/octet-stream"},
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"HTTP request to server failed: {exc}") from exc

        if resp.status_code != 200:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(f"HTTP error from server: {resp.status_code} - {detail}")

        obs_dict = pickle.loads(resp.content)
        done = self.handle_done(obs_dict)
        obs = deserialize_data(obs_dict)
        self._append_logger(obs, action_dict)  # type: ignore[arg-type]
        return obs, done

    def handle_done(self, data: dict):
        if all(
            [data[worker_id]["metric"] is not None for worker_id in self.worker_ids]
        ):
            print("=" * 20)
            print("Evaluation result:")
            result_dict = {}
            for worker_data in data.values():
                for key, value in worker_data["metric"].items():
                    result_dict[key] = value
            for key, value in result_dict.items():
                print(f"{key}: {value}")
            print("=" * 20)
            return True
        return False

    def kill_workers(self):
        resp = requests.post(
            f"{self.base_url}/kill",
            json={"data": {"worker_ids": self.worker_ids}},
            timeout=60,
        )
        if resp.status_code != 200:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(
                f"HTTP error on kill_workers: {resp.status_code} - {detail}"
            )

    def load_config(self, config_path: str):
        resp = requests.post(
            f"{self.base_url}/load_config",
            json={"data": {"config_path": config_path}},
            timeout=60,
        )
        if resp.status_code != 200:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(
                f"HTTP error on load_config: {resp.status_code} - {detail}"
            )


def fake_action(arm_type: str, gripper_type: str, control_type: str) -> dict:
    if arm_type == "franka":
        if gripper_type == "panda_hand":
            if control_type == "joint_position":
                actions = {
                    "action": [0.0] * 9,
                    "base_motion": [0.0, 0.0, 0.0],
                    "control_type": "joint_position",
                }
            elif control_type == "ee_pose":
                actions = {
                    "action": (
                        [0.001, 0.001, 0.001],
                        [1.0, 0.0, 0.0, 0.0],
                        [0.04, 0.04],
                    ),
                    "base_motion": [0.0, 0.0, 0.0],
                    "control_type": "ee_pose",
                }
            else:
                raise ValueError("Invalid control type")
        elif gripper_type == "robotiq":
            if control_type == "joint_position":
                actions = {
                    "action": [0] * 13,
                    "base_motion": [0.0, 0.0, 0.0],
                    "control_type": "joint_position",
                }
            elif control_type == "ee_pose":
                actions = {
                    "action": (
                        [0.001, 0.001, 0.001],
                        [1.0, 0.0, 0.0, 0.0],
                        [0.7853, 0.7853, -0.7853, -0.7853, -0.7853, -0.7853],
                    ),
                    "base_motion": [0.0, 0.0, 0.0],
                    "control_type": "ee_pose",
                }
            else:
                raise ValueError("Invalid control type")
        else:
            raise ValueError("Invalid gripper type")
    elif arm_type == "aloha":
        if gripper_type == "piper":
            if control_type == "joint_position":
                actions = {
                    "action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.05, 0.05] * 2,
                    "base_motion": [0.0, 0.0, 0.0],
                    "control_type": "joint_position",
                }
            elif control_type == "ee_pose":
                actions = {
                    "action": (
                        (
                            [0.001, 0.001, 0.001],
                            [1.0, 0.0, 0.0, 0.0],
                            [0.05, 0.05],
                        ),
                        (
                            [0.001, 0.001, 0.001],
                            [1.0, 0.0, 0.0, 0.0],
                            [0.05, 0.05],
                        ),
                    ),
                    "base_motion": [0.0, 0.0, 0.0],
                    "control_type": "ee_pose",
                }
            else:
                raise ValueError("Invalid control type")
        else:
            raise ValueError("Invalid gripper type")
    elif arm_type == "r5a":
        if gripper_type == "lift2":
            if control_type == "joint_position":
                actions = {
                    "action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.04, 0.04] * 2,
                    "base_motion": [0.0, 0.0, 0.0],
                    "control_type": "joint_position",
                }
            elif control_type == "ee_pose":
                actions = {
                    "action": (
                        (
                            [0.001, 0.001, 0.001],
                            [1.0, 0.0, 0.0, 0.0],
                            [0.05, 0.05],
                        ),
                        (
                            [0.001, 0.001, 0.001],
                            [1.0, 0.0, 0.0, 0.0],
                            [0.05, 0.05],
                        ),
                    ),
                    "base_motion": [0.0, 0.0, 0.0],
                    "control_type": "ee_pose",
                }
            else:
                raise ValueError("Invalid control type")
        else:
            raise ValueError("Invalid gripper type")
    else:
        raise ValueError("Invalid arm type")
    return actions


def _parse_list(s: str):
    return s.split(",")


def build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--worker_ids",
        type=_parse_list,
        default=["0"],
        help="List of worker IDs, i.e. --worker_ids 0,1,2",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8087)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("-a", "--arm_type", type=str, default="franka")
    parser.add_argument("-g", "--gripper_type", type=str, default="panda_hand")
    parser.add_argument("-c", "--control_type", type=str, default="joint_position")
    parser.add_argument("--config", type=str, default="")
    return parser


def run_cli(args: argparse.Namespace) -> int:
    base_url = f"http://{args.host}:{args.port}"
    client = EvalClient(base_url, args.worker_ids, config=args.config)
    print(f"Created workers {args.worker_ids} on server {base_url}.")

    try:
        _ = client.reset()
        while True:
            action = {
                i: fake_action(args.arm_type, args.gripper_type, args.control_type)
                for i in args.worker_ids
            }

            start = time.time()
            obs, done = client.step(action)
            print(
                f"workers {args.worker_ids} Step time: {time.time() - start:.4f} seconds"
            )

            if done or obs is None:
                break
            if obs[args.worker_ids[0]]["obs"]["reset"]:  # type: ignore[index]
                pass
    finally:
        client.kill_workers()
        print("Client cleaned.")
    return 0
