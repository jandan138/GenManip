#!/usr/bin/env python3
"""Static validator for the LabUtopia EBench proof-of-concept task package."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import math
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
TASK_ROOT = ROOT / "configs/tasks"
PACKAGE_ROOT = TASK_ROOT / "ebench/labutopia_lab_poc"
TASK_PREFIX = "ebench/labutopia_lab_poc/"
SCENE_UID = "labutopia_level1_poc"
RUNTIME_USD_NAME = "scene_usds/labutopia/level1_poc/lab_001/scene"
EXPECTED_TASKS = {"level1_pick", "level1_place", "level1_open_door"}
EXPECTED_TASK_ORDER = ["level1_pick", "level1_place", "level1_open_door"]
EXPECTED_TOP_INDEX_ENTRIES = [
    "ebench/labutopia_lab_poc/franka_poc/franka_poc.json",
    "ebench/labutopia_lab_poc/lift2_candidate/lift2_candidate.json",
]
EXPECTED_PROFILE_INDEX_ENTRIES = {
    profile: [
        f"ebench/labutopia_lab_poc/{profile}/{task}.yml"
        for task in EXPECTED_TASK_ORDER
    ]
    for profile in ("franka_poc", "lift2_candidate")
}
EXPECTED_WRAPPER_PRIM_PATHS = {
    "obj_conical_bottle02": "/World/labutopia_level1_poc/obj_obj_conical_bottle02",
    "obj_beaker2": "/World/labutopia_level1_poc/obj_obj_beaker2",
    "obj_target_plat": "/World/labutopia_level1_poc/obj_obj_target_plat",
    "obj_DryingBox_01": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
    "obj_DryingBox_01_handle": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle",
    "table": "/World/labutopia_level1_poc/obj_table",
}
EXPECTED_ARTICULATION_PART_PATHS = {
    "obj_DryingBox_01_handle": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle",
}
EXPECTED_RENDER_VISIBLE_OBJECTS = {
    "level1_pick": ["obj_conical_bottle02"],
    "level1_place": ["obj_beaker2", "obj_target_plat"],
    "level1_open_door": ["obj_DryingBox_01", "obj_DryingBox_01_handle"],
}
EXPECTED_HIDDEN_NON_TASK_OBJECTS = {
    "level1_pick": ["obj_beaker2", "obj_target_plat", "obj_DryingBox_01"],
    "level1_place": ["obj_conical_bottle02", "obj_DryingBox_01"],
    "level1_open_door": [
        "obj_conical_bottle02",
        "obj_beaker2",
        "obj_target_plat",
    ],
}
EXPECTED_FRANKA_TASK_CAMERA_CONFIGS = {
    "level1_pick": "configs/cameras/labutopia_franka_poc_pick.yml",
    "level1_place": "configs/cameras/labutopia_franka_poc_place.yml",
    "level1_open_door": "configs/cameras/labutopia_franka_poc_open_door.yml",
}
EXPECTED_FRANKA_TASK_CAMERA2_CONTRACTS = {
    "level1_pick": {
        "position": [0.28, -0.55, 1.2],
        "orientation": [0.87184, 0.4898, 0.0, 0.0],
        "resolution": [512, 512],
        "focal_length": 5.6,
        "horizontal_aperture": 10.0,
    },
    "level1_place": {
        "position": [0.26, -0.7, 1.32],
        "orientation": [0.87184, 0.4898, 0.0, 0.0],
        "resolution": [512, 512],
        "focal_length": 10.0,
        "horizontal_aperture": 10.0,
    },
    "level1_open_door": {
        "position": [0.62, 1.25, 1.35],
        "orientation": [0.87184, -0.4898, 0.0, 0.0],
        "resolution": [512, 512],
        "focal_length": 4.0,
        "horizontal_aperture": 10.0,
    },
}
EXPECTED_RENDER_PIXEL_THRESHOLDS = {
    "level1_pick": {
        "obj_conical_bottle02": {
            "min_width_px": 36,
            "min_height_px": 48,
            "min_bbox_area_fraction": 0.01,
        },
    },
    "level1_place": {
        "obj_beaker2": {
            "min_width_px": 34,
            "min_height_px": 34,
            "min_bbox_area_fraction": 0.008,
        },
        "obj_target_plat": {
            "min_width_px": 42,
            "min_height_px": 24,
            "min_bbox_area_fraction": 0.006,
        },
    },
    "level1_open_door": {
        "obj_DryingBox_01": {
            "min_width_px": 160,
            "min_height_px": 150,
            "min_bbox_area_fraction": 0.12,
        },
        "obj_DryingBox_01_handle": {
            "min_width_px": 18,
            "min_height_px": 64,
            "min_bbox_area_fraction": 0.004,
        },
    },
}
EXPECTED_RENDER_REJECTIONS = {
    "black_frame",
    "low_texture",
    "required_object_missing",
    "severe_clipping",
}
EXPECTED_DETERMINISTIC_LIGHTS = [
    {
        "prim_path": "/World/labutopia_level1_poc/DeterministicDomeLight",
        "type": "DomeLight",
        "intensity": 1000,
    }
]
EXPECTED_DRYING_BOX_RUNTIME_ASSET = {
    "strategy": "native_complex_with_additive_physics_override",
    "source_payload_used": True,
    "source_prim_path": "/World/DryingBox_01",
    "wrapper_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
    "handle_policy": "nested_native_handle",
    "surrogate_kept_for_debug_baseline": True,
    "unit_policy": "preserve_native_unit_scale_0_001",
    "fixed_base_policy": "world_fixed_joint_body0_removed",
    "door_joint_name": "RevoluteJoint",
    "door_reset_target": [0.0],
    "button_prismatic_joint_policy": "ignored_by_open_door_metric",
    "button_joint_name": "PrismaticJoint",
}
EXPECTED_NATIVE_DRYING_BOX_SCENE_TOKENS = [
    "prepend payload = @scene.usd@</World/DryingBox_01>",
    "double3 xformOp:scale = (0.001, 0.001, 0.001)",
    "delete rel physics:body0",
    'over "handle"',
    'over "button"',
    'over "RevoluteJoint"',
    "float state:angular:physics:position = 0",
]
FORBIDDEN_NATIVE_DRYING_BOX_SCENE_TOKENS = [
    'def Cube "body_link"',
    'def Cube "door_link"',
    'def Cube "handle"',
    'def Xform "obj_obj_DryingBox_01_handle" (',
]
EXPECTED_FRANKA_CAMERA_AXES = {
    "camera1": "usd",
    "camera2": "usd",
}
EXPECTED_FRANKA_CAMERA2_POSITION = [0.45, -1.1, 1.55]
EXPECTED_FRANKA_CAMERA2_ORIENTATION = [0.87184, 0.4898, 0.0, 0.0]
PROFILE_EXPECTATIONS = {
    "franka_poc": {
        "robot_type": "manip/franka/panda_hand",
        "camera_config": "configs/cameras/labutopia_franka_poc.yml",
    },
    "lift2_candidate": {
        "robot_type": "manip/lift2/R5a",
        "camera_config": "configs/cameras/fixed_camera_lift2_simbox.yml",
    },
}
CAMERA_CLEANUP_FLAGS = {
    "with_bbox2d",
    "with_bbox3d",
    "with_motion_vector",
    "with_semantic",
    "with_distance",
}
ALLOWED_METRICS = {
    "manip/labutopia/object_height_delta": {
        "obj_uid",
        "axis",
        "min_delta",
        "skip_steps",
        "succ_cnts",
    },
    "manip/labutopia/object_at_target": {
        "obj_uid",
        "target_uid",
        "xy_radius",
        "z_tolerance",
        "skip_steps",
        "succ_cnts",
    },
    "manip/labutopia/handle_displacement": {
        "obj_uid",
        "min_distance",
        "skip_steps",
        "succ_cnts",
    },
    "manip/default/check_joint_angle": {
        "articulation_obj_uid",
        "joint_name",
        "angle_deg_range",
        "skip_steps",
        "succ_cnts",
    },
}


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _task_path(relative_path: str, index_path: Path) -> Path:
    path = TASK_ROOT / relative_path
    _assert(path.exists(), f"{index_path}: indexed task path does not exist: {path}")
    return path


def _load_index(path: Path) -> list[str]:
    data = _load_json(path)
    _assert(isinstance(data, list), f"{path}: expected JSON list index")
    _assert(
        all(isinstance(item, str) for item in data),
        f"{path}: expected every index entry to be a string",
    )
    return data


def _indexed_task_yaml_paths() -> list[Path]:
    top_index = PACKAGE_ROOT / "labutopia_lab_poc.json"
    top_entries = _load_index(top_index)
    _assert(
        top_entries == EXPECTED_TOP_INDEX_ENTRIES,
        f"{top_index}: expected profile indexes {EXPECTED_TOP_INDEX_ENTRIES!r}",
    )
    profile_indexes = [_task_path(item, top_index) for item in top_entries]
    _assert(
        {path.parent.name for path in profile_indexes}
        == {"franka_poc", "lift2_candidate"},
        f"{top_index}: expected franka_poc and lift2_candidate profile indexes",
    )

    task_paths: list[Path] = []
    for index_path in profile_indexes:
        profile = index_path.parent.name
        expected_entries = EXPECTED_PROFILE_INDEX_ENTRIES[profile]
        entries = _load_index(index_path)
        _assert(
            len(entries) == len(set(entries)) == 3,
            f"{index_path}: expected 3 distinct task YAML entries",
        )
        _assert(
            entries == expected_entries,
            f"{index_path}: expected task entries {expected_entries!r}",
        )
        basenames = {Path(item).stem for item in entries}
        _assert(
            basenames == EXPECTED_TASKS,
            f"{index_path}: expected task basenames {EXPECTED_TASKS!r}",
        )
        for item in entries:
            task_path = _task_path(item, index_path)
            _assert(task_path.suffix in {".yml", ".yaml"}, f"{task_path}: expected YAML")
            task_paths.append(task_path)

    _assert(len(task_paths) == 6, f"{top_index}: expected 6 task YAMLs")
    return sorted(task_paths)


def _validate_assets_manifest() -> None:
    path = PACKAGE_ROOT / "common/assets_manifest.json"
    _assert(path.exists(), f"{path}: missing LabUtopia assets manifest")
    manifest = _load_json(path)

    _assert(
        manifest.get("scene_uid") == SCENE_UID,
        f"{path}: scene_uid must be {SCENE_UID!r}",
    )
    _assert(
        manifest.get("runtime_usd_name") == RUNTIME_USD_NAME,
        f"{path}: runtime_usd_name must be {RUNTIME_USD_NAME!r}",
    )
    overlay_root = manifest.get("overlay_root")
    _assert(
        isinstance(overlay_root, str) and overlay_root,
        f"{path}: overlay_root must be a non-empty path",
    )
    overlay_path = Path(overlay_root).expanduser()
    if not overlay_path.is_absolute():
        overlay_path = ROOT / overlay_path
    runtime_scene = overlay_path / f"{RUNTIME_USD_NAME}.usda"
    if not runtime_scene.exists():
        raise FileNotFoundError(f"{path}: runtime scene does not exist: {runtime_scene}")
    _assert(
        manifest.get("wrapper_prim_paths") == EXPECTED_WRAPPER_PRIM_PATHS,
        f"{path}: wrapper_prim_paths must preserve GenManip key stripping",
    )
    _assert(
        manifest.get("articulation_part_paths") == EXPECTED_ARTICULATION_PART_PATHS,
        f"{path}: articulation_part_paths must expose the nested drying-box handle",
    )
    contracts = manifest.get("render_object_contracts")
    _assert(
        isinstance(contracts, dict),
        f"{path}: render_object_contracts must be a mapping",
    )
    required_render_uids = {
        uid
        for required in EXPECTED_RENDER_VISIBLE_OBJECTS.values()
        for uid in required
    }
    for uid in sorted(required_render_uids):
        contract = contracts.get(uid)
        _assert(isinstance(contract, dict), f"{path}: missing render contract {uid}")
        _assert(
            contract.get("wrapper_prim_path") == EXPECTED_WRAPPER_PRIM_PATHS[uid],
            f"{path}: render contract {uid} wrapper_prim_path mismatch",
        )
        color = contract.get("display_color")
        _assert(
            isinstance(color, list)
            and len(color) == 3
            and all(isinstance(value, (int, float)) for value in color)
            and all(0.0 <= float(value) <= 1.0 for value in color)
            and color != [0.5, 0.5, 0.5],
            f"{path}: render contract {uid} must declare visible display_color",
        )
        bbox = contract.get("expected_world_bbox_lwh_m")
        _assert(
            isinstance(bbox, dict)
            and isinstance(bbox.get("min"), list)
            and isinstance(bbox.get("max"), list)
            and len(bbox["min"]) == len(bbox["max"]) == 3,
            f"{path}: render contract {uid} must declare bbox min/max",
        )
    handle_contract = contracts.get("obj_DryingBox_01_handle", {})
    _assert(
        handle_contract.get("compose_nested_transform_with_parent")
        == "obj_DryingBox_01",
        f"{path}: handle contract must compose through obj_DryingBox_01",
    )
    _assert(
        manifest.get("deterministic_lights") == EXPECTED_DETERMINISTIC_LIGHTS,
        f"{path}: deterministic_lights must declare the runtime wrapper light",
    )
    _assert(
        manifest.get("drying_box_runtime_asset") == EXPECTED_DRYING_BOX_RUNTIME_ASSET,
        f"{path}: drying_box_runtime_asset must declare native DryingBox physics override policy",
    )
    runtime_scene_text = runtime_scene.read_text(encoding="utf-8")
    _assert(
        'def DomeLight "DeterministicDomeLight"' in runtime_scene_text,
        f"{runtime_scene}: missing DeterministicDomeLight",
    )
    _assert(
        "float inputs:intensity = 1000" in runtime_scene_text,
        f"{runtime_scene}: DeterministicDomeLight must have positive fixed intensity",
    )
    _assert(
        "inputs:texture:file" not in runtime_scene_text,
        f"{runtime_scene}: DeterministicDomeLight must not depend on HDR texture",
    )
    for token in EXPECTED_NATIVE_DRYING_BOX_SCENE_TOKENS:
        _assert(
            token in runtime_scene_text,
            f"{runtime_scene}: native DryingBox_01 payload/override missing {token}",
        )
    for token in FORBIDDEN_NATIVE_DRYING_BOX_SCENE_TOKENS:
        _assert(
            token not in runtime_scene_text,
            f"{runtime_scene}: native DryingBox scene must not contain surrogate/top-level token {token}",
        )
    _assert(
        "primvars:displayColor" in runtime_scene_text,
        f"{runtime_scene}: missing task object displayColor overrides",
    )

    generated_manifest = manifest.get("generated_manifest")
    _assert(
        isinstance(generated_manifest, str) and generated_manifest,
        f"{path}: generated_manifest must be a non-empty path",
    )
    generated_path = Path(generated_manifest)
    _assert(
        generated_path.exists(),
        f"{path}: generated manifest path does not exist: {generated_path}",
    )
    generated = _load_json(generated_path)
    for common_key, generated_key in {
        "runtime_usd_name": "usd_name",
        "scene_uid": "scene_uid",
        "runtime_object_keys": "runtime_object_keys",
        "wrapper_prim_paths": "wrapper_prim_paths",
        "source_to_runtime_object_key": "source_to_runtime_object_key",
        "deterministic_lights": "deterministic_lights",
        "articulation_part_paths": "articulation_part_paths",
        "render_object_contracts": "render_object_contracts",
        "drying_box_runtime_asset": "drying_box_runtime_asset",
    }.items():
        _assert(
            manifest.get(common_key) == generated.get(generated_key),
            f"{path}: {common_key} differs from {generated_path}:{generated_key}",
        )


def _validate_task_semantics() -> None:
    path = PACKAGE_ROOT / "common/task_semantics.yml"
    data = _load_yaml(path)
    tasks = data.get("tasks") if isinstance(data, dict) else None
    _assert(isinstance(tasks, dict), f"{path}: expected top-level tasks mapping")
    _assert(set(tasks) == EXPECTED_TASKS, f"{path}: unexpected task keys: {set(tasks)}")

    open_door = tasks["level1_open_door"]
    preferred = open_door.get("metrics", {}).get("preferred")
    _assert(isinstance(preferred, dict), f"{path}: missing open_door preferred metric")
    _assert(
        preferred.get("type") == "manip/default/check_joint_angle",
        f"{path}: open_door preferred metric must be manip/default/check_joint_angle",
    )
    settings = preferred.get("sub_goal_setting")
    _assert(
        isinstance(settings, dict),
        f"{path}: open_door preferred metric missing sub_goal_setting",
    )
    for key in ("articulation_obj_uid", "joint_name", "angle_deg_range"):
        _assert(key in settings, f"{path}: open_door preferred metric missing {key}")


def _inspect_drying_box_articulation_physics(runtime_scene: Path) -> dict[str, Any]:
    from pxr import Usd, UsdGeom, UsdPhysics

    stage = Usd.Stage.Open(str(runtime_scene))
    _assert(stage is not None, f"{runtime_scene}: failed to open USD stage")
    root_path = EXPECTED_WRAPPER_PRIM_PATHS["obj_DryingBox_01"]
    root = stage.GetPrimAtPath(root_path)
    _assert(root and root.IsValid(), f"{runtime_scene}: missing {root_path}")
    root_has_articulation_api = root.HasAPI(UsdPhysics.ArticulationRootAPI)
    native_handle_path = EXPECTED_ARTICULATION_PART_PATHS["obj_DryingBox_01_handle"]
    native_handle = stage.GetPrimAtPath(native_handle_path)
    native_handle_path_exists = bool(native_handle and native_handle.IsValid())

    def _attr_value(prim: Any, attr_name: str) -> Any:
        attr = prim.GetAttribute(attr_name)
        if not attr or not attr.IsValid():
            return None
        return attr.Get()

    def _float_list(value: Any) -> list[float]:
        if value is None:
            return []
        if hasattr(value, "GetReal") and hasattr(value, "GetImaginary"):
            imaginary = value.GetImaginary()
            return [float(value.GetReal())] + [float(item) for item in imaginary]
        try:
            return [float(item) for item in value]
        except TypeError:
            return [float(value)]

    def _rounded(values: list[float]) -> list[float]:
        return [round(value, 6) for value in values]

    def _all_finite(values: list[float]) -> bool:
        return bool(values) and all(math.isfinite(value) for value in values)

    def _is_zero_principal_axes(values: list[float]) -> bool:
        return bool(values) and all(abs(value) <= 1e-9 for value in values)

    root_scale = _float_list(_attr_value(root, "xformOp:scale"))
    rounded_root_scale = _rounded(root_scale)
    non_identity_root_scale = bool(root_scale) and any(
        abs(value - 1.0) > 1e-6 for value in root_scale
    )
    root_unit_scale_ready = bool(root_scale) and all(
        abs(value - 0.001) <= 1e-6 for value in root_scale
    )

    def _world_translation(path: str) -> list[float]:
        prim = stage.GetPrimAtPath(path)
        if not prim or not prim.IsValid() or not prim.IsA(UsdGeom.Xformable):
            return []
        matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()
        )
        translation = matrix.ExtractTranslation()
        return _rounded([float(translation[0]), float(translation[1]), float(translation[2])])

    task_part_world_positions = {
        "root": _world_translation(root_path),
        "door": _world_translation(f"{root_path}/body/Group/door/mesh"),
        "handle": _world_translation(f"{root_path}/handle/mesh"),
    }

    def _inside_workspace(position: list[float]) -> bool:
        if len(position) != 3:
            return False
        x, y, z = position
        return 0.0 <= x <= 1.2 and -0.5 <= y <= 0.8 and 0.5 <= z <= 1.4

    task_visible_workspace_ready = all(
        _inside_workspace(task_part_world_positions[key])
        for key in ("root", "door", "handle")
    )

    rigid_link_paths: list[str] = []
    missing_mass_links: list[str] = []
    zero_mass_links: list[str] = []
    missing_inertia_links: list[str] = []
    zero_inertia_links: list[str] = []
    invalid_center_of_mass_links: list[str] = []
    invalid_principal_axes_links: list[str] = []
    for prim in Usd.PrimRange(root):
        if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            continue
        path = str(prim.GetPath())
        rigid_link_paths.append(path)
        mass_api = UsdPhysics.MassAPI(prim)
        mass_attr = mass_api.GetMassAttr()
        mass = mass_attr.Get() if mass_attr and mass_attr.IsValid() else None
        if mass is None:
            missing_mass_links.append(path)
        elif not math.isfinite(float(mass)) or float(mass) <= 0.0:
            zero_mass_links.append(path)
        inertia_attr = mass_api.GetDiagonalInertiaAttr()
        inertia = inertia_attr.Get() if inertia_attr and inertia_attr.IsValid() else None
        if inertia is None:
            missing_inertia_links.append(path)
        elif any(
            not math.isfinite(float(value)) or float(value) <= 0.0
            for value in inertia
        ):
            zero_inertia_links.append(path)
        center_of_mass = _float_list(_attr_value(prim, "physics:centerOfMass"))
        if not center_of_mass or not _all_finite(center_of_mass):
            invalid_center_of_mass_links.append(path)
        principal_axes = _float_list(_attr_value(prim, "physics:principalAxes"))
        if (
            not principal_axes
            or not _all_finite(principal_axes)
            or _is_zero_principal_axes(principal_axes)
        ):
            invalid_principal_axes_links.append(path)

    duplicate_rigid_link_names: dict[str, int] = {}

    expected_joint_types = {
        "PhysicsFixedJoint",
        "PhysicsRevoluteJoint",
        "PhysicsPrismaticJoint",
    }
    unexpected_joint_types: list[str] = []
    invalid_joint_body_targets: list[dict[str, str]] = []
    world_fixed_base_joint_paths: list[str] = []
    door_revolute_joint_paths: list[str] = []
    door_reset_positions: dict[str, float] = {}
    ignored_prismatic_joint_paths: list[str] = []
    joint_paths: list[str] = []
    fixed_base_body1_paths = {
        f"{root_path}/body_link",
        f"{root_path}/body/body/mesh",
    }
    button_prismatic_joint_path = f"{root_path}/button/PrismaticJoint"
    for prim in Usd.PrimRange(root):
        type_name = prim.GetTypeName()
        if "Joint" not in type_name:
            continue
        path = str(prim.GetPath())
        joint_paths.append(path)
        if type_name == "PhysicsPrismaticJoint" and path == button_prismatic_joint_path:
            ignored_prismatic_joint_paths.append(path)
        elif type_name not in expected_joint_types and type_name not in unexpected_joint_types:
            unexpected_joint_types.append(type_name)
        elif type_name == "PhysicsPrismaticJoint" and type_name not in unexpected_joint_types:
            unexpected_joint_types.append(type_name)
        for rel_name in ("physics:body0", "physics:body1"):
            relationship = prim.GetRelationship(rel_name)
            if not relationship:
                continue
            for target in relationship.GetTargets():
                target_prim = stage.GetPrimAtPath(target)
                if not target_prim or not target_prim.HasAPI(UsdPhysics.RigidBodyAPI):
                    invalid_joint_body_targets.append(
                        {
                            "joint_path": path,
                            "relationship": rel_name,
                            "target": str(target),
                        }
                    )
        if type_name == "PhysicsFixedJoint":
            body0_rel = prim.GetRelationship("physics:body0")
            body1_rel = prim.GetRelationship("physics:body1")
            body0_targets = body0_rel.GetTargets() if body0_rel else []
            body1_targets = body1_rel.GetTargets() if body1_rel else []
            if (
                not body0_targets
                and len(body1_targets) == 1
                and str(body1_targets[0]) in fixed_base_body1_paths
            ):
                world_fixed_base_joint_paths.append(path)
        if type_name == "PhysicsRevoluteJoint" and Path(path).name == "RevoluteJoint":
            door_revolute_joint_paths.append(path)
            reset_attr = prim.GetAttribute("state:angular:physics:position")
            if reset_attr and reset_attr.IsValid() and reset_attr.HasAuthoredValueOpinion():
                reset_value = reset_attr.Get()
                if reset_value is not None:
                    door_reset_positions["RevoluteJoint"] = float(reset_value)

    runtime_topology_ready = not any(
        [
            not root_has_articulation_api,
            not native_handle_path_exists,
            not root_unit_scale_ready,
            not task_visible_workspace_ready,
            duplicate_rigid_link_names,
            missing_mass_links,
            missing_inertia_links,
            zero_mass_links,
            zero_inertia_links,
            invalid_center_of_mass_links,
            invalid_principal_axes_links,
            invalid_joint_body_targets,
            unexpected_joint_types,
            not world_fixed_base_joint_paths,
            not door_revolute_joint_paths,
            door_reset_positions.get("RevoluteJoint") != 0.0,
            ignored_prismatic_joint_paths != [button_prismatic_joint_path],
        ]
    )

    return {
        "root_path": root_path,
        "root_has_articulation_api": root_has_articulation_api,
        "native_handle_path_exists": native_handle_path_exists,
        "root_scale": rounded_root_scale,
        "non_identity_root_scale": non_identity_root_scale,
        "root_unit_scale_ready": root_unit_scale_ready,
        "task_part_world_positions": task_part_world_positions,
        "task_visible_workspace_ready": task_visible_workspace_ready,
        "rigid_link_paths": rigid_link_paths,
        "duplicate_rigid_link_names": duplicate_rigid_link_names,
        "missing_mass_links": missing_mass_links,
        "zero_mass_links": zero_mass_links,
        "missing_inertia_links": missing_inertia_links,
        "zero_inertia_links": zero_inertia_links,
        "invalid_center_of_mass_links": invalid_center_of_mass_links,
        "invalid_principal_axes_links": invalid_principal_axes_links,
        "joint_paths": joint_paths,
        "world_fixed_base_joint_paths": world_fixed_base_joint_paths,
        "door_revolute_joint_paths": door_revolute_joint_paths,
        "door_reset_positions": door_reset_positions,
        "ignored_prismatic_joint_paths": ignored_prismatic_joint_paths,
        "invalid_joint_body_targets": invalid_joint_body_targets,
        "unexpected_joint_types": sorted(unexpected_joint_types),
        "runtime_topology_ready": runtime_topology_ready,
        "sanitized_for_physx": not any(
            [missing_mass_links, zero_mass_links, missing_inertia_links, zero_inertia_links]
        ),
    }


def _validate_camera_configs() -> None:
    camera_config_paths: dict[str, list[tuple[str, str | None]]] = {
        "franka_poc": [("base", None)]
        + [
            (config_path, task_name)
            for task_name, config_path in EXPECTED_FRANKA_TASK_CAMERA_CONFIGS.items()
        ],
        "lift2_candidate": [
            (PROFILE_EXPECTATIONS["lift2_candidate"]["camera_config"], None)
        ],
    }
    for profile, path_items in camera_config_paths.items():
        expected = PROFILE_EXPECTATIONS[profile]
        for config_path, task_name in path_items:
            path = ROOT / (
                expected["camera_config"] if config_path == "base" else config_path
            )
            _validate_camera_config_file(path, profile, task_name)


def _validate_camera_config_file(path: Path, profile: str, task_name: str | None) -> None:
    data = _load_yaml(path)
    _assert(isinstance(data, dict), f"{path}: expected camera mapping")
    if profile == "franka_poc":
        _assert(
            set(EXPECTED_FRANKA_CAMERA_AXES).issubset(data),
            f"{path}: franka_poc cameras must include {sorted(EXPECTED_FRANKA_CAMERA_AXES)}",
        )
    for camera_name, camera in data.items():
        _assert(
            isinstance(camera, dict),
            f"{path}:{camera_name}: expected camera settings mapping",
        )
        missing = CAMERA_CLEANUP_FLAGS - set(camera)
        _assert(
            not missing,
            f"{path}:{camera_name}: {profile} camera missing cleanup flags {missing}",
        )
        if profile == "franka_poc":
            expected_axes = EXPECTED_FRANKA_CAMERA_AXES.get(camera_name)
            if expected_axes is not None:
                _assert(
                    camera.get("camera_axes") == expected_axes,
                    f"{path}:{camera_name}: camera_axes must remain {expected_axes!r}",
                )
    if profile == "franka_poc":
        camera2 = data.get("camera2", {})
        if task_name is None:
            position = camera2.get("position")
            _assert(
                isinstance(position, list) and len(position) == 3,
                f"{path}:camera2 position must be a 3-vector",
            )
            _assert(
                all(
                    abs(float(actual) - expected) < 1e-6
                    for actual, expected in zip(position, EXPECTED_FRANKA_CAMERA2_POSITION)
                ),
                f"{path}:camera2 position must remain {EXPECTED_FRANKA_CAMERA2_POSITION!r}",
            )
            orientation = camera2.get("orientation")
            _assert(
                isinstance(orientation, list) and len(orientation) == 4,
                f"{path}:camera2 orientation must be a quaternion",
            )
            _assert(
                all(
                    abs(float(actual) - expected) < 1e-6
                    for actual, expected in zip(
                        orientation,
                        EXPECTED_FRANKA_CAMERA2_ORIENTATION,
                    )
                ),
                f"{path}:camera2 orientation must remain {EXPECTED_FRANKA_CAMERA2_ORIENTATION!r}",
            )
        else:
            contract = EXPECTED_FRANKA_TASK_CAMERA2_CONTRACTS[task_name]
            for key, expected_value in contract.items():
                _assert(
                    camera2.get(key) == expected_value,
                    f"{path}:camera2 {key} must be {expected_value!r}",
                )
            _assert(
                camera2.get("task_view") == task_name,
                f"{path}:camera2 task_view must be {task_name!r}",
            )


def _walk_goal_dicts(value: Any, path: Path) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        results: list[dict[str, Any]] = []
        for item in value:
            results.extend(_walk_goal_dicts(item, path))
        return results
    raise AssertionError(f"{path}: goal contains unsupported value {value!r}")


def _validate_metric(metric: dict[str, Any], path: Path) -> None:
    _assert("sub_goal_setting" not in metric, f"{path}: runtime goal uses sub_goal_setting")
    metric_type = metric.get("type")
    _assert(
        metric_type in ALLOWED_METRICS,
        f"{path}: unsupported LabUtopia metric type {metric_type!r}",
    )
    missing = ALLOWED_METRICS[metric_type] - set(metric)
    _assert(not missing, f"{path}: metric {metric_type} missing top-level params {missing}")


def _task_leaf_name(task_name: str) -> str:
    return task_name.rsplit("/", 1)[-1]


def _validate_render_validation(
    cfg: dict[str, Any], path: Path, camera_names: set[str]
) -> None:
    task_name = str(cfg.get("task_name"))
    leaf_name = _task_leaf_name(task_name)
    if path.parent.name != "franka_poc":
        return
    expected_objects = EXPECTED_RENDER_VISIBLE_OBJECTS.get(leaf_name)
    _assert(
        expected_objects is not None,
        f"{path}: unexpected Franka task leaf {leaf_name!r}",
    )
    validation = cfg.get("labutopia_render_validation")
    _assert(
        isinstance(validation, dict),
        f"{path}: missing labutopia_render_validation",
    )
    _assert(
        validation.get("schema_version") == 1,
        f"{path}: labutopia_render_validation.schema_version must be 1",
    )
    _assert(
        validation.get("primary_camera") == "camera2",
        f"{path}: primary_camera must be camera2",
    )
    expected_camera_config = EXPECTED_FRANKA_TASK_CAMERA_CONFIGS[leaf_name]
    _assert(
        cfg.get("domain_randomization", {})
        .get("cameras", {})
        .get("config_path")
        == expected_camera_config,
        f"{path}: franka_poc camera config must be {expected_camera_config!r}",
    )
    _assert(
        validation.get("evidence_camera_config") == expected_camera_config,
        f"{path}: evidence_camera_config must be {expected_camera_config!r}",
    )
    required_cameras = validation.get("required_camera_names")
    _assert(
        isinstance(required_cameras, list)
        and set(required_cameras).issubset(camera_names),
        f"{path}: required_camera_names must exist in camera config",
    )
    _assert(
        validation.get("required_visible_objects") == expected_objects,
        f"{path}: required_visible_objects must be {expected_objects!r}",
    )
    expected_hidden_objects = EXPECTED_HIDDEN_NON_TASK_OBJECTS[leaf_name]
    _assert(
        validation.get("hidden_non_task_objects") == expected_hidden_objects,
        f"{path}: hidden_non_task_objects must be {expected_hidden_objects!r}",
    )
    active_rules = [
        item
        for item in cfg.get("preprocess_config", [])
        if isinstance(item, dict) and item.get("type") == "set_object_active"
    ]
    _assert(
        active_rules
        == [
            {
                "type": "set_object_active",
                "config": {"active": False, "uids": expected_hidden_objects},
            }
        ],
        f"{path}: preprocess_config must hide exactly {expected_hidden_objects!r}",
    )
    thresholds = validation.get("object_pixel_thresholds")
    expected_thresholds = EXPECTED_RENDER_PIXEL_THRESHOLDS[leaf_name]
    _assert(
        isinstance(thresholds, dict),
        f"{path}: missing object_pixel_thresholds",
    )
    _assert(
        set(thresholds) == set(expected_thresholds),
        f"{path}: object_pixel_thresholds must cover {sorted(expected_thresholds)}",
    )
    for uid, expected in expected_thresholds.items():
        actual = thresholds.get(uid)
        _assert(isinstance(actual, dict), f"{path}: {uid} threshold must be a mapping")
        for key, value in expected.items():
            _assert(
                actual.get(key) == value,
                f"{path}: {uid}.{key} must be {value!r}",
            )
    _assert(
        validation.get("evidence_policy") == {"direct_render": False},
        f"{path}: evidence_policy must forbid direct render evidence",
    )
    rejection_rules = validation.get("reject_frame_if")
    _assert(
        isinstance(rejection_rules, list)
        and EXPECTED_RENDER_REJECTIONS.issubset(set(rejection_rules)),
        f"{path}: reject_frame_if missing required rules",
    )


def _validate_open_door_articulation_contract(cfg: dict[str, Any], path: Path) -> None:
    if _task_leaf_name(str(cfg.get("task_name"))) != "level1_open_door":
        return
    object_config = cfg.get("object_config")
    _assert(isinstance(object_config, dict), f"{path}: object_config must be a mapping")
    drying_box = object_config.get("obj_DryingBox_01")
    _assert(
        isinstance(drying_box, dict),
        f"{path}: open_door must configure obj_DryingBox_01 articulation",
    )
    _assert(
        drying_box.get("type") == "existed_object",
        f"{path}: obj_DryingBox_01 must be an existed_object",
    )
    _assert(
        drying_box.get("uid_list") == ["obj_DryingBox_01"],
        f"{path}: obj_DryingBox_01 uid_list mismatch",
    )
    _assert(
        drying_box.get("is_articulated") is True,
        f"{path}: obj_DryingBox_01 must be articulated",
    )
    _assert(
        drying_box.get("target_positions") == [0.0],
        f"{path}: obj_DryingBox_01 must start closed with target_positions [0.0]",
    )
    articulation_info = drying_box.get("articulation_info")
    _assert(
        isinstance(articulation_info, dict),
        f"{path}: obj_DryingBox_01 missing articulation_info",
    )
    _assert(
        articulation_info.get("is_articulated") is True,
        f"{path}: articulation_info.is_articulated must be true",
    )
    _assert(
        articulation_info.get("part", {}).get("handle") == "/handle",
        f"{path}: articulation_info.part.handle must point to /handle",
    )
    goals = cfg.get("generation_config", {}).get("goal")
    metrics = _walk_goal_dicts(goals, path)
    door_metrics = [
        metric
        for metric in metrics
        if metric.get("type") == "manip/default/check_joint_angle"
        and metric.get("articulation_obj_uid") == "obj_DryingBox_01"
    ]
    _assert(
        len(door_metrics) == 1,
        f"{path}: open_door must bind exactly one DryingBox joint-angle metric",
    )
    _assert(
        door_metrics[0].get("joint_name") == "RevoluteJoint",
        f"{path}: open_door metric must bind native RevoluteJoint",
    )
    if path.parent.name == "franka_poc":
        policy = cfg.get("labutopia_native_drying_box")
        _assert(
            isinstance(policy, dict),
            f"{path}: missing labutopia_native_drying_box policy",
        )
        expected_policy = {
            "strategy": "native_complex_with_additive_physics_override",
            "door_joint_name": "RevoluteJoint",
            "handle_part_path": "/handle",
            "button_joint_name": "PrismaticJoint",
            "button_prismatic_joint_policy": "ignored_by_open_door_metric",
        }
        _assert(
            policy == expected_policy,
            f"{path}: native DryingBox metric policy must be {expected_policy!r}",
        )


def _validate_runtime_task(path: Path) -> None:
    sys.path.insert(0, str(ROOT))
    from genmanip.core.scene.scene_config import SceneConfig
    from genmanip.utils.standalone.version_utils import process_archived_config

    data = _load_yaml(path)
    configs = data.get("evaluation_configs") if isinstance(data, dict) else None
    _assert(isinstance(configs, list), f"{path}: expected evaluation_configs list")
    _assert(len(configs) == 1, f"{path}: expected exactly one evaluation_configs item")
    cfg = configs[0]
    _assert(isinstance(cfg, dict), f"{path}: evaluation config must be a mapping")

    runtime_cfg = process_archived_config(copy.deepcopy(cfg))
    SceneConfig(**runtime_cfg)
    _assert(cfg.get("num_test") is not None, f"{path}: missing num_test")
    task_name = cfg.get("task_name")
    _assert(
        isinstance(task_name, str) and task_name.startswith(TASK_PREFIX),
        f"{path}: task_name must start with {TASK_PREFIX!r}",
    )
    _assert(cfg.get("table_uid") == "table", f"{path}: table_uid must be 'table'")

    profile = path.parent.name
    expected = PROFILE_EXPECTATIONS.get(profile)
    _assert(expected is not None, f"{path}: unknown LabUtopia task profile {profile!r}")
    robots = cfg.get("robots")
    _assert(isinstance(robots, list) and robots, f"{path}: robots must be non-empty")
    _assert(
        robots[0].get("type") == expected["robot_type"],
        f"{path}: {profile} robot type must be {expected['robot_type']!r}",
    )
    camera = cfg.get("domain_randomization", {}).get("cameras", {})
    expected_camera_config = (
        EXPECTED_FRANKA_TASK_CAMERA_CONFIGS[_task_leaf_name(str(task_name))]
        if profile == "franka_poc"
        else expected["camera_config"]
    )
    _assert(
        camera.get("config_path") == expected_camera_config,
        f"{path}: {profile} camera config must be {expected_camera_config!r}",
    )
    camera_path = ROOT / expected_camera_config
    camera_names = set(_load_yaml(camera_path))
    _validate_render_validation(cfg, path, camera_names)
    _validate_open_door_articulation_contract(cfg, path)

    generation_config = cfg.get("generation_config")
    _assert(
        isinstance(generation_config, dict),
        f"{path}: generation_config must be a mapping",
    )
    _assert(
        "articulation" in generation_config,
        f"{path}: generation_config.articulation is required by runtime config upgrade",
    )
    _assert(
        isinstance(generation_config["articulation"], (list, dict)),
        f"{path}: generation_config.articulation must be a list or mapping",
    )

    goals = generation_config.get("goal")
    _assert(goals is not None, f"{path}: missing generation_config.goal")
    metrics = _walk_goal_dicts(goals, path)
    _assert(metrics, f"{path}: generation_config.goal contains no metric dicts")
    for metric in metrics:
        _validate_metric(metric, path)


def _validate_metrics_manager_lazy_registration() -> None:
    sys.path.insert(0, str(ROOT))
    for module_name in list(sys.modules):
        if module_name == "genmanip.extensions.metrics" or module_name.startswith(
            "genmanip.extensions.metrics."
        ):
            del sys.modules[module_name]

    from genmanip.core.metrics.metrics_manager import MetricsManager

    with contextlib.redirect_stdout(io.StringIO()):
        manager = MetricsManager(
            [
                [
                    [
                        {
                            "type": "manip/labutopia/object_height_delta",
                            "sub_goal_setting": {
                                "obj_uid": "obj_conical_bottle02",
                                "axis": "z",
                                "min_delta": 0.1,
                            },
                        }
                    ]
                ]
            ]
        )
    metric = manager.cur_union_metric[0][0]
    _assert(
        metric.__class__.__name__ == "ObjectHeightDelta",
        "MetricsManager did not lazily register LabUtopia object_height_delta",
    )
    _assert(
        "genmanip.extensions.metrics" not in sys.modules,
        "MetricsManager imported the full genmanip.extensions.metrics package",
    )


def validate_task_package() -> None:
    _validate_assets_manifest()
    manifest = _load_json(PACKAGE_ROOT / "common/assets_manifest.json")
    runtime_scene = (
        Path(manifest["overlay_root"]) / f"{manifest['runtime_usd_name']}.usda"
    )
    physics_report = _inspect_drying_box_articulation_physics(runtime_scene)
    _assert(
        physics_report["sanitized_for_physx"],
        f"{runtime_scene}: DryingBox articulation physics is not sanitized: {physics_report}",
    )
    _assert(
        physics_report["runtime_topology_ready"],
        f"{runtime_scene}: DryingBox articulation topology is not runtime-ready: {physics_report}",
    )
    _validate_task_semantics()
    _validate_camera_configs()
    for path in _indexed_task_yaml_paths():
        _validate_runtime_task(path)
    _validate_metrics_manager_lazy_registration()


def main() -> None:
    validate_task_package()
    print("LabUtopia task package validation OK")


if __name__ == "__main__":
    main()
