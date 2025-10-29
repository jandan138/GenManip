"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import os
from pathlib import Path

from isaacsim import SimulationApp
from PIL import Image

from genmanip.utils.file_utils import load_default_config, load_yaml
from genmanip.utils.utils import setup_logger

current_dir = os.path.dirname(os.path.abspath(__file__))
simulation_app = SimulationApp({"headless": True})

from omni.isaac.core import World  # type: ignore

from genmanip.core.loading.loading import (
    create_camera_list,
    get_object_list,
    load_world_xform_prim,
    relate_franka_from_data,
)
from genmanip.core.pointcloud.pointcloud import objectList2meshList
from genmanip.core.sensor.camera import get_src
from genmanip.core.usd_utils import set_colliders

# 1. setup logger and config
logger = setup_logger()
default_config = load_default_config(
    current_dir=current_dir, config_name="__None__.json", anygrasp_mode="local"
)
ASSETS_DIR = default_config["ASSETS_DIR"]
TEST_USD_NAME = default_config["TEST_USD_NAME"]
TABLE_UID = "aa49db8a801d402dac6cf1579536502c"
camera_data = load_yaml("configs/cameras/fixed_camera_robotiq_simbox.yml")

# 2. load scene
scene_xform, uuid = load_world_xform_prim(
    os.path.join(ASSETS_DIR, "scene_usds/base_scenes/base.usda")
)
world = World()
print(f"scene uuid: {uuid}")

# 3. create camera/robot/object/mesh list
camera_list = create_camera_list(camera_data, uuid)
franka_list = [relate_franka_from_data(uuid)]
object_list = get_object_list(uuid, scene_xform, TABLE_UID)
meshDict = objectList2meshList(object_list)
for obj in object_list.values():
    set_colliders(obj.prim_path, "convexDecomposition")

# 4. reset world
world.reset()

# 5. camera warmup
while any(
    camera._custom_annotators["distance_to_image_plane"] is not None
    and get_src(camera, "depth") is None
    for camera in camera_list.values()
):
    world.step()

# 6. save image
for _ in range(10):
    for key, camera in camera_list.items():
        print(key, camera.get_local_pose(camera_axes="usd"))
    world.step()
Path("tmp").mkdir(parents=True, exist_ok=True)
image = Image.fromarray(get_src(camera_list["obs_camera"], "rgb"))
image.save("tmp/test.png")

# 7. close simulation app
simulation_app.close()
