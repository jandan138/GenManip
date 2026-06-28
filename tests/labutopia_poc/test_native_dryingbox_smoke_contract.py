def _pose(position=None, orientation=None):
    return {
        "position": position or [0.0, 0.0, 0.0],
        "orientation": orientation or [1.0, 0.0, 0.0, 0.0],
    }


def _step_trace(step_count=120):
    return [
        {
            "step": step + 1,
            "root_pose": _pose(),
            "handle_pose": _pose([0.1, 0.0, 0.0]),
            "joint_positions": [0.0, 0.0],
            "joint_positions_finite": True,
            "root_pose_finite": True,
            "handle_pose_finite": True,
            "door_joint_angle_deg": 0.0,
            "button_joint_position_m": 0.0,
        }
        for step in range(step_count)
    ]


def _material_notes():
    return {
        "material_collection_ok": True,
        "material_runtime_status": "resolved_native_material",
        "world_looks_present": True,
        "task_mesh_count": 3,
        "bound_task_mesh_count": 3,
        "unbound_task_mesh_count": 0,
        "unbound_task_mesh_paths": [],
        "empty_authored_binding_count": 0,
        "empty_authored_binding_paths": [],
        "unresolved_binding_target_count": 0,
        "unresolved_binding_target_paths": [],
        "unresolved_task_material_count": 0,
        "used_material_count": 2,
        "used_material_paths": ["/World/Looks/mat_a", "/World/Looks/mat_b"],
        "remote_material_dependency_count": 0,
        "remote_material_dependency_paths": [],
        "material_binding_gap_count": 0,
        "material_binding_gap_paths": [],
        "material_binding_gap_details": [],
        "material_binding_gap_policy": "warning_requires_readability_evidence",
        "material_binding_gap_readability_status": "not_required",
        "fallback_status": "none",
        "dryingbox_material_compiler_warnings": [],
        "material_compiler_warning_count": 0,
        "collection_error": None,
    }


def _valid_smoke_report():
    return {
        "stage2_status": "passed",
        "stage2_passed": True,
        "stage2_validation_errors": [],
        "schema_version": 1,
        "stage_path": "saved/diagnostics/native_dryingbox_smoke_x/native_dryingbox.usda",
        "source_prim_path": "/World/DryingBox_01",
        "smoke_prim_path": "/World/DryingBox_01",
        "handle_prim_path": "/World/DryingBox_01/handle/mesh",
        "native_stage_mode": "full_source_world",
        "used_ebench_wrapper": False,
        "used_franka_shortcut": False,
        "world_child_discovery_status": "ok",
        "world_child_discovery_method": "pxr",
        "active_world_children": ["DryingBox_01", "Looks", "PhysicsScene"],
        "inactive_world_children": ["DryingBox_02", "Robot"],
        "active_non_target_world_children": [],
        "active_non_target_world_child_count": 0,
        "root_prim_exists": True,
        "handle_prim_exists": True,
        "root_articulation_api_present": True,
        "joint_names": ["RevoluteJoint", "button/PrismaticJoint"],
        "initial_joint_positions": [0.0, 0.0],
        "post_step_joint_positions": [0.0, 0.0],
        "door_joint_path": "/World/DryingBox_01/RevoluteJoint",
        "door_joint_index": 0,
        "source_door_joint_limits_deg": [0.0, 120.0],
        "source_door_joint_limits_source": "source_usd",
        "button_joint_path": "/World/DryingBox_01/button/PrismaticJoint",
        "button_joint_index": 1,
        "root_pose": _pose(),
        "post_step_root_pose": _pose(),
        "handle_pose": _pose([0.1, 0.0, 0.0]),
        "post_step_handle_pose": _pose([0.1, 0.0, 0.0]),
        "root_pose_finite": True,
        "handle_pose_finite": True,
        "runtime_physics_stable": True,
        "physx_warnings": [],
        "physx_warning_scope": "dryingbox_runtime_and_isaac_log_filtered_physics",
        "physx_warning_allowlist": [],
        "physx_warning_denylist": [],
        "unclassified_physx_warnings": [],
        "physx_warning_sources": {
            "log_event_stream_count": 0,
            "isaac_log_count": 0,
        },
        "step_count": 120,
        "step_trace": _step_trace(),
        "finite_trace": True,
        "max_root_translation_drift_m": 0.0,
        "root_translation_drift_tolerance_m": 1e-4,
        "max_root_rotation_drift_deg": 0.0,
        "root_rotation_drift_tolerance_deg": 1e-3,
        "max_handle_translation_drift_m": 0.0,
        "handle_translation_drift_tolerance_m": 1e-4,
        "door_joint_angle_min_deg": 0.0,
        "door_joint_angle_max_deg": 0.0,
        "door_joint_angle_within_limits": True,
        "button_joint_position_min_m": 0.0,
        "button_joint_position_max_m": 0.0,
        "non_door_dof_drift_tolerance": 1e-4,
        "non_door_dof_drift_within_tolerance": True,
        "material_runtime_notes": _material_notes(),
    }


def test_native_dryingbox_smoke_report_contract():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        DEFAULT_STEP_COUNT,
        REQUIRED_SMOKE_KEYS,
        validate_smoke_report,
    )

    required_keys = {
        "stage2_status",
        "stage2_passed",
        "stage2_validation_errors",
        "stage_path",
        "source_prim_path",
        "smoke_prim_path",
        "handle_prim_path",
        "native_stage_mode",
        "used_ebench_wrapper",
        "used_franka_shortcut",
        "world_child_discovery_status",
        "world_child_discovery_method",
        "active_world_children",
        "inactive_world_children",
        "active_non_target_world_children",
        "active_non_target_world_child_count",
        "joint_names",
        "initial_joint_positions",
        "post_step_joint_positions",
        "door_joint_path",
        "door_joint_index",
        "source_door_joint_limits_deg",
        "source_door_joint_limits_source",
        "button_joint_path",
        "button_joint_index",
        "root_pose",
        "post_step_root_pose",
        "handle_pose",
        "post_step_handle_pose",
        "root_pose_finite",
        "handle_pose_finite",
        "runtime_physics_stable",
        "physx_warnings",
        "physx_warning_scope",
        "physx_warning_allowlist",
        "physx_warning_denylist",
        "unclassified_physx_warnings",
        "step_count",
        "step_trace",
        "finite_trace",
        "max_root_translation_drift_m",
        "root_translation_drift_tolerance_m",
        "max_root_rotation_drift_deg",
        "root_rotation_drift_tolerance_deg",
        "max_handle_translation_drift_m",
        "handle_translation_drift_tolerance_m",
        "door_joint_angle_min_deg",
        "door_joint_angle_max_deg",
        "door_joint_angle_within_limits",
        "button_joint_position_min_m",
        "button_joint_position_max_m",
        "non_door_dof_drift_tolerance",
        "non_door_dof_drift_within_tolerance",
        "material_runtime_notes",
    }
    sample = _valid_smoke_report()

    assert DEFAULT_STEP_COUNT == 120
    assert REQUIRED_SMOKE_KEYS == required_keys
    assert required_keys.issubset(sample)
    assert validate_smoke_report(sample) == []


def test_native_dryingbox_smoke_report_rejects_incomplete_stage2_trace():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["step_count"] = 90
    sample["step_trace"] = _step_trace(89)
    sample["finite_trace"] = False

    errors = validate_smoke_report(sample)

    assert "step_count must be exactly 120" in errors
    assert "step_trace length must equal step_count" in errors
    assert "finite_trace must be true" in errors


def test_stage2_status_prevents_partial_smoke_from_looking_passed():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["active_world_children"].append("DryingBox_02")
    sample["active_non_target_world_children"] = ["DryingBox_02"]
    sample["active_non_target_world_child_count"] = 1

    errors = validate_smoke_report(sample)

    assert "active_non_target_world_child_count must be 0" in errors
    assert "stage2_status cannot be passed when validation errors exist" in errors
    assert "stage2_passed cannot be true when validation errors exist" in errors


def test_validate_smoke_report_rejects_non_target_child_list_count_mismatch():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["active_non_target_world_children"] = ["Robot"]
    sample["active_non_target_world_child_count"] = 0

    errors = validate_smoke_report(sample)

    assert "active_non_target_world_children must be empty" in errors
    assert "active_non_target_world_child_count must match active_non_target_world_children" in errors


def test_validate_smoke_report_rejects_non_target_active_world_children_even_when_summary_is_empty():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["active_world_children"].append("Robot")
    sample["active_non_target_world_children"] = []
    sample["active_non_target_world_child_count"] = 0

    errors = validate_smoke_report(sample)

    assert "active_world_children must not include non-target source children" in errors


def test_native_dryingbox_smoke_report_rejects_drift_warning_and_material_blockers():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["max_root_translation_drift_m"] = 0.01
    sample["max_root_rotation_drift_deg"] = 0.1
    sample["max_handle_translation_drift_m"] = 0.02
    sample["door_joint_angle_within_limits"] = False
    sample["non_door_dof_drift_within_tolerance"] = False
    sample["unclassified_physx_warnings"] = ["PhysX warning: unclassified"]
    sample["material_runtime_notes"]["unresolved_binding_target_count"] = 2
    sample["material_runtime_notes"]["unresolved_task_material_count"] = 2
    sample["material_runtime_notes"]["dryingbox_material_compiler_warnings"] = [
        "failed to compile material_09"
    ]
    sample["material_runtime_notes"]["material_compiler_warning_count"] = 1

    errors = validate_smoke_report(sample)

    assert "max_root_translation_drift_m exceeds tolerance" in errors
    assert "max_root_rotation_drift_deg exceeds tolerance" in errors
    assert "max_handle_translation_drift_m exceeds tolerance" in errors
    assert "door_joint_angle_within_limits must be true" in errors
    assert "non_door_dof_drift_within_tolerance must be true" in errors
    assert "unclassified_physx_warnings must be empty" in errors
    assert "material_runtime_notes unresolved_binding_target_count must be 0" in errors
    assert "material_runtime_notes dryingbox_material_compiler_warnings must be empty" in errors


def test_validate_smoke_report_recomputes_root_and_handle_drift_from_trace():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["step_trace"][11]["root_pose"] = _pose([0.01, 0.0, 0.0])
    sample["step_trace"][13]["handle_pose"] = _pose([0.2, 0.0, 0.0])
    sample["max_root_translation_drift_m"] = 0.0
    sample["max_handle_translation_drift_m"] = 0.0
    sample["finite_trace"] = True

    errors = validate_smoke_report(sample)

    assert "max_root_translation_drift_m must match recomputed step_trace drift" in errors
    assert "max_handle_translation_drift_m must match recomputed step_trace drift" in errors
    assert "recomputed root translation drift exceeds tolerance" in errors
    assert "recomputed handle translation drift exceeds tolerance" in errors


def test_validate_smoke_report_requires_initial_and_post_step_poses_for_drift_recompute():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["root_pose"] = None
    sample["handle_pose"] = {"position": [0.0, "nan", 0.0], "orientation": [1.0, 0.0, 0.0, 0.0]}
    sample["post_step_root_pose"] = {
        "position": [0.0, 0.0, "nan"],
        "orientation": [1.0, 0.0, 0.0, 0.0],
    }
    sample["post_step_handle_pose"] = None

    errors = validate_smoke_report(sample)

    assert "root_pose must be finite" in errors
    assert "handle_pose must be finite" in errors
    assert "post_step_root_pose must be finite" in errors
    assert "post_step_handle_pose must be finite" in errors


def test_native_dryingbox_smoke_report_rejects_unstable_or_nonfinite_values():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["post_step_joint_positions"] = ["NaN", 0.0]
    sample["handle_pose_finite"] = False
    sample["runtime_physics_stable"] = False
    sample["physx_warnings"] = ["PhysX warning"]

    errors = validate_smoke_report(sample)

    assert "post_step_joint_positions must contain only finite numbers" in errors
    assert "handle_pose_finite must be true" in errors
    assert "runtime_physics_stable must be true" in errors


def test_validate_smoke_report_rejects_wrong_or_missing_door_button_readback():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["joint_names"] = ["button/PrismaticJoint", "RevoluteJoint"]
    sample["door_joint_index"] = 0
    sample["button_joint_index"] = 1
    sample["step_trace"][3]["door_joint_angle_deg"] = None
    sample["step_trace"][4]["button_joint_position_m"] = "NaN"

    errors = validate_smoke_report(sample)

    assert "door_joint_index must identify a door/revolute joint" in errors
    assert "button_joint_index must identify a button/prismatic joint" in errors
    assert "door_joint_path must match door_joint_index" in errors
    assert "button_joint_path must match button_joint_index" in errors
    assert "step_trace door_joint_angle_deg must be finite for every step" in errors
    assert "step_trace button_joint_position_m must be finite for every step" in errors

    sample = _valid_smoke_report()
    sample["button_joint_index"] = sample["door_joint_index"]
    errors = validate_smoke_report(sample)

    assert "door_joint_index and button_joint_index must be distinct" in errors

    sample = _valid_smoke_report()
    sample["door_joint_path"], sample["button_joint_path"] = (
        sample["button_joint_path"],
        sample["door_joint_path"],
    )
    errors = validate_smoke_report(sample)

    assert "door_joint_path must match door_joint_index" in errors
    assert "button_joint_path must match button_joint_index" in errors


def test_native_dryingbox_smoke_report_rejects_incomplete_joint_readback():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["joint_names"] = []
    sample["step_trace"] = _step_trace()
    sample["step_count"] = 30
    sample["door_joint_index"] = None

    errors = validate_smoke_report(sample)

    assert "joint_names must not be empty" in errors
    assert "joint_names and initial_joint_positions length mismatch" in errors
    assert "joint_names and post_step_joint_positions length mismatch" in errors
    assert "door_joint_index must identify a joint_names entry" in errors
    assert "step_count must be exactly 120" in errors


def test_validate_smoke_report_rejects_nonpassing_status_when_checks_pass():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["stage2_status"] = "attempted"
    sample["stage2_passed"] = False

    errors = validate_smoke_report(sample)

    assert "stage2_status must be passed when validation checks pass" in errors
    assert "stage2_passed must be true when validation checks pass" in errors


def test_native_dryingbox_smoke_report_rejects_runtime_errors_missing_prims_and_bool_positions():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["root_prim_exists"] = False
    sample["handle_prim_exists"] = False
    sample["root_articulation_api_present"] = False
    sample["initial_joint_positions"] = [True, 0.0]
    sample["errors"] = ["RuntimeError: handle prim not found"]
    sample["traceback"] = "Traceback ..."

    errors = validate_smoke_report(sample)

    assert "runtime reported errors: ['RuntimeError: handle prim not found']" in errors
    assert "runtime reported traceback" in errors
    assert "root_prim_exists must be true" in errors
    assert "handle_prim_exists must be true" in errors
    assert "root_articulation_api_present must be true" in errors
    assert "initial_joint_positions must contain only finite numbers" in errors


def test_validate_smoke_report_rejects_denylist_partition_and_collection_errors():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["physx_warnings"] = ["known warning", "bad warning"]
    sample["physx_warning_allowlist"] = ["known warning"]
    sample["physx_warning_denylist"] = ["different bad warning"]
    sample["material_runtime_notes"]["material_collection_ok"] = False
    sample["material_runtime_notes"]["collection_error"] = "pxr.UsdShade unavailable"

    errors = validate_smoke_report(sample)

    assert "physx_warning_denylist must be empty" in errors
    assert "physx warning classification must partition physx_warnings" in errors
    assert "material_runtime_notes material_collection_ok must be true" in errors


def test_validate_smoke_report_allows_material_gaps_only_with_readability_evidence():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    notes = sample["material_runtime_notes"]
    notes["material_runtime_status"] = "mixed_native_and_fallback"
    notes["fallback_status"] = "readability_evidence_accepted"
    notes["unbound_task_mesh_count"] = 1
    notes["unbound_task_mesh_paths"] = ["/World/DryingBox_01/button"]
    notes["material_binding_gap_count"] = 1
    notes["material_binding_gap_paths"] = ["/World/DryingBox_01/button"]
    notes["material_binding_gap_details"] = [
        {
            "mesh_path": "/World/DryingBox_01/button",
            "gap_type": "unbound",
            "displayColor": {"authored": True, "fallback_status": "usable"},
            "readability_evidence_status": "accepted",
        }
    ]
    notes["material_binding_gap_readability_status"] = "accepted"

    assert validate_smoke_report(sample) == []

    notes["material_binding_gap_readability_status"] = "missing"
    errors = validate_smoke_report(sample)

    assert (
        "material_runtime_notes material_binding_gap_readability_status must be accepted when gaps exist"
        in errors
    )


def test_validate_smoke_report_requires_per_gap_readability_details():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    notes = sample["material_runtime_notes"]
    notes["material_runtime_status"] = "mixed_native_and_fallback"
    notes["fallback_status"] = "readability_evidence_accepted"
    notes["unbound_task_mesh_count"] = 1
    notes["unbound_task_mesh_paths"] = ["/World/DryingBox_01/button"]
    notes["material_binding_gap_count"] = 1
    notes["material_binding_gap_paths"] = ["/World/DryingBox_01/button"]
    notes["material_binding_gap_details"] = []
    notes["material_binding_gap_readability_status"] = "accepted"

    errors = validate_smoke_report(sample)

    assert (
        "material_runtime_notes material_binding_gap_details must match gap paths and contain accepted readability evidence"
        in errors
    )


def test_validate_smoke_report_rejects_material_gap_status_inconsistency():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    notes = sample["material_runtime_notes"]
    notes["material_runtime_status"] = "resolved_native_material"
    notes["fallback_status"] = "none"
    notes["unbound_task_mesh_count"] = 1
    notes["unbound_task_mesh_paths"] = ["/World/DryingBox_01/button"]
    notes["material_binding_gap_count"] = 1
    notes["material_binding_gap_paths"] = ["/World/DryingBox_01/button"]
    notes["material_binding_gap_details"] = [
        {
            "mesh_path": "/World/DryingBox_01/button",
            "gap_type": "unbound",
            "displayColor": {"authored": True, "fallback_status": "usable"},
            "readability_evidence_status": "accepted",
        }
    ]
    notes["material_binding_gap_readability_status"] = "accepted"

    errors = validate_smoke_report(sample)

    assert (
        "material_runtime_notes material_runtime_status must be mixed_native_and_fallback when accepted gaps exist"
        in errors
    )
    assert (
        "material_runtime_notes fallback_status must be readability_evidence_accepted when accepted gaps exist"
        in errors
    )


def test_validate_smoke_report_rejects_no_gap_fallback_status_inconsistency():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    notes = sample["material_runtime_notes"]
    notes["material_runtime_status"] = "mixed_native_and_fallback"
    notes["fallback_status"] = "readability_evidence_accepted"
    notes["material_binding_gap_count"] = 0
    notes["material_binding_gap_paths"] = []
    notes["material_binding_gap_details"] = []
    notes["material_binding_gap_readability_status"] = "not_required"

    errors = validate_smoke_report(sample)

    assert (
        "material_runtime_notes material_runtime_status must be resolved_native_material when no gaps or unresolved bindings exist"
        in errors
    )
    assert (
        "material_runtime_notes fallback_status must be none when no gaps or unresolved bindings exist"
        in errors
    )


def test_validate_smoke_report_recomputes_step_trace_and_joint_ranges():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = _valid_smoke_report()
    sample["step_trace"][4]["step"] = 99
    sample["step_trace"][8]["joint_positions"] = [float("nan"), 0.0]
    sample["step_trace"][8]["joint_positions_finite"] = True
    sample["step_trace"][10]["door_joint_angle_deg"] = 121.0
    sample["finite_trace"] = True
    sample["door_joint_angle_within_limits"] = True

    errors = validate_smoke_report(sample)

    assert "step_trace steps must be monotonic 1..step_count" in errors
    assert "finite_trace must match recomputed step_trace finiteness" in errors
    assert "door joint trace exceeds source limits" in errors


def test_minimal_native_stage_does_not_pull_ebench_or_franka(tmp_path):
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        build_minimal_native_stage,
    )

    labutopia_root = tmp_path / "LabUtopia"
    source_stage = labutopia_root / "assets/chemistry_lab/lab_001/lab_001.usd"
    source_stage.parent.mkdir(parents=True)
    source_stage.write_text("#usda 1.0\n", encoding="utf-8")

    stage_path = build_minimal_native_stage(
        labutopia_root=labutopia_root,
        output_root=tmp_path / "smoke",
    )
    stage_text = stage_path.read_text(encoding="utf-8")

    assert "DryingBox_01" in stage_text
    assert "/World/DryingBox_01" in stage_text
    assert "@</World>" in stage_text
    assert "Franka" not in stage_text
    assert "franka" not in stage_text
    assert "EBench" not in stage_text


def test_default_native_stage_deactivates_non_target_world_children(tmp_path):
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        build_minimal_native_stage_with_report,
    )

    labutopia_root = tmp_path / "LabUtopia"
    source_stage = labutopia_root / "assets/chemistry_lab/lab_001/lab_001.usd"
    source_stage.parent.mkdir(parents=True)
    source_stage.write_text(
        "\n".join(
            [
                "#usda 1.0",
                'def Xform "World"',
                "{",
                '    def Scope "Looks" {}',
                '    def PhysicsScene "PhysicsScene" {}',
                '    def Xform "DryingBox_01" {}',
                '    def Xform "DryingBox_02" {}',
                '    def Xform "Robot" {}',
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    stage_path, stage_report = build_minimal_native_stage_with_report(
        labutopia_root=labutopia_root,
        output_root=tmp_path / "smoke",
    )
    stage_text = stage_path.read_text(encoding="utf-8")

    assert stage_report["native_stage_mode"] == "full_source_world"
    assert stage_report["used_ebench_wrapper"] is False
    assert stage_report["used_franka_shortcut"] is False
    assert stage_report["world_child_discovery_status"] == "ok"
    assert stage_report["active_world_children"] == [
        "Looks",
        "PhysicsScene",
        "DryingBox_01",
    ]
    assert stage_report["inactive_world_children"] == ["DryingBox_02", "Robot"]
    assert stage_report["active_non_target_world_children"] == []
    assert stage_report["active_non_target_world_child_count"] == 0
    assert stage_report["material_fallback_overlay_policy"] == (
        "stage2_readability_displayColor_not_native_material_closure"
    )
    assert stage_report["material_fallback_overlay_paths"] == [
        "/World/DryingBox_01/Group/_900_1",
        "/World/DryingBox_01/button",
        "/World/DryingBox_01/panel",
    ]
    assert "@</World>" in stage_text
    assert 'over "DryingBox_02" (' in stage_text
    assert 'over "Robot" (' in stage_text
    assert 'active = false' in stage_text
    assert 'over "Looks" (' not in stage_text
    assert '# Stage 2 readability fallback; not native material closure.' in stage_text
    assert 'over "DryingBox_01"' in stage_text
    assert 'over "button"' in stage_text
    assert 'over "_900_1"' in stage_text
    assert 'over "panel"' in stage_text
    assert "primvars:displayColor" in stage_text
    assert "primvars:displayColor:interpolation" in stage_text


def test_native_stage_fallback_overlay_accepts_known_material_gaps(tmp_path):
    from pxr import Usd, UsdGeom

    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        _collect_material_runtime_notes,
        build_minimal_native_stage_with_report,
        validate_smoke_report,
    )

    labutopia_root = tmp_path / "LabUtopia"
    source_stage = labutopia_root / "assets/chemistry_lab/lab_001/lab_001.usd"
    source_stage.parent.mkdir(parents=True)
    source = Usd.Stage.CreateNew(str(source_stage))
    source.DefinePrim("/World", "Xform")
    source.DefinePrim("/World/Looks", "Scope")
    root = source.DefinePrim("/World/DryingBox_01", "Xform")
    assert root.IsValid()
    UsdGeom.Mesh.Define(source, "/World/DryingBox_01/button")
    empty = UsdGeom.Mesh.Define(source, "/World/DryingBox_01/Group/_900_1")
    empty.GetPrim().CreateRelationship("material:binding").SetTargets([])
    panel = UsdGeom.Mesh.Define(source, "/World/DryingBox_01/panel")
    panel.GetPrim().CreateRelationship("material:binding").SetTargets([])
    UsdGeom.Mesh.Define(source, "/World/Other")
    source.Save()

    stage_path, _stage_report = build_minimal_native_stage_with_report(
        labutopia_root=labutopia_root,
        output_root=tmp_path / "smoke",
    )
    stage = Usd.Stage.Open(str(stage_path))
    notes = _collect_material_runtime_notes(stage, "/World/DryingBox_01")

    assert notes["material_runtime_status"] == "mixed_native_and_fallback"
    assert notes["fallback_status"] == "readability_evidence_accepted"
    assert notes["material_binding_gap_readability_status"] == "accepted"
    assert notes["material_binding_gap_count"] == 3
    assert all(
        detail["readability_evidence_status"] == "accepted"
        for detail in notes["material_binding_gap_details"]
    )

    report = _valid_smoke_report()
    report["material_runtime_notes"] = notes
    assert validate_smoke_report(report) == []


def test_default_native_stage_reports_child_discovery_failure(tmp_path, monkeypatch):
    import standalone_tools.labutopia_poc.run_native_dryingbox_smoke as smoke

    labutopia_root = tmp_path / "LabUtopia"
    source_stage = labutopia_root / "assets/chemistry_lab/lab_001/lab_001.usd"
    source_stage.parent.mkdir(parents=True)
    source_stage.write_text("#usda 1.0\n", encoding="utf-8")
    monkeypatch.setattr(
        smoke,
        "_source_world_child_report",
        lambda _source_stage: {
            "status": "unavailable",
            "method": "none",
            "children": [],
            "error": "pxr unavailable",
        },
    )

    stage_path, stage_report = smoke.build_minimal_native_stage_with_report(
        labutopia_root=labutopia_root,
        output_root=tmp_path / "smoke",
    )

    assert stage_path.exists()
    assert stage_report["world_child_discovery_status"] == "unavailable"
    assert stage_report["world_child_discovery_error"] == "pxr unavailable"
    assert stage_report["active_non_target_world_child_count"] is None


def test_minimal_native_stage_splits_source_and_smoke_prim_paths(tmp_path):
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        build_minimal_native_stage_with_report,
    )

    labutopia_root = tmp_path / "LabUtopia"
    source_stage = labutopia_root / "assets/chemistry_lab/lab_001/lab_001.usd"
    source_stage.parent.mkdir(parents=True)
    source_stage.write_text("#usda 1.0\n", encoding="utf-8")

    stage_path, stage_report = build_minimal_native_stage_with_report(
        labutopia_root=labutopia_root,
        output_root=tmp_path / "smoke",
        source_prim_path="/World/OriginalDryingBox",
        smoke_prim_path="/World/SmokeDryingBox",
    )
    stage_text = stage_path.read_text(encoding="utf-8")

    assert stage_report["native_stage_mode"] == "split_source_smoke_reference"
    assert 'def Xform "SmokeDryingBox"' in stage_text
    assert "@</World/OriginalDryingBox>" in stage_text
    assert 'def Scope "Looks"' in stage_text


def test_classify_physx_warnings_splits_known_and_unclassified():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        _classify_physx_warnings,
    )

    duplicate = "2026 [Warning] [omni.physx.tensors.plugin] Duplicate link name 'mesh' in articulation metatype"
    scale = "2026 [Warning] [omni.physicsschema.plugin] ScaleOrientation is not supported for rigid bodies, prim path: /World/DryingBox_01/handle/mesh."
    unknown = "2026 [Warning] [omni.physx.plugin] New unexpected native smoke warning"

    classified = _classify_physx_warnings([duplicate, scale, unknown])

    assert classified["physx_warning_allowlist"] == [duplicate, scale]
    assert classified["physx_warning_denylist"] == []
    assert classified["unclassified_physx_warnings"] == [unknown]


def test_material_runtime_notes_classify_empty_unbound_and_unresolved_bindings():
    from pxr import Sdf, Usd, UsdGeom, UsdShade

    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        _collect_material_runtime_notes,
    )

    stage = Usd.Stage.CreateInMemory()
    stage.DefinePrim("/World", "Xform")
    stage.DefinePrim("/World/Looks", "Scope")
    root = stage.DefinePrim("/World/DryingBox_01", "Xform")
    assert root.IsValid()
    material = UsdShade.Material.Define(stage, "/World/Looks/mat")
    bound_mesh = UsdGeom.Mesh.Define(stage, "/World/DryingBox_01/bound_mesh")
    UsdShade.MaterialBindingAPI.Apply(bound_mesh.GetPrim()).Bind(material)
    UsdGeom.Mesh.Define(stage, "/World/DryingBox_01/unbound_mesh")
    empty_mesh = UsdGeom.Mesh.Define(stage, "/World/DryingBox_01/empty_binding_mesh")
    empty_mesh.GetPrim().CreateRelationship("material:binding").SetTargets([])
    unresolved_mesh = UsdGeom.Mesh.Define(stage, "/World/DryingBox_01/unresolved_mesh")
    binding_api = UsdShade.MaterialBindingAPI.Apply(unresolved_mesh.GetPrim())
    binding_api.GetDirectBindingRel().SetTargets([Sdf.Path("/World/Looks/missing")])

    notes = _collect_material_runtime_notes(stage, "/World/DryingBox_01")

    assert notes["material_collection_ok"] is True
    assert notes["world_looks_present"] is True
    assert notes["task_mesh_count"] == 4
    assert notes["bound_task_mesh_count"] == 1
    assert notes["used_material_count"] == 1
    assert notes["used_material_paths"] == ["/World/Looks/mat"]
    assert notes["unbound_task_mesh_count"] == 1
    assert notes["unbound_task_mesh_paths"] == ["/World/DryingBox_01/unbound_mesh"]
    assert notes["empty_authored_binding_count"] == 1
    assert notes["empty_authored_binding_paths"] == [
        "/World/DryingBox_01/empty_binding_mesh"
    ]
    assert notes["unresolved_binding_target_count"] == 1
    assert notes["unresolved_binding_target_paths"] == [
        "/World/DryingBox_01/unresolved_mesh"
    ]
    assert notes["material_binding_gap_count"] == 2
    assert notes["material_binding_gap_paths"] == [
        "/World/DryingBox_01/empty_binding_mesh",
        "/World/DryingBox_01/unbound_mesh",
    ]
    assert notes["material_binding_gap_readability_status"] == "missing"


def test_extract_physx_warnings_from_isaac_log(tmp_path):
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        _extract_physx_warnings_from_log,
    )

    log_path = tmp_path / "kit.log"
    log_path.write_text(
        "\n".join(
            [
                "2026 [Info] [omni.physx.plugin] Using CUDA device ordinal 0.",
                "2026 [Warning] [omni.physx.tensors.plugin] Duplicate link name 'mesh' in articulation metatype",
                "2026 [Warn] [omni.physx.tensors.plugin] Alternate warning spelling",
                "2026 [Warning] [omni.usd] Material binding target outside reference scope",
                "2026 [Warning] [omni.physics] Joint target did not resolve",
            ]
        ),
        encoding="utf-8",
    )

    warnings = _extract_physx_warnings_from_log(log_path)

    assert warnings == [
        "2026 [Warning] [omni.physx.tensors.plugin] Duplicate link name 'mesh' in articulation metatype",
        "2026 [Warn] [omni.physx.tensors.plugin] Alternate warning spelling",
        "2026 [Warning] [omni.physics] Joint target did not resolve",
    ]


def test_isaac_log_candidates_searches_supplied_roots(tmp_path):
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        _isaac_log_candidates,
    )

    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b" / "4.1"
    root_a.mkdir()
    root_b.mkdir(parents=True)
    old_log = root_a / "kit_old.log"
    new_log = root_b / "kit_new.log"
    old_log.write_text("old", encoding="utf-8")
    new_log.write_text("new", encoding="utf-8")

    candidates = _isaac_log_candidates(log_roots=[root_a, tmp_path / "root_b"])

    assert candidates == [old_log, new_log]
