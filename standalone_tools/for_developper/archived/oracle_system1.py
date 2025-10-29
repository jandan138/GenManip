import argparse
import pickle
import struct
import socket
import time
import numpy as np


def send_message(send_socket: socket.socket, data: dict):
    serialized_data = pickle.dumps(data)
    message_size = struct.pack("Q", len(serialized_data))
    send_socket.sendall(message_size + serialized_data)


def wait_message(conn: socket.socket):
    data = b""
    payload_size = struct.calcsize("Q")
    while len(data) < payload_size:
        data += conn.recv(4096)
    packed_msg_size = data[:payload_size]
    data = data[payload_size:]
    msg_size = struct.unpack("Q", packed_msg_size)[0]

    while len(data) < msg_size:
        data += conn.recv(4096)

    frame_data = data[:msg_size]
    data = data[msg_size:]

    received_data = pickle.loads(frame_data)

    return received_data


def create_send_port_and_wait(port: int):
    serial = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serial.bind(("localhost", port))
    serial.listen(1)
    print("Waiting for a connection...")
    conn, addr = serial.accept()
    print("Connected by", addr)
    return conn


def create_receive_port_and_attach(port: int):
    serial = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serial.connect(("localhost", port))
    print("connected port ", port)
    return serial


parser = argparse.ArgumentParser()
parser.add_argument("-r", "--receive_port", type=int, default=10012)
parser.add_argument("-s", "--send_port", type=int, default=10013)
args = parser.parse_args()

import torch
from curobo.types.math import Pose as CuroboPose
from curobo.types.robot import JointState as CuroboJointState
from curobo.wrap.reacher.motion_gen import (
    MotionGen,
    MotionGenConfig,
    MotionGenPlanConfig,
)
from curobo.types.base import TensorDeviceType
from curobo.geom.sdf.world import CollisionCheckerType


class CuroboPlanner:
    def __init__(self, robot_cfg):
        self.tensor_args = TensorDeviceType()
        self.world_config = {
            "cuboid": {
                "table": {
                    "dims": [5.0, 5.0, 0.2],  # x, y, z
                    "pose": [0.0, 0.0, -0.1, 1, 0, 0, 0.0],  # x, y, z, qw, qx, qy, qz
                },
            },
        }
        self.motion_gen_config = MotionGenConfig.load_from_robot_config(
            robot_cfg,
            self.world_config,
            self.tensor_args,
            interpolation_dt=0.02,
            collision_activation_distance=0.05,
            trajopt_tsteps=32,
            collision_checker_type=CollisionCheckerType.VOXEL,
            use_cuda_graph=True,
            self_collision_check=True,
        )
        self.motion_gen = MotionGen(self.motion_gen_config)
        self.motion_gen.warmup(warmup_js_trajopt=False)
        self.motion_gen.clear_world_cache()
        self.motion_gen.reset(reset_seed=False)
        self.joint_names = [
            "panda_joint1",
            "panda_joint2",
            "panda_joint3",
            "panda_joint4",
            "panda_joint5",
            "panda_joint6",
            "panda_joint7",
        ]
        self.plan_config = MotionGenPlanConfig(
            enable_graph=False,
            enable_graph_attempt=7,
            max_attempts=10,
            pose_cost_metric=None,
            enable_finetune_trajopt=True,
        )

    def plan(self, start_state, goal_pose):
        start_state = CuroboJointState.from_position(
            torch.from_numpy(
                np.array(start_state[:7]).astype(np.float32).reshape(1, 7)
            ).cuda(),
            joint_names=self.joint_names,
        )
        goal_pose = CuroboPose.from_list(goal_pose)
        result = self.motion_gen.plan_single(
            start_state, goal_pose, self.plan_config.clone()
        )
        if result.success.item():
            cmd_plan = result.get_interpolated_plan()
            cmd_plan = cmd_plan.get_ordered_joint_state(self.joint_names)
            position_list = []
            for idx in range(len(cmd_plan.position)):
                joint_positions = cmd_plan.position[idx].cpu().numpy()
                position_list.append(joint_positions[:7])
            return position_list
        return None


from mplib import Planner as MPPlanner
from mplib import Pose as MPPose


class MPLibPlanner:
    def __init__(self, urdf_path, srdf_path, move_group="panda_hand"):
        self.planner = MPPlanner(
            urdf=urdf_path,
            srdf=srdf_path,
            move_group=move_group,
        )

    def plan(self, start_state, goal_pose):
        start_pose = np.array(start_state[:9])
        goal_pose = MPPose(p=goal_pose[:3], q=goal_pose[3:])
        result = self.planner.plan_pose(
            goal_pose, start_pose, time_step=1 / 60.0, rrt_range=0.01
        )
        assert "position" in result, "Plan failed"
        actions = [
            result["position"][i].tolist() for i in range(result["position"].shape[0])
        ]
        return np.array(actions)


from scipy.spatial.transform import Rotation as R


def adjust_translation_along_quaternion(
    translation, quaternion, distance, aug_distance=0.0
):
    rotation = R.from_quat(quaternion[[1, 2, 3, 0]])
    direction_vector = rotation.apply([0, 0, 1])
    reverse_direction = -direction_vector
    new_translation = translation + reverse_direction * distance
    arbitrary_vector = (
        np.array([1, 0, 0]) if direction_vector[0] == 0 else np.array([0, 1, 0])
    )
    perp_vector1 = np.cross(direction_vector, arbitrary_vector)
    perp_vector2 = np.cross(direction_vector, perp_vector1)
    perp_vector1 /= np.linalg.norm(perp_vector1)
    perp_vector2 /= np.linalg.norm(perp_vector2)
    random_shift = np.random.uniform(-aug_distance, aug_distance, size=2)
    new_translation += random_shift[0] * perp_vector1 + random_shift[1] * perp_vector2
    return new_translation


def prepare_motion_planning_payload(
    init_grasp, grasp_tar_t, grasp_tar_o, steps=30, aug_distance=0.0
):
    action_list = []
    action_list.append(
        {
            "name": "pre_grasp",
            "translation": adjust_translation_along_quaternion(
                init_grasp["translation"],
                init_grasp["orientation"],
                0.08,
                aug_distance=aug_distance,
            ),
            "orientation": init_grasp["orientation"],
            "steps": steps,
            "grasp": False,
        }
    )
    action_list.append(
        {
            "name": "grasp",
            "translation": adjust_translation_along_quaternion(
                init_grasp["translation"], init_grasp["orientation"], 0.0
            ),
            "orientation": init_grasp["orientation"],
            "steps": steps,
            "grasp": False,
        }
    )
    action_list.append(
        {
            "name": "post_grasp",
            "translation": adjust_translation_along_quaternion(
                init_grasp["translation"],
                init_grasp["orientation"],
                0.16,
                aug_distance=aug_distance,
            ),
            "orientation": init_grasp["orientation"],
            "steps": steps,
            "grasp": True,
        }
    )
    action_list.append(
        {
            "name": "pre_place",
            "translation": adjust_translation_along_quaternion(
                grasp_tar_t, grasp_tar_o, 0.14, aug_distance=aug_distance
            ),
            "orientation": grasp_tar_o,
            "steps": steps,
            "grasp": True,
        }
    )
    action_list.append(
        {
            "name": "place",
            "translation": adjust_translation_along_quaternion(
                grasp_tar_t, grasp_tar_o, 0.0
            ),
            "orientation": grasp_tar_o,
            "steps": steps,
            "grasp": True,
        }
    )
    action_list.append(
        {
            "name": "post_place",
            "translation": adjust_translation_along_quaternion(
                grasp_tar_t, grasp_tar_o, 0.06, aug_distance=aug_distance
            ),
            "orientation": grasp_tar_o,
            "steps": steps,
            "grasp": False,
        }
    )
    return action_list


class SimPlanner:
    def __init__(self, planner_type="curobo"):
        self.planner_type = planner_type
        if self.planner_type == "curobo":
            robot_cfg = "franka.yml"
            self.planner = CuroboPlanner(robot_cfg)
        elif self.planner_type == "mplib":
            urdf_path = "assets/robots/panda/panda_v2.urdf"
            srdf_path = "assets/robots/panda/panda_v2.srdf"
            move_group = "panda_hand"
            self.planner = MPLibPlanner(urdf_path, srdf_path, move_group)
        self.payload_list = []
        self.joint_position_list = []

    def plan(self, key_action, currnet_joint_position, reset=False):
        if reset:
            self.payload_list = prepare_motion_planning_payload(
                {
                    "translation": np.array(key_action[1][0]),
                    "orientation": np.array(key_action[1][1]),
                },
                np.array(key_action[2][0]),
                np.array(key_action[2][1]),
            )
        if len(self.joint_position_list) == 0:
            if len(self.payload_list) == 0:
                return np.array(currnet_joint_position)
            motion = self.payload_list.pop(0)
            self.joint_position_list = self.planner.plan(
                currnet_joint_position,
                np.concatenate([motion["translation"], motion["orientation"]]),
            )
            self.joint_position_list = [
                np.array(
                    joint_position[:7].tolist()
                    + ([0.0, 0.0] if motion["grasp"] else [0.04, 0.04])
                )
                for joint_position in self.joint_position_list
            ]
            if motion["name"] == "grasp":
                for _ in range(5):
                    self.joint_position_list.append(
                        np.array(self.joint_position_list[-1][:7].tolist() + [0.0, 0.0])
                    )
            if motion["name"] == "place":
                for _ in range(5):
                    self.joint_position_list.append(
                        np.array(
                            self.joint_position_list[-1][:7].tolist() + [0.04, 0.04]
                        )
                    )
        return self.joint_position_list.pop(0)


if __name__ == "__main__":
    send_socket = create_send_port_and_wait(port=args.send_port)
    time.sleep(1)
    receive_socket = create_receive_port_and_attach(port=args.receive_port)
    sim_planner = SimPlanner(planner_type="curobo")
    delta_joint_position = np.zeros(9)
    while True:
        data = wait_message(receive_socket)
        if data["reset"]:
            last_joint_position = data["joint_position_state"]
        actions = sim_planner.plan(
            data["key_action"], data["joint_position_state"], reset=data["reset"]
        )
        delta_joint_position[:7] = actions[:7] - last_joint_position[:7]
        delta_joint_position[7:] = actions[7:]
        last_joint_position = actions
        send_message(send_socket, {"action": delta_joint_position.tolist()})
