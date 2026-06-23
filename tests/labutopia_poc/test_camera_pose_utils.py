from genmanip.utils.standalone.camera_pose_utils import (
    set_camera_local_pose_from_config,
)


class _FakeCamera:
    def __init__(self):
        self.calls = []

    def set_local_pose(self, **kwargs):
        self.calls.append(kwargs)


def test_genmanip_style_camera_pose_passes_explicit_camera_axes():
    camera = _FakeCamera()

    applied = set_camera_local_pose_from_config(
        camera,
        {
            "position": [0.1, 0.0, 2.5],
            "orientation": [0.70711, 0.0, 0.0, -0.70711],
            "camera_axes": "usd",
        },
    )

    assert applied is True
    assert camera.calls == [
        {
            "translation": [0.1, 0.0, 2.5],
            "orientation": [0.70711, 0.0, 0.0, -0.70711],
            "camera_axes": "usd",
        }
    ]


def test_simbox_camera_pose_preserves_default_usd_axes():
    camera = _FakeCamera()

    applied = set_camera_local_pose_from_config(
        camera,
        {
            "position": [0.07, 0.01, 0.08],
            "orientation": [0.62, 0.33, -0.33, -0.62],
        },
        default_camera_axes="usd",
    )

    assert applied is True
    assert camera.calls[0]["camera_axes"] == "usd"


def test_camera_pose_is_not_reapplied_without_complete_pose():
    camera = _FakeCamera()

    applied = set_camera_local_pose_from_config(
        camera,
        {"position": [0.1, 0.0, 2.5], "camera_axes": "usd"},
    )

    assert applied is False
    assert camera.calls == []
