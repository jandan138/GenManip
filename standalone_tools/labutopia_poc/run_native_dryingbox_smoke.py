#!/usr/bin/env python3
"""Native-only Isaac smoke for the LabUtopia DryingBox asset."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LABUTOPIA_ROOT = Path("/cpfs/shared/simulation/zhuzihou/dev/LabUtopia")
DEFAULT_SOURCE_SCENE_RELATIVE = Path("assets/chemistry_lab/lab_001/lab_001.usd")
DEFAULT_SOURCE_PRIM_PATH = "/World/DryingBox_01"
DEFAULT_SMOKE_PRIM_PATH = "/World/DryingBox_01"
DEFAULT_HANDLE_PRIM_PATH = "/World/DryingBox_01/handle/mesh"
DEFAULT_STEP_COUNT = 120
DEFAULT_TRANSLATION_DRIFT_TOLERANCE_M = 1e-4
DEFAULT_ROTATION_DRIFT_TOLERANCE_DEG = 1e-3
DEFAULT_NON_DOOR_DOF_DRIFT_TOLERANCE = 1e-4
DEFAULT_SOURCE_DOOR_JOINT_LIMITS_DEG = [0.0, 120.0]
DEFAULT_MATERIAL_FALLBACK_OVERLAY_POLICY = (
    "stage2_readability_displayColor_not_native_material_closure"
)
DEFAULT_MATERIAL_FALLBACK_DISPLAY_COLORS = {
    "/World/DryingBox_01/Group/_900_1": [0.12, 0.28, 0.95],
    "/World/DryingBox_01/button": [1.0, 0.48, 0.04],
    "/World/DryingBox_01/panel": [0.88, 0.92, 0.96],
}
REQUIRED_SMOKE_KEYS = {
    "stage2_status",
    "stage2_passed",
    "stage2_validation_errors",
    "stage_path",
    "source_prim_path",
    "smoke_prim_path",
    "handle_prim_path",
    "native_stage_mode",
    "used_ebench_wrapper",
    "used_franka_shortcut",
    "world_child_discovery_status",
    "world_child_discovery_method",
    "active_world_children",
    "inactive_world_children",
    "active_non_target_world_children",
    "active_non_target_world_child_count",
    "joint_names",
    "initial_joint_positions",
    "post_step_joint_positions",
    "door_joint_path",
    "door_joint_index",
    "source_door_joint_limits_deg",
    "source_door_joint_limits_source",
    "button_joint_path",
    "button_joint_index",
    "root_pose",
    "post_step_root_pose",
    "handle_pose",
    "post_step_handle_pose",
    "root_pose_finite",
    "handle_pose_finite",
    "runtime_physics_stable",
    "physx_warnings",
    "physx_warning_scope",
    "step_count",
    "step_trace",
    "finite_trace",
    "max_root_translation_drift_m",
    "root_translation_drift_tolerance_m",
    "max_root_rotation_drift_deg",
    "root_rotation_drift_tolerance_deg",
    "max_handle_translation_drift_m",
    "handle_translation_drift_tolerance_m",
    "door_joint_angle_min_deg",
    "door_joint_angle_max_deg",
    "door_joint_angle_within_limits",
    "button_joint_position_min_m",
    "button_joint_position_max_m",
    "non_door_dof_drift_tolerance",
    "non_door_dof_drift_within_tolerance",
    "physx_warning_allowlist",
    "physx_warning_denylist",
    "unclassified_physx_warnings",
    "material_runtime_notes",
}


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    if hasattr(value, "GetReal") and hasattr(value, "GetImaginary"):
        imaginary = _jsonable(value.GetImaginary())
        if not isinstance(imaginary, list):
            imaginary = [imaginary]
        return [_jsonable(value.GetReal()), *imaginary]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    try:
        return [_jsonable(item) for item in value]
    except TypeError:
        return str(value)


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _finite_number_list(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    return all(_is_finite_number(item) for item in value)


def _flatten_numbers(value: Any) -> list[Any]:
    converted = _jsonable(value)
    if isinstance(converted, list):
        flattened: list[Any] = []
        for item in converted:
            flattened.extend(_flatten_numbers(item))
        return flattened
    return [converted]


def _pose_is_finite(pose: dict[str, Any] | None) -> bool:
    if not pose:
        return False
    values = _flatten_numbers([pose.get("position"), pose.get("orientation")])
    return bool(values) and all(_is_finite_number(item) for item in values)


def _finite_float_list(value: Any, length: int | None = None) -> list[float] | None:
    if not isinstance(value, list):
        return None
    if length is not None and len(value) < length:
        return None
    result: list[float] = []
    for item in value[:length]:
        if not _is_finite_number(item):
            return None
        result.append(float(item))
    return result


def _pose_position(pose: dict[str, Any] | None) -> list[float] | None:
    if not pose:
        return None
    return _finite_float_list(pose.get("position"), 3)


def _pose_orientation(pose: dict[str, Any] | None) -> list[float] | None:
    if not pose:
        return None
    return _finite_float_list(pose.get("orientation"), 4)


def _translation_distance_m(
    first: dict[str, Any] | None,
    second: dict[str, Any] | None,
) -> float | None:
    first_position = _pose_position(first)
    second_position = _pose_position(second)
    if first_position is None or second_position is None:
        return None
    return math.sqrt(
        sum((second_position[index] - first_position[index]) ** 2 for index in range(3))
    )


def _rotation_delta_deg(
    first: dict[str, Any] | None,
    second: dict[str, Any] | None,
) -> float | None:
    first_quat = _pose_orientation(first)
    second_quat = _pose_orientation(second)
    if first_quat is None or second_quat is None:
        return None
    first_norm = math.sqrt(sum(item * item for item in first_quat))
    second_norm = math.sqrt(sum(item * item for item in second_quat))
    if first_norm == 0 or second_norm == 0:
        return None
    dot = sum(
        (first_quat[index] / first_norm) * (second_quat[index] / second_norm)
        for index in range(4)
    )
    dot = max(-1.0, min(1.0, abs(dot)))
    return math.degrees(2.0 * math.acos(dot))


def _first_matching_index(names: list[str], needles: tuple[str, ...]) -> int | None:
    lowered = [name.lower() for name in names]
    for index, name in enumerate(lowered):
        if any(needle in name for needle in needles):
            return index
    return None


def _joint_path_for_name(smoke_prim_path: str, joint_name: str | None) -> str | None:
    if not joint_name:
        return None
    if joint_name.startswith("/"):
        return joint_name
    cleaned = joint_name.strip("/")
    if not cleaned:
        return None
    if "/" in cleaned:
        return f"{smoke_prim_path.rstrip('/')}/{cleaned}"
    if cleaned.lower() == "prismaticjoint":
        return f"{smoke_prim_path.rstrip('/')}/button/{cleaned}"
    return f"{smoke_prim_path.rstrip('/')}/{cleaned}"


def _joint_path_for_index(
    smoke_prim_path: str,
    joint_names: list[str],
    index: int | None,
) -> str | None:
    if index is None or index < 0 or index >= len(joint_names):
        return None
    return _joint_path_for_name(smoke_prim_path, joint_names[index])


def _joint_value(
    joint_names: list[str],
    joint_positions: list[Any],
    needles: tuple[str, ...],
) -> float | None:
    index = _first_matching_index(joint_names, needles)
    if index is None or index >= len(joint_positions):
        return None
    value = joint_positions[index]
    if not _is_finite_number(value):
        return None
    return float(value)


def _trace_record(
    *,
    step: int,
    root: Any,
    handle: Any,
    joint_names: list[str],
    joint_positions: list[Any],
) -> dict[str, Any]:
    root_pose = _pose_from_prim(root)
    handle_pose = _pose_from_prim(handle)
    door_position = _joint_value(joint_names, joint_positions, ("door", "revolute"))
    button_position = _joint_value(joint_names, joint_positions, ("button", "prismatic"))
    return {
        "step": step,
        "root_pose": root_pose,
        "handle_pose": handle_pose,
        "joint_positions": joint_positions,
        "joint_positions_finite": _finite_number_list(joint_positions),
        "root_pose_finite": _pose_is_finite(root_pose),
        "handle_pose_finite": _pose_is_finite(handle_pose),
        "door_joint_angle_deg": (
            math.degrees(door_position) if door_position is not None else None
        ),
        "button_joint_position_m": button_position,
    }


def _max_present(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return max(present)


def _min_present(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return min(present)


def _trace_metrics(
    *,
    initial_root_pose: dict[str, Any] | None,
    initial_handle_pose: dict[str, Any] | None,
    initial_joint_positions: list[Any],
    joint_names: list[str],
    step_trace: list[dict[str, Any]],
    source_door_joint_limits_deg: list[float] | None = None,
) -> dict[str, Any]:
    root_translation_drifts = [
        _translation_distance_m(initial_root_pose, record.get("root_pose"))
        for record in step_trace
    ]
    root_rotation_drifts = [
        _rotation_delta_deg(initial_root_pose, record.get("root_pose"))
        for record in step_trace
    ]
    handle_translation_drifts = [
        _translation_distance_m(initial_handle_pose, record.get("handle_pose"))
        for record in step_trace
    ]
    door_angles = [record.get("door_joint_angle_deg") for record in step_trace]
    button_positions = [record.get("button_joint_position_m") for record in step_trace]
    door_min = _min_present(door_angles)
    door_max = _max_present(door_angles)
    limits = source_door_joint_limits_deg or DEFAULT_SOURCE_DOOR_JOINT_LIMITS_DEG
    source_min, source_max = limits
    door_within_limits = bool(
        door_min is not None
        and door_max is not None
        and door_min >= source_min - DEFAULT_ROTATION_DRIFT_TOLERANCE_DEG
        and door_max <= source_max + DEFAULT_ROTATION_DRIFT_TOLERANCE_DEG
    )

    door_index = _first_matching_index(joint_names, ("door", "revolute"))
    non_door_drift_within_tolerance = True
    for record in step_trace:
        positions = record.get("joint_positions")
        if not isinstance(positions, list):
            non_door_drift_within_tolerance = False
            break
        for index, initial_value in enumerate(initial_joint_positions):
            if index == door_index:
                continue
            if index >= len(positions) or not (
                _is_finite_number(initial_value) and _is_finite_number(positions[index])
            ):
                non_door_drift_within_tolerance = False
                break
            if (
                abs(float(positions[index]) - float(initial_value))
                > DEFAULT_NON_DOOR_DOF_DRIFT_TOLERANCE
            ):
                non_door_drift_within_tolerance = False
                break
        if not non_door_drift_within_tolerance:
            break

    return {
        "finite_trace": all(
            bool(record.get("root_pose_finite"))
            and bool(record.get("handle_pose_finite"))
            and bool(record.get("joint_positions_finite"))
            for record in step_trace
        ),
        "max_root_translation_drift_m": _max_present(root_translation_drifts),
        "root_translation_drift_tolerance_m": DEFAULT_TRANSLATION_DRIFT_TOLERANCE_M,
        "max_root_rotation_drift_deg": _max_present(root_rotation_drifts),
        "root_rotation_drift_tolerance_deg": DEFAULT_ROTATION_DRIFT_TOLERANCE_DEG,
        "max_handle_translation_drift_m": _max_present(handle_translation_drifts),
        "handle_translation_drift_tolerance_m": DEFAULT_TRANSLATION_DRIFT_TOLERANCE_M,
        "door_joint_angle_min_deg": door_min,
        "door_joint_angle_max_deg": door_max,
        "source_door_joint_limits_deg": list(limits),
        "door_joint_angle_within_limits": door_within_limits,
        "button_joint_position_min_m": _min_present(button_positions),
        "button_joint_position_max_m": _max_present(button_positions),
        "non_door_dof_drift_tolerance": DEFAULT_NON_DOOR_DOF_DRIFT_TOLERANCE,
        "non_door_dof_drift_within_tolerance": non_door_drift_within_tolerance,
    }


def _empty_material_runtime_notes() -> dict[str, Any]:
    return {
        "material_collection_ok": False,
        "material_runtime_status": "not_collected",
        "world_looks_present": False,
        "task_mesh_count": 0,
        "bound_task_mesh_count": 0,
        "unbound_task_mesh_count": 0,
        "unbound_task_mesh_paths": [],
        "empty_authored_binding_count": 0,
        "empty_authored_binding_paths": [],
        "unresolved_binding_target_count": 0,
        "unresolved_binding_target_paths": [],
        "unresolved_task_material_count": 0,
        "used_material_count": 0,
        "used_material_paths": [],
        "remote_material_dependency_count": 0,
        "remote_material_dependency_paths": [],
        "material_binding_gap_count": 0,
        "material_binding_gap_paths": [],
        "material_binding_gap_details": [],
        "material_binding_gap_policy": "warning_requires_readability_evidence",
        "material_binding_gap_readability_status": "not_required",
        "fallback_status": "not_collected",
        "dryingbox_material_compiler_warnings": [],
        "material_compiler_warning_count": 0,
        "collection_error": None,
    }


def _attr_json_value(attr: Any) -> Any:
    if not attr:
        return None
    try:
        return _jsonable(attr.Get())
    except Exception:
        return None


def _display_color_report(prim: Any) -> dict[str, Any]:
    attr = prim.GetAttribute("primvars:displayColor")
    value = _attr_json_value(attr)
    authored = bool(attr and attr.HasAuthoredValueOpinion())
    report = {
        "authored": authored,
        "value": value,
        "fallback_status": "absent",
    }
    if value is None:
        return report
    colors = value if isinstance(value, list) else [value]
    flattened: list[float] = []
    for color in colors:
        if isinstance(color, list):
            flattened.extend(
                float(channel)
                for channel in color
                if isinstance(channel, (int, float)) and not isinstance(channel, bool)
            )
        elif isinstance(color, (int, float)) and not isinstance(color, bool):
            flattened.append(float(color))
    if not flattened:
        report["fallback_status"] = "invalid"
    elif max(abs(channel) for channel in flattened) <= 0.05:
        report["fallback_status"] = "black_or_low_contrast"
    else:
        report["fallback_status"] = "usable"
    return report


def _material_gap_detail(prim: Any, gap_type: str, bindings: list[dict[str, Any]]) -> dict[str, Any]:
    display_color = _display_color_report(prim)
    readability_status = (
        "accepted" if display_color["fallback_status"] == "usable" else "missing"
    )
    return {
        "mesh_path": str(prim.GetPath()),
        "gap_type": gap_type,
        "bindings": bindings,
        "displayColor": display_color,
        "readability_evidence_status": readability_status,
    }


def _authored_material_bindings(prim: Any, stop_path: str) -> list[dict[str, Any]]:
    try:
        from pxr import Usd  # type: ignore
    except Exception:
        Usd = None  # type: ignore[assignment]
    bindings: list[dict[str, Any]] = []
    current = prim
    while current and current.IsValid():
        if not str(current.GetPath()).startswith(stop_path):
            break
        for relationship in current.GetRelationships():
            name = relationship.GetName()
            if name != "material:binding" and not name.startswith("material:binding:"):
                continue
            try:
                property_stack = relationship.GetPropertyStack()
            except TypeError:
                if Usd is None:
                    property_stack = []
                else:
                    property_stack = relationship.GetPropertyStack(Usd.TimeCode.Default())
            targets = [str(target) for target in relationship.GetTargets()]
            if relationship.HasAuthoredTargets() or targets or property_stack:
                bindings.append(
                    {
                        "prim_path": str(current.GetPath()),
                        "relationship": name,
                        "targets": targets,
                    }
                )
        current = current.GetParent()
    return bindings


def _remote_asset_path(value: Any) -> str | None:
    authored_path = getattr(value, "authoredPath", None)
    if authored_path:
        value_text = str(authored_path)
    else:
        value_text = str(value or "")
    if value_text.startswith(("omniverse://", "omni://")):
        return value_text
    return None


def _remote_material_asset_paths(material: Any) -> list[str]:
    remote_paths: set[str] = set()
    try:
        from pxr import Usd  # type: ignore
    except Exception:
        return []
    try:
        prim_range = Usd.PrimRange(material.GetPrim())
    except Exception:
        return []
    for prim in prim_range:
        for attr in prim.GetAttributes():
            try:
                remote_path = _remote_asset_path(attr.Get())
            except Exception:
                remote_path = None
            if remote_path:
                remote_paths.add(remote_path)
    return sorted(remote_paths)


def _collect_material_runtime_notes(
    stage: Any,
    smoke_prim_path: str,
) -> dict[str, Any]:
    notes = _empty_material_runtime_notes()
    try:
        from pxr import Usd, UsdGeom, UsdShade  # type: ignore
    except Exception:
        notes["collection_error"] = "pxr.UsdShade unavailable"
        notes["material_runtime_status"] = "collection_error"
        return notes

    looks_prim = stage.GetPrimAtPath("/World/Looks")
    notes["world_looks_present"] = bool(looks_prim and looks_prim.IsValid())
    unbound_paths: list[str] = []
    empty_binding_paths: list[str] = []
    unresolved_paths: list[str] = []
    gap_details: list[dict[str, Any]] = []
    used_material_paths: set[str] = set()
    remote_paths: set[str] = set()
    bound_mesh_count = 0
    root_prim = stage.GetPrimAtPath(smoke_prim_path)
    if not root_prim or not root_prim.IsValid():
        notes["collection_error"] = f"task root prim not found: {smoke_prim_path}"
        notes["material_runtime_status"] = "collection_error"
        return notes
    try:
        prim_range = Usd.PrimRange(root_prim)
    except Exception as exc:
        notes["collection_error"] = f"{type(exc).__name__}: {exc}"
        notes["material_runtime_status"] = "collection_error"
        return notes
    for prim in prim_range:
        if not prim.IsA(UsdGeom.Mesh):
            continue
        notes["task_mesh_count"] += 1
        material, _relationship = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
        if not material or not material.GetPrim().IsValid():
            authored_bindings = _authored_material_bindings(prim, smoke_prim_path)
            non_empty_bindings = [
                binding for binding in authored_bindings if binding["targets"]
            ]
            if non_empty_bindings:
                unresolved_paths.append(str(prim.GetPath()))
            elif authored_bindings:
                empty_binding_paths.append(str(prim.GetPath()))
                gap_details.append(
                    _material_gap_detail(prim, "authored_empty", authored_bindings)
                )
            else:
                unbound_paths.append(str(prim.GetPath()))
                gap_details.append(_material_gap_detail(prim, "unbound", []))
            continue
        bound_mesh_count += 1
        material_path = str(material.GetPrim().GetPath())
        used_material_paths.add(material_path)
        remote_paths.update(_remote_material_asset_paths(material))

    notes["material_collection_ok"] = True
    notes["bound_task_mesh_count"] = bound_mesh_count
    notes["unbound_task_mesh_count"] = len(unbound_paths)
    notes["unbound_task_mesh_paths"] = unbound_paths
    notes["empty_authored_binding_count"] = len(empty_binding_paths)
    notes["empty_authored_binding_paths"] = empty_binding_paths
    notes["unresolved_binding_target_count"] = len(unresolved_paths)
    notes["unresolved_binding_target_paths"] = unresolved_paths
    notes["unresolved_task_material_count"] = len(unresolved_paths)
    notes["used_material_paths"] = sorted(used_material_paths)
    notes["used_material_count"] = len(used_material_paths)
    notes["remote_material_dependency_paths"] = sorted(remote_paths)
    notes["remote_material_dependency_count"] = len(remote_paths)
    gap_details = sorted(gap_details, key=lambda detail: detail["mesh_path"])
    notes["material_binding_gap_details"] = gap_details
    notes["material_binding_gap_paths"] = [
        detail["mesh_path"] for detail in gap_details
    ]
    notes["material_binding_gap_count"] = len(gap_details)
    if gap_details:
        if all(
            detail.get("readability_evidence_status") == "accepted"
            for detail in gap_details
        ):
            notes["material_binding_gap_readability_status"] = "accepted"
        else:
            notes["material_binding_gap_readability_status"] = "missing"
    else:
        notes["material_binding_gap_readability_status"] = "not_required"
    if unresolved_paths:
        notes["material_runtime_status"] = "blocked_unresolved_binding"
        notes["fallback_status"] = "unresolved_native_binding"
    elif unbound_paths or empty_binding_paths:
        notes["material_runtime_status"] = "mixed_native_and_fallback"
        if notes["material_binding_gap_readability_status"] == "accepted":
            notes["fallback_status"] = "readability_evidence_accepted"
        else:
            notes["fallback_status"] = "binding_gaps_require_readability_evidence"
    else:
        notes["material_runtime_status"] = "resolved_native_material"
        notes["fallback_status"] = "none"
    return notes


def _classify_physx_warnings(warnings: list[str]) -> dict[str, list[str]]:
    allow_needles = (
        "Duplicate link name 'mesh' in articulation metatype",
        "ScaleOrientation is not supported for rigid bodies",
    )
    deny_needles = (
        "nan",
        "inf",
        "failed to create",
        "invalid",
    )
    allowlist: list[str] = []
    denylist: list[str] = []
    unclassified: list[str] = []
    for warning in warnings:
        lowered = warning.lower()
        if any(needle.lower() in lowered for needle in allow_needles):
            allowlist.append(warning)
        elif any(needle in lowered for needle in deny_needles):
            denylist.append(warning)
        else:
            unclassified.append(warning)
    return {
        "physx_warning_allowlist": allowlist,
        "physx_warning_denylist": denylist,
        "unclassified_physx_warnings": unclassified,
    }


def _resolve_source_stage(labutopia_root: str | Path) -> Path:
    stage_path = Path(labutopia_root) / DEFAULT_SOURCE_SCENE_RELATIVE
    if not stage_path.exists():
        raise FileNotFoundError(f"native LabUtopia stage not found: {stage_path}")
    return stage_path


def _pxr_world_child_names(source_stage: str | Path) -> list[str]:
    from pxr import Usd  # type: ignore

    stage = Usd.Stage.Open(str(source_stage))
    world = stage.GetPrimAtPath("/World") if stage else None
    if not world or not world.IsValid():
        raise RuntimeError(f"/World not found in source stage: {source_stage}")
    return [child.GetName() for child in world.GetChildren()]


def _isaac_python_world_child_names(source_stage: str | Path) -> list[str]:
    isaac_python = Path("/isaac-sim/python.sh")
    if not isaac_python.exists():
        raise FileNotFoundError(f"Isaac Python runtime not found: {isaac_python}")
    script = "\n".join(
        [
            "import json",
            "import sys",
            "from pxr import Usd",
            "stage = Usd.Stage.Open(sys.argv[1])",
            "world = stage.GetPrimAtPath('/World') if stage else None",
            "if not world or not world.IsValid():",
            "    raise RuntimeError('/World not found')",
            "print('JSON_RESULT:' + json.dumps([c.GetName() for c in world.GetChildren()]))",
        ]
    )
    result = subprocess.run(
        [str(isaac_python), "-c", script, str(source_stage)],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()[-2000:]
        raise RuntimeError(f"Isaac Python child discovery failed: {stderr}")
    for line in reversed(result.stdout.splitlines()):
        if line.startswith("JSON_RESULT:"):
            return json.loads(line.removeprefix("JSON_RESULT:"))
    raise RuntimeError("Isaac Python child discovery did not emit JSON_RESULT")


def _source_world_child_report(source_stage: str | Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        return {
            "status": "ok",
            "method": "pxr",
            "children": _pxr_world_child_names(source_stage),
            "error": None,
        }
    except Exception as exc:
        errors.append(f"pxr: {type(exc).__name__}: {exc}")
    try:
        return {
            "status": "ok",
            "method": "isaac_python_sh",
            "children": _isaac_python_world_child_names(source_stage),
            "error": None,
        }
    except Exception as exc:
        errors.append(f"isaac_python_sh: {type(exc).__name__}: {exc}")
    return {
        "status": "unavailable",
        "method": "none",
        "children": [],
        "error": "; ".join(errors),
    }


def _source_world_child_names(source_stage: str | Path) -> list[str]:
    report = _source_world_child_report(source_stage)
    if report["status"] != "ok":
        return []
    return list(report["children"])


def _usd_vec3(value: list[float]) -> str:
    return f"({value[0]:.6g}, {value[1]:.6g}, {value[2]:.6g})"


def _fallback_paths_for_source(source_prim_path: str) -> dict[str, list[float]]:
    if source_prim_path != DEFAULT_SOURCE_PRIM_PATH:
        return {}
    return dict(DEFAULT_MATERIAL_FALLBACK_DISPLAY_COLORS)


def _fallback_overlay_lines(source_prim_path: str) -> list[str]:
    fallback_paths = _fallback_paths_for_source(source_prim_path)
    if not fallback_paths:
        return []
    target_world_child = source_prim_path.strip("/").split("/", 1)[1].split("/", 1)[0]
    grouped: dict[tuple[str, ...], list[tuple[str, list[float]]]] = {}
    for path, color in sorted(fallback_paths.items()):
        parts = path.strip("/").split("/")
        if len(parts) < 3 or parts[0] != "World" or parts[1] != target_world_child:
            continue
        parents = tuple(parts[2:-1])
        grouped.setdefault(parents, []).append((parts[-1], color))
    lines = [
        "    # Stage 2 readability fallback; not native material closure.",
        f'    over "{target_world_child}"',
        "    {",
    ]
    for parents, children in sorted(grouped.items()):
        indent_level = 2
        for parent in parents:
            indent = "    " * indent_level
            lines.extend([f'{indent}over "{parent}"', f"{indent}{{"])
            indent_level += 1
        for child, color in children:
            indent = "    " * indent_level
            lines.extend(
                [
                    f'{indent}over "{child}"',
                    f"{indent}{{",
                    f"{indent}    color3f[] primvars:displayColor = [{_usd_vec3(color)}]",
                    f'{indent}    uniform token primvars:displayColor:interpolation = "constant"',
                    f"{indent}}}",
                    "",
                ]
            )
        for _parent in reversed(parents):
            indent_level -= 1
            indent = "    " * indent_level
            lines.append(f"{indent}}}")
            lines.append("")
    lines.append("    }")
    lines.append("")
    return lines


def _default_output_root() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("saved/diagnostics") / f"native_dryingbox_smoke_{stamp}"


def build_minimal_native_stage_with_report(
    *,
    labutopia_root: str | Path = DEFAULT_LABUTOPIA_ROOT,
    output_root: str | Path,
    source_prim_path: str = DEFAULT_SOURCE_PRIM_PATH,
    smoke_prim_path: str = DEFAULT_SMOKE_PRIM_PATH,
) -> tuple[Path, dict[str, Any]]:
    output_dir = Path(output_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    stage_path = output_dir / "native_dryingbox.usda"
    source_stage = _resolve_source_stage(labutopia_root)
    smoke_prim_name = smoke_prim_path.rstrip("/").split("/")[-1]
    if not smoke_prim_path.startswith("/World/") or "/" in smoke_prim_name:
        raise ValueError(f"smoke_prim_path must be a direct /World child: {smoke_prim_path}")
    stage_report: dict[str, Any] = {
        "native_stage_mode": "full_source_world",
        "used_ebench_wrapper": False,
        "used_franka_shortcut": False,
        "world_child_discovery_status": "not_started",
        "world_child_discovery_method": None,
        "world_child_discovery_error": None,
        "active_world_children": [],
        "inactive_world_children": [],
        "active_non_target_world_children": [],
        "active_non_target_world_child_count": None,
        "material_fallback_overlay_policy": "none",
        "material_fallback_overlay_paths": [],
    }
    if smoke_prim_path == source_prim_path and source_prim_path.startswith("/World/"):
        target_world_child = source_prim_path.strip("/").split("/", 1)[1].split("/", 1)[0]
        allowed_world_children = {target_world_child, "Looks", "PhysicsScene", "physicsScene"}
        child_report = _source_world_child_report(source_stage)
        source_world_children = list(child_report.get("children") or [])
        inactive_world_children: list[str] = []
        active_world_children: list[str] = []
        if child_report["status"] == "ok":
            inactive_world_children = [
                name for name in source_world_children if name not in allowed_world_children
            ]
            active_world_children = [
                name for name in source_world_children if name in allowed_world_children
            ]
            active_non_target_world_children: list[str] = []
            active_non_target_count: int | None = 0
        else:
            active_non_target_world_children = []
            active_non_target_count = None
        stage_report.update(
            {
                "native_stage_mode": "full_source_world",
                "world_child_discovery_status": child_report["status"],
                "world_child_discovery_method": child_report["method"],
                "world_child_discovery_error": child_report.get("error"),
                "active_world_children": active_world_children,
                "inactive_world_children": inactive_world_children,
                "active_non_target_world_children": active_non_target_world_children,
                "active_non_target_world_child_count": active_non_target_count,
                "material_fallback_overlay_policy": (
                    DEFAULT_MATERIAL_FALLBACK_OVERLAY_POLICY
                    if _fallback_paths_for_source(source_prim_path)
                    else "none"
                ),
                "material_fallback_overlay_paths": sorted(
                    _fallback_paths_for_source(source_prim_path)
                ),
            }
        )
        inactive_lines: list[str] = []
        for name in inactive_world_children:
            inactive_lines.extend(
                [
                    f'    over "{name}" (',
                    "        active = false",
                    "    )",
                    "    {",
                    "    }",
                    "",
                ]
            )
        fallback_lines = _fallback_overlay_lines(source_prim_path)
        stage_path.write_text(
            "\n".join(
                [
                    "#usda 1.0",
                    f"# smoke source prim: {source_prim_path}",
                    "(",
                    '    defaultPrim = "World"',
                    "    metersPerUnit = 1",
                    '    upAxis = "Z"',
                    ")",
                    "",
                    'def Xform "World" (',
                    f"    prepend references = @{source_stage}@</World>",
                    ")",
                    "{",
                    *inactive_lines,
                    *fallback_lines,
                    "}",
                    "",
                    'def PhysicsScene "physicsScene"',
                    "{",
                    "    vector3f physics:gravityDirection = (0, 0, -1)",
                    "    float physics:gravityMagnitude = 9.81",
                    "}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return stage_path, stage_report
    stage_report.update(
        {
            "native_stage_mode": "split_source_smoke_reference",
            "world_child_discovery_status": "not_applicable",
            "world_child_discovery_method": None,
            "world_child_discovery_error": None,
            "active_world_children": ["Looks", smoke_prim_name],
            "inactive_world_children": [],
            "active_non_target_world_children": [],
            "active_non_target_world_child_count": 0,
        }
    )
    stage_path.write_text(
        "\n".join(
            [
                "#usda 1.0",
                "(",
                '    defaultPrim = "World"',
                "    metersPerUnit = 1",
                '    upAxis = "Z"',
                ")",
                "",
                'def Xform "World"',
                "{",
                '    def Scope "Looks" (',
                f"        prepend references = @{source_stage}@</World/Looks>",
                "    )",
                "    {",
                "    }",
                "",
                f'    def Xform "{smoke_prim_name}" (',
                f"        prepend references = @{source_stage}@<{source_prim_path}>",
                "    )",
                "    {",
                "    }",
                "}",
                "",
                'def PhysicsScene "physicsScene"',
                "{",
                "    vector3f physics:gravityDirection = (0, 0, -1)",
                "    float physics:gravityMagnitude = 9.81",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return stage_path, stage_report


def build_minimal_native_stage(
    *,
    labutopia_root: str | Path = DEFAULT_LABUTOPIA_ROOT,
    output_root: str | Path,
    source_prim_path: str = DEFAULT_SOURCE_PRIM_PATH,
    smoke_prim_path: str = DEFAULT_SMOKE_PRIM_PATH,
) -> Path:
    stage_path, _stage_report = build_minimal_native_stage_with_report(
        labutopia_root=labutopia_root,
        output_root=output_root,
        source_prim_path=source_prim_path,
        smoke_prim_path=smoke_prim_path,
    )
    return stage_path


def _valid_index(value: Any, names: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and isinstance(names, list)
        and 0 <= value < len(names)
    )


def _target_world_child(path: Any) -> str | None:
    if not isinstance(path, str) or not path.startswith("/World/"):
        return None
    parts = path.strip("/").split("/")
    if len(parts) < 2:
        return None
    return parts[1]


def _allowed_active_world_children(report: dict[str, Any]) -> set[str]:
    target = _target_world_child(report.get("source_prim_path"))
    allowed = {"Looks", "PhysicsScene", "physicsScene"}
    if target:
        allowed.add(target)
    return allowed


def _step_record_recomputed_finite(record: dict[str, Any]) -> bool:
    return bool(
        isinstance(record, dict)
        and _pose_is_finite(record.get("root_pose"))
        and _pose_is_finite(record.get("handle_pose"))
        and _finite_number_list(record.get("joint_positions"))
    )


def _physx_warning_partition_is_complete(report: dict[str, Any]) -> bool:
    warnings = report.get("physx_warnings")
    allowlist = report.get("physx_warning_allowlist")
    denylist = report.get("physx_warning_denylist")
    unclassified = report.get("unclassified_physx_warnings")
    if not all(isinstance(item, list) for item in (warnings, allowlist, denylist, unclassified)):
        return False
    return sorted(allowlist + denylist + unclassified) == sorted(warnings)


def _material_count_has_paths(notes: dict[str, Any], count_key: str, paths_key: str) -> bool:
    count = notes.get(count_key)
    paths = notes.get(paths_key)
    return isinstance(count, int) and not isinstance(count, bool) and (
        count == 0 or (isinstance(paths, list) and len(paths) == count)
    )


def _close_enough(first: Any, second: Any, *, tolerance: float = 1e-9) -> bool:
    return (
        _is_finite_number(first)
        and _is_finite_number(second)
        and abs(float(first) - float(second)) <= tolerance
    )


def _initial_pose_for_trace(
    report: dict[str, Any],
    step_trace: list[Any],
    report_key: str,
    trace_key: str,
) -> dict[str, Any] | None:
    report_pose = report.get(report_key)
    if isinstance(report_pose, dict) and _pose_is_finite(report_pose):
        return report_pose
    if step_trace and isinstance(step_trace[0], dict):
        trace_pose = step_trace[0].get(trace_key)
        if isinstance(trace_pose, dict) and _pose_is_finite(trace_pose):
            return trace_pose
    return None


def _joint_name_at(report: dict[str, Any], index_key: str) -> str | None:
    names = report.get("joint_names")
    index = report.get(index_key)
    if _valid_index(index, names):
        return str(names[index])
    return None


def _material_gap_details_are_accepted(notes: dict[str, Any]) -> bool:
    count = notes.get("material_binding_gap_count")
    paths = notes.get("material_binding_gap_paths")
    details = notes.get("material_binding_gap_details")
    if count == 0:
        return details == []
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or not isinstance(paths, list)
        or not isinstance(details, list)
        or len(details) != count
    ):
        return False
    detail_paths = [detail.get("mesh_path") for detail in details if isinstance(detail, dict)]
    if sorted(detail_paths) != sorted(paths):
        return False
    for detail in details:
        if not isinstance(detail, dict):
            return False
        display_color = detail.get("displayColor")
        if detail.get("readability_evidence_status") != "accepted":
            return False
        if not isinstance(display_color, dict):
            return False
        if display_color.get("fallback_status") != "usable":
            return False
    return True


def validate_smoke_report(
    report: dict[str, Any],
    *,
    require_final_status: bool = True,
) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_SMOKE_KEYS.difference(report))
    if missing:
        errors.append(f"missing required keys: {missing}")
        return errors

    if report.get("stage2_status") not in {"attempted", "blocked", "failed", "passed"}:
        errors.append("stage2_status must be attempted, blocked, failed, or passed")
    if not isinstance(report.get("stage2_passed"), bool):
        errors.append("stage2_passed must be a bool")
    if not isinstance(report.get("stage2_validation_errors"), list):
        errors.append("stage2_validation_errors must be a list")
    if report.get("native_stage_mode") != "full_source_world":
        errors.append("native_stage_mode must be full_source_world")
    if report.get("used_ebench_wrapper") is not False:
        errors.append("used_ebench_wrapper must be false")
    if report.get("used_franka_shortcut") is not False:
        errors.append("used_franka_shortcut must be false")
    if report.get("world_child_discovery_status") != "ok":
        errors.append("world_child_discovery_status must be ok")
    if not isinstance(report.get("active_world_children"), list):
        errors.append("active_world_children must be a list")
    else:
        invalid_active_children = [
            child
            for child in report["active_world_children"]
            if not isinstance(child, str)
            or child not in _allowed_active_world_children(report)
        ]
        if invalid_active_children:
            errors.append("active_world_children must not include non-target source children")
    if not isinstance(report.get("inactive_world_children"), list):
        errors.append("inactive_world_children must be a list")
    if not isinstance(report.get("active_non_target_world_children"), list):
        errors.append("active_non_target_world_children must be a list")
    if report.get("active_non_target_world_child_count") != 0:
        errors.append("active_non_target_world_child_count must be 0")
    active_non_target_children = report.get("active_non_target_world_children")
    active_non_target_count = report.get("active_non_target_world_child_count")
    if isinstance(active_non_target_children, list):
        if active_non_target_children:
            errors.append("active_non_target_world_children must be empty")
        if isinstance(active_non_target_count, int) and not isinstance(
            active_non_target_count, bool
        ):
            if active_non_target_count != len(active_non_target_children):
                errors.append(
                    "active_non_target_world_child_count must match active_non_target_world_children"
                )

    if report.get("errors"):
        errors.append(f"runtime reported errors: {report['errors']}")
    if report.get("traceback"):
        errors.append("runtime reported traceback")
    if report.get("root_prim_exists") is not True:
        errors.append("root_prim_exists must be true")
    if report.get("handle_prim_exists") is not True:
        errors.append("handle_prim_exists must be true")
    if report.get("root_articulation_api_present") is not True:
        errors.append("root_articulation_api_present must be true")
    if not isinstance(report["joint_names"], list):
        errors.append("joint_names must be a list")
    elif not report["joint_names"]:
        errors.append("joint_names must not be empty")
    if not _finite_number_list(report["initial_joint_positions"]):
        errors.append("initial_joint_positions must contain only finite numbers")
    if not _finite_number_list(report["post_step_joint_positions"]):
        errors.append("post_step_joint_positions must contain only finite numbers")
    if isinstance(report["joint_names"], list) and isinstance(
        report["initial_joint_positions"], list
    ):
        if len(report["joint_names"]) != len(report["initial_joint_positions"]):
            errors.append("joint_names and initial_joint_positions length mismatch")
    if isinstance(report["joint_names"], list) and isinstance(
        report["post_step_joint_positions"], list
    ):
        if len(report["joint_names"]) != len(report["post_step_joint_positions"]):
            errors.append("joint_names and post_step_joint_positions length mismatch")
    if not isinstance(report.get("door_joint_path"), str) or not report.get("door_joint_path"):
        errors.append("door_joint_path must be a non-empty string")
    if not _valid_index(report.get("door_joint_index"), report.get("joint_names")):
        errors.append("door_joint_index must identify a joint_names entry")
    if not isinstance(report.get("button_joint_path"), str) or not report.get("button_joint_path"):
        errors.append("button_joint_path must be a non-empty string")
    if not _valid_index(report.get("button_joint_index"), report.get("joint_names")):
        errors.append("button_joint_index must identify a joint_names entry")
    door_joint_name = _joint_name_at(report, "door_joint_index")
    button_joint_name = _joint_name_at(report, "button_joint_index")
    if door_joint_name and not any(
        needle in door_joint_name.lower() for needle in ("door", "revolute")
    ):
        errors.append("door_joint_index must identify a door/revolute joint")
    if button_joint_name and not any(
        needle in button_joint_name.lower() for needle in ("button", "prismatic")
    ):
        errors.append("button_joint_index must identify a button/prismatic joint")
    if (
        _valid_index(report.get("door_joint_index"), report.get("joint_names"))
        and _valid_index(report.get("button_joint_index"), report.get("joint_names"))
        and report.get("door_joint_index") == report.get("button_joint_index")
    ):
        errors.append("door_joint_index and button_joint_index must be distinct")
    if isinstance(report.get("smoke_prim_path"), str) and isinstance(
        report.get("joint_names"), list
    ):
        expected_door_path = _joint_path_for_index(
            report["smoke_prim_path"],
            report["joint_names"],
            report.get("door_joint_index"),
        )
        expected_button_path = _joint_path_for_index(
            report["smoke_prim_path"],
            report["joint_names"],
            report.get("button_joint_index"),
        )
        if expected_door_path and report.get("door_joint_path") != expected_door_path:
            errors.append("door_joint_path must match door_joint_index")
        if expected_button_path and report.get("button_joint_path") != expected_button_path:
            errors.append("button_joint_path must match button_joint_index")
    limits = report.get("source_door_joint_limits_deg")
    if (
        not isinstance(limits, list)
        or len(limits) != 2
        or not all(_is_finite_number(item) for item in limits)
        or float(limits[0]) > float(limits[1])
    ):
        errors.append("source_door_joint_limits_deg must be [lower, upper]")
        limits = list(DEFAULT_SOURCE_DOOR_JOINT_LIMITS_DEG)
    if not isinstance(report.get("source_door_joint_limits_source"), str) or not report.get(
        "source_door_joint_limits_source"
    ):
        errors.append("source_door_joint_limits_source must be a non-empty string")
    if report["root_pose_finite"] is not True:
        errors.append("root_pose_finite must be true")
    if report["handle_pose_finite"] is not True:
        errors.append("handle_pose_finite must be true")
    if not _pose_is_finite(report.get("root_pose")):
        errors.append("root_pose must be finite")
    if not _pose_is_finite(report.get("post_step_root_pose")):
        errors.append("post_step_root_pose must be finite")
    if not _pose_is_finite(report.get("handle_pose")):
        errors.append("handle_pose must be finite")
    if not _pose_is_finite(report.get("post_step_handle_pose")):
        errors.append("post_step_handle_pose must be finite")
    if report["runtime_physics_stable"] is not True:
        errors.append("runtime_physics_stable must be true")
    if not isinstance(report["physx_warnings"], list):
        errors.append("physx_warnings must be a list")
    if "step_count" in report:
        step_count = report["step_count"]
        if not isinstance(step_count, int) or step_count != DEFAULT_STEP_COUNT:
            errors.append("step_count must be exactly 120")
    step_trace = report.get("step_trace")
    if not isinstance(step_trace, list):
        errors.append("step_trace must be a list")
    elif isinstance(report.get("step_count"), int) and len(step_trace) != report["step_count"]:
        errors.append("step_trace length must equal step_count")
    if isinstance(step_trace, list):
        expected_steps = list(range(1, len(step_trace) + 1))
        actual_steps = [
            record.get("step") if isinstance(record, dict) else None
            for record in step_trace
        ]
        if actual_steps != expected_steps:
            errors.append("step_trace steps must be monotonic 1..step_count")
        recomputed_finite_trace = all(
            _step_record_recomputed_finite(record)
            for record in step_trace
            if isinstance(record, dict)
        ) and all(isinstance(record, dict) for record in step_trace)
        if bool(report.get("finite_trace")) != recomputed_finite_trace:
            errors.append("finite_trace must match recomputed step_trace finiteness")
        if not all(
            _is_finite_number(record.get("door_joint_angle_deg"))
            for record in step_trace
            if isinstance(record, dict)
        ):
            errors.append("step_trace door_joint_angle_deg must be finite for every step")
        if not all(
            _is_finite_number(record.get("button_joint_position_m"))
            for record in step_trace
            if isinstance(record, dict)
        ):
            errors.append("step_trace button_joint_position_m must be finite for every step")
        initial_root_pose = _initial_pose_for_trace(
            report, step_trace, "root_pose", "root_pose"
        )
        initial_handle_pose = _initial_pose_for_trace(
            report, step_trace, "handle_pose", "handle_pose"
        )
        recomputed_root_drifts = [
            _translation_distance_m(initial_root_pose, record.get("root_pose"))
            for record in step_trace
            if isinstance(record, dict)
        ]
        recomputed_handle_drifts = [
            _translation_distance_m(initial_handle_pose, record.get("handle_pose"))
            for record in step_trace
            if isinstance(record, dict)
        ]
        recomputed_root_drift = _max_present(recomputed_root_drifts)
        recomputed_handle_drift = _max_present(recomputed_handle_drifts)
        if recomputed_root_drift is not None:
            if not _close_enough(
                report.get("max_root_translation_drift_m"), recomputed_root_drift
            ):
                errors.append(
                    "max_root_translation_drift_m must match recomputed step_trace drift"
                )
            root_tolerance = report.get("root_translation_drift_tolerance_m")
            if _is_finite_number(root_tolerance) and recomputed_root_drift > float(
                root_tolerance
            ):
                errors.append("recomputed root translation drift exceeds tolerance")
        if recomputed_handle_drift is not None:
            if not _close_enough(
                report.get("max_handle_translation_drift_m"), recomputed_handle_drift
            ):
                errors.append(
                    "max_handle_translation_drift_m must match recomputed step_trace drift"
                )
            handle_tolerance = report.get("handle_translation_drift_tolerance_m")
            if _is_finite_number(handle_tolerance) and recomputed_handle_drift > float(
                handle_tolerance
            ):
                errors.append("recomputed handle translation drift exceeds tolerance")
        door_angles = [
            record.get("door_joint_angle_deg")
            for record in step_trace
            if isinstance(record, dict) and record.get("door_joint_angle_deg") is not None
        ]
        if door_angles and all(_is_finite_number(angle) for angle in door_angles):
            lower, upper = [float(item) for item in limits]
            if min(float(angle) for angle in door_angles) < lower - DEFAULT_ROTATION_DRIFT_TOLERANCE_DEG or max(
                float(angle) for angle in door_angles
            ) > upper + DEFAULT_ROTATION_DRIFT_TOLERANCE_DEG:
                errors.append("door joint trace exceeds source limits")
    if report.get("finite_trace") is not True:
        errors.append("finite_trace must be true")
    for metric_key, tolerance_key in (
        ("max_root_translation_drift_m", "root_translation_drift_tolerance_m"),
        ("max_root_rotation_drift_deg", "root_rotation_drift_tolerance_deg"),
        ("max_handle_translation_drift_m", "handle_translation_drift_tolerance_m"),
    ):
        metric = report.get(metric_key)
        tolerance = report.get(tolerance_key)
        if not (_is_finite_number(metric) and _is_finite_number(tolerance)):
            errors.append(f"{metric_key} and {tolerance_key} must be finite numbers")
        elif float(metric) > float(tolerance):
            errors.append(f"{metric_key} exceeds tolerance")
    if report.get("door_joint_angle_within_limits") is not True:
        errors.append("door_joint_angle_within_limits must be true")
    if report.get("non_door_dof_drift_within_tolerance") is not True:
        errors.append("non_door_dof_drift_within_tolerance must be true")
    if not isinstance(report.get("physx_warning_allowlist"), list):
        errors.append("physx_warning_allowlist must be a list")
    if not isinstance(report.get("physx_warning_denylist"), list):
        errors.append("physx_warning_denylist must be a list")
    elif report.get("physx_warning_denylist"):
        errors.append("physx_warning_denylist must be empty")
    unclassified = report.get("unclassified_physx_warnings")
    if not isinstance(unclassified, list):
        errors.append("unclassified_physx_warnings must be a list")
    elif unclassified:
        errors.append("unclassified_physx_warnings must be empty")
    if not _physx_warning_partition_is_complete(report):
        errors.append("physx warning classification must partition physx_warnings")
    material_notes = report.get("material_runtime_notes")
    if not isinstance(material_notes, dict):
        errors.append("material_runtime_notes must be a dict")
    else:
        unresolved = material_notes.get("unresolved_binding_target_count")
        compiler_warnings = material_notes.get("dryingbox_material_compiler_warnings")
        if material_notes.get("material_collection_ok") is not True:
            errors.append("material_runtime_notes material_collection_ok must be true")
        if unresolved != 0:
            errors.append("material_runtime_notes unresolved_binding_target_count must be 0")
        if not isinstance(compiler_warnings, list) or compiler_warnings:
            errors.append(
                "material_runtime_notes dryingbox_material_compiler_warnings must be empty"
            )
        if material_notes.get("material_compiler_warning_count") not in (0, None):
            errors.append("material_runtime_notes material_compiler_warning_count must be 0")
        for count_key, paths_key in (
            ("unbound_task_mesh_count", "unbound_task_mesh_paths"),
            ("empty_authored_binding_count", "empty_authored_binding_paths"),
            ("unresolved_binding_target_count", "unresolved_binding_target_paths"),
            ("remote_material_dependency_count", "remote_material_dependency_paths"),
            ("material_binding_gap_count", "material_binding_gap_paths"),
        ):
            if not _material_count_has_paths(material_notes, count_key, paths_key):
                errors.append(f"material_runtime_notes {count_key} must include matching paths")
        if material_notes.get("material_binding_gap_count", 0) and material_notes.get(
            "material_binding_gap_readability_status"
        ) != "accepted":
            errors.append(
                "material_runtime_notes material_binding_gap_readability_status must be accepted when gaps exist"
            )
        if not _material_gap_details_are_accepted(material_notes):
            errors.append(
                "material_runtime_notes material_binding_gap_details must match gap paths and contain accepted readability evidence"
            )
        if material_notes.get("material_binding_gap_count", 0) and material_notes.get(
            "material_binding_gap_readability_status"
        ) == "accepted":
            if material_notes.get("material_runtime_status") != "mixed_native_and_fallback":
                errors.append(
                    "material_runtime_notes material_runtime_status must be mixed_native_and_fallback when accepted gaps exist"
                )
            if material_notes.get("fallback_status") != "readability_evidence_accepted":
                errors.append(
                    "material_runtime_notes fallback_status must be readability_evidence_accepted when accepted gaps exist"
                )
        if (
            material_notes.get("material_binding_gap_count") == 0
            and material_notes.get("unresolved_binding_target_count") == 0
        ):
            if material_notes.get("material_runtime_status") != "resolved_native_material":
                errors.append(
                    "material_runtime_notes material_runtime_status must be resolved_native_material when no gaps or unresolved bindings exist"
                )
            if material_notes.get("fallback_status") != "none":
                errors.append(
                    "material_runtime_notes fallback_status must be none when no gaps or unresolved bindings exist"
                )
    if errors:
        if report.get("stage2_status") == "passed":
            errors.append("stage2_status cannot be passed when validation errors exist")
        if report.get("stage2_passed") is True:
            errors.append("stage2_passed cannot be true when validation errors exist")
    else:
        if report.get("stage2_validation_errors"):
            errors.append("stage2_validation_errors must be empty when validation passes")
        if require_final_status:
            if report.get("stage2_status") != "passed":
                errors.append("stage2_status must be passed when validation checks pass")
            if report.get("stage2_passed") is not True:
                errors.append("stage2_passed must be true when validation checks pass")
    return errors


def write_smoke_report(report: dict[str, Any], output_root: str | Path) -> Path:
    output_path = Path(output_root) / "smoke.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return output_path


class PhysxWarningCollector:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self._subscription: Any = None

    def __enter__(self) -> "PhysxWarningCollector":
        try:
            import omni.kit.app  # type: ignore

            stream = omni.kit.app.get_app().get_log_event_stream()
            self._subscription = stream.create_subscription_to_pop(self._on_log_event)
        except Exception:
            self._subscription = None
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._subscription = None

    def _on_log_event(self, event: Any) -> None:
        payload = getattr(event, "payload", None) or {}
        if not isinstance(payload, dict):
            return
        message = str(
            payload.get("message")
            or payload.get("msg")
            or payload.get("text")
            or payload
        )
        level = str(payload.get("level") or payload.get("severity") or "").lower()
        lowered = message.lower()
        if "physx" in lowered and ("warn" in level or "warning" in lowered):
            self.warnings.append(message[:1000])


def _pose_from_prim(prim: Any) -> dict[str, Any] | None:
    try:
        position, orientation = prim.get_world_pose()
    except Exception:
        return None
    return {
        "position": _jsonable(position),
        "orientation": _jsonable(orientation),
    }


def _dof_names(articulation: Any) -> list[str]:
    names = getattr(articulation, "dof_names", None)
    if names is None:
        articulation_view = getattr(articulation, "_articulation_view", None)
        names = getattr(articulation_view, "dof_names", None)
    if names is None:
        return []
    return [str(name) for name in _jsonable(names)]


def _joint_positions(articulation: Any) -> list[Any]:
    return _jsonable(articulation.get_joint_positions())


def _source_door_joint_limits(
    stage: Any,
    door_joint_path: str | None,
) -> tuple[list[float], str]:
    if door_joint_path:
        try:
            from pxr import UsdPhysics  # type: ignore

            prim = stage.GetPrimAtPath(door_joint_path)
            joint = UsdPhysics.RevoluteJoint(prim)
            lower = joint.GetLowerLimitAttr().Get()
            upper = joint.GetUpperLimitAttr().Get()
            if _is_finite_number(lower) and _is_finite_number(upper):
                return [float(lower), float(upper)], "source_usd"
        except Exception:
            pass
    return (
        list(DEFAULT_SOURCE_DOOR_JOINT_LIMITS_DEG),
        "default_labutopia_dryingbox_revolute_joint_fallback",
    )


def _candidate_isaac_log_roots() -> list[Path]:
    site_packages = (
        Path(sys.prefix)
        / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    )
    roots = [
        site_packages / "omni/logs/Kit/Isaac-Sim",
        Path("/isaac-sim/kit/logs/Kit/Isaac-Sim"),
        Path.home() / ".nvidia-omniverse/logs/Kit/Isaac-Sim",
    ]
    for env_name in ("ISAAC_PATH", "EXP_PATH", "CARB_APP_PATH"):
        env_path = os.environ.get(env_name)
        if env_path:
            roots.append(Path(env_path) / "logs/Kit/Isaac-Sim")
    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.expanduser()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(resolved)
    return deduped


def _isaac_log_candidates(
    started_at: float | None = None,
    log_roots: list[Path] | None = None,
) -> list[Path]:
    candidates: list[Path] = []
    for log_root in log_roots or _candidate_isaac_log_roots():
        if log_root.exists():
            candidates.extend(log_root.glob("*/kit_*.log"))
            candidates.extend(log_root.glob("kit_*.log"))
    if started_at is not None:
        candidates = [
            path
            for path in candidates
            if path.exists() and path.stat().st_mtime >= started_at - 2.0
        ]
    return sorted(candidates, key=lambda path: path.stat().st_mtime)


def _extract_physx_warnings_from_log(log_path: str | Path) -> list[str]:
    path = Path(log_path)
    if not path.exists():
        return []
    warnings: list[str] = []
    warning_pattern = re.compile(r"\[(warning|warn)\]|(?:^|\s)(warning|warn)(?:\s|:)", re.IGNORECASE)
    physics_needles = (
        "physx",
        "physics",
        "articulation",
        "duplicate link name",
    )
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        lowered = line.lower()
        if not warning_pattern.search(line):
            continue
        if not any(needle in lowered for needle in physics_needles):
            continue
        warnings.append(line.strip()[:1000])
    return warnings


def _runtime_smoke(
    *,
    stage_path: Path,
    smoke_prim_path: str,
    handle_prim_path: str,
    step_count: int,
) -> dict[str, Any]:
    started_at = time.time()
    from isaacsim import SimulationApp  # type: ignore

    simulation_app = SimulationApp({"headless": True, "multi_gpu": False})
    warning_collector = PhysxWarningCollector()
    root_prim_exists = False
    handle_prim_exists = False
    root_articulation_api_present = False
    initial_joint_positions: list[Any] = []
    post_step_joint_positions: list[Any] = []
    root_pose = None
    post_root_pose = None
    handle_pose = None
    post_handle_pose = None
    joint_names: list[str] = []
    door_joint_index: int | None = None
    button_joint_index: int | None = None
    door_joint_path: str | None = None
    button_joint_path: str | None = None
    source_door_joint_limits_deg = list(DEFAULT_SOURCE_DOOR_JOINT_LIMITS_DEG)
    source_door_joint_limits_source = "not_read"
    step_trace: list[dict[str, Any]] = []
    from omni.isaac.core import World  # type: ignore
    from omni.isaac.core.articulations import Articulation  # type: ignore
    from omni.isaac.core.prims import XFormPrim  # type: ignore
    from omni.isaac.core.utils.stage import open_stage  # type: ignore
    import omni.usd  # type: ignore
    from pxr import UsdPhysics  # type: ignore

    open_stage(str(stage_path))
    simulation_app.update()
    stage = omni.usd.get_context().get_stage()
    root_prim = stage.GetPrimAtPath(smoke_prim_path)
    handle_prim = stage.GetPrimAtPath(handle_prim_path)
    root_prim_exists = bool(root_prim and root_prim.IsValid())
    handle_prim_exists = bool(handle_prim and handle_prim.IsValid())
    root_articulation_api_present = bool(
        root_prim_exists and root_prim.HasAPI(UsdPhysics.ArticulationRootAPI)
    )
    if not root_prim_exists:
        raise RuntimeError(f"root prim not found in smoke stage: {smoke_prim_path}")
    if not handle_prim_exists:
        raise RuntimeError(f"handle prim not found in smoke stage: {handle_prim_path}")
    if not root_articulation_api_present:
        raise RuntimeError(
            f"root prim lacks PhysicsArticulationRootAPI: {smoke_prim_path}"
        )

    world = World(stage_units_in_meters=1.0)
    root = Articulation(prim_path=smoke_prim_path, name="native_dryingbox")
    handle = XFormPrim(prim_path=handle_prim_path, name="native_dryingbox_handle")
    world.scene.add(root)
    world.scene.add(handle)

    with warning_collector:
        world.reset()
        root.initialize()
        world.initialize_physics()
        joint_names = _dof_names(root)
        door_joint_index = _first_matching_index(joint_names, ("door", "revolute"))
        button_joint_index = _first_matching_index(joint_names, ("button", "prismatic"))
        door_joint_path = _joint_path_for_index(
            smoke_prim_path, joint_names, door_joint_index
        )
        button_joint_path = _joint_path_for_index(
            smoke_prim_path, joint_names, button_joint_index
        )
        (
            source_door_joint_limits_deg,
            source_door_joint_limits_source,
        ) = _source_door_joint_limits(stage, door_joint_path)
        initial_joint_positions = _joint_positions(root)
        root_pose = _pose_from_prim(root)
        handle_pose = _pose_from_prim(handle)
        for step in range(step_count):
            world.step(render=False)
            step_joint_positions = _joint_positions(root)
            step_trace.append(
                _trace_record(
                    step=step + 1,
                    root=root,
                    handle=handle,
                    joint_names=joint_names,
                    joint_positions=step_joint_positions,
                )
            )
        post_step_joint_positions = _joint_positions(root)
        post_root_pose = _pose_from_prim(root)
        post_handle_pose = _pose_from_prim(handle)
    simulation_app.update()

    isaac_log_path = None
    log_candidates = _isaac_log_candidates(started_at)
    log_warnings: list[str] = []
    if log_candidates:
        isaac_log_path = str(log_candidates[-1])
        log_warnings = _extract_physx_warnings_from_log(log_candidates[-1])

    root_pose_finite = _pose_is_finite(root_pose) and _pose_is_finite(post_root_pose)
    handle_pose_finite = _pose_is_finite(handle_pose) and _pose_is_finite(
        post_handle_pose
    )
    joint_positions_finite = _finite_number_list(initial_joint_positions) and (
        _finite_number_list(post_step_joint_positions)
    )
    physx_warnings = sorted(set(warning_collector.warnings + log_warnings))
    trace_metrics = _trace_metrics(
        initial_root_pose=root_pose,
        initial_handle_pose=handle_pose,
        initial_joint_positions=initial_joint_positions,
        joint_names=joint_names,
        step_trace=step_trace,
        source_door_joint_limits_deg=source_door_joint_limits_deg,
    )
    warning_classification = _classify_physx_warnings(physx_warnings)
    material_runtime_notes = _collect_material_runtime_notes(stage, smoke_prim_path)
    return {
        "root_prim_exists": root_prim_exists,
        "handle_prim_exists": handle_prim_exists,
        "root_articulation_api_present": root_articulation_api_present,
        "joint_names": joint_names,
        "initial_joint_positions": initial_joint_positions,
        "post_step_joint_positions": post_step_joint_positions,
        "door_joint_path": door_joint_path,
        "door_joint_index": door_joint_index,
        "source_door_joint_limits_source": source_door_joint_limits_source,
        "button_joint_path": button_joint_path,
        "button_joint_index": button_joint_index,
        "root_pose": root_pose,
        "post_step_root_pose": post_root_pose,
        "handle_pose": handle_pose,
        "post_step_handle_pose": post_handle_pose,
        "step_trace": step_trace,
        **trace_metrics,
        "root_pose_finite": root_pose_finite,
        "handle_pose_finite": handle_pose_finite,
        "runtime_physics_stable": bool(
            root_pose_finite
            and handle_pose_finite
            and joint_positions_finite
            and trace_metrics["finite_trace"]
        ),
        "physx_warnings": physx_warnings,
        **warning_classification,
        "physx_warning_sources": {
            "log_event_stream_count": len(set(warning_collector.warnings)),
            "isaac_log_count": len(set(log_warnings)),
        },
        "material_runtime_notes": material_runtime_notes,
        "simulation_app_close_policy": (
            "not_called_in_isaacsim41_conda_smoke;"
            " SimulationApp.close() segfaulted in this runtime before smoke.json could be written"
        ),
        "isaac_log_path": isaac_log_path,
    }


def _stage2_status_from_errors(report: dict[str, Any], errors: list[str]) -> str:
    if not errors:
        return "passed"
    blocker_needles = (
        "world_child_discovery_status",
        "material_runtime_notes material_collection_ok",
        "runtime reported errors",
        "runtime reported traceback",
        "not found",
    )
    if any(any(needle in error for needle in blocker_needles) for error in errors):
        return "blocked"
    failure_needles = (
        "runtime_physics_stable",
        "finite_trace",
        "exceeds tolerance",
        "door joint trace exceeds",
        "physx_warning_denylist",
        "unclassified_physx_warnings",
    )
    if any(any(needle in error for needle in failure_needles) for error in errors):
        return "failed"
    if report.get("errors") or report.get("traceback"):
        return "blocked"
    return "attempted"


def _finalize_stage2_report(report: dict[str, Any]) -> None:
    errors = validate_smoke_report(report, require_final_status=False)
    report["stage2_validation_errors"] = errors
    report["stage2_passed"] = not errors
    report["stage2_status"] = _stage2_status_from_errors(report, errors)


def run_native_dryingbox_smoke(
    *,
    labutopia_root: str | Path = DEFAULT_LABUTOPIA_ROOT,
    output_root: str | Path,
    source_prim_path: str = DEFAULT_SOURCE_PRIM_PATH,
    smoke_prim_path: str = DEFAULT_SMOKE_PRIM_PATH,
    handle_prim_path: str = DEFAULT_HANDLE_PRIM_PATH,
    step_count: int = DEFAULT_STEP_COUNT,
) -> tuple[dict[str, Any], Path]:
    output_dir = Path(output_root)
    stage_path = output_dir / "native_dryingbox.usda"
    report: dict[str, Any] = {
        "stage2_status": "attempted",
        "stage2_passed": False,
        "stage2_validation_errors": [],
        "schema_version": 1,
        "labutopia_root": str(Path(labutopia_root)),
        "stage_path": str(stage_path),
        "source_prim_path": source_prim_path,
        "smoke_prim_path": smoke_prim_path,
        "handle_prim_path": handle_prim_path,
        "native_stage_mode": "not_built",
        "used_ebench_wrapper": False,
        "used_franka_shortcut": False,
        "world_child_discovery_status": "not_started",
        "world_child_discovery_method": None,
        "world_child_discovery_error": None,
        "active_world_children": [],
        "inactive_world_children": [],
        "active_non_target_world_children": [],
        "active_non_target_world_child_count": None,
        "step_count": step_count,
        "root_prim_exists": False,
        "handle_prim_exists": False,
        "root_articulation_api_present": False,
        "joint_names": [],
        "initial_joint_positions": [],
        "post_step_joint_positions": [],
        "door_joint_path": None,
        "door_joint_index": None,
        "source_door_joint_limits_source": "not_read",
        "button_joint_path": None,
        "button_joint_index": None,
        "root_pose": None,
        "post_step_root_pose": None,
        "handle_pose": None,
        "post_step_handle_pose": None,
        "step_trace": [],
        "finite_trace": False,
        "max_root_translation_drift_m": None,
        "root_translation_drift_tolerance_m": DEFAULT_TRANSLATION_DRIFT_TOLERANCE_M,
        "max_root_rotation_drift_deg": None,
        "root_rotation_drift_tolerance_deg": DEFAULT_ROTATION_DRIFT_TOLERANCE_DEG,
        "max_handle_translation_drift_m": None,
        "handle_translation_drift_tolerance_m": DEFAULT_TRANSLATION_DRIFT_TOLERANCE_M,
        "door_joint_angle_min_deg": None,
        "door_joint_angle_max_deg": None,
        "source_door_joint_limits_deg": list(DEFAULT_SOURCE_DOOR_JOINT_LIMITS_DEG),
        "door_joint_angle_within_limits": False,
        "button_joint_position_min_m": None,
        "button_joint_position_max_m": None,
        "non_door_dof_drift_tolerance": DEFAULT_NON_DOOR_DOF_DRIFT_TOLERANCE,
        "non_door_dof_drift_within_tolerance": False,
        "root_pose_finite": False,
        "handle_pose_finite": False,
        "runtime_physics_stable": False,
        "physx_warnings": [],
        "physx_warning_scope": "dryingbox_runtime_and_isaac_log_filtered_physics",
        "physx_warning_allowlist": [],
        "physx_warning_denylist": [],
        "unclassified_physx_warnings": [],
        "physx_warning_policy": "capture_only_for_task4_triage",
        "physx_warning_sources": {
            "log_event_stream_count": 0,
            "isaac_log_count": 0,
        },
        "material_runtime_notes": _empty_material_runtime_notes(),
        "simulation_app_close_policy": (
            "not_called_in_isaacsim41_conda_smoke;"
            " SimulationApp.close() segfaulted in this runtime before smoke.json could be written"
        ),
        "isaac_log_path": None,
        "errors": [],
    }
    try:
        stage_path, stage_report = build_minimal_native_stage_with_report(
            labutopia_root=labutopia_root,
            output_root=output_dir,
            source_prim_path=source_prim_path,
            smoke_prim_path=smoke_prim_path,
        )
        report["stage_path"] = str(stage_path)
        report.update(stage_report)
        runtime_report = _runtime_smoke(
            stage_path=stage_path,
            smoke_prim_path=smoke_prim_path,
            handle_prim_path=handle_prim_path,
            step_count=step_count,
        )
        report.update(runtime_report)
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        report["traceback"] = traceback.format_exc()

    _finalize_stage2_report(report)
    output_path = write_smoke_report(report, output_dir)
    return report, output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a native-only Isaac smoke for LabUtopia DryingBox_01."
    )
    parser.add_argument(
        "--labutopia-root",
        default=str(DEFAULT_LABUTOPIA_ROOT),
        help="Path to the LabUtopia repository.",
    )
    parser.add_argument(
        "--source-prim-path",
        default=DEFAULT_SOURCE_PRIM_PATH,
        help="Native DryingBox prim path in the source LabUtopia stage.",
    )
    parser.add_argument(
        "--smoke-prim-path",
        default=DEFAULT_SMOKE_PRIM_PATH,
        help="DryingBox prim path to create and read in the smoke stage.",
    )
    parser.add_argument(
        "--handle-prim-path",
        default=DEFAULT_HANDLE_PRIM_PATH,
        help="Native handle prim path to read world pose from.",
    )
    parser.add_argument(
        "--step-count",
        type=int,
        default=DEFAULT_STEP_COUNT,
        help="Number of post-reset physics steps to run.",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Directory where native_dryingbox.usda and smoke.json should be written.",
    )
    args = parser.parse_args()

    output_root = args.output_root or _default_output_root()
    report, output_path = run_native_dryingbox_smoke(
        labutopia_root=args.labutopia_root,
        output_root=output_root,
        source_prim_path=args.source_prim_path,
        smoke_prim_path=args.smoke_prim_path,
        handle_prim_path=args.handle_prim_path,
        step_count=args.step_count,
    )
    errors = validate_smoke_report(report)
    print(output_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
