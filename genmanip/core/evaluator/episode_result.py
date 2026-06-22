from __future__ import annotations

from numbers import Real
from typing import Any


def _coerce_score(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Real):
        return float(value)
    return None


def resolve_episode_score(
    worker_post_process_result: Any,
    done_info: dict[str, Any] | None,
    *,
    allow_done_info_fallback: bool = True,
) -> float | None:
    """Resolve an episode score from finalize output, then done info fallback."""
    if isinstance(worker_post_process_result, dict):
        score = _coerce_score(worker_post_process_result.get("score"))
        if score is not None:
            return score
    else:
        score = _coerce_score(worker_post_process_result)
        if score is not None:
            return score

    if (
        not allow_done_info_fallback
        or not isinstance(done_info, dict)
        or "error" in done_info
    ):
        return None
    return _coerce_score(done_info.get("info"))
