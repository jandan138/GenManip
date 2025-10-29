"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from omni.isaac.core import World  # type: ignore

from genmanip.thirdparty.curobo_planners.base import CuroboPlanner


class CuroboFrankaPlanner(CuroboPlanner):
    def __init__(self, robot_cfg: dict, world: World, robot_prim_path: str) -> None:
        super().__init__(robot_cfg, world, robot_prim_path)
        self.ordered_js_names = [
            "panda_joint1",
            "panda_joint2",
            "panda_joint3",
            "panda_joint4",
            "panda_joint5",
            "panda_joint6",
            "panda_joint7",
        ]
        self.dof_len = 7
