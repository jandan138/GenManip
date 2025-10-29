"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from genmanip.utils.transform_utils import (
    adjust_orientation,
    adjust_translation_along_quaternion,
)


def prepare_grasp_motion_planning_payload(
    init_grasp: dict,
    steps: int = 30,
    padding: float = 0.08,
    pre_offset: float = 0.06,
    post_offset: float = 0.22,
) -> list[dict]:
    init_grasp["orientation"] = adjust_orientation(init_grasp["orientation"])
    action_list = []
    action_list.append(
        {
            "name": "pre_grasp",
            "translation": adjust_translation_along_quaternion(
                init_grasp["translation"], init_grasp["orientation"], padding + pre_offset
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
                init_grasp["translation"], init_grasp["orientation"], padding
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
                init_grasp["translation"], init_grasp["orientation"], padding + post_offset
            ),
            "orientation": init_grasp["orientation"],
            "steps": steps,
            "grasp": True,
        }
    )
    return action_list
