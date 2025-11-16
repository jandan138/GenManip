"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import os

from genmanip.core.loading.loading import (
    build_scene_from_config,
    collect_meta_infos,
    load_object_pool,
    preprocess_scene,
    warmup_world,
)
from genmanip.demogen.planning.utils import check_eval_finished
from genmanip.utils.file_utils import make_dir


def get_next_seed(eval_config: dict, default_config: dict) -> str | None:
    seed = check_eval_finished(eval_config, default_config)
    if seed == -1:
        return None
    seed = str(seed).zfill(3)
    make_dir(
        os.path.join(default_config["EVAL_RESULT_DIR"], eval_config["task_name"], seed)
    )
    return seed


def initialize_scene(eval_config: dict, default_config: dict, current_dir: str) -> dict:
    scene = build_scene_from_config(
        eval_config,
        default_config,
        current_dir,
        is_eval=True,
        physics_dt=1 / 30,
        rendering_dt=1 / 30,
        only_depth_rep_for_camera=True,
    )
    load_object_pool(scene, eval_config, current_dir)
    preprocess_scene(scene, eval_config)
    warmup_world(scene)
    collect_meta_infos(scene)
    return scene
