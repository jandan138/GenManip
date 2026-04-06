"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from typing import Any, Tuple
from pydantic import BaseModel, Field
import numpy as np

from genmanip.core.metrics.base import BaseMetric
from genmanip.core.metrics.utils import MetricFactory
from genmanip.extensions.metrics.default.check_joint_angle import CheckJointAngle
from genmanip.extensions.metrics.default.sr_based_genmanip_relationship import (
    SRBasedGenmanipRelationship,
    check_subgoal_finished_rigid,
)


class JointConstraintConfig(BaseModel):
    joint_name: str = Field(..., description="DOF name of the articulation joint")
    angle_deg_range: Tuple[float, float] = Field(
        ..., description="Allowed joint angle range in degrees: (min_angle, max_angle)"
    )


class PutGlassInGlassboxConfig(BaseModel):
    glass_uid: str = Field(..., description="UID of the glass")
    glass_box_uid: str | None = Field(..., description="UID of the glass box")
    left_glass_leg_constraint: JointConstraintConfig = Field(
        ..., description="constraint of the left glass leg"
    )
    right_glass_leg_constraint: JointConstraintConfig = Field(
        ..., description="constraint of the right glass leg"
    )
    glass_box_constraint: JointConstraintConfig = Field(
        ..., description="constraint of the glass box"
    )


@MetricFactory.register("manip/exciting_benchmark/put_glass_in_glassbox")
class PutGlassInGlassbox(BaseMetric):
    def __init__(
        self, skip_steps=1, succ_cnts=0, sub_goal_setting: dict[str, Any] = {}, **kwargs
    ):

        super().__init__(skip_steps, succ_cnts, sub_goal_setting, **kwargs)
        self.setting = PutGlassInGlassboxConfig(**sub_goal_setting)

        self.check_left_glass_leg = CheckJointAngle(
            sub_goal_setting={
                "articulation_obj_uid": self.setting.glass_uid,
                "joint_name": self.setting.left_glass_leg_constraint.joint_name,
                "angle_deg_range": self.setting.left_glass_leg_constraint.angle_deg_range,
            }
        )

        self.check_right_glass_leg = CheckJointAngle(
            sub_goal_setting={
                "articulation_obj_uid": self.setting.glass_uid,
                "joint_name": self.setting.left_glass_leg_constraint.joint_name,
                "angle_deg_range": self.setting.left_glass_leg_constraint.angle_deg_range,
            }
        )

        self.check_glass_box = CheckJointAngle(
            sub_goal_setting={
                "articulation_obj_uid": self.setting.glass_box_uid,
                "joint_name": self.setting.glass_box_constraint.joint_name,
                "angle_deg_range": self.setting.glass_box_constraint.angle_deg_range,
            }
        )

        self.check_relationship_1 = SRBasedGenmanipRelationship(
            sub_goal_setting={
                "obj1_uid": f"{self.setting.glass_uid}_base",
                "obj2_uid": f"{self.setting.glass_box_uid}_group_1",
                "position": "on",
            }
        )

        self.check_relationship_2 = SRBasedGenmanipRelationship(
            sub_goal_setting={
                "obj1_uid": f"{self.setting.glass_box_uid}_group_2",
                "obj2_uid": f"{self.setting.glass_uid}_base",
                "position": "on",
            }
        )

    def check_status(self, scene):
        # Rule 1: Check if the glass are closed.
        if not self.check_left_glass_leg.check_status(scene):
            return False

        if not self.check_right_glass_leg.check_status(scene):
            return False

        # Rule 2: Check if the glass box are closed.
        if not self.check_glass_box.check_status(scene):
            return False

        # Rule 3: Check if the glasses are in the glasses case.
        target_uids = [
            f"{self.setting.glass_uid}_base",
            f"{self.setting.glass_box_uid}_group_1",
            f"{self.setting.glass_box_uid}_group_2",
        ]
        pclist = SRBasedGenmanipRelationship.get_target_pc_list(scene, target_uids)

        pcd1 = pclist[f"{self.setting.glass_uid}_base"]
        pcd2 = np.concatenate(
            [
                pclist[f"{self.setting.glass_box_uid}_group_1"],
                pclist[f"{self.setting.glass_box_uid}_group_2"],
            ],
            axis=0,
        )

        if not check_subgoal_finished_rigid("in", pcd1, pcd2, None):
            return False

        return True
