from types import SimpleNamespace


def test_optional_robot_pose_uses_config_position_and_default_orientation():
    from genmanip.core.robot.pose_config import resolve_optional_robot_pose

    pose = resolve_optional_robot_pose(
        SimpleNamespace(position=[-0.4, 0.0, 0.71], orientation=None)
    )

    assert pose == {
        "position": [-0.4, 0.0, 0.71],
        "orientation": [1.0, 0.0, 0.0, 0.0],
    }


def test_optional_robot_pose_is_absent_without_pose_config():
    from genmanip.core.robot.pose_config import resolve_optional_robot_pose

    assert resolve_optional_robot_pose(SimpleNamespace(position=None, orientation=None)) is None
