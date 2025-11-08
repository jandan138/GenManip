import os
import copy

from curobo.util.trajectory import get_smooth_trajectory
import numpy as np
from scipy.spatial.transform import Rotation as R
from tqdm import tqdm
import torch

from omni.isaac.core.prims import XFormPrim  # type: ignore

from genmanip.core.loading.utils import collect_world_pose_list, reset_object_xyz
from genmanip.core.pointcloud.pointcloud import get_current_meshList
from genmanip.core.random_place.random_place import place_object_to_object_by_relation
from genmanip.core.robot.embodiment import BaseEmbodiment
from genmanip.core.sensor.camera import set_camera_look_at
from genmanip.demogen.recoder.planning_recorder import Logger as PlanningLogger
from genmanip.thirdparty.anygrasp import get_init_grasp
from genmanip.utils.transform_utils import (
    adjust_orientation,
    adjust_translation_along_quaternion,
    compute_final_pose,
    rot_orientation_by_axis,
    rot_orientation_by_z_axis,
)
from genmanip.demogen.planning.action_info import (
    ExecutableActionInfo,
    action_dict_to_action_info,
)


def get_action_init_grasp(
    scene: dict,
    action_info: dict | ExecutableActionInfo,
    default_config: dict,
    action_meta_info: dict,
) -> dict:
    if not action_info.options.force_fixed_grasp:
        set_camera_look_at(
            scene["camera_list"]["camera1"],
            scene["object_list"][action_info.obj1_uid],
            azimuth=180.0,
        )
        current_pose_list = collect_world_pose_list(scene["object_list"])
        current_joint_positions = scene["robot_info"]["robot_list"][
            0
        ].robot.get_joint_positions()
        robot_world_pose = scene["robot_info"]["robot_list"][0].robot.get_world_pose()
        scene["robot_info"]["robot_list"][0].robot.set_world_pose(
            robot_world_pose[0] + np.array([1000.0, 0.0, 0.0]), robot_world_pose[1]
        )
        for _ in range(5):
            scene["world"].step(render=True)
    meshlist = get_current_meshList(
        scene["object_list"], scene["cacheDict"]["meshDict"]
    )
    mesh = meshlist[action_info.obj1_uid]
    action_meta_info["init_grasp"] = get_init_grasp(
        scene["camera_list"]["camera1"],
        mesh,
        address=default_config["ANYGRASP_ADDR"],
        allow_fixed_grasp=action_info.options.allow_fixed_grasp,
        force_fixed_grasp=action_info.options.force_fixed_grasp,
    )
    if not action_info.options.force_fixed_grasp:
        for _ in range(5):
            reset_object_xyz(scene["object_list"], current_pose_list)
            scene["robot_info"]["robot_list"][0].robot.set_joint_positions(
                current_joint_positions
            )
            scene["robot_info"]["robot_list"][0].robot.set_world_pose(*robot_world_pose)
            scene["world"].step(render=True)
    if action_info.options.force_fixed_grasp or (
        action_info.options.allow_fixed_grasp
        and action_meta_info["init_grasp"]["translation"][0] == 0.0
        and action_meta_info["init_grasp"]["translation"][1] == 0.0
    ):
        action_meta_info["init_grasp"]["translation"][:2] = scene["object_list"][
            action_info.obj1_uid
        ].get_world_pose()[0][:2]
        if action_info.options.fixed_grasp_config is not None:
            action_meta_info["init_grasp"]["translation"] += np.array(
                action_info.options.fixed_grasp_config["translation"]
            )
    action_meta_info["obj_init_t"], action_meta_info["obj_init_o"] = scene[
        "object_list"
    ][action_info.obj1_uid].get_world_pose()
    return action_meta_info


def compute_final_grasp(
    object_list: dict[str, XFormPrim],
    action: ExecutableActionInfo,
    meshDict: dict,
    extra_erosion: float = 0.05,
) -> tuple[np.ndarray, np.ndarray] | tuple[None, None]:
    obj_init_t, obj_init_o = object_list[action.obj1_uid].get_world_pose()
    if action.position == "top" or action.position == "in":
        IS_OK = place_object_to_object_by_relation(
            action.obj1_uid,
            action.obj2_uid,
            object_list,
            meshDict,
            "on",
            platform_uid=(
                "00000000000000000000000000000000"
                if not action.options.without_platform
                else None
            ),
            ignored_uid=action.ignored_uid,
            extra_erosion=extra_erosion,
            fixed_position=action.options.fixed_position,
            mesh_top_only=action.options.mesh_top_only,
        )
    elif action.position == "near":
        IS_OK = place_object_to_object_by_relation(
            action.obj1_uid,
            action.obj2_uid,
            object_list,
            meshDict,
            "near",
            platform_uid="00000000000000000000000000000000",
            ignored_uid=action.ignored_uid,
            extra_erosion=extra_erosion,
        )
    else:
        if action.another_obj2_uid is not None:
            IS_OK = place_object_to_object_by_relation(
                action.obj1_uid,
                action.obj2_uid,
                object_list,
                meshDict,
                action.position,
                platform_uid="00000000000000000000000000000000",
                ignored_uid=action.ignored_uid,
                extra_erosion=extra_erosion,
                another_object2_uid=action.another_obj2_uid,
            )
        else:
            IS_OK = place_object_to_object_by_relation(
                action.obj1_uid,
                action.obj2_uid,
                object_list,
                meshDict,
                action.position,
                platform_uid="00000000000000000000000000000000",
                ignored_uid=action.ignored_uid,
                extra_erosion=extra_erosion,
            )
    if IS_OK == -1:
        return None, None
    obj_tar_t, obj_tar_o = object_list[action.obj1_uid].get_world_pose()
    object_list[action.obj1_uid].set_world_pose(
        position=obj_init_t, orientation=obj_init_o
    )
    if action.options.fixed_position_config is not None:
        obj_tar_t = obj_tar_t + np.array(
            action.options.fixed_position_config["translation"]
        )
        obj_tar_o = (
            R.from_quat(
                np.array(action.options.fixed_position_config["orientation"])[
                    [1, 2, 3, 0]
                ]
            )
            * R.from_quat(obj_tar_o[[1, 2, 3, 0]])
        ).as_quat()[[3, 0, 1, 2]]
    return obj_tar_t, obj_tar_o


def prepare_motion_planning_payload(
    init_grasp: dict,
    grasp_tar_t: np.ndarray,
    grasp_tar_o: np.ndarray,
    steps: int = 30,
    aug_distance: float = 0.0,
    pre_grasp_distance: float = 0.08,
    post_grasp_distance: float = 0.16,
    pre_place_distance: float = 0.16,
    post_place_distance: float = 0.08,
) -> list[dict]:
    action_list = []
    if pre_grasp_distance is not None:
        action_list.append(
            {
                "name": "pre_grasp",
                "translation": adjust_translation_along_quaternion(
                    init_grasp["translation"],
                    init_grasp["orientation"],
                    pre_grasp_distance,
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
    if post_grasp_distance is not None:
        action_list.append(
            {
                "name": "post_grasp",
                "translation": adjust_translation_along_quaternion(
                    init_grasp["translation"],
                    init_grasp["orientation"],
                    post_grasp_distance,
                    aug_distance=aug_distance,
                ),
                "orientation": init_grasp["orientation"],
                "steps": steps,
                "grasp": True,
            }
        )
    if pre_place_distance is not None:
        action_list.append(
            {
                "name": "pre_place",
                "translation": adjust_translation_along_quaternion(
                    grasp_tar_t,
                    grasp_tar_o,
                    pre_place_distance,
                    aug_distance=aug_distance,
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
                grasp_tar_t, grasp_tar_o, 0.02
            ),
            "orientation": grasp_tar_o,
            "steps": steps,
            "grasp": True,
        }
    )
    if post_place_distance is not None:
        action_list.append(
            {
                "name": "post_place",
                "translation": adjust_translation_along_quaternion(
                    grasp_tar_t,
                    grasp_tar_o,
                    post_place_distance,
                    aug_distance=aug_distance,
                ),
                "orientation": grasp_tar_o,
                "steps": steps,
                "grasp": False,
            }
        )
    return action_list


def record_planning_result_curobo(
    init_grasp: dict,
    grasp_tar_t: np.ndarray,
    grasp_tar_o: np.ndarray,
    embodiment: BaseEmbodiment,
    arm: str,
    recorder: PlanningLogger,
    idx_name: str,
    scene: dict,
    aug_distance: float = 0.0,
    reset_tcp: tuple[np.ndarray, np.ndarray] | bool | None = None,
    smooth: bool = False,
    motion_config: dict = {},
) -> bool:
    action_list = prepare_motion_planning_payload(
        init_grasp,
        grasp_tar_t,
        grasp_tar_o,
        aug_distance=aug_distance,
        **motion_config,
    )
    for target in action_list:
        target = adjust_grasp_by_embodiment(target, embodiment)
    data_list = []
    sim_js = embodiment.robot.get_joints_state()
    if arm == "auto":
        arm = embodiment.reference_arm_type(init_grasp["translation"])
    for idx, target in tqdm(enumerate(action_list)):
        results = embodiment.plan_pose(
            (target["translation"], target["orientation"]),
            sim_js,
            arm=arm,
        )
        if smooth:
            results = get_smooth_trajectory(
                torch.from_numpy(np.array(results)), 5
            ).numpy()
        if results is not None:
            for res in results:
                data_list.append(
                    {
                        "action": embodiment.convert_curobo_result_to_action(
                            res, target["grasp"], arm
                        ).tolist(),
                        "name": target["name"],
                        "grasp": target["grasp"],
                    }
                )
                sim_js.positions = embodiment.convert_action_to_joint_state(
                    data_list[-1]["action"], arm
                )
            if idx != len(action_list) - 1:
                if target["grasp"] != action_list[idx + 1]["grasp"]:
                    action = data_list[-1]["action"]
                    for _ in range(13):
                        data_list.append(
                            {
                                "action": embodiment.convert_curobo_result_to_action(
                                    action, action_list[idx + 1]["grasp"], arm
                                ).tolist(),
                                "name": target["name"],
                                "grasp": action_list[idx + 1]["grasp"],
                            }
                        )
        else:
            raise Exception("motion planning failed at step: " + str(idx))
    if isinstance(reset_tcp, bool) and reset_tcp:
        reset_tcp = 0.0
    if reset_tcp != -1:
        original_final_joint_position = np.array(data_list[-1]["action"])
        reset_tcp_ratio = np.random.uniform(0.0, reset_tcp)
        target_reset_joint_position = (
            np.array(data_list[0]["action"]) * (1 - reset_tcp_ratio)
            + original_final_joint_position * reset_tcp_ratio
        )
        delta_joint_position = (
            target_reset_joint_position - original_final_joint_position
        ) / 100
        for i in range(100):
            data_list.append(
                {
                    "action": (
                        original_final_joint_position + delta_joint_position * i
                    ).tolist(),
                    "name": "reset_tcp",
                    "grasp": False,
                }
            )
    while data_list:
        action = data_list.pop(0)
        embodiment.robot_view.set_joint_position_targets(
            action["action"], joint_indices=embodiment.default_dof_indices
        )
        recorder.load_dynamic_info(
            action["action"],
            1 if action["grasp"] else -1,
            arm=arm,
            name=f"{idx_name}/{action['name']}",
        )
        scene["world"].step(render=False)
        if os.environ.get("GENMANIP_DEBUG", "0") == "1":
            scene["world"].render()
    return True, arm


def adjust_grasp_by_embodiment(
    grasp: dict,
    embodiment: BaseEmbodiment,
) -> dict:
    grasp["orientation"] = adjust_orientation(grasp["orientation"])
    if embodiment.embodiment_name == "franka":
        if embodiment.gripper_name == "panda_hand":
            grasp["translation"] = adjust_translation_along_quaternion(
                grasp["translation"],
                grasp["orientation"],
                0.08,
                aug_distance=0.0,
            )
        elif embodiment.gripper_name == "robotiq":
            # robotiq 的 grasp pose 需要绕 z 轴旋转 45 度
            grasp["orientation"] = rot_orientation_by_z_axis(grasp["orientation"], -45)
            grasp["translation"] = adjust_translation_along_quaternion(
                grasp["translation"],
                grasp["orientation"],
                0.15,
                aug_distance=0.0,
            )
    elif embodiment.embodiment_name == "aloha_split":
        if embodiment.gripper_name == "piper":
            grasp["orientation"] = rot_orientation_by_z_axis(grasp["orientation"], -90)
            grasp["translation"] = adjust_translation_along_quaternion(
                grasp["translation"],
                grasp["orientation"],
                0.11,
                aug_distance=0.0,
            )
    elif embodiment.embodiment_name == "lift2":
        if embodiment.gripper_name == "lift2":
            grasp["translation"] = adjust_translation_along_quaternion(
                grasp["translation"],
                grasp["orientation"],
                0.135,
                aug_distance=0.0,
            )
            grasp["orientation"] = rot_orientation_by_axis(
                grasp["orientation"], "y", 90
            )
            grasp["orientation"] = rot_orientation_by_axis(
                grasp["orientation"], "z", 180
            )
    return grasp


def get_action_meta_info(
    scene: dict,
    action_info: ExecutableActionInfo | dict,
    default_config: dict,
) -> dict:
    if isinstance(action_info, dict):
        action_info = action_dict_to_action_info(action_info)
    action_meta_info = {}
    action_meta_info["obj_tar_t"], action_meta_info["obj_tar_o"] = compute_final_grasp(
        scene["object_list"],
        action_info,
        scene["cacheDict"]["meshDict"],
    )
    if action_meta_info["obj_tar_t"] is None or action_meta_info["obj_tar_o"] is None:
        raise Exception("can't create target position, retry......")
    action_meta_info = get_action_init_grasp(
        scene,
        action_info,
        default_config,
        action_meta_info,
    )
    action_meta_info["grasp_tar_t"], action_meta_info["grasp_tar_o"] = (
        compute_final_pose(
            action_meta_info["obj_init_t"],
            action_meta_info["obj_init_o"],
            action_meta_info["init_grasp"]["translation"],
            action_meta_info["init_grasp"]["orientation"],
            action_meta_info["obj_tar_t"],
            action_meta_info["obj_tar_o"],
        )
    )
    return action_meta_info


def record_planning(
    scene: dict,
    recorder: PlanningLogger,
    demogen_config: dict,
    action_meta_info: dict,
    action_info: dict,
    idx: str,
) -> bool:
    if demogen_config["generation_config"]["planner"] == "curobo":
        if action_info.get(
            "update_planner",
            demogen_config["generation_config"].get("update_planner", False),
        ):
            ignore_list = [
                f"obj_{action_info['obj1_uid']}",
                f"obj_{demogen_config['table_uid']}",
            ]
            ignore_list.extend(action_info.get("plan_ignored_list", []))
            scene["planner_list"][0].update(ignore_list=ignore_list)
        is_success, action_info["arm"] = record_planning_result_curobo(
            action_meta_info["init_grasp"],
            action_meta_info["grasp_tar_t"],
            action_meta_info["grasp_tar_o"],
            scene["robot_info"]["robot_list"][0],
            action_info.get("arm", "default"),
            recorder,
            idx_name=idx,
            scene=scene,
            aug_distance=demogen_config["generation_config"].get("aug_distance", 0.0),
            reset_tcp=action_info.get(
                "reset_tcp", demogen_config["generation_config"].get("reset_tcp", -1)
            ),
            smooth=demogen_config["generation_config"].get("smooth", False),
            motion_config=action_info.get("motion_config", {}),
        )
    elif demogen_config["generation_config"]["planner"] == "mplib":
        raise NotImplementedError(
            "mplib planner is not supported for pick and place anymore!!!"
        )
    else:
        raise NotImplementedError(
            f"planner {demogen_config['generation_config']['planner']} is not supported"
        )
    if not is_success:
        raise ValueError("Task planning failed")
    return is_success
