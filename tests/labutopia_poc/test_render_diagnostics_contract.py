from standalone_tools.labutopia_poc.capture_eval_render_diagnostics import (
    build_camera_frame_stats,
    classify_frame_stats,
)


def test_classify_black_frame_as_failed():
    stats = build_camera_frame_stats(
        camera_name="camera2",
        frame_path="camera2/00000.png",
        width=256,
        height=256,
        channel_min=[0, 0, 0],
        channel_max=[0, 0, 0],
        channel_mean=[0.0, 0.0, 0.0],
        nonzero_pixels=0,
    )

    assert classify_frame_stats(stats) == "black_frame_fail"


def test_classify_visible_frame_as_pass():
    stats = build_camera_frame_stats(
        camera_name="camera2",
        frame_path="camera2/00000.png",
        width=256,
        height=256,
        channel_min=[0, 1, 0],
        channel_max=[180, 190, 170],
        channel_mean=[72.0, 80.0, 69.0],
        nonzero_pixels=42000,
    )

    assert classify_frame_stats(stats) == "visible_frame"
