from __future__ import annotations

from typing import Any


VALID_CAMERA_AXES = {"world", "ros", "usd"}


def _camera_axes_from_config(
    camera_cfg: dict[str, Any], default_camera_axes: str
) -> str:
    camera_axes = camera_cfg.get("camera_axes", default_camera_axes)
    if camera_axes not in VALID_CAMERA_AXES:
        raise ValueError(
            f"camera_axes must be one of {sorted(VALID_CAMERA_AXES)}, got {camera_axes!r}"
        )
    return str(camera_axes)


def set_camera_local_pose_from_config(
    camera: Any,
    camera_cfg: dict[str, Any],
    *,
    default_camera_axes: str = "world",
) -> bool:
    if "position" not in camera_cfg or "orientation" not in camera_cfg:
        return False
    camera.set_local_pose(
        translation=camera_cfg["position"],
        orientation=camera_cfg["orientation"],
        camera_axes=_camera_axes_from_config(camera_cfg, default_camera_axes),
    )
    return True
