def test_native_dryingbox_smoke_report_contract():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        REQUIRED_SMOKE_KEYS,
        validate_smoke_report,
    )

    required_keys = {
        "stage_path",
        "source_prim_path",
        "joint_names",
        "initial_joint_positions",
        "post_step_joint_positions",
        "root_pose_finite",
        "handle_pose_finite",
        "runtime_physics_stable",
        "physx_warnings",
    }
    sample = {
        "stage_path": "saved/diagnostics/native_dryingbox_smoke_x/native_dryingbox.usda",
        "source_prim_path": "/World/DryingBox_01",
        "root_prim_exists": True,
        "handle_prim_exists": True,
        "root_articulation_api_present": True,
        "joint_names": ["RevoluteJoint"],
        "initial_joint_positions": [0.0],
        "post_step_joint_positions": [0.0],
        "root_pose_finite": True,
        "handle_pose_finite": True,
        "runtime_physics_stable": True,
        "physx_warnings": [],
        "step_count": 90,
    }

    assert REQUIRED_SMOKE_KEYS == required_keys
    assert required_keys.issubset(sample)
    assert validate_smoke_report(sample) == []


def test_native_dryingbox_smoke_report_rejects_unstable_or_nonfinite_values():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = {
        "stage_path": "saved/diagnostics/native_dryingbox_smoke_x/native_dryingbox.usda",
        "source_prim_path": "/World/DryingBox_01",
        "root_prim_exists": True,
        "handle_prim_exists": True,
        "root_articulation_api_present": True,
        "joint_names": ["RevoluteJoint"],
        "initial_joint_positions": [0.0],
        "post_step_joint_positions": ["NaN"],
        "root_pose_finite": True,
        "handle_pose_finite": False,
        "runtime_physics_stable": False,
        "physx_warnings": ["PhysX warning"],
    }

    errors = validate_smoke_report(sample)

    assert "post_step_joint_positions must contain only finite numbers" in errors
    assert "handle_pose_finite must be true" in errors
    assert "runtime_physics_stable must be true" in errors


def test_native_dryingbox_smoke_report_rejects_incomplete_joint_readback():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = {
        "stage_path": "saved/diagnostics/native_dryingbox_smoke_x/native_dryingbox.usda",
        "source_prim_path": "/World/DryingBox_01",
        "root_prim_exists": True,
        "handle_prim_exists": True,
        "root_articulation_api_present": True,
        "joint_names": [],
        "initial_joint_positions": [0.0],
        "post_step_joint_positions": [0.0],
        "root_pose_finite": True,
        "handle_pose_finite": True,
        "runtime_physics_stable": True,
        "physx_warnings": [],
        "step_count": 30,
    }

    errors = validate_smoke_report(sample)

    assert "joint_names must not be empty" in errors
    assert "joint_names and initial_joint_positions length mismatch" in errors
    assert "joint_names and post_step_joint_positions length mismatch" in errors
    assert "step_count must be an integer between 60 and 120" in errors


def test_native_dryingbox_smoke_report_rejects_runtime_errors_missing_prims_and_bool_positions():
    from standalone_tools.labutopia_poc.run_native_dryingbox_smoke import (
        validate_smoke_report,
    )

    sample = {
        "stage_path": "saved/diagnostics/native_dryingbox_smoke_x/native_dryingbox.usda",
        "source_prim_path": "/World/DryingBox_01",
        "root_prim_exists": False,
        "handle_prim_exists": False,
        "root_articulation_api_present": False,
        "joint_names": ["RevoluteJoint"],
        "initial_joint_positions": [True],
        "post_step_joint_positions": [0.0],
        "root_pose_finite": True,
        "handle_pose_finite": True,
        "runtime_physics_stable": True,
        "physx_warnings": [],
        "errors": ["RuntimeError: handle prim not found"],
        "traceback": "Traceback ...",
    }

    errors = validate_smoke_report(sample)

    assert "runtime reported errors: ['RuntimeError: handle prim not found']" in errors
    assert "runtime reported traceback" in errors
    assert "root_prim_exists must be true" in errors
    assert "handle_prim_exists must be true" in errors
    assert "root_articulation_api_present must be true" in errors
    assert "initial_joint_positions must contain only finite numbers" in errors


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
    assert "Franka" not in stage_text
    assert "franka" not in stage_text
    assert "EBench" not in stage_text


def test_minimal_native_stage_splits_source_and_smoke_prim_paths(tmp_path):
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
        source_prim_path="/World/OriginalDryingBox",
        smoke_prim_path="/World/SmokeDryingBox",
    )
    stage_text = stage_path.read_text(encoding="utf-8")

    assert 'def Xform "SmokeDryingBox"' in stage_text
    assert "@</World/OriginalDryingBox>" in stage_text


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
