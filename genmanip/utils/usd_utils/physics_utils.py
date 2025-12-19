"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from omni.isaac.core.prims import GeometryPrim  # type: ignore
from omni.isaac.core.materials import PhysicsMaterial  # type: ignore
import omni.usd  # type: ignore
from pxr import PhysxSchema  # type: ignore


def setup_physics_scene(GPUDynamics: bool = False) -> None:
    stage = omni.usd.get_context().get_stage()
    physxSceneAPI = PhysxSchema.PhysxSceneAPI.Get(stage, "/physicsScene")
    physxSceneAPI.GetEnableGPUDynamicsAttr().Set(GPUDynamics)
    physxSceneAPI.GetEnableStabilizationAttr().Set(True)
    physxSceneAPI.GetEnableCCDAttr().Set(False)
    physxSceneAPI.GetBroadphaseTypeAttr().Set("GPU")
    physxSceneAPI.GetSolverTypeAttr().Set("TGS")
    physxSceneAPI.GetGpuTotalAggregatePairsCapacityAttr().Set(10 * 1024 * 1024)
    physxSceneAPI.GetGpuFoundLostAggregatePairsCapacityAttr().Set(10 * 1024 * 1024)


def add_physics_material(
    prim_path: str,
    static_friction: float = 1.0,
    dynamic_friction: float = 1.0,
) -> GeometryPrim:
    prim = str(prim_path)
    prim = GeometryPrim(prim_path)
    try:
        physics_material = PhysicsMaterial(
            prim_path=prim_path + "/physics_material",
            static_friction=static_friction,
            dynamic_friction=dynamic_friction,
            restitution=0.1,
        )
        prim.apply_physics_material(physics_material)
    except Exception as e:
        print("Physics material already exists")
    return prim
