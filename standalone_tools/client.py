import time
import requests
import argparse
import pickle
import base64
import numpy as np
import torch
from PIL import Image
import io


def decode_numpy(metadata: dict) -> np.ndarray:
    decoded_bytes = base64.b64decode(metadata["data"])
    numpy_array = np.frombuffer(decoded_bytes, dtype=np.dtype(metadata["dtype"]))
    numpy_array = numpy_array.reshape(metadata["shape"])
    return numpy_array


def decode_tensor(metadata: dict) -> torch.Tensor:
    decoded_bytes = base64.b64decode(metadata["data"])
    tensor = torch.frombuffer(
        bytearray(decoded_bytes), dtype=getattr(torch, metadata["dtype"])
    )
    tensor = tensor.reshape(eval(metadata["shape"]))
    return tensor.to(metadata["device"])


def decode_image(metadata: dict) -> Image.Image:
    try:
        decoded_bytes = base64.b64decode(metadata["data"])
        image = Image.open(io.BytesIO(decoded_bytes))

        if "size" in metadata and image.size != metadata["size"]:
            image = image.resize(metadata["size"], Image.Resampling.LANCZOS)

        if "mode" in metadata and image.mode != metadata["mode"]:
            image = image.convert(metadata["mode"])

        return image
    except Exception as e:
        raise RuntimeError(f"Image decoding failed: {e}")


def deserialize_data(data):
    if isinstance(data, dict) and "type" in data:
        if data["type"] == "numpy_array":
            return decode_numpy(data)
        elif data["type"] == "tensor":
            return decode_tensor(data)
        elif data["type"] == "image":
            return decode_image(data)
    elif isinstance(data, (list, tuple)):
        return [deserialize_data(item) for item in data]
    elif isinstance(data, dict):
        return {key: deserialize_data(value) for key, value in data.items()}
    else:
        return data


class EvalClient:
    """
    EvalClient in binary mode:
    - /step:  pickled action_dict <-> pickled response_dict
    - /reset: pickled {"worker_ids": [...]} <-> pickled obs_dict
    The rest APIs are still in JSON.
    """

    def __init__(self, base_url: str, worker_ids: list):
        self.base_url = base_url.rstrip("/")
        self.worker_ids = worker_ids

        # create workers on server
        self._create_workers()

    def _create_workers(self):
        resp = requests.post(
            f"{self.base_url}/create_workers",
            json={"data": {"worker_ids": self.worker_ids}},
            timeout=300,
        )
        if resp.status_code != 200:
            # HTTPExceptions layer
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(
                f"HTTP error when create_workers: {resp.status_code} - {detail}"
            )

    def reset(self):
        """
        Gym-style reset: Return initial obs_dict
        """
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
        return obs_dict

    def step(self, action_dict: dict):
        """
        step function, step the workers with given actions

        Args:
            action_dict: {worker_id: action}

        Return:
            response_dict = {worker_id: {...}}
            You can get obs / metric / reset from response_dict[worker_id]["obs"], etc.
        """
        payload = pickle.dumps(action_dict, protocol=pickle.HIGHEST_PROTOCOL)
        try:
            resp = requests.post(
                f"{self.base_url}/step",
                data=payload,
                headers={"Content-Type": "application/octet-stream"},
            )
        except requests.RequestException as e:
            raise RuntimeError(f"HTTP request to server failed: {e}") from e

        if resp.status_code != 200:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(f"HTTP error from server: {resp.status_code} - {detail}")

        obs_dict = pickle.loads(resp.content)
        done = self.handle_done(obs_dict)
        return deserialize_data(obs_dict), done

    def handle_done(self, data: dict):
        if all([data[worker_id]["metric"] != None for worker_id in self.worker_ids]):
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


def fake_action(arm_type: str, gripper_type: str, control_type: str) -> dict:
    if arm_type == "franka":
        if gripper_type == "panda_hand":
            if control_type == "joint_position":
                actions = {"action": [0.0] * 9, "control_type": "joint_position"}
            elif control_type == "ee_pose":
                actions = {
                    "action": (
                        [0.001, 0.001, 0.001],
                        [1.0, 0.0, 0.0, 0.0],
                        [0.04, 0.04],
                    ),
                    "control_type": "ee_pose",
                }
            else:
                raise ValueError("Invalid control type")
        elif gripper_type == "robotiq":
            if control_type == "joint_position":
                actions = {"action": [0] * 13, "control_type": "joint_position"}
            elif control_type == "ee_pose":
                actions = {
                    "action": (
                        [0.001, 0.001, 0.001],
                        [1.0, 0.0, 0.0, 0.0],
                        [0.7853, 0.7853, -0.7853, -0.7853, -0.7853, -0.7853],
                    ),
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
                    "control_type": "ee_pose",
                }
            else:
                raise ValueError("Invalid control type")
        else:
            raise ValueError("Invalid gripper type")
    else:
        raise ValueError("Invalid arm type")
    return actions


def parse_list(s):
    return s.split(",")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--worker_ids",
        type=parse_list,
        default=["0"],
        help="List of worker IDs, i.e. --worker_ids 0,1,2",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8087)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("-a", "--arm_type", type=str, default="franka")
    parser.add_argument("-g", "--gripper_type", type=str, default="panda_hand")
    parser.add_argument("-c", "--control_type", type=str, default="joint_position")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    host = args.host
    port = args.port
    worker_ids = args.worker_ids
    base_url = f"http://{host}:{port}"

    # Create workers on server here, make sure they are created before stepping
    client = EvalClient(base_url, worker_ids)
    print(f"Created workers {worker_ids} on server {base_url}.")

    # wrap the eval loop in a try-finally to ensure cleanup
    try:

        obs = client.reset()

        while True:

            action = {
                i: fake_action(args.arm_type, args.gripper_type, args.control_type)
                for i in worker_ids
            }

            start = time.time()
            obs, done = client.step(action)
            print(f"workers {worker_ids} Step time: {time.time() - start:.4f} seconds")

            if done:
                # finished all evaluations
                break
            if obs is None:
                break
            if obs[worker_ids[0]]["obs"]["reset"]:  # type: ignore
                # model.reset()
                pass
    finally:
        client.kill_workers()
        print("Client cleaned.")
