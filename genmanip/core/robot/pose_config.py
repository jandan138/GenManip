from typing import Any


def resolve_optional_robot_pose(robot_config: Any) -> dict[str, list[float]] | None:
    position = getattr(robot_config, "position", None)
    orientation = getattr(robot_config, "orientation", None)
    if position is None and orientation is None:
        return None
    if position is None:
        position = [0.0, 0.0, 0.0]
    if orientation is None:
        orientation = [1.0, 0.0, 0.0, 0.0]
    return {
        "position": [float(value) for value in position],
        "orientation": [float(value) for value in orientation],
    }
