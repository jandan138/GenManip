"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import os
from typing import cast

from genmanip.utils.pointcloud.pointcloud import get_current_pcList_by_meshList
from genmanip.utils.usd_utils import set_mass
from genmanip.core.metrics.metrics import check_subgoal_finished_rigid
from genmanip.demogen.planning.pick_and_place import (
    get_action_meta_info,
    record_planning,
)
from genmanip.demogen.planning.skill_lib import record_code_skill, record_mimicgen_skill
from genmanip.demogen.planning.action_info import (
    ActionInfo,
    ExecutableActionInfo,
    RuleActionInfo,
    PnPActionInfo,
    SyncActionInfo,
    WaitActionInfo,
)
from genmanip.demogen.recoder.planning_recorder import Logger as PlanningLogger


def planning(
    scene: dict,
    default_config: dict,
    demogen_config: dict,
    action_info_dict: dict[
        str, list[WaitActionInfo | ExecutableActionInfo | SyncActionInfo]
    ] = {},
    action_dict: dict[str, list[dict]] = {},
) -> list[dict] | dict[str, list[str]] | None:
    # 1. if all arm has action to execute
    if all(len(action_list) != 0 for action_list in action_dict.values()):
        return [action_dict[key].pop(0) for key in action_dict.keys()]

    # 2. if all actions are sync, finish sync
    if all(
        isinstance(action_info_list[0], SyncActionInfo)
        for action_info_list in action_info_dict.values()
    ):
        for key in action_info_dict.keys():
            action_info_dict[key].pop(0)

    # 3. plan action for each arm if it has no action to execute
    for arm_name in action_dict.keys():
        if len(action_dict[arm_name]) == 0:
            if len(action_info_dict[arm_name]) == 0 or isinstance(
                action_info_dict[arm_name][0], SyncActionInfo
            ):
                action_dict[arm_name].append(
                    {
                        "joint_action": scene["robot_list"][0].get_joint_postion_by_arm(
                            arm_name
                        ),
                        "gripper_action": None,
                        "name": "wait",
                    }
                )
            elif isinstance(action_info_dict[arm_name][0], WaitActionInfo):
                for _ in range(
                    int(cast(WaitActionInfo, action_info_dict[arm_name][0]).wait_step)
                ):
                    action_dict[arm_name].append(
                        {
                            "joint_action": scene["robot_list"][
                                0
                            ].get_joint_postion_by_arm(arm_name),
                            "gripper_action": None,
                            "name": "wait",
                        }
                    )
                action_info_dict[arm_name].pop(0)
            elif isinstance(action_info_dict[arm_name][0], ExecutableActionInfo):
                action_dict[arm_name].extend(
                    plan_executable_action(
                        scene,
                        cast(ExecutableActionInfo, action_info_dict[arm_name][0]),
                        default_config,
                        demogen_config,
                    )
                )
                action_info_dict[arm_name].pop(0)
            else:
                raise ValueError(
                    f"Unsupported, {type(action_info_dict[arm_name][0])} is not ExecutableActionInfo"
                )

    # 4. if all actions are done, return None
    if all(
        len(action_info_list) == 0 for action_info_list in action_info_dict.values()
    ) and all(len(action_list) == 0 for action_list in action_dict.values()):
        return None
    # 5. if all arms have action to execute, return the action
    elif all(len(action_list) != 0 for action_list in action_dict.values()):
        detailed_action_list = {
            key: action_dict[key].pop(0) for key in action_dict.keys()
        }
        joint_action_list = [
            detailed_action_list[key]["joint_action"]
            for key in detailed_action_list.keys()
        ]
        gripper_action_list = [
            detailed_action_list[key]["gripper_action"]
            for key in detailed_action_list.keys()
        ]
        name_list = [
            f"{key}/{detailed_action_list[key]['name']}"
            for key in detailed_action_list.keys()
        ]
        return {
            "joint_action_list": joint_action_list,
            "gripper_action_list": gripper_action_list,
            "name_list": name_list,
        }
    else:
        raise ValueError("Unsupported, some arm has action to execute but some not")


def plan_executable_action(
    scene: dict,
    action_info: ExecutableActionInfo,
    default_config: dict,
    demogen_config: dict,
) -> list[dict]:
    if isinstance(action_info, PnPActionInfo):
        return plan_pick_and_place_action(
            scene, action_info, default_config, demogen_config
        )
    else:
        raise ValueError(f"Unsupported action type: {action_info.type}")


def plan_pick_and_place_action(
    scene: dict,
    action_info: PnPActionInfo,
    default_config: dict,
    demogen_config: dict,
) -> list[dict]:
    set_mass(scene["object_list"][action_info.obj1_uid].prim_path, 0.1)
    set_mass(scene["object_list"][action_info.obj2_uid].prim_path, 10.0)
    # action_meta_info = get_action_meta_info(scene, action_info, default_config)
    return [{}]


def execute_action(
    scene: dict,
    action: dict,
    recorder: PlanningLogger,
) -> None:
    scene["robot_list"][0].robot_view.set_joint_position_targets(action["joint_action"])
    recorder.load_dynamic_info(
        action["joint_action"],
        action["gripper_action"],
        name=action["name_list"],
    )
    scene["world"].step(render=False)
    if os.environ.get("GENMANIP_DEBUG", "0") == "1":
        scene["world"].render()


def check_action_finished(
    scene: dict,
    action_info: dict,
    default_config: dict,
    demogen_config: dict,
    recorder: PlanningLogger,
) -> bool:
    return False


def apply_action_by_config(
    scene: dict,
    action_info: dict,
    default_config: dict,
    demogen_config: dict,
    recorder: PlanningLogger,
    idx: str,
) -> bool:
    # if is pick and place action
    if (
        "position" in action_info
        and "obj1_uid" in action_info
        and "obj2_uid" in action_info
    ):
        set_mass(scene["object_list"][action_info["obj1_uid"]].prim_path, 0.1)
        set_mass(scene["object_list"][action_info["obj2_uid"]].prim_path, 10.0)
        action_meta_info = get_action_meta_info(scene, action_info, default_config)
        record_planning(
            scene, recorder, demogen_config, action_meta_info, action_info, idx
        )
        pclist = get_current_pcList_by_meshList(
            scene["object_list"], scene["cacheDict"]["meshDict"]
        )
        is_success = check_subgoal_finished_rigid(
            action_info,
            pclist[action_info["obj1_uid"]],
            pclist[action_info["obj2_uid"]],
        )
        return is_success or (
            action_info.get("fixed_position", False)
            and action_info.get("mesh_top_only", False)
        )
    elif "type" in action_info and action_info["type"] == "code_skill":
        is_success = record_code_skill(
            scene, recorder, demogen_config, action_info, idx
        )
        return is_success
    elif "type" in action_info and action_info["type"] == "mimicgen_skill":
        is_success = record_mimicgen_skill(
            scene, recorder, demogen_config, action_info, idx
        )
        return is_success
    else:
        raise ValueError("Unsupported action")
