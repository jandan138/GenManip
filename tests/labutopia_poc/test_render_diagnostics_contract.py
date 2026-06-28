import hashlib
import json

from standalone_tools.labutopia_poc import capture_eval_render_diagnostics as render_diag
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


def test_frame_stats_from_png_records_frame_sha256(tmp_path):
    frame_path = tmp_path / "frame.png"
    _write_test_png(frame_path, [(10, 10, 30, 30, [26, 184, 138])])

    stats = frame_stats_from_png(camera_name="camera2", frame_path=frame_path)

    assert stats["sha256"] == hashlib.sha256(frame_path.read_bytes()).hexdigest()


def test_next_camera_frame_path_keeps_repeated_readbacks_unique(tmp_path):
    counters = {}

    first = render_diag.next_camera_frame_path(
        output_dir=tmp_path,
        stage="readback_after_get_eval_camera_data",
        camera_name="camera2",
        counters=counters,
    )
    second = render_diag.next_camera_frame_path(
        output_dir=tmp_path,
        stage="readback_after_get_eval_camera_data",
        camera_name="camera2",
        counters=counters,
    )

    assert first.name == "00000.png"
    assert second.name == "00001.png"
    assert first != second


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


def test_native_door_target_ignores_button_prismatic_dof():
    report = classify_articulation_runtime_state(
        {
            "obj_DryingBox_01": {
                "joint_positions": [0.0, 0.0],
                "dof_names": ["RevoluteJoint", "PrismaticJoint"],
            }
        },
        expected_joint_positions={"obj_DryingBox_01": [0.0]},
        expected_joint_names={"obj_DryingBox_01": ["RevoluteJoint"]},
        joint_position_tolerance_rad=1e-3,
    )

    assert report["runtime_physics_stable"] is True
    item = report["articulations"]["obj_DryingBox_01"]
    assert item["status"] == "stable"
    assert item["compared_joint_names"] == ["RevoluteJoint"]
    assert item["ignored_joint_names"] == ["PrismaticJoint"]


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


def test_native_dryingbox_evidence_hashes_audit_and_smoke(tmp_path):
    audit_path = tmp_path / "native_dryingbox_audit_20260624_001000" / "audit.json"
    smoke_path = tmp_path / "native_dryingbox_smoke_20260624_001500" / "smoke.json"
    audit_path.parent.mkdir(parents=True)
    smoke_path.parent.mkdir(parents=True)
    audit_bytes = b'{"source_prim_path": "/World/DryingBox_01"}\n'
    smoke_bytes = b'{"runtime_physics_stable": true}\n'
    audit_path.write_bytes(audit_bytes)
    smoke_path.write_bytes(smoke_bytes)

    evidence = render_diag.build_native_dryingbox_evidence(
        audit_json_path=audit_path,
        smoke_json_path=smoke_path,
    )

    assert (
        evidence["drying_box_strategy"]
        == "native_complex_with_additive_physics_override"
    )
    assert evidence["native_asset_audit_path"] == str(audit_path)
    assert evidence["native_asset_audit_sha256"] == hashlib.sha256(audit_bytes).hexdigest()
    assert evidence["native_smoke_path"] == str(smoke_path)
    assert evidence["native_smoke_sha256"] == hashlib.sha256(smoke_bytes).hexdigest()
    assert evidence["native_smoke_runtime_physics_stable"] is True


def test_native_dryingbox_evidence_copies_stage4_physics_override_material_gate(tmp_path):
    audit_path = tmp_path / "native_dryingbox_audit_20260624_001000" / "audit.json"
    smoke_path = tmp_path / "native_dryingbox_smoke_20260624_001500" / "smoke.json"
    physics_path = (
        tmp_path
        / "native_dryingbox_physics_override_20260624_002000"
        / "physics_override.json"
    )
    audit_path.parent.mkdir(parents=True)
    smoke_path.parent.mkdir(parents=True)
    physics_path.parent.mkdir(parents=True)
    audit_path.write_text('{"source_prim_path": "/World/DryingBox_01"}\n')
    smoke_path.write_text('{"runtime_physics_stable": true}\n')
    physics_payload = {
        "remote_aluminum_disposition": "explicit_waiver",
        "material_closure_kept_open": True,
        "remote_aluminum_waiver": {
            "waiver_id": "ALUMINUM_REMOTE_MDL_001",
            "affected_material_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/Aluminum_Anodized_Charcoal",
            "affected_task_visible_surfaces": [
                "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Group_01/mesh"
            ],
        },
        "static_material_dependency_gate": {
            "status": "passed",
            "remote_waiver_count": 1,
            "local_mirror_count": 0,
        },
        "dof_map": {
            "metric_dof": {
                "joint_name": "RevoluteJoint",
                "joint_type": "PhysicsRevoluteJoint",
            },
            "ignored_dofs": [{"joint_name": "PrismaticJoint"}],
        },
    }
    physics_bytes = (
        render_diag.json.dumps(physics_payload, sort_keys=True).encode("utf-8")
        + b"\n"
    )
    physics_path.write_bytes(physics_bytes)

    evidence = render_diag.build_native_dryingbox_evidence(
        audit_json_path=audit_path,
        smoke_json_path=smoke_path,
        physics_override_json_path=physics_path,
    )

    assert evidence["native_physics_override_path"] == str(physics_path)
    assert (
        evidence["native_physics_override_sha256"]
        == hashlib.sha256(physics_bytes).hexdigest()
    )
    assert evidence["remote_aluminum_disposition"] == "explicit_waiver"
    assert evidence["remote_aluminum_waiver_id"] == "ALUMINUM_REMOTE_MDL_001"
    assert evidence["material_closure_kept_open"] is True
    assert evidence["static_material_dependency_gate"]["status"] == "passed"
    assert evidence["stage4_dof_map"]["metric_dof"]["joint_name"] == "RevoluteJoint"


def test_material_closure_status_keeps_explicit_aluminum_waiver_open():
    report = render_diag.classify_runtime_material_closure(
        {
            "remote_aluminum_disposition": "explicit_waiver",
            "material_closure_kept_open": True,
            "remote_aluminum_waiver": {"waiver_id": "ALUMINUM_REMOTE_MDL_001"},
        },
        runtime_material_readback={
            "records": [
                {
                    "runtime_material_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/Aluminum_Anodized_Charcoal",
                    "compute_bound_material_valid": True,
                }
            ],
            "fallback_surface_count": 0,
            "blocked": False,
        },
    )

    assert report["native_material_closure_status"] == "open_remote_dependency_waived"
    assert report["runtime_material_dependency_status"] == "open_waived"
    assert report["material_closure_eligible"] is False
    assert report["remote_aluminum_disposition"] == "explicit_waiver"
    assert "ALUMINUM_REMOTE_MDL_001" in report["open_waiver_ids"]


def test_material_closure_status_requires_runtime_readback():
    report = render_diag.classify_runtime_material_closure(
        {
            "remote_aluminum_disposition": "local_mirror",
            "material_closure_kept_open": False,
        },
        runtime_material_readback=None,
    )

    assert report["native_material_closure_status"] == "blocked"
    assert report["runtime_material_dependency_status"] == "blocked"
    assert "runtime_material_readback_missing" in report["blockers"]


def test_material_closure_status_blocks_unresolved_runtime_material_records():
    report = render_diag.classify_runtime_material_closure(
        {
            "remote_aluminum_disposition": "local_mirror",
            "material_closure_kept_open": False,
        },
        runtime_material_readback={
            "records": [
                {
                    "prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/panel",
                    "compute_bound_material_valid": False,
                    "displayColor_fallback_status": "absent",
                }
            ],
            "fallback_surface_count": 0,
            "blocked": False,
        },
    )

    assert report["native_material_closure_status"] == "blocked"
    assert report["runtime_material_dependency_status"] == "blocked"
    assert "runtime_material_binding_unresolved" in report["blockers"]


def test_native_runtime_material_root_path_comes_from_stage4_waiver():
    root_path = render_diag.native_runtime_material_root_path(
        {
            "remote_aluminum_waiver": {
                "affected_material_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/Aluminum_Anodized_Charcoal"
            }
        }
    )

    assert root_path == "/World/labutopia_level1_poc/obj_obj_DryingBox_01"


def test_observation_schema_summary_records_camera_and_state_keys():
    schema = render_diag.summarize_observation_schema(
        {
            "instruction": "Open the door.",
            "state.joints": [0.0] * 7,
            "state.gripper": [0.04, 0.04],
            "state.base": [0.0, 0.0, 0.0],
            "state.ee_pose": [0.0] * 7,
            "timestep": 0,
            "reset": True,
            "robot_id": "manip/franka/panda_hand",
            "video.camera2_view": {
                "type": "jpeg_bytes",
                "dtype": "uint8",
                "shape": (512, 512, 3),
                "data": b"jpeg",
            },
        }
    )

    assert schema["keys"] == sorted(schema["keys"])
    assert "video.camera2_view" in schema["camera_keys"]
    assert schema["entries"]["state.joints"]["length"] == 7
    assert schema["entries"]["video.camera2_view"]["shape"] == [512, 512, 3]
    assert schema["entries"]["video.camera2_view"]["bytes"] == 4


def test_open_door_metric_contract_reads_revolute_joint_and_ignores_button():
    contract = render_diag.build_open_door_metric_contract(
        {
            "generation_config": {
                "goal": [
                    [
                        [
                            {
                                "type": "manip/default/check_joint_angle",
                                "articulation_obj_uid": "obj_DryingBox_01",
                                "joint_name": "RevoluteJoint",
                                "angle_deg_range": [30, 120],
                            }
                        ]
                    ]
                ]
            },
            "labutopia_native_drying_box": {
                "door_joint_name": "RevoluteJoint",
                "button_joint_name": "PrismaticJoint",
                "button_prismatic_joint_policy": "ignored_by_open_door_metric",
            },
        }
    )

    assert contract["metric_reads_door_revolute_joint"] is True
    assert contract["metric_joint_name"] == "RevoluteJoint"
    assert contract["ignored_button_joint_name"] == "PrismaticJoint"
    assert contract["button_joint_ignored_by_metric"] is True


def test_zero_action_and_step_response_summary_are_jsonable():
    action = render_diag.build_zero_joint_position_action([0.1, -0.2, 0.3])
    assert action == {
        "action": [0.1, -0.2, 0.3],
        "base_motion": [0.0, 0.0, 0.0],
        "control_type": "joint_position",
        "is_rel": False,
        "base_is_rel": True,
    }

    summary = render_diag.summarize_step_response(
        obs={"timestep": 1, "reset": False},
        reward=0.0,
        done=False,
        info={"info": 0.0},
    )

    assert summary["reward"] == 0.0
    assert summary["done"] is False
    assert summary["metric_raw_output"] == 0.0
    assert summary["obs_schema"]["keys"] == ["reset", "timestep"]


def test_eval_step_contract_rejects_nonfinite_action_and_invalid_termination():
    contract = render_diag.classify_eval_step_contract(
        zero_action={
            "action": [float("nan")] * 9,
            "base_motion": [0.0, 0.0, 0.0],
            "control_type": "joint_position",
            "is_rel": False,
            "base_is_rel": True,
        },
        step_response={
            "done": True,
            "reward": 0.0,
            "metric_raw_output": 0.0,
            "obs_schema": {"present": True, "camera_keys": ["video.camera2_view"]},
            "info": {"termination_reason": "non_finite_arm_state", "info": 0.0},
        },
    )

    assert contract["passed"] is False
    assert "zero_action_non_finite" in contract["blockers"]
    assert "invalid_step_termination:non_finite_arm_state" in contract["blockers"]


def test_eval_step_contract_accepts_finite_action_and_metric_readback():
    contract = render_diag.classify_eval_step_contract(
        zero_action={
            "action": [0.0] * 9,
            "base_motion": [0.0, 0.0, 0.0],
            "control_type": "joint_position",
            "is_rel": False,
            "base_is_rel": True,
        },
        step_response={
            "done": False,
            "reward": 0.0,
            "metric_raw_output": 0.0,
            "obs_schema": {"present": True, "camera_keys": ["video.camera2_view"]},
            "info": {"info": 0.0},
        },
    )

    assert contract["passed"] is True
    assert contract["blockers"] == []


def test_stage5_evidence_contract_requires_frame_hashes_logs_and_reset_seed():
    contract = render_diag.classify_stage5_evidence_contract(
        {
            "run_id": "labutopia_native_open_door_eval_20260628_182045",
            "seed": "000",
            "output_dir": "saved/diagnostics/run",
            "worker_id": "local",
            "reset_info": {
                "task": "ebench/labutopia_lab_poc/franka_poc/level1_open_door"
            },
            "diagnostic_logs": {"result_dir": "", "stdout_log_path": "", "stderr_log_path": ""},
            "camera_frames": [
                {
                    "stage": "readback_after_get_eval_camera_data",
                    "camera_name": "camera2",
                    "frame_path": "camera2/00000.png",
                }
            ],
        }
    )

    assert contract["passed"] is False
    assert "camera_frame_sha256_missing" in contract["blockers"]
    assert "diagnostic_stdout_log_path_missing" in contract["blockers"]
    assert "reset_seed_missing" in contract["blockers"]
    assert "episode_id_missing" in contract["blockers"]


def test_stage5_evidence_contract_accepts_required_paths_and_hashes():
    contract = render_diag.classify_stage5_evidence_contract(
        {
            "run_id": "labutopia_native_open_door_eval_20260628_182045",
            "seed": "000",
            "output_dir": "saved/diagnostics/run",
            "worker_id": "local",
            "episode_id": "episode-000",
            "reset_info": {
                "task": "ebench/labutopia_lab_poc/franka_poc/level1_open_door",
                "seed": "000",
            },
            "diagnostic_logs": {
                "result_dir": "saved/diagnostics/run",
                "stdout_log_path": "saved/diagnostics/run/stdout.log",
                "stderr_log_path": "saved/diagnostics/run/stderr.log",
            },
            "camera_frames": [
                {
                    "stage": "readback_after_get_eval_camera_data",
                    "camera_name": "camera2",
                    "frame_path": "camera2/00000.png",
                    "sha256": "a" * 64,
                }
            ],
        }
    )

    assert contract["passed"] is True
    assert contract["blockers"] == []


def test_stage5_eval_manifest_records_claim_boundary_and_artifacts():
    manifest = render_diag.build_stage5_eval_manifest(
        {
            "run_id": "labutopia_native_open_door_eval_20260628_182659",
            "worker_id": "local",
            "episode_id": "episode-000",
            "seed": "000",
            "native_eval_readback_ready": True,
            "native_material_closure_status": "open_remote_dependency_waived",
            "runtime_material_dependency_status": "open_waived",
            "material_closure_eligible": False,
            "lift2_contract_ready": False,
            "diagnostic_logs": {
                "result_dir": "saved/diagnostics/run",
                "stdout_log_path": "saved/diagnostics/run/stdout.log",
                "stderr_log_path": "saved/diagnostics/run/stderr.log",
            },
            "camera_frames": [
                {
                    "stage": "readback_after_get_eval_camera_data",
                    "camera_name": "camera2",
                    "frame_path": "saved/diagnostics/run/camera2/00000.png",
                    "sha256": "a" * 64,
                }
            ],
            "open_door_metric_contract": {
                "metric_reads_door_revolute_joint": True,
                "metric_joint_name": "RevoluteJoint",
            },
            "eval_step_contract": {"passed": True},
            "stage5_evidence_contract": {"passed": True},
        },
        diagnostics_path="saved/diagnostics/run/diagnostics.json",
    )

    assert manifest["stage"] == "acceptance_stage_5_eval_readback"
    assert manifest["diagnostics_path"] == "saved/diagnostics/run/diagnostics.json"
    assert manifest["claim_boundary"]["lift2_contract_ready"] is False
    assert manifest["claim_boundary"]["native_material_closure_claim_allowed"] is False
    assert manifest["camera_frames"][0]["sha256"] == "a" * 64


def test_native_eval_readback_summary_promotes_task5_claim_fields():
    diagnostics = {
        "boundary_classification": "readback_visible",
        "render_validation": {"passed": True},
        "runtime_sanity": {"runtime_physics_stable": True},
        "runtime_material_readback": {
            "records": [
                {
                    "runtime_material_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/Aluminum_Anodized_Charcoal",
                    "compute_bound_material_valid": True,
                }
            ],
            "fallback_surface_count": 0,
            "blocked": False,
        },
        "zero_action": {
            "action": [0.0] * 9,
            "base_motion": [0.0, 0.0, 0.0],
            "control_type": "joint_position",
            "is_rel": False,
            "base_is_rel": True,
        },
        "step_response": {
            "done": False,
            "reward": 0.0,
            "metric_raw_output": 0.0,
            "obs_schema": {"present": True, "camera_keys": ["video.camera2_view"]},
            "info": {"info": 0.0},
        },
        "claim_boundary": build_claim_boundary(
            boundary_classification="readback_visible",
            render_validation_passed=True,
            runtime_physics_stable=True,
        ),
        "open_door_metric_contract": {
            "metric_reads_door_revolute_joint": True,
        },
        "stage5_evidence_contract": {"passed": True, "blockers": []},
    }
    native_evidence = {
        "drying_box_strategy": "native_complex_with_additive_physics_override",
        "native_smoke_runtime_physics_stable": True,
        "remote_aluminum_disposition": "explicit_waiver",
        "material_closure_kept_open": True,
        "remote_aluminum_waiver": {"waiver_id": "ALUMINUM_REMOTE_MDL_001"},
    }

    render_diag.apply_native_eval_readback_summary(
        diagnostics,
        native_evidence=native_evidence,
    )

    assert (
        diagnostics["drying_box_strategy"]
        == "native_complex_with_additive_physics_override"
    )
    assert diagnostics["runtime_physics_stable"] is True
    assert diagnostics["task_render_accepted"] is True
    assert diagnostics["official_baseline_evaluable"] is False
    assert diagnostics["native_complex_dryingbox_ready"] is True
    assert diagnostics["native_eval_readback_ready"] is True
    assert diagnostics["lift2_contract_ready"] is False
    assert diagnostics["remote_aluminum_disposition"] == "explicit_waiver"
    assert (
        diagnostics["native_material_closure_status"]
        == "open_remote_dependency_waived"
    )


def test_native_eval_readback_summary_blocks_metric_contract_regression():
    diagnostics = {
        "boundary_classification": "readback_visible",
        "render_validation": {"passed": True},
        "runtime_sanity": {"runtime_physics_stable": True},
        "runtime_material_readback": {
            "records": [{"compute_bound_material_valid": True}],
            "fallback_surface_count": 0,
            "blocked": False,
        },
        "zero_action": {
            "action": [0.0] * 9,
            "base_motion": [0.0, 0.0, 0.0],
            "control_type": "joint_position",
            "is_rel": False,
            "base_is_rel": True,
        },
        "step_response": {
            "done": False,
            "reward": 0.0,
            "metric_raw_output": 0.0,
            "obs_schema": {"present": True, "camera_keys": ["video.camera2_view"]},
            "info": {"info": 0.0},
        },
        "open_door_metric_contract": {
            "metric_reads_door_revolute_joint": False,
            "metric_joint_name": "PrismaticJoint",
        },
        "stage5_evidence_contract": {"passed": True, "blockers": []},
        "claim_boundary": build_claim_boundary(
            boundary_classification="readback_visible",
            render_validation_passed=True,
            runtime_physics_stable=True,
        ),
    }
    native_evidence = {
        "drying_box_strategy": "native_complex_with_additive_physics_override",
        "native_smoke_runtime_physics_stable": True,
        "remote_aluminum_disposition": "explicit_waiver",
        "material_closure_kept_open": True,
        "remote_aluminum_waiver": {"waiver_id": "ALUMINUM_REMOTE_MDL_001"},
    }

    render_diag.apply_native_eval_readback_summary(
        diagnostics,
        native_evidence=native_evidence,
    )

    assert diagnostics["native_eval_readback_ready"] is False
    assert "open_door_metric_contract_failed" in diagnostics["blockers"]


def test_native_eval_readback_summary_blocks_invalid_step_contract():
    diagnostics = {
        "boundary_classification": "readback_visible",
        "render_validation": {"passed": True},
        "runtime_sanity": {"runtime_physics_stable": True},
        "runtime_material_readback": {
            "records": [
                {
                    "runtime_material_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/Aluminum_Anodized_Charcoal",
                    "compute_bound_material_valid": True,
                }
            ],
            "fallback_surface_count": 0,
            "blocked": False,
        },
        "zero_action": {
            "action": [float("nan")] * 9,
            "base_motion": [0.0, 0.0, 0.0],
            "control_type": "joint_position",
            "is_rel": False,
            "base_is_rel": True,
        },
        "step_response": {
            "done": True,
            "reward": 0.0,
            "metric_raw_output": 0.0,
            "obs_schema": {"present": True, "camera_keys": ["video.camera2_view"]},
            "info": {"termination_reason": "non_finite_arm_state", "info": 0.0},
        },
        "claim_boundary": build_claim_boundary(
            boundary_classification="readback_visible",
            render_validation_passed=True,
            runtime_physics_stable=True,
        ),
    }
    native_evidence = {
        "drying_box_strategy": "native_complex_with_additive_physics_override",
        "native_smoke_runtime_physics_stable": True,
        "remote_aluminum_disposition": "explicit_waiver",
        "material_closure_kept_open": True,
        "remote_aluminum_waiver": {"waiver_id": "ALUMINUM_REMOTE_MDL_001"},
    }

    render_diag.apply_native_eval_readback_summary(
        diagnostics,
        native_evidence=native_evidence,
    )

    assert diagnostics["eval_step_contract"]["passed"] is False
    assert diagnostics["native_eval_readback_ready"] is False
    assert "eval_step_contract_failed" in diagnostics["blockers"]
    assert diagnostics["runtime_material_dependency_status"] == "open_waived"
    assert diagnostics["material_closure_eligible"] is False


def test_render_validation_accepts_native_scene_readback_when_color_mask_fails(tmp_path):
    frame_path = tmp_path / "native_open_door_gray.png"
    _write_test_png(
        frame_path,
        [
            (120, 120, 360, 290, [132, 132, 132]),
            (246, 165, 270, 245, [218, 218, 218]),
            (252, 205, 286, 216, [70, 76, 84]),
            (280, 199, 288, 264, [214, 102, 45]),
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
    config["labutopia_native_drying_box"] = {
        "strategy": "native_complex_with_additive_physics_override",
        "door_joint_name": "RevoluteJoint",
        "handle_part_path": "/handle",
    }
    scene_evidence = {
        "scene_collections": {
            "articulation_uids": ["obj_DryingBox_01"],
            "object_uids": [],
        },
        "articulation_state": {
            "obj_DryingBox_01": {
                "prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
                "world_position": [0.75, 0.1, 0.78],
                "world_orientation": [1.0, 0.0, 0.0, 0.0],
                "joint_positions": [0.0],
                "dof_names": ["RevoluteJoint"],
            }
        },
        "native_handle_parts": {
            "obj_DryingBox_01_handle": {
                "prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle",
                "world_pose_finite": True,
            }
        },
        "projected_task_parts": {
            "camera2": {
                "obj_DryingBox_01": {"pixel": [260.0, 210.0]},
                "obj_DryingBox_01_handle": {"pixel": [284.0, 230.0]},
            }
        },
    }

    report = evaluate_render_validation(config, [stats], scene_evidence=scene_evidence)

    assert report["passed"] is True
    assert (
        report["required_objects"]["obj_DryingBox_01"]["evidence_method"]
        == "native_scene_readback"
    )
    assert (
        report["required_objects"]["obj_DryingBox_01_handle"]["evidence_method"]
        == "native_handle_part_readback"
    )


def test_render_validation_accepts_native_handle_with_parent_material_mask(tmp_path):
    frame_path = tmp_path / "native_open_door_blue_handle.png"
    _write_test_png(
        frame_path,
        [
            (150, 120, 360, 310, [82, 130, 190]),
            (245, 165, 275, 255, [70, 118, 180]),
            (280, 199, 310, 270, [55, 96, 150]),
            (290, 178, 340, 245, [42, 52, 62]),
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
    config["labutopia_native_drying_box"] = {
        "strategy": "native_complex_with_additive_physics_override",
        "door_joint_name": "RevoluteJoint",
        "handle_part_path": "/handle",
    }
    scene_evidence = {
        "scene_collections": {
            "articulation_uids": ["obj_DryingBox_01"],
            "object_uids": [],
        },
        "articulation_state": {
            "obj_DryingBox_01": {
                "prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
                "world_position": [0.75, 0.1, 0.78],
                "world_orientation": [1.0, 0.0, 0.0, 0.0],
                "joint_positions": [0.0],
                "dof_names": ["RevoluteJoint"],
            }
        },
        "native_handle_parts": {
            "obj_DryingBox_01_handle": {
                "prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle",
                "world_pose_finite": True,
            }
        },
        "projected_task_parts": {
            "camera2": {
                "obj_DryingBox_01": {"pixel": [260.0, 210.0]},
                "obj_DryingBox_01_handle": {"pixel": [284.0, 230.0]},
            }
        },
    }

    report = evaluate_render_validation(config, [stats], scene_evidence=scene_evidence)

    assert report["passed"] is True
    handle_report = report["required_objects"]["obj_DryingBox_01_handle"]
    assert handle_report["color_mask_failed_thresholds"] == ["required_object_missing"]
    assert handle_report["evidence_method"] == "native_handle_part_readback"
    assert (
        handle_report["projected_rgb_evidence"]["mask_uid"]
        == "obj_DryingBox_01"
    )


def test_render_validation_accepts_native_handle_projected_on_blue_door_material(tmp_path):
    frame_path = tmp_path / "native_open_door_blue_door_projection.png"
    _write_test_png(
        frame_path,
        [
            (150, 120, 240, 310, [112, 135, 162]),
            (240, 120, 365, 310, [55, 96, 150]),
            (250, 165, 280, 255, [52, 88, 138]),
            (290, 178, 340, 245, [42, 52, 62]),
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
    config["labutopia_native_drying_box"] = {
        "strategy": "native_complex_with_additive_physics_override",
        "door_joint_name": "RevoluteJoint",
        "handle_part_path": "/handle",
    }
    scene_evidence = {
        "scene_collections": {
            "articulation_uids": ["obj_DryingBox_01"],
            "object_uids": [],
        },
        "articulation_state": {
            "obj_DryingBox_01": {
                "prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
                "world_position": [0.75, 0.1, 0.78],
                "world_orientation": [1.0, 0.0, 0.0, 0.0],
                "joint_positions": [0.0],
                "dof_names": ["RevoluteJoint"],
            }
        },
        "native_handle_parts": {
            "obj_DryingBox_01_handle": {
                "prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle",
                "world_pose_finite": True,
            }
        },
        "projected_task_parts": {
            "camera2": {
                "obj_DryingBox_01": {"pixel": [200.0, 210.0]},
                "obj_DryingBox_01_handle": {"pixel": [260.0, 258.0]},
            }
        },
    }

    report = evaluate_render_validation(config, [stats], scene_evidence=scene_evidence)

    assert report["passed"] is True
    handle_report = report["required_objects"]["obj_DryingBox_01_handle"]
    assert handle_report["evidence_method"] == "native_handle_part_readback"
    assert handle_report["projected_rgb_evidence"]["object_mask_area_px"] > 0


def test_render_validation_rejects_native_readback_without_camera_projection(tmp_path):
    frame_path = tmp_path / "native_open_door_table_only.png"
    _write_test_png(frame_path, [(0, 270, 512, 512, [132, 132, 132])])
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
    config["labutopia_native_drying_box"] = {
        "strategy": "native_complex_with_additive_physics_override",
        "door_joint_name": "RevoluteJoint",
        "handle_part_path": "/handle",
    }
    scene_evidence = {
        "scene_collections": {
            "articulation_uids": ["obj_DryingBox_01"],
            "object_uids": [],
        },
        "articulation_state": {
            "obj_DryingBox_01": {
                "prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
                "world_position": [37.0, 20.0, 30.0],
                "world_orientation": [1.0, 0.0, 0.0, 0.0],
                "joint_positions": [0.0],
                "dof_names": ["RevoluteJoint"],
            }
        },
        "native_handle_parts": {
            "obj_DryingBox_01_handle": {
                "prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle",
                "world_pose_finite": True,
            }
        },
        "projected_task_parts": {
            "camera2": {
                "obj_DryingBox_01": {"pixel": [17000.0, -9000.0]},
                "obj_DryingBox_01_handle": {"pixel": [18000.0, -9100.0]},
            }
        },
    }

    report = evaluate_render_validation(config, [stats], scene_evidence=scene_evidence)

    assert report["passed"] is False
    assert "obj_DryingBox_01:projected_target_not_visible" in report["failures"]
    assert (
        "obj_DryingBox_01_handle:projected_target_not_visible"
        in report["failures"]
    )


def test_render_validation_rejects_native_readback_without_projected_rgb_evidence(tmp_path):
    frame_path = tmp_path / "native_open_door_occluded.png"
    _write_test_png(
        frame_path,
        [
            (20, 20, 90, 90, [40, 40, 40]),
            (410, 410, 500, 500, [230, 230, 230]),
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
    config["labutopia_native_drying_box"] = {
        "strategy": "native_complex_with_additive_physics_override",
        "door_joint_name": "RevoluteJoint",
        "handle_part_path": "/handle",
    }
    scene_evidence = {
        "scene_collections": {
            "articulation_uids": ["obj_DryingBox_01"],
            "object_uids": [],
        },
        "articulation_state": {
            "obj_DryingBox_01": {
                "prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
                "world_position": [0.75, 0.1, 0.78],
                "world_orientation": [1.0, 0.0, 0.0, 0.0],
                "joint_positions": [0.0],
                "dof_names": ["RevoluteJoint"],
            }
        },
        "native_handle_parts": {
            "obj_DryingBox_01_handle": {
                "prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle",
                "world_pose_finite": True,
            }
        },
        "projected_task_parts": {
            "camera2": {
                "obj_DryingBox_01": {"pixel": [260.0, 260.0]},
                "obj_DryingBox_01_handle": {"pixel": [280.0, 260.0]},
            }
        },
    }

    report = evaluate_render_validation(config, [stats], scene_evidence=scene_evidence)

    assert report["passed"] is False
    assert "obj_DryingBox_01:projected_rgb_evidence_missing" in report["failures"]
    assert (
        "obj_DryingBox_01_handle:projected_rgb_evidence_missing"
        in report["failures"]
    )


def test_render_validation_rejects_native_readback_with_unrelated_projected_texture(tmp_path):
    import cv2
    import numpy as np

    frame_path = tmp_path / "native_open_door_unrelated_texture.png"
    image = np.full((512, 512, 3), [170, 170, 170], dtype=np.uint8)
    for y in range(220, 315, 10):
        for x in range(220, 315, 10):
            image[y : y + 10, x : x + 10] = (
                [120, 120, 120]
                if ((x + y) // 10) % 2 == 0
                else [210, 210, 210]
            )
    cv2.imwrite(str(frame_path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
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
    config["labutopia_native_drying_box"] = {
        "strategy": "native_complex_with_additive_physics_override",
        "door_joint_name": "RevoluteJoint",
        "handle_part_path": "/handle",
    }
    scene_evidence = {
        "scene_collections": {
            "articulation_uids": ["obj_DryingBox_01"],
            "object_uids": [],
        },
        "articulation_state": {
            "obj_DryingBox_01": {
                "prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
                "world_position": [0.75, 0.1, 0.78],
                "world_orientation": [1.0, 0.0, 0.0, 0.0],
                "joint_positions": [0.0],
                "dof_names": ["RevoluteJoint"],
            }
        },
        "native_handle_parts": {
            "obj_DryingBox_01_handle": {
                "prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle",
                "world_pose_finite": True,
            }
        },
        "projected_task_parts": {
            "camera2": {
                "obj_DryingBox_01": {"pixel": [260.0, 260.0]},
                "obj_DryingBox_01_handle": {"pixel": [280.0, 260.0]},
            }
        },
    }

    report = evaluate_render_validation(config, [stats], scene_evidence=scene_evidence)

    assert report["passed"] is False
    assert "obj_DryingBox_01:projected_rgb_evidence_missing" in report["failures"]
    assert (
        "obj_DryingBox_01_handle:projected_rgb_evidence_missing"
        in report["failures"]
    )


def test_parse_args_accepts_output_root_and_derives_run_id():
    args = render_diag.parse_args(
        [
            "--task",
            "level1_open_door",
            "--output-root",
            "saved/diagnostics/native_dryingbox_open_door_eval_20260624_001500",
        ]
    )

    assert args.output_dir == (
        "saved/diagnostics/native_dryingbox_open_door_eval_20260624_001500"
    )
    assert args.run_id == "native_dryingbox_open_door_eval_20260624_001500"


def test_parse_args_accepts_stage5_log_paths():
    args = render_diag.parse_args(
        [
            "--task",
            "level1_open_door",
            "--output-root",
            "saved/diagnostics/native_dryingbox_open_door_eval_20260624_001500",
            "--stdout-log-path",
            "saved/diagnostics/native_dryingbox_open_door_eval_20260624_001500/stdout.log",
            "--stderr-log-path",
            "saved/diagnostics/native_dryingbox_open_door_eval_20260624_001500/stderr.log",
        ]
    )

    assert args.stdout_log_path.endswith("stdout.log")
    assert args.stderr_log_path.endswith("stderr.log")


def test_jsonable_converts_usd_asset_paths_for_runtime_material_readback():
    class AssetPath:
        def __init__(self, path, resolved_path):
            self.path = path
            self.resolvedPath = resolved_path

    payload = {
        "runtime_material_readback": {
            "records": [
                {
                    "shader_reports": [
                        {
                            "mdl_source_asset": AssetPath(
                                "@OmniPBR.mdl@",
                                "/isaac-sim/materials/OmniPBR.mdl",
                            )
                        }
                    ]
                }
            ]
        }
    }

    converted = render_diag._jsonable(payload)

    json.dumps(converted)
    assert converted["runtime_material_readback"]["records"][0]["shader_reports"][0][
        "mdl_source_asset"
    ] == {
        "path": "@OmniPBR.mdl@",
        "resolved_path": "/isaac-sim/materials/OmniPBR.mdl",
    }


def test_shader_material_metadata_records_resolved_mdl_path_and_hash(tmp_path):
    mdl_path = tmp_path / "material_11.mdl"
    mdl_path.write_text("mdl body\n")

    class AssetPath:
        def __init__(self, path, resolved_path):
            self.path = path
            self.resolvedPath = resolved_path

    class Attr:
        def __init__(self, value):
            self.value = value

        def Get(self):
            return self.value

    class ShaderPrim:
        def GetTypeName(self):
            return "Shader"

        def GetPath(self):
            return "/World/Looks/mdl_0007/Shader"

        def GetAttribute(self, name):
            return Attr(
                {
                    "info:implementationSource": "sourceAsset",
                    "info:mdl:sourceAsset": AssetPath(
                        "./SubUSDs/materials/material_11.mdl",
                        str(mdl_path),
                    ),
                    "info:mdl:sourceAsset:subIdentifier": "mdl_0007",
                }.get(name)
            )

    class MaterialPrim:
        def GetChildren(self):
            return [ShaderPrim()]

    class Material:
        def GetPrim(self):
            return MaterialPrim()

    reports = render_diag._shader_material_metadata(Material())

    assert reports[0]["resolved_mdl_path"] == str(mdl_path)
    assert reports[0]["mdl_sha256"] == hashlib.sha256(mdl_path.read_bytes()).hexdigest()


def test_material_binding_metadata_reads_default_purpose_and_strength():
    class BindingRel:
        def GetName(self):
            return "material:binding"

        def GetMetadata(self, name):
            return "strongerThanDescendants" if name == "bindMaterialAs" else None

    metadata = render_diag._material_binding_metadata(BindingRel())

    assert metadata["binding_purpose"] == "allPurpose"
    assert metadata["binding_strength"] == "strongerThanDescendants"
