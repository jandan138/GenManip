import copy
import json

import pytest

from standalone_tools.labutopia_poc import aan_consumer_check


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_package_file(package_dir, relative_path, content="fixture"):
    path = package_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _base_manifest():
    return {
        "schema_version": "asset_application_normalizer.v1",
        "package_id": "dryingbox_01_overlay_ebench-lift2_isaac41",
        "overall_status": "pass",
        "target": {
            "target_runtime_profile": "isaac41",
            "target_benchmark_profile": "ebench-lift2",
        },
        "entrypoints": {
            "root_usd": "asset.usd",
            "task_config": "task/task_config.yaml",
            "required_prims": "task/required_prims.yaml",
            "metric_evaluator": "task/evaluator.yaml",
        },
        "dependency_closure": {
            "local_files": [
                {"package_path": "asset.usd", "status": "packaged"},
                {"package_path": "task/task_config.yaml", "status": "packaged"},
            ],
        },
        "stage_gates": [
            {"stage": "usd_closure", "status": "pass"},
            {"stage": "material_closure", "status": "pass"},
            {"stage": "physics_static", "status": "pass"},
            {"stage": "runtime_smoke", "status": "pass"},
            {"stage": "benchmark_contract", "status": "pass"},
        ],
        "blocked_reasons": [],
        "waivers": [],
    }


def _write_ready_fixture(tmp_path, manifest_overrides=None, omit_entrypoint=None):
    package_dir = tmp_path / "package"
    for rel_path in (
        "asset.usd",
        "task/task_config.yaml",
        "task/required_prims.yaml",
        "task/evaluator.yaml",
    ):
        if rel_path != omit_entrypoint:
            _write_package_file(package_dir, rel_path)

    manifest = _base_manifest()
    if manifest_overrides:
        manifest = copy.deepcopy(manifest)
        for key, value in manifest_overrides.items():
            manifest[key] = value
    manifest_path = tmp_path / "dryingbox_runtime_ready_manifest.json"
    _write_json(manifest_path, manifest)
    return package_dir, manifest_path


def _run_check(tmp_path, package_dir, manifest_path, *extra_args):
    consumer_out = tmp_path / "consumer_check.json"
    intake_out = tmp_path / "package_intake.json"
    exit_code = aan_consumer_check.main(
        [
            "--package-dir",
            str(package_dir),
            "--manifest",
            str(manifest_path),
            "--json-out",
            str(consumer_out),
            "--intake-json-out",
            str(intake_out),
            *extra_args,
        ]
    )
    return (
        exit_code,
        json.loads(consumer_out.read_text(encoding="utf-8")),
        json.loads(intake_out.read_text(encoding="utf-8")),
    )


def test_ready_manifest_records_intake_and_consumer_flags(tmp_path):
    package_dir, manifest_path = _write_ready_fixture(tmp_path)

    exit_code, consumer, intake = _run_check(tmp_path, package_dir, manifest_path)

    assert exit_code == 0
    assert consumer["status"] == "pass"
    assert consumer["aan_consumer_manifest_ready"] is True
    assert consumer["aan_package_mount_allowed"] is True
    assert consumer["local_usd_repair_allowed"] is False
    assert consumer["forbidden_claims"] == ["ebench_task_execution_passed"]
    assert consumer["blockers"] == []
    assert set(consumer["entrypoints"].keys()) == {
        "root_usd",
        "task_config",
        "required_prims",
        "metric_evaluator",
    }
    assert all(entry["resolved_inside_package"] for entry in consumer["entrypoints"].values())

    assert intake["status"] == "pass"
    assert intake["package_owner"] == "ConvertAsset"
    assert intake["consumer_owner"] == "GenManip / LabUtopia POC"
    assert intake["retained_package_root"] == str(package_dir.resolve())
    assert intake["retained_manifest_path"] == str(manifest_path.resolve())
    assert intake["source_manifest_sha256"]
    assert intake["package_directory_file_count"] == 4
    assert intake["package_consumption"]["read_only"] is True
    assert intake["package_consumption"]["generated_mount_namespace_copy"] is False


def test_wrong_target_profile_records_structured_blocker(tmp_path):
    manifest = _base_manifest()
    manifest["target"]["target_runtime_profile"] = "isaac51"
    package_dir, manifest_path = _write_ready_fixture(tmp_path, {"target": manifest["target"]})

    exit_code, consumer, _intake = _run_check(tmp_path, package_dir, manifest_path)

    assert exit_code == 1
    assert consumer["status"] == "blocked"
    assert consumer["aan_consumer_manifest_ready"] is False
    assert consumer["aan_package_mount_allowed"] is False
    assert {
        "code": "wrong_target_profile",
        "field": "target.target_runtime_profile",
        "expected": "isaac41",
        "actual": "isaac51",
    } in consumer["blockers"]


def test_missing_entrypoint_records_structured_blocker(tmp_path):
    package_dir, manifest_path = _write_ready_fixture(
        tmp_path, omit_entrypoint="task/evaluator.yaml"
    )

    exit_code, consumer, _intake = _run_check(tmp_path, package_dir, manifest_path)

    assert exit_code == 1
    assert {
        "code": "missing_entrypoint",
        "field": "entrypoints.metric_evaluator",
        "path": "task/evaluator.yaml",
    } in consumer["blockers"]


def test_blocked_reason_blocks_mount(tmp_path):
    package_dir, manifest_path = _write_ready_fixture(
        tmp_path, {"blocked_reasons": ["runtime smoke missing"]}
    )

    exit_code, consumer, _intake = _run_check(tmp_path, package_dir, manifest_path)

    assert exit_code == 1
    assert consumer["aan_package_mount_allowed"] is False
    assert {
        "code": "blocked_reason",
        "field": "blocked_reasons",
        "reason": "runtime smoke missing",
    } in consumer["blockers"]


def test_unaccepted_waiver_blocks_until_explicitly_accepted(tmp_path):
    package_dir, manifest_path = _write_ready_fixture(
        tmp_path, {"waivers": [{"id": "waive-material-note", "reason": "fixture"}]}
    )

    exit_code, consumer, _intake = _run_check(tmp_path, package_dir, manifest_path)

    assert exit_code == 1
    assert {
        "code": "unaccepted_waiver",
        "field": "waivers",
        "waiver_id": "waive-material-note",
    } in consumer["blockers"]

    exit_code, accepted, _intake = _run_check(
        tmp_path, package_dir, manifest_path, "--accept-waiver", "waive-material-note"
    )
    assert exit_code == 0
    assert accepted["status"] == "pass"
    assert accepted["accepted_waivers"] == ["waive-material-note"]


def test_unresolved_dependency_records_structured_blocker(tmp_path):
    manifest = _base_manifest()
    manifest["dependency_closure"]["local_files"].append(
        {"package_path": "deps/missing.usd", "status": "missing"}
    )
    package_dir, manifest_path = _write_ready_fixture(
        tmp_path, {"dependency_closure": manifest["dependency_closure"]}
    )

    exit_code, consumer, _intake = _run_check(tmp_path, package_dir, manifest_path)

    assert exit_code == 1
    assert {
        "code": "unresolved_dependency",
        "field": "dependency_closure.local_files[2].status",
        "path": "deps/missing.usd",
        "status": "missing",
    } in consumer["blockers"]
