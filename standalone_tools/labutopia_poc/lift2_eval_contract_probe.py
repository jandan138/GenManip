#!/usr/bin/env python3
"""Stage 7 Lift2 baseline-style contract probe for LabUtopia tasks."""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any


VALID_STATUSES = {"PASS", "FAIL", "BLOCKED"}
REQUIRED_TASKS = ["level1_pick", "level1_place", "level1_open_door"]
BASELINE_CAMERA_INPUT_KEYS = [
    "video.overlook_camera_view",
    "video.left_camera_view",
    "video.right_camera_view",
]
REQUIRED_OBSERVATION_KEYS = [
    "instruction",
    "state.joints",
    "state.gripper",
    "state.base",
    "state.ee_pose",
    *BASELINE_CAMERA_INPUT_KEYS,
    "timestep",
    "reset",
    "robot_id",
]
REQUIRED_ACTION_FIELDS = [
    "action",
    "base_motion",
    "control_type",
    "is_rel",
    "base_is_rel",
]
EXPECTED_ACTION_SHAPE = [16]
EXPECTED_BASE_MOTION_SHAPE = [3]
TASK_ROW_STATUS_FIELDS = ["Reset", "Step", "Reachability", "Camera Inputs", "Metric"]


def _read_json(path: str | None) -> Any:
    if not path:
        return None
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, bytes):
        return {"type": "bytes", "bytes": len(value)}
    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    return value


def _nested_shape(value: Any) -> list[int] | None:
    if isinstance(value, dict) and isinstance(value.get("shape"), (list, tuple)):
        return [int(item) for item in value["shape"]]
    if hasattr(value, "shape"):
        return [int(item) for item in value.shape]
    if isinstance(value, (list, tuple)):
        shape = [len(value)]
        current = value
        while current and isinstance(current, (list, tuple)):
            first = current[0]
            if not isinstance(first, (list, tuple)):
                break
            shape.append(len(first))
            current = first
        return shape
    return None


def _status_row(
    name: str,
    status: str,
    finding: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid Stage 7 row status: {status}")
    row: dict[str, Any] = {"name": name, "status": status, "finding": finding}
    if details:
        row["details"] = _jsonable(details)
    return row


def summarize_observation_schema(observation: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(observation, dict):
        return {
            "present": False,
            "keys": [],
            "camera_keys": [],
            "entries": {},
        }
    entries: dict[str, Any] = {}
    for key, value in sorted(observation.items()):
        item: dict[str, Any] = {"type": type(value).__name__}
        shape = _nested_shape(value)
        if shape is not None:
            item["shape"] = shape
        if isinstance(value, dict) and "bytes" in value:
            item["bytes"] = value["bytes"]
        elif isinstance(value, dict) and isinstance(value.get("data"), bytes):
            item["bytes"] = len(value["data"])
        elif isinstance(value, (list, tuple)):
            item["length"] = len(value)
        entries[key] = item
    keys = sorted(observation)
    return {
        "present": True,
        "keys": keys,
        "camera_keys": [key for key in keys if key.startswith("video.")],
        "entries": entries,
    }


def classify_observation_keys(schema: dict[str, Any]) -> dict[str, Any]:
    if not schema.get("present"):
        return _status_row(
            "observation keys",
            "BLOCKED",
            "no reset observation schema was provided",
        )
    keys = set(schema.get("keys", []))
    missing = [key for key in REQUIRED_OBSERVATION_KEYS if key not in keys]
    if missing:
        return _status_row(
            "observation keys",
            "BLOCKED",
            "reset observation is missing required Lift2 baseline inputs",
            details={"missing": missing},
        )
    return _status_row(
        "observation keys",
        "PASS",
        "reset observation exposes required Lift2 baseline inputs",
    )


def classify_camera_input_keys(schema: dict[str, Any]) -> dict[str, Any]:
    if not schema.get("present"):
        return _status_row(
            "camera input keys",
            "BLOCKED",
            "no reset observation schema was provided",
        )
    entries = schema.get("entries", {})
    missing = [key for key in BASELINE_CAMERA_INPUT_KEYS if key not in entries]
    if missing:
        return _status_row(
            "camera input keys",
            "BLOCKED",
            "baseline camera input keys are absent from reset observation",
            details={"missing": missing},
        )
    bad_shapes: dict[str, Any] = {}
    for key in BASELINE_CAMERA_INPUT_KEYS:
        shape = entries.get(key, {}).get("shape")
        if not isinstance(shape, list) or len(shape) != 3 or int(shape[-1]) not in (3, 4):
            bad_shapes[key] = shape
    if bad_shapes:
        return _status_row(
            "camera input keys",
            "FAIL",
            "baseline camera inputs are present but not image-like HWC arrays",
            details={"bad_shapes": bad_shapes},
        )
    return _status_row(
        "camera input keys",
        "PASS",
        "required baseline camera inputs are present and image-shaped",
    )


def _action(name: str, *, base_is_rel: bool, action: list[float]) -> dict[str, Any]:
    return {
        "name": name,
        "action": action,
        "base_motion": [0.0, 0.0, 0.0],
        "control_type": "joint_position",
        "is_rel": False,
        "base_is_rel": base_is_rel,
    }


def build_action_dialect_matrix(
    *,
    joint_positions: list[float] | tuple[float, ...],
    include_optional_internvla: bool = False,
) -> list[dict[str, Any]]:
    base_action = [0.0 for _ in range(len(joint_positions))]
    actions = [
        _action("zero_action", base_is_rel=True, action=base_action),
        _action("openpi_relative_base_motion", base_is_rel=True, action=base_action),
        _action("xvla_absolute_base_motion", base_is_rel=False, action=base_action),
    ]
    if include_optional_internvla:
        actions.extend(
            [
                _action(
                    "internvla_a1_single_step_relative_base_motion",
                    base_is_rel=True,
                    action=base_action,
                ),
                _action(
                    "internvla_a1_chunk_absolute_base_motion",
                    base_is_rel=False,
                    action=base_action,
                ),
            ]
        )
    return actions


def classify_action_dialects(
    actions: list[dict[str, Any]] | None,
    action_execution_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(actions, list) or not actions:
        return _status_row(
            "action dialects",
            "BLOCKED",
            "no action dialect matrix was provided",
        )
    findings: dict[str, list[str]] = {}
    for action in actions:
        name = str(action.get("name", "<unnamed>"))
        issues: list[str] = []
        missing = [field for field in REQUIRED_ACTION_FIELDS if field not in action]
        if missing:
            issues.append(f"missing_fields:{','.join(missing)}")
        if _nested_shape(action.get("action")) != EXPECTED_ACTION_SHAPE:
            issues.append(f"action_shape:{_nested_shape(action.get('action'))}")
        if _nested_shape(action.get("base_motion")) != EXPECTED_BASE_MOTION_SHAPE:
            issues.append(f"base_motion_shape:{_nested_shape(action.get('base_motion'))}")
        if action.get("control_type") != "joint_position":
            issues.append(f"control_type:{action.get('control_type')}")
        if not isinstance(action.get("is_rel"), bool):
            issues.append("is_rel_not_bool")
        if not isinstance(action.get("base_is_rel"), bool):
            issues.append("base_is_rel_not_bool")
        if issues:
            findings[name] = issues
    if findings:
        return _status_row(
            "action dialects",
            "FAIL",
            "one or more action dialects do not match the Lift2 contract",
            details={"findings": findings},
        )
    if action_execution_results is not None:
        expected_names = [str(action.get("name")) for action in actions]
        executed_names = [
            str(result.get("action_name"))
            for result in action_execution_results
            if result.get("response_present") is True
        ]
        missing_execution = [
            name for name in expected_names if name not in set(executed_names)
        ]
        if missing_execution:
            return _status_row(
                "action dialects",
                "BLOCKED",
                "not every action dialect produced a live step response",
                details={
                    "missing_execution": missing_execution,
                    "step_results": action_execution_results,
                },
            )
        return _status_row(
            "action dialects",
            "PASS",
            "all supplied action dialects match the Lift2 action contract and produced live step responses",
            details={"dialects": expected_names, "step_results": action_execution_results},
        )
    return _status_row(
        "action dialects",
        "PASS",
        "all supplied action dialects match the Lift2 action contract",
        details={"dialects": [str(action.get("name")) for action in actions]},
    )


def classify_reward_success_fields(
    step_response: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(step_response, dict):
        return _status_row(
            "reward/success fields",
            "BLOCKED",
            "no GenManip/EBench step response was provided",
        )
    info = step_response.get("info")
    info_dict = info if isinstance(info, dict) else {}
    reward_present = step_response.get("reward") is not None
    metric_present = (
        step_response.get("metric_raw_output") is not None
        or info_dict.get("info") is not None
    )
    success_present = isinstance(info_dict.get("success"), bool)
    if not (reward_present or metric_present or success_present):
        return _status_row(
            "reward/success fields",
            "BLOCKED",
            "step response does not expose GenManip/EBench metric output",
        )
    return _status_row(
        "reward/success fields",
        "PASS",
        "reward/success fields are sourced from GenManip/EBench step output",
    )


def classify_logging_fields(logging: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(logging, dict):
        return _status_row(
            "logging fields",
            "BLOCKED",
            "no run logging metadata was provided",
        )
    required = [
        "run_id",
        "worker_id",
        "episode_id",
        "seed",
        "result_path",
        "stdout_path",
        "stderr_path",
    ]
    missing = [field for field in required if logging.get(field) in (None, "")]
    if missing:
        return _status_row(
            "logging fields",
            "BLOCKED",
            "run logging metadata is incomplete",
            details={"missing": missing},
        )
    return _status_row(
        "logging fields",
        "PASS",
        "run id, worker, episode, seed, result path, and logs are recorded",
    )


def classify_task_readiness_matrix(
    task_rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if not isinstance(task_rows, list) or not task_rows:
        return _status_row(
            "task readiness matrix",
            "BLOCKED",
            "no per-task reset/step/reachability/camera input/metric matrix was provided",
        )
    rows_by_task = {str(row.get("task")): row for row in task_rows}
    missing_tasks = [task for task in REQUIRED_TASKS if task not in rows_by_task]
    if missing_tasks:
        return _status_row(
            "task readiness matrix",
            "BLOCKED",
            "per-task matrix is missing one or more required tasks",
            details={"missing_tasks": missing_tasks},
        )
    statuses: list[str] = []
    invalid: dict[str, dict[str, Any]] = {}
    for task in REQUIRED_TASKS:
        row = rows_by_task[task]
        task_statuses = {field: row.get(field) for field in TASK_ROW_STATUS_FIELDS}
        bad_fields = {
            field: status
            for field, status in task_statuses.items()
            if status not in VALID_STATUSES
        }
        if bad_fields:
            invalid[task] = bad_fields
        statuses.extend(str(status) for status in task_statuses.values())
    if invalid:
        raise ValueError(f"invalid Stage 7 task row statuses: {invalid}")
    if "BLOCKED" in statuses:
        return _status_row(
            "task readiness matrix",
            "BLOCKED",
            "one or more tasks lack reset, step, reachability, camera input, or metric evidence",
            details={"task_rows": task_rows},
        )
    if "FAIL" in statuses:
        return _status_row(
            "task readiness matrix",
            "FAIL",
            "one or more tasks failed reset, step, reachability, camera input, or metric evidence",
            details={"task_rows": task_rows},
        )
    return _status_row(
        "task readiness matrix",
        "PASS",
        "all required tasks passed reset, step, reachability, camera input, and metric evidence",
    )


def classify_stage7_readiness(
    rows: list[dict[str, Any]],
    *,
    task_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    evaluated_rows = list(rows)
    schema_statuses = [row.get("status") for row in evaluated_rows]
    if task_rows is None:
        invalid = sorted(
            {status for status in schema_statuses if status not in VALID_STATUSES}
        )
        if invalid:
            raise ValueError(f"invalid Stage 7 statuses: {invalid}")
        if "BLOCKED" in schema_statuses:
            probe_status = "single-task live schema probe blocked"
        elif "FAIL" in schema_statuses:
            probe_status = "single-task live schema probe failed"
        else:
            probe_status = "single-task live schema probe passed"
        return {
            "stage7_status": "Stage 7 not evaluated by single-task live schema probe",
            "claim_scope": "single_task_live_schema_probe_only",
            "probe_status": probe_status,
            "aggregate_stage7_manifest_required": True,
            "lift2_contract_ready": None,
            "local_official_baseline_style_contract_ready": None,
            "official_baseline_evaluable": False,
            "blocked_rows": [
                row for row in evaluated_rows if row.get("status") == "BLOCKED"
            ],
            "failed_rows": [
                row for row in evaluated_rows if row.get("status") == "FAIL"
            ],
        }
    else:
        evaluated_rows.append(classify_task_readiness_matrix(task_rows))
    statuses = [row.get("status") for row in evaluated_rows]
    invalid = sorted({status for status in statuses if status not in VALID_STATUSES})
    if invalid:
        raise ValueError(f"invalid Stage 7 statuses: {invalid}")
    if "BLOCKED" in statuses:
        stage7_status = "Stage 7 attempted, blocked"
    elif "FAIL" in statuses:
        stage7_status = "Stage 7 attempted, failed"
    else:
        stage7_status = "Stage 7 passed"
    return {
        "stage7_status": stage7_status,
        "lift2_contract_ready": stage7_status == "Stage 7 passed",
        "local_official_baseline_style_contract_ready": (
            stage7_status == "Stage 7 passed"
        ),
        "official_baseline_evaluable": False,
        "blocked_rows": [
            row for row in evaluated_rows if row.get("status") == "BLOCKED"
        ],
        "failed_rows": [row for row in evaluated_rows if row.get("status") == "FAIL"],
    }


def build_contract_snapshot(
    *,
    task_name: str,
    observation: dict[str, Any] | None,
    actions: list[dict[str, Any]] | None,
    action_execution_results: list[dict[str, Any]] | None = None,
    step_response: dict[str, Any] | None,
    logging: dict[str, Any] | None,
    task_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    observation_schema = summarize_observation_schema(observation)
    schema_rows = [
        classify_observation_keys(observation_schema),
        classify_camera_input_keys(observation_schema),
        classify_action_dialects(actions, action_execution_results),
        classify_reward_success_fields(step_response),
        classify_logging_fields(logging),
    ]
    claim_boundary = classify_stage7_readiness(schema_rows, task_rows=task_rows)
    claim_boundary["native_material_closure_claim_allowed"] = False
    return {
        "schema_version": 1,
        "stage": "acceptance_stage_7_lift2_contract_probe",
        "task_name": task_name,
        "required_tasks": REQUIRED_TASKS,
        "observation_schema": observation_schema,
        "action_dialect_matrix": _jsonable(actions or []),
        "step_response_summary": _jsonable(step_response),
        "logging": _jsonable(logging),
        "schema_rows": schema_rows,
        "claim_boundary": claim_boundary,
    }


def _extract_worker_observation(response: Any, worker_id: str) -> dict[str, Any] | None:
    if not isinstance(response, dict):
        return None
    worker_payload = response.get(worker_id)
    if isinstance(worker_payload, dict) and isinstance(worker_payload.get("obs"), dict):
        return worker_payload["obs"]
    if isinstance(response.get("obs"), dict):
        return response["obs"]
    return None


def _summarize_worker_step_response(response: Any, worker_id: str) -> dict[str, Any] | None:
    if not isinstance(response, dict):
        return None
    worker_payload = response.get(worker_id)
    payload = worker_payload if isinstance(worker_payload, dict) else response
    if not isinstance(payload, dict):
        return None
    metric = payload.get("metric", payload.get("reward"))
    info = {
        "info": metric,
        "episode_result": payload.get("episode_result"),
        "success": payload.get("success"),
    }
    return {
        "reward": metric,
        "done": bool(payload.get("done", False)),
        "info": info,
        "observation_schema": summarize_observation_schema(payload.get("obs")),
    }


def _action_for_client(action: dict[str, Any]) -> dict[str, Any]:
    return {
        field: action[field]
        for field in REQUIRED_ACTION_FIELDS
        if field in action
    }


def run_live_probe(
    *,
    client_factory: Any,
    worker_id: str,
    task_name: str,
    joint_position_count: int,
    include_optional_internvla: bool,
    logging: dict[str, Any] | None,
) -> dict[str, Any]:
    actions = build_action_dialect_matrix(
        joint_positions=[0.0] * joint_position_count,
        include_optional_internvla=include_optional_internvla,
    )
    client = None
    observation: dict[str, Any] | None = None
    step_response: dict[str, Any] | None = None
    step_results: list[dict[str, Any]] = []
    action_execution_results: list[dict[str, Any]] | None = None
    try:
        client = client_factory()
        reset_response = client.reset()
        observation = _extract_worker_observation(reset_response, worker_id)
        action_execution_results = step_results
        for action in actions:
            response, done = client.step({worker_id: _action_for_client(action)})
            step_response = _summarize_worker_step_response(response, worker_id)
            if step_response is not None:
                step_response["done"] = bool(done)
            step_results.append(
                {
                    "action_name": action.get("name"),
                    "response_present": step_response is not None,
                    "done": bool(done),
                }
            )
            if done:
                break
        snapshot = build_contract_snapshot(
            task_name=task_name,
            observation=observation,
            actions=actions,
            action_execution_results=action_execution_results,
            step_response=step_response,
            logging=logging,
        )
        snapshot["live_probe"] = {
            "status": "attempted",
            "worker_id": worker_id,
            "reset_observation_present": observation is not None,
            "step_results": step_results,
        }
        return snapshot
    except Exception as exc:
        snapshot = build_contract_snapshot(
            task_name=task_name,
            observation=observation,
            actions=actions,
            action_execution_results=(
                action_execution_results
                if observation is not None or step_results
                else None
            ),
            step_response=step_response,
            logging=logging,
        )
        snapshot["live_probe"] = {
            "status": "blocked",
            "worker_id": worker_id,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "exception_stack": traceback.format_exc(),
        }
        return snapshot
    finally:
        if client is not None and hasattr(client, "close"):
            client.close()


def build_eval_client_factory(
    *,
    base_url: str,
    worker_id: str,
    run_id: str,
) -> Any:
    def _client_factory() -> Any:
        from genmanip_client import EvalClient

        return EvalClient(
            base_url,
            worker_ids=[worker_id],
            run_id=run_id,
        )

    return _client_factory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-name", default="level1_open_door")
    parser.add_argument("--observation-json")
    parser.add_argument("--step-response-json")
    parser.add_argument("--logging-json")
    parser.add_argument("--joint-position-count", type=int, default=16)
    parser.add_argument("--include-optional-internvla", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8087)
    parser.add_argument("--worker-id", default="0")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    logging = _read_json(args.logging_json)
    if args.live:
        run_id = args.run_id or (
            str(logging.get("run_id")) if isinstance(logging, dict) and logging.get("run_id") else ""
        )

        snapshot = run_live_probe(
            client_factory=build_eval_client_factory(
                base_url=f"http://{args.host}:{args.port}",
                worker_id=args.worker_id,
                run_id=run_id,
            ),
            worker_id=args.worker_id,
            task_name=args.task_name,
            joint_position_count=args.joint_position_count,
            include_optional_internvla=args.include_optional_internvla,
            logging=logging,
        )
    else:
        snapshot = build_contract_snapshot(
            task_name=args.task_name,
            observation=_read_json(args.observation_json),
            actions=build_action_dialect_matrix(
                joint_positions=[0.0] * args.joint_position_count,
                include_optional_internvla=args.include_optional_internvla,
            ),
            step_response=_read_json(args.step_response_json),
            logging=logging,
        )
    text = json.dumps(snapshot, indent=2, sort_keys=True)
    if args.output == "-":
        print(text)
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
