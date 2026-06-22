import json

from genmanip.core.evaluator.episode_result import resolve_episode_score
from genmanip.core.evaluator.progress_manager import ProgressManager


def test_resolve_episode_score_falls_back_to_done_info_numeric_score():
    assert resolve_episode_score(None, {"info": 0.0}) == 0.0
    assert resolve_episode_score(None, {"info": 1}) == 1.0


def test_resolve_episode_score_prefers_worker_post_process_result():
    assert (
        resolve_episode_score(
            {"score": 0.5, "finalize_payload": {"episode": "payload"}},
            {"info": 0.0},
        )
        == 0.5
    )


def test_resolve_episode_score_ignores_non_score_done_info():
    assert resolve_episode_score(None, {"info": "Done"}) is None
    assert resolve_episode_score(None, {"info": True}) is None
    assert resolve_episode_score(None, {"error": "lock_lost", "info": 0.0}) is None


def test_resolve_episode_score_can_disable_done_info_fallback_after_post_process_error():
    assert (
        resolve_episode_score(
            None,
            {"info": 0.0, "termination_reason": "non_finite_arm_state"},
            allow_done_info_fallback=False,
        )
        is None
    )


def test_record_result_persists_result_info_without_async_finalize(tmp_path):
    progress = ProgressManager(
        result_base_dir=str(tmp_path),
        benchmark_id="ebench",
        run_id="run",
    )
    progress.add_evaluation_config(
        [{"task_name": "task_a"}],
        {"task_a": ["000"]},
        {"task_a": 1},
    )
    config, seed = progress.get_next_task("worker-0")
    assert config["task_name"] == "task_a"
    assert seed == "000"

    episode_result = progress.record_result("worker-0", 0.0, release_lock=True)

    result_path = tmp_path / "ebench" / "run" / "task_a" / "000" / "result_info.json"
    assert episode_result["score"] == 0.0
    assert json.loads(result_path.read_text(encoding="utf-8"))["score"] == 0.0
    assert progress.reconcile_task_state_from_filesystem() is True
    assert progress.check_finished()
