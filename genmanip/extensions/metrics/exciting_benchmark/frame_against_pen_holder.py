"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from typing import Any
from pydantic import BaseModel, Field

from genmanip.core.metrics.base import BaseMetric
from genmanip.core.metrics.utils import MetricFactory
from genmanip.extensions.metrics.default.match_local_world_orientation import (
    MatchLocalWorldOrientation,
)
from genmanip.extensions.metrics.default.sr_based_genmanip_relationship import (
    SRBasedGenmanipRelationship,
    calculate_distance_between_two_point_clouds,
)


class FrameAgainstPenHolderConfig(BaseModel):
    obj1_uid: str = Field(..., description="UID of the object to measure the distance")
    obj2_uid: str | None = Field(
        ..., description="UID of the object to measure the distance"
    )
    tolerance: float = Field(
        ..., description="distance tolerance between obj1_uid and obj2_uid"
    )


@MetricFactory.register("manip/exciting_benchmark/frame_against_pen_holder")
class FrameAgainstPenHolder(BaseMetric):
    def __init__(
        self, skip_steps=1, succ_cnts=0, sub_goal_setting: dict[str, Any] = {}, **kwargs
    ):
        super().__init__(skip_steps, succ_cnts, sub_goal_setting, **kwargs)
        self.setting = FrameAgainstPenHolderConfig(**sub_goal_setting)
        self.check_frame_orien = MatchLocalWorldOrientation(
            sub_goal_setting=sub_goal_setting
        )

    def check_status(self, scene):
        target_uids = [self.setting.obj1_uid, self.setting.obj2_uid]
        pclist = SRBasedGenmanipRelationship.get_target_pc_list(scene, target_uids)

        dist = calculate_distance_between_two_point_clouds(
            pclist[self.setting.obj1_uid], pclist[self.setting.obj2_uid]
        )

        # Rule 1: The picture frame came into contact with the pen holder.
        if not dist < self.setting.tolerance:
            return False

        # Rule 2: The back of the picture frame rests against the pen holder, and keeping it upright.
        if not self.check_frame_orien.check_status(scene=scene):
            return False

        return True
