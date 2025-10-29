"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from dataclasses import dataclass, field


class ActionInfo:
    type: str = ""


class ExecutableActionInfo(ActionInfo):
    pass


class RuleActionInfo(ActionInfo):
    pass


@dataclass
class PnPOptions:
    # grasp position
    force_fixed_grasp: bool = False
    allow_fixed_grasp: bool = False
    fixed_grasp_config: dict | None = None

    # place position
    fixed_position: bool = False
    fixed_position_config: dict | None = None

    # special options
    mesh_top_only: bool = False
    without_platform: bool = False


@dataclass
class PnPActionInfo(ExecutableActionInfo):
    type: str = "pnp"
    obj1_uid: str = ""
    obj2_uid: str = ""
    another_obj2_uid: str | None = None
    position: str = ""
    ignored_uid: list[str] = field(default_factory=list)
    options: PnPOptions = field(default_factory=PnPOptions)


@dataclass
class SyncActionInfo(RuleActionInfo):
    type: str = "sync"


@dataclass
class WaitActionInfo(RuleActionInfo):
    type: str = "wait"
    wait_step: int | str = "-inf"


def action_dict_to_action_info(action_dict: dict) -> ExecutableActionInfo:
    if (
        "obj1_uid" in action_dict
        and "obj2_uid" in action_dict
        and "position" in action_dict
    ):
        return PnPActionInfo(
            obj1_uid=action_dict["obj1_uid"],
            obj2_uid=action_dict["obj2_uid"],
            another_obj2_uid=action_dict.get("another_obj2_uid", None),
            position=action_dict["position"],
            ignored_uid=action_dict.get("ignored_uid", []),
            options=PnPOptions(
                force_fixed_grasp=action_dict.get("force_fixed_grasp", False),
                allow_fixed_grasp=action_dict.get("allow_fixed_grasp", False),
                fixed_grasp_config=action_dict.get("fixed_grasp_config", None),
                fixed_position=action_dict.get("fixed_position", False),
                fixed_position_config=action_dict.get("fixed_position_config", None),
                mesh_top_only=action_dict.get("mesh_top_only", False),
                without_platform=action_dict.get("without_platform", False),
            ),
        )
    else:
        raise ValueError(f"Unsupported action dict: {action_dict}")
