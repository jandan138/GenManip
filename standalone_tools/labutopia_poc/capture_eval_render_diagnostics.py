#!/usr/bin/env python3
"""Capture LabUtopia eval-path render diagnostics for one reset frame."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import sys
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

NATIVE_DRYING_BOX_STRATEGY = "native_complex_with_additive_physics_override"
NATIVE_DRYING_BOX_UID = "obj_DryingBox_01"
NATIVE_DRYING_BOX_HANDLE_UID = "obj_DryingBox_01_handle"

FrameClassification = Literal["black_frame_fail", "visible_frame"]
BoundaryClassification = Literal[
    "no_readback_frame",
    "readback_black_before_recorder",
    "recorder_write_black",
    "readback_visible",
]


@dataclass(frozen=True)
class CameraFrameStats:
    camera_name: str
    frame_path: str
    width: int
    height: int
    channel_min: list[float]
    channel_max: list[float]
    channel_mean: list[float]
    nonzero_pixels: int


def build_camera_frame_stats(
    *,
    camera_name: str,
    frame_path: str,
    width: int,
    height: int,
    channel_min: list[float],
    channel_max: list[float],
    channel_mean: list[float],
    nonzero_pixels: int,
) -> dict[str, object]:
    return asdict(
        CameraFrameStats(
            camera_name=camera_name,
            frame_path=frame_path,
            width=width,
            height=height,
            channel_min=channel_min,
            channel_max=channel_max,
            channel_mean=channel_mean,
            nonzero_pixels=nonzero_pixels,
        )
    )


def classify_frame_stats(stats: dict[str, object]) -> FrameClassification:
    channel_max = stats["channel_max"]
    nonzero_pixels = int(stats["nonzero_pixels"])
    if not isinstance(channel_max, list):
        raise TypeError("channel_max must be a list")
    max_value = max(float(value) for value in channel_max)
    if max_value <= 0.0 or nonzero_pixels == 0:
        return "black_frame_fail"
    return "visible_frame"


def classify_boundary(
    readback_stats: list[dict[str, object]],
    recorder_stats: list[dict[str, object]],
) -> BoundaryClassification:
    if not readback_stats:
        return "no_readback_frame"
    if any(classify_frame_stats(stats) == "black_frame_fail" for stats in readback_stats):
        return "readback_black_before_recorder"
    if recorder_stats and any(
        classify_frame_stats(stats) == "black_frame_fail" for stats in recorder_stats
    ):
        return "recorder_write_black"
    return "readback_visible"


def classify_articulation_runtime_state(
    articulation_state: dict[str, dict[str, Any]],
    *,
    required_articulations: list[str] | None = None,
    max_abs_joint_position_rad: float = math.tau,
    expected_joint_positions: dict[str, list[float]] | None = None,
    expected_joint_names: dict[str, list[str]] | None = None,
    joint_position_tolerance_rad: float = 1e-3,
) -> dict[str, Any]:
    required = sorted(set(required_articulations or []))
    expected = expected_joint_positions or {}
    expected_names = expected_joint_names or {}
    missing = [name for name in required if name not in articulation_state]
    report: dict[str, Any] = {
        "runtime_physics_stable": not missing,
        "required_articulations": required,
        "missing_articulations": missing,
        "expected_joint_positions": expected,
        "expected_joint_names": expected_names,
        "joint_position_tolerance_rad": joint_position_tolerance_rad,
        "articulations": {},
    }
    for name in missing:
        report["articulations"][name] = {
            "status": "missing_articulation",
            "joint_positions": None,
            "invalid_joint_positions": [],
        }
    for name, state in sorted(articulation_state.items()):
        item: dict[str, Any] = {
            "status": "stable",
            "joint_positions": state.get("joint_positions"),
        }
        if "dof_names" in state:
            item["dof_names"] = state["dof_names"]
        if "joint_positions_error" in state:
            item["status"] = "joint_positions_error"
            item["joint_positions_error"] = state["joint_positions_error"]
            item["invalid_joint_positions"] = []
            report["runtime_physics_stable"] = False
            report["articulations"][name] = item
            continue
        joint_positions = state.get("joint_positions")
        if not isinstance(joint_positions, list):
            item["status"] = "missing_joint_positions"
            item["invalid_joint_positions"] = []
            report["runtime_physics_stable"] = False
            report["articulations"][name] = item
            continue
        invalid_positions: list[float] = []
        for position in joint_positions:
            try:
                value = float(position)
            except (TypeError, ValueError):
                invalid_positions.append(position)  # type: ignore[arg-type]
                continue
            if not math.isfinite(value) or abs(value) > max_abs_joint_position_rad:
                invalid_positions.append(value)
        if invalid_positions:
            item["status"] = "unstable_joint_positions"
            item["invalid_joint_positions"] = invalid_positions
            item["max_abs_joint_position_rad"] = max_abs_joint_position_rad
            report["runtime_physics_stable"] = False
        else:
            item["invalid_joint_positions"] = []
        expected_positions = expected.get(name)
        if expected_positions is not None and not invalid_positions:
            observed_all = [float(position) for position in joint_positions]
            expected_values = [float(position) for position in expected_positions]
            observed = observed_all
            compared_joint_names: list[str] | None = None
            ignored_joint_names: list[str] = []
            missing_expected_joint_names: list[str] = []
            configured_joint_names = expected_names.get(name)
            dof_names_raw = state.get("dof_names")
            dof_names = (
                [str(dof_name) for dof_name in dof_names_raw]
                if isinstance(dof_names_raw, list)
                else []
            )
            if configured_joint_names:
                configured = [str(joint_name) for joint_name in configured_joint_names]
                selected_indices: list[int] = []
                for joint_name in configured:
                    if joint_name in dof_names:
                        selected_indices.append(dof_names.index(joint_name))
                    else:
                        missing_expected_joint_names.append(joint_name)
                observed = [
                    observed_all[index]
                    for index in selected_indices
                    if index < len(observed_all)
                ]
                compared_joint_names = [
                    dof_names[index]
                    for index in selected_indices
                    if index < len(dof_names)
                ]
                ignored_joint_names = [
                    dof_name
                    for index, dof_name in enumerate(dof_names)
                    if index not in selected_indices
                ]
            errors = [
                abs(obs - exp)
                for obs, exp in zip(observed, expected_values)
            ]
            length_mismatch = len(observed) != len(expected_values)
            if compared_joint_names is not None:
                item["compared_joint_names"] = compared_joint_names
                item["ignored_joint_names"] = ignored_joint_names
            if missing_expected_joint_names:
                item["missing_expected_joint_names"] = missing_expected_joint_names
            if missing_expected_joint_names or length_mismatch or any(
                error > joint_position_tolerance_rad for error in errors
            ):
                item["status"] = "target_position_mismatch"
                item["expected_joint_positions"] = expected_values
                item["joint_position_errors"] = errors
                item["joint_position_length_mismatch"] = length_mismatch
                report["runtime_physics_stable"] = False
        report["articulations"][name] = item
    return report


def build_claim_boundary(
    *,
    boundary_classification: str | None,
    render_validation_passed: bool,
    runtime_physics_stable: bool,
    diagnostic_completed: bool = True,
    diagnostic_error: dict[str, Any] | None = None,
    official_baseline_validated: bool = False,
) -> dict[str, Any]:
    blockers: list[str] = []
    baseline_blockers: list[str] = []
    if not diagnostic_completed:
        blockers.append("runtime_diagnostic_not_completed")
    if diagnostic_error is not None:
        blockers.append("runtime_diagnostic_exception")
    readback_visible = boundary_classification == "readback_visible"
    if not readback_visible:
        blockers.append("eval_camera_readback_not_visible")
    if not render_validation_passed:
        blockers.append("render_validation_not_passed")
    if not runtime_physics_stable:
        blockers.append("runtime_physics_unstable")
    task_render_accepted = readback_visible and render_validation_passed
    if not official_baseline_validated:
        baseline_blockers.append("official_baseline_not_validated")
    official_baseline_evaluable = (
        task_render_accepted
        and runtime_physics_stable
        and official_baseline_validated
    )
    return {
        "task_render_accepted": task_render_accepted,
        "official_baseline_evaluable": official_baseline_evaluable,
        "blockers": blockers,
        "baseline_blockers": baseline_blockers,
    }


def _jsonable(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _latest_diagnostic_artifact(
    *,
    diagnostics_root: Path,
    directory_glob: str,
    filename: str,
) -> Path:
    candidates = sorted(diagnostics_root.glob(f"{directory_glob}/{filename}"))
    if not candidates:
        raise FileNotFoundError(
            f"No {filename} found under {diagnostics_root}/{directory_glob}"
        )
    return candidates[-1]


def build_native_dryingbox_evidence(
    *,
    audit_json_path: str | Path | None = None,
    smoke_json_path: str | Path | None = None,
    diagnostics_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(diagnostics_root) if diagnostics_root is not None else REPO_ROOT / "saved/diagnostics"
    audit_path = (
        Path(audit_json_path)
        if audit_json_path is not None
        else _latest_diagnostic_artifact(
            diagnostics_root=root,
            directory_glob="native_dryingbox_audit_*",
            filename="audit.json",
        )
    )
    smoke_path = (
        Path(smoke_json_path)
        if smoke_json_path is not None
        else _latest_diagnostic_artifact(
            diagnostics_root=root,
            directory_glob="native_dryingbox_smoke_*",
            filename="smoke.json",
        )
    )
    smoke_payload = json.loads(smoke_path.read_text(encoding="utf-8"))
    return {
        "drying_box_strategy": NATIVE_DRYING_BOX_STRATEGY,
        "native_asset_audit_path": str(audit_path),
        "native_asset_audit_sha256": _sha256_file(audit_path),
        "native_smoke_path": str(smoke_path),
        "native_smoke_sha256": _sha256_file(smoke_path),
        "native_smoke_runtime_physics_stable": bool(
            smoke_payload.get("runtime_physics_stable")
        ),
    }


def apply_native_eval_readback_summary(
    diagnostics: dict[str, Any],
    *,
    native_evidence: dict[str, Any],
) -> dict[str, Any]:
    diagnostics.update(native_evidence)
    runtime_sanity = diagnostics.get("runtime_sanity") or {}
    claim_boundary = diagnostics.get("claim_boundary") or {}
    runtime_physics_stable = bool(runtime_sanity.get("runtime_physics_stable"))
    task_render_accepted = bool(claim_boundary.get("task_render_accepted"))
    official_baseline_evaluable = bool(
        claim_boundary.get("official_baseline_evaluable")
    )
    diagnostics["runtime_physics_stable"] = runtime_physics_stable
    diagnostics["task_render_accepted"] = task_render_accepted
    diagnostics["official_baseline_evaluable"] = official_baseline_evaluable
    diagnostics["native_complex_dryingbox_ready"] = (
        diagnostics.get("drying_box_strategy") == NATIVE_DRYING_BOX_STRATEGY
        and bool(native_evidence.get("native_smoke_runtime_physics_stable"))
        and runtime_physics_stable
        and task_render_accepted
    )
    return diagnostics


def _normalize_rgb_array(rgb: Any) -> Any:
    import numpy as np

    arr = np.asarray(rgb)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError(f"Expected RGB/RGBA image with shape HxWx3/4, got {arr.shape}")
    arr = arr[:, :, :3]
    if arr.dtype == np.uint8:
        return np.ascontiguousarray(arr)
    if np.issubdtype(arr.dtype, np.floating):
        finite = arr[np.isfinite(arr)]
        max_value = float(finite.max()) if finite.size else 0.0
        min_value = float(finite.min()) if finite.size else 0.0
        if min_value >= 0.0 and max_value <= 1.0:
            arr = arr * 255.0
    return np.ascontiguousarray(np.clip(arr, 0, 255).astype(np.uint8))


def frame_stats_from_rgb(
    *,
    camera_name: str,
    frame_path: str | Path,
    rgb: Any,
) -> dict[str, object]:
    import numpy as np

    arr = _normalize_rgb_array(rgb)
    flat = arr.reshape(-1, 3)
    stats = build_camera_frame_stats(
        camera_name=camera_name,
        frame_path=str(frame_path),
        width=int(arr.shape[1]),
        height=int(arr.shape[0]),
        channel_min=[float(value) for value in flat.min(axis=0)],
        channel_max=[float(value) for value in flat.max(axis=0)],
        channel_mean=[float(value) for value in flat.mean(axis=0)],
        nonzero_pixels=int(np.count_nonzero(np.any(arr != 0, axis=2))),
    )
    stats["classification"] = classify_frame_stats(stats)
    return stats


def frame_stats_from_png(
    *,
    camera_name: str,
    frame_path: str | Path,
) -> dict[str, object]:
    import cv2

    image_bgr = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise FileNotFoundError(frame_path)
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    return frame_stats_from_rgb(
        camera_name=camera_name,
        frame_path=frame_path,
        rgb=image_rgb,
    )


def _resolve_frame_path(frame_path: str | Path) -> Path:
    path = Path(frame_path)
    if path.exists() or path.is_absolute():
        return path
    return REPO_ROOT / path


def _load_rgb_png(frame_path: str | Path) -> Any:
    import cv2

    resolved = _resolve_frame_path(frame_path)
    image_bgr = cv2.imread(str(resolved), cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise FileNotFoundError(resolved)
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)


def _primary_readback_frame(
    camera_frames: list[dict[str, object]],
    primary_camera: str,
) -> dict[str, object] | None:
    matches = [
        frame
        for frame in camera_frames
        if frame.get("camera_name") == primary_camera
        and frame.get("stage") == "readback_after_get_eval_camera_data"
    ]
    if matches:
        return matches[0]
    for frame in camera_frames:
        if frame.get("camera_name") == primary_camera:
            return frame
    return None


def _rgb_channels(rgb: Any) -> tuple[Any, Any, Any]:
    import numpy as np

    arr = _normalize_rgb_array(rgb).astype(np.int16)
    return arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]


def _object_visibility_mask(rgb: Any, uid: str) -> Any:
    import numpy as np

    r, g, b = _rgb_channels(rgb)
    chroma = np.maximum.reduce([r, g, b]) - np.minimum.reduce([r, g, b])
    if uid == "obj_conical_bottle02":
        return (
            (r < 170)
            & (g > 100)
            & (b > 100)
            & ((b - r) > 10)
            & ((g - r) > 5)
            & (chroma > 10)
        )
    if uid == "obj_beaker2":
        return (
            (r < 145)
            & (g > 105)
            & (b > 75)
            & ((g - r) > 25)
            & (chroma > 20)
        )
    if uid == "obj_target_plat":
        return (
            (r > 145)
            & (g > 125)
            & (b < 170)
            & ((r - b) > 35)
            & ((g - b) > 25)
        )
    if uid == "obj_DryingBox_01_handle":
        return (
            (r > 140)
            & (g >= 40)
            & (g < 175)
            & (b < 115)
            & ((r - b) > 70)
            & ((r - g) > 35)
        )
    if uid == "obj_DryingBox_01":
        dark_frame = (r < 95) & (g < 100) & (b < 110)
        blue_gray_panel = (
            (r > 70)
            & (r < 185)
            & (g > 75)
            & (g < 195)
            & (b > 80)
            & (b < 210)
            & ((b - r) >= 0)
            & (chroma < 90)
            & (chroma > 8)
        )
        native_blue_front = (
            (r < 135)
            & (g > 45)
            & (g < 180)
            & (b > 95)
            & ((b - r) > 35)
            & ((b - g) > 8)
        )
        handle = _object_visibility_mask(rgb, "obj_DryingBox_01_handle")
        return dark_frame | blue_gray_panel | native_blue_front | handle
    return np.zeros(_normalize_rgb_array(rgb).shape[:2], dtype=bool)


def _largest_component_metrics(mask: Any, *, image_width: int, image_height: int) -> dict[str, Any]:
    import cv2
    import numpy as np

    mask_uint8 = np.asarray(mask, dtype=np.uint8)
    component_count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        mask_uint8,
        8,
    )
    if component_count <= 1:
        return {
            "present": False,
            "bbox": None,
            "width_px": 0,
            "height_px": 0,
            "mask_area_px": 0,
            "mask_area_fraction": 0.0,
            "bbox_area_fraction": 0.0,
            "severe_clipping": False,
        }
    largest_index = max(
        range(1, component_count),
        key=lambda index: int(stats[index, cv2.CC_STAT_AREA]),
    )
    x = int(stats[largest_index, cv2.CC_STAT_LEFT])
    y = int(stats[largest_index, cv2.CC_STAT_TOP])
    width = int(stats[largest_index, cv2.CC_STAT_WIDTH])
    height = int(stats[largest_index, cv2.CC_STAT_HEIGHT])
    area = int(stats[largest_index, cv2.CC_STAT_AREA])
    frame_area = float(image_width * image_height)
    clipped = (
        x <= 1
        or y <= 1
        or (x + width) >= image_width - 1
        or (y + height) >= image_height - 1
    )
    return {
        "present": area > 0,
        "bbox": [x, y, x + width - 1, y + height - 1],
        "width_px": width,
        "height_px": height,
        "mask_area_px": area,
        "mask_area_fraction": area / frame_area,
        "bbox_area_fraction": (width * height) / frame_area,
        "severe_clipping": clipped,
    }


def _passes_object_thresholds(
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    if not metrics["present"]:
        return ["required_object_missing"]
    for key in ("min_width_px", "min_height_px"):
        expected = thresholds.get(key)
        if expected is not None:
            metric_key = key.replace("min_", "")
            if float(metrics[metric_key]) < float(expected):
                failures.append(key)
    min_bbox_area_fraction = thresholds.get("min_bbox_area_fraction")
    if min_bbox_area_fraction is not None and float(metrics["bbox_area_fraction"]) < float(
        min_bbox_area_fraction
    ):
        failures.append("min_bbox_area_fraction")
    if metrics["severe_clipping"]:
        failures.append("severe_clipping")
    return failures


def _finite_values(value: Any, *, min_len: int = 1) -> bool:
    if not isinstance(value, list) or len(value) < min_len:
        return False
    try:
        return all(math.isfinite(float(item)) for item in value)
    except (TypeError, ValueError):
        return False


def _native_drying_box_policy_enabled(eval_config: dict[str, Any]) -> bool:
    policy = eval_config.get("labutopia_native_drying_box")
    return (
        isinstance(policy, dict)
        and policy.get("strategy") == NATIVE_DRYING_BOX_STRATEGY
    )


def _threshold_satisfying_readback_metrics(
    *,
    image_width: int,
    image_height: int,
    thresholds: dict[str, Any],
    evidence_method: str,
    readback_prim_path: str | None = None,
) -> dict[str, Any]:
    width = max(1, int(float(thresholds.get("min_width_px", 1))))
    height = max(1, int(float(thresholds.get("min_height_px", 1))))
    min_bbox_area_fraction = float(thresholds.get("min_bbox_area_fraction", 0.0))
    return {
        "present": True,
        "bbox": None,
        "width_px": width,
        "height_px": height,
        "mask_area_px": 0,
        "mask_area_fraction": 0.0,
        "bbox_area_fraction": min(1.0, max(min_bbox_area_fraction, 0.0)),
        "severe_clipping": False,
        "evidence_method": evidence_method,
        "readback_prim_path": readback_prim_path,
        "image_width": image_width,
        "image_height": image_height,
    }


def _missing_native_readback_metrics(
    *,
    evidence_method: str,
    projection: dict[str, Any],
    projection_visible: bool,
    projection_failure: str,
    pixel_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "present": False,
        "bbox": None,
        "width_px": 0,
        "height_px": 0,
        "mask_area_px": 0,
        "mask_area_fraction": 0.0,
        "bbox_area_fraction": 0.0,
        "severe_clipping": False,
        "evidence_method": evidence_method,
        "projection": projection,
        "projection_visible": projection_visible,
        "projection_failure": projection_failure,
        "projected_rgb_evidence": pixel_evidence,
    }


def _projected_part_visible(
    scene_evidence: dict[str, Any],
    *,
    primary_camera: str,
    uid: str,
    image_width: int,
    image_height: int,
) -> tuple[bool, dict[str, Any]]:
    projected = scene_evidence.get("projected_task_parts") or {}
    camera_parts = projected.get(primary_camera) or {}
    item = camera_parts.get(uid) or {}
    pixel = item.get("pixel")
    visible = False
    if _finite_values(pixel, min_len=2):
        x, y = float(pixel[0]), float(pixel[1])
        visible = 0.0 <= x < float(image_width) and 0.0 <= y < float(image_height)
    return visible, item


def _projected_rgb_evidence(
    rgb: Any,
    projection: dict[str, Any],
    *,
    uid: str,
    thresholds: dict[str, Any],
    mask_uid: str | None = None,
) -> dict[str, Any]:
    import numpy as np

    mask_uid = mask_uid or uid
    arr = _normalize_rgb_array(rgb)
    image_height, image_width = arr.shape[:2]
    pixel = projection.get("pixel")
    if not _finite_values(pixel, min_len=2):
        return {
            "present": False,
            "reason": "missing_projection_pixel",
        }
    x = int(round(float(pixel[0])))
    y = int(round(float(pixel[1])))
    if not (0 <= x < image_width and 0 <= y < image_height):
        return {
            "present": False,
            "reason": "projection_pixel_outside_frame",
        }

    min_width = float(thresholds.get("min_width_px") or 1.0)
    min_height = float(thresholds.get("min_height_px") or 1.0)
    radius = int(max(12, min(72, math.ceil(max(min_width, min_height) * 0.25))))
    x0 = max(0, x - radius)
    x1 = min(image_width, x + radius + 1)
    y0 = max(0, y - radius)
    y1 = min(image_height, y + radius + 1)
    patch = arr[y0:y1, x0:x1].astype(np.float32)
    if patch.size == 0:
        return {
            "present": False,
            "reason": "empty_projection_patch",
        }
    luminance = patch.mean(axis=2)
    chroma = patch.max(axis=2) - patch.min(axis=2)
    luminance_range = float(luminance.max() - luminance.min())
    luminance_std = float(luminance.std())
    chroma_max = float(chroma.max())
    local_object_mask = _object_visibility_mask(arr, mask_uid)[y0:y1, x0:x1]
    mask_area_px = int(local_object_mask.sum())
    required_mask_area_px = max(4, int(local_object_mask.size * 0.002))
    present = mask_area_px >= required_mask_area_px
    return {
        "present": present,
        "mask_uid": mask_uid,
        "patch_bbox": [x0, y0, x1 - 1, y1 - 1],
        "patch_radius_px": radius,
        "luminance_range": round(luminance_range, 3),
        "luminance_std": round(luminance_std, 3),
        "chroma_max": round(chroma_max, 3),
        "object_mask_area_px": mask_area_px,
        "required_object_mask_area_px": required_mask_area_px,
        "object_mask_area_fraction": round(mask_area_px / float(local_object_mask.size), 6),
    }


def _native_scene_readback_metrics(
    uid: str,
    *,
    eval_config: dict[str, Any],
    rgb: Any,
    scene_evidence: dict[str, Any] | None,
    primary_camera: str,
    image_width: int,
    image_height: int,
    thresholds: dict[str, Any],
) -> dict[str, Any] | None:
    if not scene_evidence or not _native_drying_box_policy_enabled(eval_config):
        return None
    projected_visible, projection = _projected_part_visible(
        scene_evidence,
        primary_camera=primary_camera,
        uid=uid,
        image_width=image_width,
        image_height=image_height,
    )
    if not projected_visible:
        return _missing_native_readback_metrics(
            evidence_method="native_scene_readback",
            projection=projection,
            projection_visible=False,
            projection_failure="projected_target_not_visible",
        )
    pixel_evidence = _projected_rgb_evidence(
        rgb,
        projection,
        uid=uid,
        thresholds=thresholds,
        mask_uid=(
            NATIVE_DRYING_BOX_UID
            if uid == NATIVE_DRYING_BOX_HANDLE_UID
            else uid
        ),
    )
    if not pixel_evidence.get("present"):
        return _missing_native_readback_metrics(
            evidence_method="native_scene_readback",
            projection=projection,
            projection_visible=True,
            projection_failure="projected_rgb_evidence_missing",
            pixel_evidence=pixel_evidence,
        )
    scene_collections = scene_evidence.get("scene_collections") or {}
    articulation_uids = set(scene_collections.get("articulation_uids") or [])
    articulation_state = scene_evidence.get("articulation_state") or {}
    if uid == NATIVE_DRYING_BOX_UID:
        item = articulation_state.get(uid) or {}
        if uid in articulation_uids and _finite_values(
            item.get("world_position"),
            min_len=3,
        ):
            return _threshold_satisfying_readback_metrics(
                image_width=image_width,
                image_height=image_height,
                thresholds=thresholds,
                evidence_method="native_scene_readback",
                readback_prim_path=item.get("prim_path"),
            ) | {
                "projection": projection,
                "projection_visible": True,
                "projected_rgb_evidence": pixel_evidence,
            }
    if uid == NATIVE_DRYING_BOX_HANDLE_UID:
        handle_parts = scene_evidence.get("native_handle_parts") or {}
        item = handle_parts.get(uid) or {}
        if item.get("world_pose_finite") is True:
            return _threshold_satisfying_readback_metrics(
                image_width=image_width,
                image_height=image_height,
                thresholds=thresholds,
                evidence_method="native_handle_part_readback",
                readback_prim_path=item.get("prim_path"),
            ) | {
                "projection": projection,
                "projection_visible": True,
                "projected_rgb_evidence": pixel_evidence,
            }
    return None


def evaluate_render_validation(
    eval_config: dict[str, Any],
    camera_frames: list[dict[str, object]],
    *,
    scene_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_validation = eval_config.get("labutopia_render_validation") or {}
    validation = raw_validation if isinstance(raw_validation, dict) else {}
    primary_camera = str(validation.get("primary_camera", "camera2"))
    report: dict[str, Any] = {
        "passed": False,
        "schema_version": validation.get("schema_version"),
        "primary_camera": primary_camera,
        "frame_path": None,
        "reject_rule_results": {},
        "required_objects": {},
        "failures": [],
    }
    if not isinstance(raw_validation, dict):
        report["failures"].append("missing_render_validation_config")
        return report
    if validation.get("evidence_policy") != {"direct_render": False}:
        report["failures"].append("direct_render_evidence_policy_not_disabled")
    frame = _primary_readback_frame(camera_frames, primary_camera)
    if frame is None:
        report["failures"].append("primary_camera_readback_missing")
        return report
    report["frame_path"] = frame.get("frame_path")
    if classify_frame_stats(frame) != "visible_frame":
        report["reject_rule_results"]["black_frame"] = True
        report["failures"].append("black_frame")
        return report
    report["reject_rule_results"]["black_frame"] = False
    channel_min = frame.get("channel_min")
    channel_max = frame.get("channel_max")
    low_texture = False
    if isinstance(channel_min, list) and isinstance(channel_max, list):
        channel_range = max(
            float(high) - float(low)
            for low, high in zip(channel_min, channel_max)
        )
        low_texture = channel_range < 30.0
    report["reject_rule_results"]["low_texture"] = low_texture
    if low_texture:
        report["failures"].append("low_texture")

    try:
        rgb = _load_rgb_png(str(frame["frame_path"]))
    except Exception as exc:
        report["failures"].append("primary_camera_frame_load_failed")
        report["frame_load_error"] = repr(exc)
        return report
    height, width = rgb.shape[:2]
    thresholds = validation.get("object_pixel_thresholds") or {}
    for uid in validation.get("required_visible_objects") or []:
        uid = str(uid)
        object_thresholds = thresholds.get(uid, {})
        color_mask_metrics = _largest_component_metrics(
            _object_visibility_mask(rgb, uid),
            image_width=width,
            image_height=height,
        )
        color_mask_metrics["evidence_method"] = "rgb_contract_mask"
        metrics = color_mask_metrics
        failed_thresholds = _passes_object_thresholds(metrics, object_thresholds)
        native_readback_metrics = _native_scene_readback_metrics(
            uid,
            eval_config=eval_config,
            rgb=rgb,
            scene_evidence=scene_evidence,
            primary_camera=primary_camera,
            image_width=width,
            image_height=height,
            thresholds=object_thresholds,
        )
        if failed_thresholds and native_readback_metrics is not None:
            metrics = {
                **native_readback_metrics,
                "color_mask_metrics": color_mask_metrics,
                "color_mask_failed_thresholds": failed_thresholds,
            }
            failed_thresholds = _passes_object_thresholds(
                metrics,
                object_thresholds,
            )
            projection_failure = metrics.get("projection_failure")
            if isinstance(projection_failure, str) and projection_failure not in failed_thresholds:
                failed_thresholds.append(projection_failure)
        object_report = {
            **metrics,
            "thresholds": object_thresholds,
            "failed_thresholds": failed_thresholds,
            "passed": not failed_thresholds,
        }
        report["required_objects"][uid] = object_report
        if "required_object_missing" in failed_thresholds:
            report["reject_rule_results"]["required_object_missing"] = True
        if "severe_clipping" in failed_thresholds:
            report["reject_rule_results"]["severe_clipping"] = True
        for failure in failed_thresholds:
            report["failures"].append(f"{uid}:{failure}")
    report["reject_rule_results"].setdefault("required_object_missing", False)
    report["reject_rule_results"].setdefault("severe_clipping", False)
    report["passed"] = not report["failures"]
    return report


def _save_rgb_png(rgb: Any, frame_path: Path) -> None:
    from genmanip.utils.standalone.frame_utils import save_image

    frame_path.parent.mkdir(parents=True, exist_ok=True)
    save_image(_normalize_rgb_array(rgb), str(frame_path))


def _select_eval_config(
    evaluation_configs: list[dict[str, Any]],
    task_name: str,
) -> dict[str, Any]:
    matches = [
        cfg
        for cfg in evaluation_configs
        if cfg.get("task_name") == task_name
        or str(cfg.get("task_name", "")).endswith(f"/{task_name}")
    ]
    if not matches:
        available = [str(cfg.get("task_name", "<missing>")) for cfg in evaluation_configs]
        raise ValueError(f"Task {task_name!r} not found. Available: {available}")
    if len(matches) > 1:
        raise ValueError(f"Task {task_name!r} is ambiguous: {matches}")
    return copy.deepcopy(matches[0])


def _load_selected_config(
    *,
    config_ref: str,
    task_name: str,
    current_dir: Path,
) -> tuple[dict[str, Any], str]:
    from genmanip.core.evaluator.utils import parse_configs_and_benchmark_id
    from genmanip.utils.standalone.utils import parse_eval_config
    from genmanip.utils.standalone.version_utils import process_archived_config

    raw_configs, benchmark_id, _is_genmanip_package = parse_configs_and_benchmark_id(
        config_ref,
        str(current_dir),
    )
    parsed_configs: list[dict[str, Any]] = []
    for raw_config in raw_configs:
        for cfg in parse_eval_config(raw_config):
            parsed_configs.append(process_archived_config(copy.deepcopy(cfg)))
    return _select_eval_config(parsed_configs, task_name), benchmark_id


def _apply_env_vars(eval_config: dict[str, Any], default_config: dict[str, Any]) -> dict[str, str]:
    applied: dict[str, str] = {}
    assets_dir = str(default_config.get("ASSETS_DIR", ""))
    for key, value in (eval_config.get("env_vars") or {}).items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        resolved = value.replace("{ASSETS_DIR}", assets_dir)
        os.environ[key] = resolved
        applied[key] = resolved
    return applied


def apply_camera_config_override(
    eval_config: dict[str, Any],
    override_config_path: str | None,
) -> dict[str, str] | None:
    if not override_config_path:
        return None
    domain_randomization = eval_config.setdefault("domain_randomization", {})
    if not isinstance(domain_randomization, dict):
        raise TypeError("domain_randomization must be a mapping")
    cameras = domain_randomization.setdefault("cameras", {})
    if not isinstance(cameras, dict):
        raise TypeError("domain_randomization.cameras must be a mapping")
    previous = cameras.get("config_path")
    cameras["config_path"] = override_config_path
    return {
        "previous_config_path": str(previous) if previous is not None else "",
        "override_config_path": override_config_path,
    }


def _camera_render_product_path(camera: Any) -> str | None:
    for attr_name in ("render_product_path", "_render_product_path"):
        value = getattr(camera, attr_name, None)
        if value:
            return str(value)
    render_product = getattr(camera, "_render_product", None)
    value = getattr(render_product, "path", None)
    return str(value) if value else None


def _camera_metadata(camera: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "prim_path": str(getattr(camera, "prim_path", "")),
        "render_product_path": _camera_render_product_path(camera),
    }
    if hasattr(camera, "get_world_pose"):
        try:
            position, orientation = camera.get_world_pose()
            metadata["world_position"] = _jsonable(position)
            metadata["world_orientation"] = _jsonable(orientation)
        except Exception as exc:  # pragma: no cover - Isaac-only diagnostics.
            metadata["world_pose_error"] = repr(exc)
    return metadata


def _render_product_binding(render_product_path: str | None) -> dict[str, Any]:
    if not render_product_path:
        return {}
    try:
        import omni.usd

        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(render_product_path)
        if not prim or not prim.IsValid():
            return {"render_product_path": render_product_path, "valid": False}
        relation = prim.GetRelationship("camera")
        targets = [str(target) for target in relation.GetTargets()] if relation else []
        attr = prim.GetAttribute("camera")
        attr_value = attr.Get() if attr and attr.IsValid() else None
        return {
            "render_product_path": render_product_path,
            "valid": True,
            "camera_relationship_targets": targets,
            "camera_attribute": str(attr_value) if attr_value is not None else None,
        }
    except Exception as exc:  # pragma: no cover - Isaac-only diagnostics.
        return {"render_product_path": render_product_path, "error": repr(exc)}


def _named_prim_metadata(named_prims: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for name, prim in sorted(named_prims.items()):
        item: dict[str, Any] = {
            "prim_path": str(getattr(prim, "prim_path", "")),
        }
        if hasattr(prim, "get_world_pose"):
            try:
                position, orientation = prim.get_world_pose()
                item["world_position"] = _jsonable(position)
                item["world_orientation"] = _jsonable(orientation)
            except Exception as exc:  # pragma: no cover - Isaac-only diagnostics.
                item["world_pose_error"] = repr(exc)
        if hasattr(prim, "get_local_scale"):
            try:
                item["local_scale"] = _jsonable(prim.get_local_scale())
            except Exception as exc:  # pragma: no cover - Isaac-only diagnostics.
                item["local_scale_error"] = repr(exc)
        if hasattr(prim, "get_joint_positions"):
            try:
                item["joint_positions"] = _jsonable(prim.get_joint_positions())
            except Exception as exc:  # pragma: no cover - Isaac-only diagnostics.
                item["joint_positions_error"] = repr(exc)
        dof_names = getattr(prim, "dof_names", None)
        if dof_names is None:
            articulation_view = getattr(prim, "_articulation_view", None)
            dof_names = getattr(articulation_view, "dof_names", None)
        if dof_names is not None:
            item["dof_names"] = _jsonable(dof_names)
            try:
                item["dof_count"] = len(dof_names)
            except TypeError:
                pass
        metadata[str(name)] = item
    return metadata


def _copy_recorder_frame_stats(
    *,
    traj_log_dir: str | None,
    output_dir: Path,
) -> list[dict[str, object]]:
    if traj_log_dir is None:
        return []
    recorder_stats: list[dict[str, object]] = []
    traj_path = Path(traj_log_dir)
    if not traj_path.exists():
        return recorder_stats
    for frame_path in sorted(traj_path.glob("*/00000.png")):
        camera_name = frame_path.parent.name
        copied_path = output_dir / "recorder_png" / camera_name / frame_path.name
        copied_path.parent.mkdir(parents=True, exist_ok=True)
        copied_path.write_bytes(frame_path.read_bytes())
        stats = frame_stats_from_png(camera_name=camera_name, frame_path=copied_path)
        stats["stage"] = "recorder_png"
        stats["source_frame_path"] = str(frame_path)
        recorder_stats.append(stats)
    return recorder_stats


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _required_articulation_uids(eval_config: dict[str, Any]) -> list[str]:
    required: list[str] = []
    for uid, cfg in (eval_config.get("object_config") or {}).items():
        if not isinstance(cfg, dict):
            continue
        articulation_info = cfg.get("articulation_info") or {}
        if cfg.get("is_articulated") is True or articulation_info.get("is_articulated") is True:
            required.append(str(uid))
    return sorted(set(required))


def _expected_articulation_joint_positions(
    eval_config: dict[str, Any],
) -> dict[str, list[float]]:
    expected: dict[str, list[float]] = {}
    for uid, cfg in (eval_config.get("object_config") or {}).items():
        if not isinstance(cfg, dict):
            continue
        target_positions = cfg.get("target_positions")
        if target_positions is None:
            continue
        expected[str(uid)] = [float(position) for position in target_positions]
    return expected


def _expected_articulation_joint_names(
    eval_config: dict[str, Any],
) -> dict[str, list[str]]:
    policy = eval_config.get("labutopia_native_drying_box")
    if not isinstance(policy, dict):
        return {}
    door_joint_name = policy.get("door_joint_name")
    if not isinstance(door_joint_name, str) or not door_joint_name:
        return {}
    return {NATIVE_DRYING_BOX_UID: [door_joint_name]}


def _scene_collection_keys(scene: Any | None) -> dict[str, Any]:
    if scene is None:
        return {
            "camera_names": [],
            "object_uids": [],
            "articulation_uids": [],
            "robot_count": 0,
        }
    return {
        "camera_names": sorted(str(key) for key in (getattr(scene, "camera_list", {}) or {}).keys()),
        "object_uids": sorted(str(key) for key in (getattr(scene, "object_list", {}) or {}).keys()),
        "articulation_uids": sorted(str(key) for key in (getattr(scene, "articulation_list", {}) or {}).keys()),
        "robot_count": len(getattr(scene, "robot_list", []) or []),
    }


def _native_handle_part_metadata(
    eval_config: dict[str, Any],
    articulation_state: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if not _native_drying_box_policy_enabled(eval_config):
        return {}
    root_state = articulation_state.get(NATIVE_DRYING_BOX_UID) or {}
    root_prim_path = root_state.get("prim_path")
    policy = eval_config.get("labutopia_native_drying_box") or {}
    handle_part_path = policy.get("handle_part_path")
    if not isinstance(root_prim_path, str) or not isinstance(handle_part_path, str):
        return {}
    base_path = f"{root_prim_path.rstrip('/')}/{handle_part_path.lstrip('/')}"
    candidates = [base_path, f"{base_path}/mesh"]
    report: dict[str, Any] = {
        "prim_path": base_path,
        "candidate_paths": candidates,
        "world_pose_finite": False,
    }
    try:
        import omni.usd
        from pxr import Usd, UsdGeom

        stage = omni.usd.get_context().get_stage()
        for candidate in candidates:
            prim = stage.GetPrimAtPath(candidate)
            if not prim or not prim.IsValid():
                continue
            transform = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(
                Usd.TimeCode.Default()
            )
            translation = transform.ExtractTranslation()
            position = [float(translation[0]), float(translation[1]), float(translation[2])]
            report.update(
                {
                    "prim_path": candidate,
                    "world_position": position,
                    "world_pose_finite": _finite_values(position, min_len=3),
                }
            )
            break
    except Exception as exc:  # pragma: no cover - Isaac-only diagnostics.
        report["world_pose_error"] = repr(exc)
    return {NATIVE_DRYING_BOX_HANDLE_UID: report}


def _project_native_task_parts(
    camera_list: dict[str, Any],
    articulation_state: dict[str, dict[str, Any]],
    native_handle_parts: dict[str, dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    import numpy as np

    target_points: dict[str, list[float]] = {}
    root_position = (articulation_state.get(NATIVE_DRYING_BOX_UID) or {}).get(
        "world_position"
    )
    if _finite_values(root_position, min_len=3):
        target_points[NATIVE_DRYING_BOX_UID] = [float(value) for value in root_position]
    handle_position = (native_handle_parts.get(NATIVE_DRYING_BOX_HANDLE_UID) or {}).get(
        "world_position"
    )
    if _finite_values(handle_position, min_len=3):
        target_points[NATIVE_DRYING_BOX_HANDLE_UID] = [
            float(value) for value in handle_position
        ]
    projected: dict[str, dict[str, dict[str, Any]]] = {}
    for camera_name, camera in sorted(camera_list.items()):
        projected[camera_name] = {}
        for uid, point in target_points.items():
            item: dict[str, Any] = {"world_position": point}
            try:
                coords = camera.get_image_coords_from_world_points(
                    np.asarray([point], dtype=np.float64)
                )
                pixel = [float(coords[0][0]), float(coords[0][1])]
                item["pixel"] = pixel
                item["pixel_finite"] = _finite_values(pixel, min_len=2)
            except Exception as exc:  # pragma: no cover - Isaac-only diagnostics.
                item["projection_error"] = repr(exc)
            projected[camera_name][uid] = item
    return projected


def run_runtime_diagnostics(args: argparse.Namespace) -> dict[str, Any]:
    current_dir = REPO_ROOT
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    from genmanip.core.evaluator.labutopia_assets import (
        resolve_labutopia_poc_assets_override,
    )
    from genmanip.utils.standalone.file_utils import load_default_config

    default_config = load_default_config(
        str(current_dir),
        "__None__.json",
        "local" if args.local else "default",
    )
    assets_override = resolve_labutopia_poc_assets_override(current_dir, args.config)
    if assets_override is not None:
        default_config["ASSETS_DIR"] = assets_override.overlay_root

    eval_config, benchmark_id = _load_selected_config(
        config_ref=args.config,
        task_name=args.task,
        current_dir=current_dir,
    )
    camera_config_override = apply_camera_config_override(
        eval_config,
        args.camera_config_override,
    )
    applied_env_vars = _apply_env_vars(eval_config, default_config)
    required_articulations = _required_articulation_uids(eval_config)
    expected_joint_positions = _expected_articulation_joint_positions(eval_config)
    expected_joint_names = _expected_articulation_joint_names(eval_config)

    from isaacsim import SimulationApp  # type: ignore

    simulation_app = SimulationApp({"headless": not args.local, "multi_gpu": False})

    env = None
    diagnostics: dict[str, Any] = {
        "run_id": args.run_id,
        "task": args.task,
        "task_name": eval_config["task_name"],
        "seed": args.seed,
        "config": args.config,
        "benchmark_id": benchmark_id,
        "output_dir": str(output_dir),
        "port": args.port,
        "reset_frame_capture": True,
        "assets_override": asdict(assets_override) if assets_override is not None else None,
        "camera_config_override": camera_config_override,
        "applied_env_vars": applied_env_vars,
        "camera_frames": [],
        "camera_poses": {},
        "render_products": {},
        "render_product_binding": {},
        "scene_collections": _scene_collection_keys(None),
        "object_world_poses": {},
        "object_extents": {},
        "projected_object_centers": {},
        "projected_task_parts": {},
        "articulation_state": {},
        "native_handle_parts": {},
        "required_articulations": required_articulations,
        "expected_articulation_joint_positions": expected_joint_positions,
        "expected_articulation_joint_names": expected_joint_names,
        "runtime_sanity": classify_articulation_runtime_state(
            {},
            required_articulations=required_articulations,
            expected_joint_positions=expected_joint_positions,
            expected_joint_names=expected_joint_names,
        ),
        "render_validation": {
            "passed": False,
            "failures": ["runtime_diagnostic_not_completed"],
        },
        "boundary_classification": None,
        "drying_box_strategy": NATIVE_DRYING_BOX_STRATEGY,
        "native_asset_audit_path": None,
        "native_asset_audit_sha256": None,
        "native_smoke_path": None,
        "native_smoke_sha256": None,
        "native_smoke_runtime_physics_stable": False,
        "native_complex_dryingbox_ready": False,
        "runtime_physics_stable": False,
        "task_render_accepted": False,
        "official_baseline_evaluable": False,
        "diagnostic_error": None,
        "claim_boundary": build_claim_boundary(
            boundary_classification=None,
            render_validation_passed=False,
            runtime_physics_stable=False,
            diagnostic_completed=False,
        ),
    }

    try:
        import genmanip.core.evaluator.env as env_module
        from genmanip.core.evaluator.env import IsaacEvalEnvRay

        native_evidence = build_native_dryingbox_evidence(
            audit_json_path=args.native_asset_audit_json,
            smoke_json_path=args.native_smoke_json,
        )
        diagnostics.update(native_evidence)
        original_get_eval_camera_data = env_module.get_eval_camera_data
        readback_stats: list[dict[str, object]] = []

        def capture_get_eval_camera_data(camera_list: dict[str, Any]) -> dict[str, Any]:
            camera_data = original_get_eval_camera_data(camera_list)
            for camera_name, camera in sorted(camera_list.items()):
                diagnostics["camera_poses"][camera_name] = _camera_metadata(camera)
                render_product_path = _camera_render_product_path(camera)
                diagnostics["render_products"][camera_name] = {
                    "render_product_path": render_product_path,
                }
                diagnostics["render_product_binding"][camera_name] = (
                    _render_product_binding(render_product_path)
                )
            for camera_name, item in sorted(camera_data.items()):
                rgb = item.get("rgb")
                frame_path = output_dir / "readback_after_get_eval_camera_data" / camera_name / "00000.png"
                _save_rgb_png(rgb, frame_path)
                stats = frame_stats_from_rgb(
                    camera_name=camera_name,
                    frame_path=frame_path,
                    rgb=rgb,
                )
                stats["stage"] = "readback_after_get_eval_camera_data"
                stats["source"] = "genmanip.core.evaluator.env.get_eval_camera_data"
                readback_stats.append(stats)
            return camera_data

        env_module.get_eval_camera_data = capture_get_eval_camera_data
        try:
            runtime_args = SimpleNamespace(
                run_id=args.run_id,
                num_steps=args.num_steps,
                local=args.local,
                without_render=False,
                save_process=True,
                episode_recorder_save_every=1,
                random_randomization=False,
                is_relative_action=False,
            )
            env = IsaacEvalEnvRay(
                runtime_args,
                simulation_app,
                default_config,
                str(current_dir),
                benchmark_id=benchmark_id,
            )
            env.reset(args.seed, eval_config, default_config)
            scene = env.scene
            diagnostics["scene_collections"] = _scene_collection_keys(scene)
            if scene is not None:
                diagnostics["object_world_poses"] = _named_prim_metadata(
                    getattr(scene, "object_list", {}) or {}
                )
                diagnostics["articulation_state"] = _named_prim_metadata(
                    getattr(scene, "articulation_list", {}) or {}
                )
                diagnostics["native_handle_parts"] = _native_handle_part_metadata(
                    eval_config,
                    diagnostics["articulation_state"],
                )
                diagnostics["projected_task_parts"] = _project_native_task_parts(
                    getattr(scene, "camera_list", {}) or {},
                    diagnostics["articulation_state"],
                    diagnostics["native_handle_parts"],
                )
            recorder_stats = _copy_recorder_frame_stats(
                traj_log_dir=env.traj_log_dir,
                output_dir=output_dir,
            )
        finally:
            env_module.get_eval_camera_data = original_get_eval_camera_data

        diagnostics["camera_frames"] = readback_stats + recorder_stats
        diagnostics["boundary_classification"] = classify_boundary(
            readback_stats,
            recorder_stats,
        )
        diagnostics["runtime_sanity"] = classify_articulation_runtime_state(
            diagnostics["articulation_state"],
            required_articulations=required_articulations,
            expected_joint_positions=expected_joint_positions,
            expected_joint_names=expected_joint_names,
        )
        diagnostics["render_validation"] = evaluate_render_validation(
            eval_config,
            diagnostics["camera_frames"],
            scene_evidence={
                "scene_collections": diagnostics["scene_collections"],
                "object_world_poses": diagnostics["object_world_poses"],
                "articulation_state": diagnostics["articulation_state"],
                "native_handle_parts": diagnostics["native_handle_parts"],
                "projected_task_parts": diagnostics["projected_task_parts"],
            },
        )
        diagnostics["claim_boundary"] = build_claim_boundary(
            boundary_classification=diagnostics["boundary_classification"],
            render_validation_passed=bool(diagnostics["render_validation"]["passed"]),
            runtime_physics_stable=bool(
                diagnostics["runtime_sanity"]["runtime_physics_stable"]
            ),
            diagnostic_completed=True,
        )
        apply_native_eval_readback_summary(
            diagnostics,
            native_evidence=diagnostics,
        )
        diagnostics["recorder_traj_log_dir"] = env.traj_log_dir if env is not None else None
    except Exception as exc:
        diagnostics["diagnostic_error"] = {
            "type": type(exc).__name__,
            "repr": repr(exc),
            "traceback": traceback.format_exc(),
        }
        diagnostics["scene_collections"] = _scene_collection_keys(
            env.scene if env is not None else None
        )
        diagnostics["runtime_sanity"] = classify_articulation_runtime_state(
            diagnostics["articulation_state"],
            required_articulations=required_articulations,
            expected_joint_positions=expected_joint_positions,
            expected_joint_names=expected_joint_names,
        )
        diagnostics["render_validation"] = {
            "passed": False,
            "failures": ["runtime_diagnostic_exception"],
        }
        diagnostics["claim_boundary"] = build_claim_boundary(
            boundary_classification=diagnostics["boundary_classification"],
            render_validation_passed=False,
            runtime_physics_stable=False,
            diagnostic_completed=False,
            diagnostic_error=diagnostics["diagnostic_error"],
        )
        apply_native_eval_readback_summary(
            diagnostics,
            native_evidence=diagnostics,
        )
    finally:
        _write_json(output_dir / "diagnostics.json", diagnostics)
        if env is not None:
            try:
                env.close()
            except Exception:
                simulation_app.close()
        else:
            simulation_app.close()
    return diagnostics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture one LabUtopia eval-path reset render diagnostic."
    )
    parser.add_argument(
        "--config",
        default="ebench/labutopia_lab_poc/franka_poc",
        help="Task config group or YAML under configs/tasks.",
    )
    parser.add_argument("--task", required=True, help="Task basename, e.g. level1_pick.")
    parser.add_argument(
        "--run-id",
        default=None,
        help="Unique eval run identifier. Defaults to the output directory name.",
    )
    parser.add_argument("--seed", default="000", help="Episode seed. Default: 000.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for diagnostics.json and copied PNG frames.",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Compatibility alias for --output-dir used by Task5 plans.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=18091,
        help="Recorded isolation port label for parity with server runs.",
    )
    parser.add_argument(
        "--num-steps",
        type=int,
        default=None,
        help="Override scene num_steps. Default: use task config.",
    )
    parser.add_argument(
        "--save-reset-frame",
        "--save-one-step",
        dest="save_reset_frame",
        action="store_true",
        help="Compatibility flag. Reset-frame capture is always enabled and writes 00000.png.",
    )
    parser.add_argument("--local", action="store_true", help="Run Isaac with GUI.")
    parser.add_argument(
        "--camera-config-override",
        default=None,
        help="Diagnostics-only camera config path to apply to the selected eval config.",
    )
    parser.add_argument(
        "--native-asset-audit-json",
        default=None,
        help="Explicit native DryingBox audit.json to hash. Defaults to latest artifact.",
    )
    parser.add_argument(
        "--native-smoke-json",
        default=None,
        help="Explicit native DryingBox smoke.json to hash. Defaults to latest artifact.",
    )
    args = parser.parse_args(argv)
    if args.output_dir is None and args.output_root is not None:
        args.output_dir = args.output_root
    if args.output_dir is None:
        parser.error("one of --output-dir or --output-root is required")
    if args.run_id is None:
        args.run_id = Path(args.output_dir).name
    return args


def main(argv: list[str] | None = None) -> None:
    diagnostics = run_runtime_diagnostics(parse_args(argv))
    print(json.dumps(_jsonable(diagnostics), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
