from standalone_tools.labutopia_poc.capture_eval_render_diagnostics import (
    apply_camera_config_override,
    build_camera_frame_stats,
    build_claim_boundary,
    classify_articulation_runtime_state,
    classify_frame_stats,
    evaluate_render_validation,
    frame_stats_from_png,
)


def _write_test_png(path, rectangles):
    import cv2
    import numpy as np

    image = np.full((512, 512, 3), [170, 170, 170], dtype=np.uint8)
    for x1, y1, x2, y2, color in rectangles:
        image[y1:y2, x1:x2] = color
    cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))


def _render_validation_config(task_name, required_objects, thresholds):
    return {
        "task_name": f"ebench/labutopia_lab_poc/franka_poc/{task_name}",
        "labutopia_render_validation": {
            "schema_version": 1,
            "primary_camera": "camera2",
            "required_camera_names": ["camera2"],
            "required_visible_objects": required_objects,
            "object_pixel_thresholds": thresholds,
            "reject_frame_if": [
                "black_frame",
                "low_texture",
                "required_object_missing",
                "severe_clipping",
            ],
            "evidence_policy": {"direct_render": False},
        },
    }


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


def test_render_validation_accepts_required_object_pixel_thresholds(tmp_path):
    frame_path = tmp_path / "place.png"
    _write_test_png(
        frame_path,
        [
            (210, 150, 258, 195, [26, 184, 138]),
            (260, 270, 314, 301, [242, 199, 31]),
        ],
    )
    stats = frame_stats_from_png(camera_name="camera2", frame_path=frame_path)
    stats["stage"] = "readback_after_get_eval_camera_data"
    config = _render_validation_config(
        "level1_place",
        ["obj_beaker2", "obj_target_plat"],
        {
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
    )

    report = evaluate_render_validation(config, [stats])

    assert report["passed"] is True
    assert report["required_objects"]["obj_beaker2"]["passed"] is True
    assert report["required_objects"]["obj_target_plat"]["passed"] is True


def test_render_validation_rejects_required_object_below_threshold(tmp_path):
    frame_path = tmp_path / "pick_too_small.png"
    _write_test_png(frame_path, [(240, 230, 260, 290, [26, 122, 242])])
    stats = frame_stats_from_png(camera_name="camera2", frame_path=frame_path)
    stats["stage"] = "readback_after_get_eval_camera_data"
    config = _render_validation_config(
        "level1_pick",
        ["obj_conical_bottle02"],
        {
            "obj_conical_bottle02": {
                "min_width_px": 36,
                "min_height_px": 48,
                "min_bbox_area_fraction": 0.01,
            }
        },
    )

    report = evaluate_render_validation(config, [stats])

    assert report["passed"] is False
    bottle = report["required_objects"]["obj_conical_bottle02"]
    assert bottle["passed"] is False
    assert "min_width_px" in bottle["failed_thresholds"]


def test_render_validation_accepts_open_door_nested_handle_visuals(tmp_path):
    frame_path = tmp_path / "open_door.png"
    _write_test_png(
        frame_path,
        [
            (120, 120, 360, 290, [45, 54, 62]),
            (180, 135, 330, 280, [112, 135, 162]),
            (245, 165, 270, 245, [255, 46, 10]),
        ],
    )
    stats = frame_stats_from_png(camera_name="camera2", frame_path=frame_path)
    stats["stage"] = "readback_after_get_eval_camera_data"
    config = _render_validation_config(
        "level1_open_door",
        ["obj_DryingBox_01", "obj_DryingBox_01_handle"],
        {
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
    )

    report = evaluate_render_validation(config, [stats])

    assert report["passed"] is True
    assert report["required_objects"]["obj_DryingBox_01"]["passed"] is True
    assert report["required_objects"]["obj_DryingBox_01_handle"]["passed"] is True


def test_classify_huge_articulation_joint_position_as_unstable():
    report = classify_articulation_runtime_state(
        {
            "obj_DryingBox_01": {
                "joint_positions": [3.888585221393613e16, 0.0],
                "dof_names": ["RevoluteJoint", "FixedJoint"],
            }
        }
    )

    assert report["runtime_physics_stable"] is False
    assert report["articulations"]["obj_DryingBox_01"]["status"] == (
        "unstable_joint_positions"
    )
    assert report["articulations"]["obj_DryingBox_01"]["invalid_joint_positions"] == [
        3.888585221393613e16
    ]


def test_required_articulation_missing_is_unstable():
    report = classify_articulation_runtime_state(
        {},
        required_articulations=["obj_DryingBox_01"],
    )

    assert report["runtime_physics_stable"] is False
    assert report["missing_articulations"] == ["obj_DryingBox_01"]
    assert report["articulations"]["obj_DryingBox_01"]["status"] == (
        "missing_articulation"
    )


def test_configured_articulation_target_mismatch_is_unstable():
    report = classify_articulation_runtime_state(
        {
            "obj_DryingBox_01": {
                "joint_positions": [0.7112835049629211],
                "dof_names": ["RevoluteJoint"],
            }
        },
        expected_joint_positions={"obj_DryingBox_01": [0.0]},
        joint_position_tolerance_rad=1e-3,
    )

    item = report["articulations"]["obj_DryingBox_01"]
    assert report["runtime_physics_stable"] is False
    assert item["status"] == "target_position_mismatch"
    assert item["expected_joint_positions"] == [0.0]
    assert item["joint_position_errors"][0] > 0.7


def test_claim_boundary_requires_runtime_physics_for_baseline():
    claim_boundary = build_claim_boundary(
        boundary_classification="readback_visible",
        render_validation_passed=True,
        runtime_physics_stable=False,
    )

    assert claim_boundary["task_render_accepted"] is True
    assert claim_boundary["official_baseline_evaluable"] is False
    assert "runtime_physics_unstable" in claim_boundary["blockers"]


def test_claim_boundary_keeps_official_baseline_separate_from_task_render():
    claim_boundary = build_claim_boundary(
        boundary_classification="readback_visible",
        render_validation_passed=True,
        runtime_physics_stable=True,
    )

    assert claim_boundary["task_render_accepted"] is True
    assert claim_boundary["official_baseline_evaluable"] is False
    assert claim_boundary["blockers"] == []
    assert "official_baseline_not_validated" in claim_boundary["baseline_blockers"]


def test_claim_boundary_allows_official_baseline_when_explicitly_validated():
    claim_boundary = build_claim_boundary(
        boundary_classification="readback_visible",
        render_validation_passed=True,
        runtime_physics_stable=True,
        official_baseline_validated=True,
    )

    assert claim_boundary["task_render_accepted"] is True
    assert claim_boundary["official_baseline_evaluable"] is True
    assert claim_boundary["baseline_blockers"] == []


def test_claim_boundary_marks_incomplete_diagnostic_not_evaluable():
    claim_boundary = build_claim_boundary(
        boundary_classification=None,
        render_validation_passed=False,
        runtime_physics_stable=True,
        diagnostic_completed=False,
    )

    assert claim_boundary["task_render_accepted"] is False
    assert claim_boundary["official_baseline_evaluable"] is False
    assert "runtime_diagnostic_not_completed" in claim_boundary["blockers"]


def test_camera_config_override_is_scoped_to_diagnostic_eval_config():
    eval_config = {
        "domain_randomization": {
            "cameras": {
                "type": "fixed",
                "config_path": "configs/cameras/original.yml",
            }
        }
    }

    applied = apply_camera_config_override(
        eval_config,
        "configs/cameras/open_door_trial.yml",
    )

    assert applied == {
        "previous_config_path": "configs/cameras/original.yml",
        "override_config_path": "configs/cameras/open_door_trial.yml",
    }
    assert (
        eval_config["domain_randomization"]["cameras"]["config_path"]
        == "configs/cameras/open_door_trial.yml"
    )
