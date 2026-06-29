from standalone_tools.labutopia_poc.asset_acceptance import (
    ACCEPTANCE_STAGE_CONTRACT,
    assert_acceptance_stages_are_ordered,
)


def test_acceptance_stage_contract_defines_stages_zero_through_seven():
    assert [stage["stage_index"] for stage in ACCEPTANCE_STAGE_CONTRACT] == list(
        range(8)
    )
    assert [stage["stage_id"] for stage in ACCEPTANCE_STAGE_CONTRACT] == [
        "asset_contract_declaration",
        "static_usd_physics_audit",
        "isolated_native_physics_smoke",
        "ebench_wrapper_composition",
        "additive_physics_articulation_override",
        "task_runtime_eval_readback",
        "evidence_package_claim_boundary",
        "evaluator_robot_contract",
    ]


def test_acceptance_stage_order_validator_rejects_missing_stage():
    stages = [
        {
            "stage_index": stage["stage_index"],
            "stage_id": stage["stage_id"],
            "stage_name": stage["stage_name"],
            "status": "PASS",
            "evidence": {},
        }
        for stage in ACCEPTANCE_STAGE_CONTRACT
        if stage["stage_index"] != 3
    ]

    try:
        assert_acceptance_stages_are_ordered(stages, required_indices=range(8))
    except AssertionError as exc:
        assert "acceptance_stages indices must be [0, 1, 2, 3, 4, 5, 6, 7]" in str(
            exc
        )
    else:
        raise AssertionError("missing Stage 3 should fail validation")
