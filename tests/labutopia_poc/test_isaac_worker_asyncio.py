import asyncio

import pytest


def test_isaac_worker_replaces_uvloop_with_cpython_loop():
    uvloop = pytest.importorskip("uvloop")
    worker_module = pytest.importorskip("genmanip.core.evaluator.isaac_worker")

    old_policy = asyncio.get_event_loop_policy()
    try:
        old_loop = asyncio.get_event_loop()
    except RuntimeError:
        old_loop = None

    created_loops = []
    try:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        incompatible_loop = asyncio.new_event_loop()
        created_loops.append(incompatible_loop)
        asyncio.set_event_loop(incompatible_loop)

        assert not hasattr(asyncio.get_event_loop(), "_check_closed")

        worker_module._ensure_isaac_compatible_asyncio_loop()
        fixed_loop = asyncio.get_event_loop()
        created_loops.append(fixed_loop)

        assert hasattr(fixed_loop, "_check_closed")
        assert hasattr(fixed_loop, "_ready")
        assert hasattr(fixed_loop, "_scheduled")
    finally:
        for loop in created_loops:
            if loop is old_loop or loop.is_closed():
                continue
            loop.close()
        asyncio.set_event_loop_policy(old_policy)
        if old_loop is not None and not old_loop.is_closed():
            asyncio.set_event_loop(old_loop)
        else:
            asyncio.set_event_loop(None)
