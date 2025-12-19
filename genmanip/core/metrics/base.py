"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from genmanip.core.metrics.utils import MetricFactory

if TYPE_CHECKING:
    from genmanip.core.scene.scene import Scene


@MetricFactory.register("base")
class BaseMetric(ABC):
    def __init__(self, skip_steps=1, succ_cnts=0, **kwargs) -> None:
        self.skip_steps = skip_steps
        self.succ_cnts = succ_cnts
        self.kwargs = kwargs

        self._step_cnt = 0
        self._succ_cnt = 0

        self.succ_flag = False

    @property
    def status(self) -> bool:
        return self.succ_flag

    @abstractmethod
    def check_status(self, scene: Scene) -> bool:
        raise NotImplementedError("check_status must be implemented in subclass")

    def update(self, scene: Scene):
        if self.status:
            return

        if self._step_cnt % self.skip_steps == 0:
            _status = self.check_status(scene)

            self._succ_cnt += 1 if _status else 0

        self._step_cnt += 1
        self.succ_flag = self._succ_cnt > self.succ_cnts
