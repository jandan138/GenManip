"""Small preprocessing rules that do not require importing Isaac modules."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _as_float_list(values: Iterable[Any]) -> list[float]:
    return [float(value) for value in values]


def _find_scene_entry(scene: Any, uid: str) -> Any:
    for collection_name in (
        "object_list",
        "articulation_list",
        "articulation_part_list",
    ):
        collection = getattr(scene, collection_name, {}) or {}
        if uid in collection:
            return collection[uid]
    raise KeyError(uid)


def _entry_prim(entry: Any) -> Any:
    prim = getattr(entry, "prim", None)
    if prim is not None:
        return prim
    get_prim = getattr(entry, "GetPrim", None)
    if callable(get_prim):
        return get_prim()
    raise AttributeError(f"{entry!r} does not expose a USD prim")


def set_scene_object_active(scene: Any, uids: Iterable[str], active: bool) -> None:
    """Toggle runtime scene object prims by LabUtopia/GenManip uid."""

    for uid in uids:
        entry = _find_scene_entry(scene, uid)
        prim = _entry_prim(entry)
        if prim.IsActive() != active:
            prim.SetActive(active)
        if not active:
            cache_library = getattr(scene, "cache_library", None)
            mesh_dict = getattr(cache_library, "mesh_dict", None)
            if isinstance(mesh_dict, dict):
                mesh_dict.pop(uid, None)


def resettable_scene_object_uids(scene: Any) -> list[str]:
    """Return object_list uids safe for direct world-pose reset and velocity cleanup."""

    object_list = getattr(scene, "object_list", {}) or {}
    articulation_uids = set(getattr(scene, "articulation_list", {}) or {})
    articulation_part_uids = set(getattr(scene, "articulation_part_list", {}) or {})
    skipped = articulation_uids | articulation_part_uids
    return sorted(uid for uid in object_list if uid not in skipped)


def configured_articulation_targets(scene_config: Any) -> dict[str, list[float]]:
    """Return articulation target positions from a SceneConfig-like object."""

    generation_config = getattr(scene_config, "generation_config", None)
    articulation_config = getattr(generation_config, "articulation", {}) or {}
    targets: dict[str, list[float]] = {}
    for uid, config in articulation_config.items():
        target_positions = None
        if isinstance(config, dict):
            target_positions = config.get("target_positions")
        else:
            target_positions = getattr(config, "target_positions", None)
        if target_positions is None:
            continue
        targets[uid] = _as_float_list(target_positions)
    return targets


def articulation_target_for_uid(scene_config: Any, uid: str) -> list[float] | None:
    return configured_articulation_targets(scene_config).get(uid)


def _call_optional_setter(handle: Any, setter_name: str, values: list[float]) -> bool:
    setter = getattr(handle, setter_name, None)
    if not callable(setter):
        return False
    setter(values)
    return True


def apply_articulation_initial_targets(scene: Any) -> dict[str, list[float]]:
    """Replay configured articulation starts after world resets or warmup steps."""

    targets = configured_articulation_targets(getattr(scene, "scene_config", None))
    articulation_list = getattr(scene, "articulation_list", {}) or {}
    articulation_data = getattr(scene, "articulation_data", {}) or {}
    applied: dict[str, list[float]] = {}
    for uid, target_positions in targets.items():
        articulation = articulation_list.get(uid)
        if articulation is None:
            continue
        data = articulation_data.get(uid, {})
        if data and not data.get("is_articulated", True):
            continue
        view = getattr(articulation, "_articulation_view", None)
        position_written = _call_optional_setter(
            articulation, "set_joint_positions", target_positions
        )
        if not position_written and view is not None:
            position_written = _call_optional_setter(
                view, "set_joint_positions", target_positions
            )
        if not position_written:
            continue
        zero_velocities = [0.0 for _ in target_positions]
        if not _call_optional_setter(articulation, "set_joint_velocities", zero_velocities):
            if view is not None:
                _call_optional_setter(view, "set_joint_velocities", zero_velocities)
        if not _call_optional_setter(
            articulation, "set_joint_position_targets", target_positions
        ):
            if view is not None:
                _call_optional_setter(view, "set_joint_position_targets", target_positions)
        applied[uid] = target_positions
    return applied
