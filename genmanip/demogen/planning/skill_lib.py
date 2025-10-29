"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from genmanip.demogen.planning.skills.mimicgen_skill import replay_mimicgen_skill
from genmanip.demogen.planning.skills.pick_up_banana import pick_up_banana
from genmanip.demogen.recoder.planning_recorder import Logger as PlanningLogger


def record_code_skill(
    scene: dict,
    recorder: PlanningLogger,
    demogen_config: dict,
    action_info: dict,
    idx: str,
) -> bool:
    if action_info["name"] == "pick_up_banana":
        return pick_up_banana(scene, recorder, demogen_config, action_info, idx)
    else:
        raise ValueError("Unsupported action")


def record_mimicgen_skill(
    scene: dict,
    recorder: PlanningLogger,
    demogen_config: dict,
    action_info: dict,
    idx: str,
) -> bool:
    if "obj1_uid" in action_info and "skill_name" in action_info:
        if (
            action_info["obj1_uid"] in scene["articulation_data"]
            and action_info["skill_name"]
            in scene["articulation_data"][action_info["obj1_uid"]]["skills"]
        ):
            return replay_mimicgen_skill(
                scene, recorder, demogen_config, action_info, idx
            )
        else:
            raise ValueError(
                f"{action_info['obj1_uid']} unsupported action {action_info['skill_name']}"
            )
    else:
        raise ValueError("Unsupported action")
