from standalone_tools.labutopia_poc.capture_eval_render_diagnostics import (
    apply_camera_config_override,
    build_camera_frame_stats,
    build_claim_boundary,
    classify_articulation_runtime_state,
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
