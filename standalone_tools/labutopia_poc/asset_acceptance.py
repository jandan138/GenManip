"""Shared LabUtopia asset acceptance stage contract helpers."""

from __future__ import annotations

import copy
from collections.abc import Iterable
from typing import Any


ACCEPTANCE_STAGE_SCHEMA_VERSION = 1

ACCEPTANCE_STAGE_CONTRACT: list[dict[str, object]] = [
    {
        "stage_index": 0,
        "stage_id": "asset_contract_declaration",
        "stage_name": "Asset Contract Declaration",
    },
    {
        "stage_index": 1,
        "stage_id": "static_usd_physics_audit",
        "stage_name": "Static USD/Physics Audit",
    },
    {
        "stage_index": 2,
        "stage_id": "isolated_native_physics_smoke",
        "stage_name": "Isolated Native Physics Smoke",
    },
    {
        "stage_index": 3,
        "stage_id": "ebench_wrapper_composition",
        "stage_name": "EBench Wrapper Composition",
    },
    {
        "stage_index": 4,
        "stage_id": "additive_physics_articulation_override",
        "stage_name": "Additive Physics + Articulation Override",
    },
    {
        "stage_index": 5,
        "stage_id": "task_runtime_eval_readback",
        "stage_name": "Task Runtime + Eval Readback",
    },
    {
        "stage_index": 6,
        "stage_id": "evidence_package_claim_boundary",
        "stage_name": "Evidence Package + Claim Boundary",
    },
    {
        "stage_index": 7,
        "stage_id": "evaluator_robot_contract",
        "stage_name": "Evaluator Robot Contract",
    },
]

VALID_ACCEPTANCE_STAGE_STATUSES = {"PASS", "WARN", "FAIL", "BLOCKED", "PENDING"}


def _stage_contract(stage_index: int) -> dict[str, object]:
    for stage in ACCEPTANCE_STAGE_CONTRACT:
        if stage["stage_index"] == stage_index:
            return stage
    raise AssertionError(f"unknown acceptance stage index: {stage_index}")


def acceptance_stage_entry(
    stage_index: int,
    *,
    status: str,
    evidence: dict[str, Any],
    source_report: str | None = None,
    gate_keys: Iterable[str] = (),
    artifact_paths: Iterable[str] = (),
    artifact_sha256: dict[str, str] | None = None,
    blockers: Iterable[str] = (),
    allowed_claim_keys: Iterable[str] = (),
    blocked_claim_keys: Iterable[str] = (),
    raw_status: str | None = None,
) -> dict[str, Any]:
    if status not in VALID_ACCEPTANCE_STAGE_STATUSES:
        raise AssertionError(f"invalid acceptance stage status: {status}")
    contract = _stage_contract(stage_index)
    entry: dict[str, Any] = {
        "stage_index": contract["stage_index"],
        "stage_id": contract["stage_id"],
        "stage_name": contract["stage_name"],
        "status": status,
        "evidence": copy.deepcopy(evidence),
        "gate_keys": list(gate_keys),
        "artifact_paths": list(artifact_paths),
        "artifact_sha256": copy.deepcopy(artifact_sha256 or {}),
        "blockers": list(blockers),
        "allowed_claim_keys": list(allowed_claim_keys),
        "blocked_claim_keys": list(blocked_claim_keys),
    }
    if source_report is not None:
        entry["source_report"] = source_report
    if raw_status is not None:
        entry["raw_status"] = raw_status
    return entry


def assert_acceptance_stages_are_ordered(
    stages: object,
    *,
    required_indices: Iterable[int] | None = None,
) -> None:
    expected_indices = list(
        required_indices
        if required_indices is not None
        else range(len(ACCEPTANCE_STAGE_CONTRACT))
    )
    if not isinstance(stages, list):
        raise AssertionError("missing asset_acceptance.acceptance_stages")
    actual_indices = [
        stage.get("stage_index") if isinstance(stage, dict) else None
        for stage in stages
    ]
    if actual_indices != expected_indices:
        raise AssertionError(f"acceptance_stages indices must be {expected_indices}")
    for stage in stages:
        if not isinstance(stage, dict):
            raise AssertionError("acceptance_stages entries must be mappings")
        contract = _stage_contract(int(stage["stage_index"]))
        if stage.get("stage_id") != contract["stage_id"]:
            raise AssertionError(
                f"acceptance stage {stage['stage_index']} id must be "
                f"{contract['stage_id']}"
            )
        if stage.get("stage_name") != contract["stage_name"]:
            raise AssertionError(
                f"acceptance stage {stage['stage_index']} name must be "
                f"{contract['stage_name']}"
            )
        if stage.get("status") not in VALID_ACCEPTANCE_STAGE_STATUSES:
            raise AssertionError(
                f"acceptance stage {stage['stage_index']} has invalid status"
            )
        if not isinstance(stage.get("evidence"), dict):
            raise AssertionError(
                f"acceptance stage {stage['stage_index']} evidence must be a mapping"
            )
        for list_key in (
            "gate_keys",
            "artifact_paths",
            "blockers",
            "allowed_claim_keys",
            "blocked_claim_keys",
        ):
            if list_key in stage and not isinstance(stage[list_key], list):
                raise AssertionError(
                    f"acceptance stage {stage['stage_index']} {list_key} must be a list"
                )
        if "artifact_sha256" in stage and not isinstance(
            stage["artifact_sha256"], dict
        ):
            raise AssertionError(
                f"acceptance stage {stage['stage_index']} artifact_sha256 must be a mapping"
            )
