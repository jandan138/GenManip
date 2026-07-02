import json
from pathlib import Path

from standalone_tools.labutopia_poc import aan_runtime_smoke


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _adapter_record() -> dict:
    return {
        "stage": "aan_runtime_adapter_preflight",
        "status": "pass",
        "allowed_claims": {
            "aan_runtime_adapter_preflight_passed": True,
            "aan_live_eval_smoke_passed": False,
        },
        "blockers": [],
        "command": "python standalone_tools/labutopia_poc/aan_runtime_adapter.py ...",
        "config_path": "ebench/labutopia_lab_poc/aan_lift2_candidate/level1_open_door.yml",
        "task_name": "ebench/labutopia_lab_poc/aan_lift2_candidate/level1_open_door",
        "composite_assets_root": "/assets",
        "namespace": "labutopia_aan_packages/dryingbox_01_overlay",
        "mounted_root_usd": "/assets/labutopia_aan_packages/dryingbox_01_overlay/asset.usd",
        "mounted_root_usd_sha256": "asset-sha",
        "package_tree_digest": "tree-digest",
        "mounted_package_tree_digest": "tree-digest",
        "runtime_usd_name": "scene_usds/labutopia/aan/dryingbox_01_overlay_scene",
        "resolved_runtime_scene": "/assets/scene_usds/labutopia/aan/dryingbox_01_overlay_scene.usda",
        "runtime_scene_sha256": "wrapper-sha",
        "wrapper_references": [
            "../../../labutopia_aan_packages/dryingbox_01_overlay/asset.usd"
        ],
        "legacy_overlay_used": False,
        "required_prim_resolution_rows": [
            {
                "role": "asset_root",
                "path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
                "required": True,
                "exists_in_runtime_wrapper": True,
            }
        ],
    }


def _probe_record(result_info_path: Path, stdout_path: Path, stderr_path: Path) -> dict:
    return {
        "stage": "acceptance_stage_7_lift2_contract_probe",
        "task_name": "level1_open_door",
        "live_probe": {
            "status": "attempted",
            "worker_id": "0",
            "reset_observation_present": True,
            "step_results": [
                {"action_name": "zero_action", "response_present": True, "done": False}
            ],
        },
        "schema_rows": [
            {
                "name": "observation keys",
                "status": "PASS",
                "finding": "reset observation exposes required Lift2 baseline inputs",
            },
            {
                "name": "camera input keys",
                "status": "PASS",
                "finding": "required baseline camera inputs are present and image-shaped",
            },
            {
                "name": "action dialects",
                "status": "PASS",
                "finding": "all supplied action dialects produced live step responses",
            },
            {
                "name": "reward/success fields",
                "status": "PASS",
                "finding": "reward/success fields are sourced from GenManip/EBench step output",
            },
            {
                "name": "logging fields",
                "status": "PASS",
                "finding": "run id, worker, episode, seed, result path, and logs are recorded",
            },
        ],
        "logging": {
            "run_id": "labutopia_aan_live_20260701_0000",
            "worker_id": "0",
            "episode_id": "live_probe",
            "seed": "000",
            "result_path": str(result_info_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
        },
    }


def _result_info_path(tmp_path: Path) -> Path:
    return (
        tmp_path
        / "saved/eval_results/ebench/labutopia_aan_live_20260701_0000/"
        / "ebench/labutopia_lab_poc/aan_lift2_candidate/level1_open_door/000/result_info.json"
    )


def test_builds_pass_record_from_adapter_probe_and_result_info(tmp_path):
    adapter_path = tmp_path / "adapter.json"
    probe_path = tmp_path / "probe.json"
    result_info_path = _result_info_path(tmp_path)
    stdout_path = tmp_path / "probe.stdout.txt"
    stderr_path = tmp_path / "probe.stderr.txt"
    _write_json(adapter_path, _adapter_record())
    _write_json(result_info_path, {"score": 0.0, "success_rate": 0})
    stdout_path.write_text("reset ok\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    _write_json(probe_path, _probe_record(result_info_path, stdout_path, stderr_path))

    record = aan_runtime_smoke.build_runtime_smoke_record(
        adapter_record_path=adapter_path,
        probe_json_path=probe_path,
        json_out=None,
        commands={
            "server": "python ray_eval_server.py --run_id labutopia_aan_live_20260701_0000",
            "submit": "gmp submit ... --run_id labutopia_aan_live_20260701_0000",
            "probe": "python lift2_eval_contract_probe.py --live --run-id labutopia_aan_live_20260701_0000",
            "eval_or_smoke_client": "python -m genmanip_client.cli eval --run_id labutopia_aan_live_20260701_0000 -a r5a -g lift2",
        },
        submit_exit_code=0,
        probe_or_eval_exit_code=0,
        expected_run_id="labutopia_aan_live_20260701_0000",
    )

    assert record["status"] == "PASS"
    assert record["stage"] == "aan_stage4b_live_smoke"
    assert record["run_id"] == "labutopia_aan_live_20260701_0000"
    assert record["run_id_is_fresh"] is True
    assert record["run_id_matches_submit"] is True
    assert record["run_id_matches_probe_or_eval"] is True
    assert record["run_id_matches_result_info_path"] is True
    assert record["config_path"] == (
        "ebench/labutopia_lab_poc/aan_lift2_candidate/level1_open_door.yml"
    )
    assert record["legacy_overlay_used"] is False
    assert record["reset_passed"] is True
    assert record["step_passed"] is True
    assert record["render_passed"] is True
    assert record["metric_passed"] is True
    assert record["logging_passed"] is True
    assert record["result_info_exists"] is True
    assert record["stdout_exists"] is True
    assert record["stderr_exists"] is True
    assert record["submit_exit_code"] == 0
    assert record["probe_or_eval_exit_code"] == 0
    assert record["no_fail_or_blocked_rows"] is True
    assert record["aan_live_eval_smoke_passed"] is True
    assert record["failure_phase"] is None
    assert record["failure_owner"] is None
    assert record["blocker_or_next_action"] is None
    assert record["score"] == 0.0
    assert record["success_rate"] == 0
    assert record["allowed_claims"]["aan_live_eval_smoke_passed"] is True
    assert record["allowed_claims"]["policy_success_proven"] is False
    assert record["blockers"] == []


def test_blocks_when_probe_schema_row_is_blocked(tmp_path):
    adapter_path = tmp_path / "adapter.json"
    probe_path = tmp_path / "probe.json"
    result_info_path = _result_info_path(tmp_path)
    stdout_path = tmp_path / "probe.stdout.txt"
    stderr_path = tmp_path / "probe.stderr.txt"
    _write_json(adapter_path, _adapter_record())
    _write_json(result_info_path, {"score": 0.0, "success_rate": 0})
    stdout_path.write_text("reset ok\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    probe_record = _probe_record(result_info_path, stdout_path, stderr_path)
    probe_record["schema_rows"][1]["status"] = "BLOCKED"
    probe_record["schema_rows"][1]["finding"] = "camera inputs missing"
    _write_json(probe_path, probe_record)

    record = aan_runtime_smoke.build_runtime_smoke_record(
        adapter_record_path=adapter_path,
        probe_json_path=probe_path,
        json_out=None,
        commands={
            "submit": "gmp submit ... --run_id labutopia_aan_live_20260701_0000",
            "probe": "python lift2_eval_contract_probe.py --live --run-id labutopia_aan_live_20260701_0000",
        },
        submit_exit_code=0,
        probe_or_eval_exit_code=0,
        expected_run_id="labutopia_aan_live_20260701_0000",
    )

    assert record["status"] == "BLOCKED"
    assert record["render_passed"] is False
    assert record["failure_phase"] == "render"
    assert record["failure_owner"] == "GenManip/EBench runtime"
    assert record["blocker_or_next_action"]
    assert {
        "code": "probe_row_blocked",
        "field": "schema_rows.camera input keys",
        "status": "BLOCKED",
        "finding": "camera inputs missing",
    } in record["blockers"]
    assert record["allowed_claims"]["aan_live_eval_smoke_passed"] is False


def test_cli_writes_runtime_smoke_record(tmp_path):
    adapter_path = tmp_path / "adapter.json"
    probe_path = tmp_path / "probe.json"
    result_info_path = _result_info_path(tmp_path)
    stdout_path = tmp_path / "probe.stdout.txt"
    stderr_path = tmp_path / "probe.stderr.txt"
    json_out = tmp_path / "runtime_smoke.json"
    _write_json(adapter_path, _adapter_record())
    _write_json(result_info_path, {"score": 0.0, "success_rate": 0})
    stdout_path.write_text("reset ok\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    _write_json(probe_path, _probe_record(result_info_path, stdout_path, stderr_path))

    exit_code = aan_runtime_smoke.main(
        [
            "--adapter-record",
            str(adapter_path),
            "--probe-json",
            str(probe_path),
            "--json-out",
            str(json_out),
            "--expected-run-id",
            "labutopia_aan_live_20260701_0000",
            "--submit-exit-code",
            "0",
            "--probe-or-eval-exit-code",
            "0",
            "--command",
            "submit=gmp submit --run_id labutopia_aan_live_20260701_0000",
            "--command",
            "probe=python lift2_eval_contract_probe.py --live --run-id labutopia_aan_live_20260701_0000",
        ]
    )

    assert exit_code == 0
    record = json.loads(json_out.read_text(encoding="utf-8"))
    assert record["status"] == "PASS"
    assert (
        record["commands"]["probe"]
        == "python lift2_eval_contract_probe.py --live --run-id labutopia_aan_live_20260701_0000"
    )


def test_blocks_without_run_id_artifact_and_exit_code_consistency(tmp_path):
    adapter_path = tmp_path / "adapter.json"
    probe_path = tmp_path / "probe.json"
    result_info_path = _result_info_path(tmp_path)
    stdout_path = tmp_path / "probe.stdout.txt"
    stderr_path = tmp_path / "probe.stderr.txt"
    _write_json(adapter_path, _adapter_record())
    _write_json(result_info_path, {"score": 0.0, "success_rate": 0})
    stdout_path.write_text("reset ok\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    _write_json(probe_path, _probe_record(result_info_path, stdout_path, stderr_path))

    record = aan_runtime_smoke.build_runtime_smoke_record(
        adapter_record_path=adapter_path,
        probe_json_path=probe_path,
        json_out=None,
        commands={
            "submit": "gmp submit ... --run_id stale_old_run",
            "probe": "python lift2_eval_contract_probe.py --live --run-id stale_old_run",
        },
        submit_exit_code=0,
        probe_or_eval_exit_code=1,
        expected_run_id="labutopia_aan_live_20260701_0000",
    )

    assert record["status"] == "BLOCKED"
    assert record["run_id_matches_submit"] is False
    assert record["run_id_matches_probe_or_eval"] is False
    assert record["probe_or_eval_exit_code"] == 1
    assert record["failure_phase"] == "client_probe"
    assert record["failure_owner"] == "LabUtopia consumer"
    blocker_codes = {blocker["code"] for blocker in record["blockers"]}
    assert "run_id_missing_from_submit_command" in blocker_codes
    assert "run_id_missing_from_probe_or_eval_command" in blocker_codes
    assert "probe_or_eval_failed" in blocker_codes


def test_records_runtime_warning_log_without_blocking_stage4b_pass(tmp_path):
    adapter_path = tmp_path / "adapter.json"
    probe_path = tmp_path / "probe.json"
    result_info_path = _result_info_path(tmp_path)
    stdout_path = tmp_path / "probe.stdout.txt"
    stderr_path = tmp_path / "probe.stderr.txt"
    warning_log = tmp_path / "server.stderr.txt"
    _write_json(adapter_path, _adapter_record())
    _write_json(result_info_path, {"score": 0.0, "success_rate": 0})
    stdout_path.write_text("reset ok\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    warning_log.write_text(
        "[MDLC:COMPILER] comp error: OmniPBR_ClearCoat missing\n"
        "[MDLC:COMPILER] comp error: vray_materials missing\n",
        encoding="utf-8",
    )
    _write_json(probe_path, _probe_record(result_info_path, stdout_path, stderr_path))

    record = aan_runtime_smoke.build_runtime_smoke_record(
        adapter_record_path=adapter_path,
        probe_json_path=probe_path,
        json_out=None,
        commands={
            "submit": "gmp submit ... --run_id labutopia_aan_live_20260701_0000",
            "probe": "python lift2_eval_contract_probe.py --live --run-id labutopia_aan_live_20260701_0000",
        },
        submit_exit_code=0,
        probe_or_eval_exit_code=0,
        expected_run_id="labutopia_aan_live_20260701_0000",
        runtime_warning_logs=[warning_log],
    )

    assert record["status"] == "PASS"
    assert record["runtime_warning_summary"]["warning_log_count"] == 1
    assert record["runtime_warning_summary"]["mdl_compiler_error_count"] == 2
    assert record["runtime_warning_summary"]["material_warning_claim_boundary"] == (
        "Stage 4b PASS proves runtime reset/step/render/metric/logging, not full visual material parity."
    )
