import sys
from types import SimpleNamespace

from standalone_tools.labutopia_poc import lift2_eval_contract_probe as probe


def _complete_observation():
    return {
        "instruction": "Open the door of the drying box.",
        "state.joints": [0.0] * 16,
        "state.gripper": [0.0, 0.0],
        "state.base": [0.0, 0.0, 0.0],
        "state.ee_pose": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]],
        "video.overlook_camera_view": {
            "type": "jpeg_bytes",
            "dtype": "uint8",
            "shape": [720, 1280, 3],
            "bytes": 1024,
        },
        "video.left_camera_view": {
            "type": "jpeg_bytes",
            "dtype": "uint8",
            "shape": [480, 640, 3],
            "bytes": 512,
        },
        "video.right_camera_view": {
            "type": "jpeg_bytes",
            "dtype": "uint8",
            "shape": [480, 640, 3],
            "bytes": 512,
        },
        "timestep": 0,
        "reset": True,
        "episode_id": "benchmark/run/task/0",
        "robot_id": "manip/lift2/R5a",
    }


def _complete_logging():
    return {
        "run_id": "labutopia_lift2_schema_smoke",
        "worker_id": "0",
        "episode_id": "benchmark/run/task/0",
        "seed": 0,
        "result_path": "/tmp/labutopia_lift2_schema_client_results/result_info.json",
        "stdout_path": "/tmp/labutopia_lift2_schema_client_results/stdout.log",
        "stderr_path": "/tmp/labutopia_lift2_schema_client_results/stderr.log",
    }


def _complete_task_rows():
    return [
        {
            "task": task,
            "Reset": "PASS",
            "Step": "PASS",
            "Reachability": "PASS",
            "Camera Inputs": "PASS",
            "Metric": "PASS",
            "Finding": "live evidence passed",
        }
        for task in probe.REQUIRED_TASKS
    ]


def test_stage7_readiness_requires_every_row_to_pass():
    rows = [
        {"name": "level1_pick reset", "status": "PASS"},
        {"name": "level1_place camera", "status": "BLOCKED"},
    ]

    result = probe.classify_stage7_readiness(rows, task_rows=_complete_task_rows())

    assert result["stage7_status"] == "Stage 7 attempted, blocked"
    assert result["lift2_contract_ready"] is False


def test_stage7_readiness_reports_failed_when_no_blocker_remains():
    rows = [
        {"name": "level1_pick reset", "status": "PASS"},
        {"name": "level1_place action dialect", "status": "FAIL"},
    ]

    result = probe.classify_stage7_readiness(rows, task_rows=_complete_task_rows())

    assert result["stage7_status"] == "Stage 7 attempted, failed"
    assert result["lift2_contract_ready"] is False


def test_stage7_readiness_passes_only_all_pass_rows():
    rows = [
        {"name": "level1_pick reset", "status": "PASS"},
        {"name": "observation keys", "status": "PASS"},
    ]

    result = probe.classify_stage7_readiness(rows, task_rows=_complete_task_rows())

    assert result["stage7_status"] == "Stage 7 passed"
    assert result["lift2_contract_ready"] is True
    assert result["local_official_baseline_style_contract_ready"] is True
    assert result["official_baseline_evaluable"] is False


def test_stage7_readiness_blocks_when_task_matrix_is_requested_but_missing():
    rows = [
        {"name": "observation keys", "status": "PASS"},
        {"name": "camera input keys", "status": "PASS"},
        {"name": "action dialects", "status": "PASS"},
        {"name": "reward/success fields", "status": "PASS"},
        {"name": "logging fields", "status": "PASS"},
    ]

    result = probe.classify_stage7_readiness(rows, task_rows=[])

    assert result["stage7_status"] == "Stage 7 attempted, blocked"
    assert result["lift2_contract_ready"] is False
    assert result["blocked_rows"][0]["name"] == "task readiness matrix"


def test_schema_only_probe_does_not_make_global_stage7_claim():
    rows = [
        {"name": "observation keys", "status": "PASS"},
        {"name": "camera input keys", "status": "PASS"},
        {"name": "action dialects", "status": "PASS"},
        {"name": "reward/success fields", "status": "PASS"},
        {"name": "logging fields", "status": "PASS"},
    ]

    result = probe.classify_stage7_readiness(rows)

    assert result["stage7_status"] == (
        "Stage 7 not evaluated by single-task live schema probe"
    )
    assert result["claim_scope"] == "single_task_live_schema_probe_only"
    assert result["probe_status"] == "single-task live schema probe passed"
    assert result["aggregate_stage7_manifest_required"] is True
    assert result["lift2_contract_ready"] is None
    assert result["local_official_baseline_style_contract_ready"] is None
    assert result["blocked_rows"] == []


def test_probe_accepts_complete_lift2_schema_snapshot():
    snapshot = probe.build_contract_snapshot(
        task_name="level1_open_door",
        observation=_complete_observation(),
        actions=probe.build_action_dialect_matrix(
            joint_positions=[0.0] * 16,
            include_optional_internvla=True,
        ),
        step_response={
            "reward": 0.0,
            "done": False,
            "info": {"info": 0.0, "success": False},
        },
        logging=_complete_logging(),
    )

    rows = {row["name"]: row for row in snapshot["schema_rows"]}

    assert rows["observation keys"]["status"] == "PASS"
    assert rows["camera input keys"]["status"] == "PASS"
    assert rows["action dialects"]["status"] == "PASS"
    assert rows["reward/success fields"]["status"] == "PASS"
    assert rows["logging fields"]["status"] == "PASS"
    assert snapshot["claim_boundary"]["lift2_contract_ready"] is None
    assert snapshot["claim_boundary"]["stage7_status"] == (
        "Stage 7 not evaluated by single-task live schema probe"
    )
    assert snapshot["claim_boundary"]["probe_status"] == (
        "single-task live schema probe passed"
    )
    assert snapshot["claim_boundary"]["official_baseline_evaluable"] is False
    assert snapshot["claim_boundary"]["native_material_closure_claim_allowed"] is False


def test_probe_requires_non_null_metric_output_for_reward_success_pass():
    row = probe.classify_reward_success_fields(
        {
            "reward": None,
            "done": False,
            "info": {"info": None, "success": None},
        }
    )

    assert row["status"] == "BLOCKED"


def test_probe_blocks_without_live_eval_observation_evidence():
    snapshot = probe.build_contract_snapshot(
        task_name="level1_open_door",
        observation=None,
        actions=probe.build_action_dialect_matrix(joint_positions=[0.0] * 16),
        step_response=None,
        logging={
            "run_id": "labutopia_lift2_schema_smoke",
            "worker_id": "0",
        },
    )

    rows = {row["name"]: row for row in snapshot["schema_rows"]}

    assert rows["observation keys"]["status"] == "BLOCKED"
    assert rows["camera input keys"]["status"] == "BLOCKED"
    assert rows["reward/success fields"]["status"] == "BLOCKED"
    assert rows["logging fields"]["status"] == "BLOCKED"
    assert snapshot["claim_boundary"]["stage7_status"] == (
        "Stage 7 not evaluated by single-task live schema probe"
    )
    assert snapshot["claim_boundary"]["probe_status"] == (
        "single-task live schema probe blocked"
    )
    assert snapshot["claim_boundary"]["official_baseline_evaluable"] is False


def test_eval_client_factory_passes_run_id(monkeypatch):
    captured = {}

    class FakeEvalClient:
        def __init__(self, base_url, *, worker_ids, run_id):
            captured["base_url"] = base_url
            captured["worker_ids"] = worker_ids
            captured["run_id"] = run_id

    monkeypatch.setitem(
        sys.modules,
        "genmanip_client",
        SimpleNamespace(EvalClient=FakeEvalClient),
    )

    factory = probe.build_eval_client_factory(
        base_url="http://127.0.0.1:18088",
        worker_id="0",
        run_id="labutopia_lift2_schema_smoke_20260628_191421",
    )
    factory()

    assert captured == {
        "base_url": "http://127.0.0.1:18088",
        "worker_ids": ["0"],
        "run_id": "labutopia_lift2_schema_smoke_20260628_191421",
    }


def test_live_probe_resets_and_steps_action_dialect_matrix():
    class FakeClient:
        def __init__(self):
            self.actions = []
            self.closed = False

        def reset(self):
            return {"0": {"obs": _complete_observation()}}

        def step(self, action_by_worker):
            self.actions.append(action_by_worker["0"])
            return (
                {
                    "0": {
                        "obs": _complete_observation(),
                        "metric": 0.0,
                    }
                },
                False,
            )

        def close(self):
            self.closed = True

    client = FakeClient()

    result = probe.run_live_probe(
        client_factory=lambda: client,
        worker_id="0",
        task_name="level1_open_door",
        joint_position_count=16,
        include_optional_internvla=True,
        logging=_complete_logging(),
    )

    assert len(client.actions) == 5
    assert client.closed is True
    assert result["live_probe"]["status"] == "attempted"
    assert result["schema_rows"][2]["name"] == "action dialects"
    assert result["schema_rows"][2]["status"] == "PASS"


def test_live_probe_blocks_action_row_when_not_every_dialect_executes():
    class FakeClient:
        def __init__(self):
            self.actions = []

        def reset(self):
            return {"0": {"obs": _complete_observation()}}

        def step(self, action_by_worker):
            self.actions.append(action_by_worker["0"])
            return (
                {
                    "0": {
                        "obs": _complete_observation(),
                        "metric": 0.0,
                    }
                },
                True,
            )

        def close(self):
            pass

    client = FakeClient()

    result = probe.run_live_probe(
        client_factory=lambda: client,
        worker_id="0",
        task_name="level1_open_door",
        joint_position_count=16,
        include_optional_internvla=True,
        logging=_complete_logging(),
    )

    rows = {row["name"]: row for row in result["schema_rows"]}
    assert len(client.actions) == 1
    assert rows["action dialects"]["status"] == "BLOCKED"


def test_live_probe_records_exception_as_blocked_evidence():
    def failing_client_factory():
        raise ModuleNotFoundError("No module named 'turbojpeg'")

    result = probe.run_live_probe(
        client_factory=failing_client_factory,
        worker_id="0",
        task_name="level1_open_door",
        joint_position_count=16,
        include_optional_internvla=False,
        logging={"run_id": "labutopia_lift2_schema_smoke", "worker_id": "0"},
    )

    assert result["live_probe"]["status"] == "blocked"
    assert "ModuleNotFoundError" in result["live_probe"]["exception_type"]
    assert result["claim_boundary"]["stage7_status"] == (
        "Stage 7 not evaluated by single-task live schema probe"
    )
    assert result["claim_boundary"]["probe_status"] == (
        "single-task live schema probe blocked"
    )
