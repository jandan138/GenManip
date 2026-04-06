from datetime import datetime
from concurrent.futures import Future, ThreadPoolExecutor
import logging
import os
import time
from pathlib import Path
import threading
from typing import Dict, Any, List

import ray
import torch
from ray.exceptions import GetTimeoutError, RayActorError

from genmanip.core.evaluator.exceptions import InsufficientResourcesError
from genmanip.core.evaluator.logging_utils import (
    build_file_logger,
    get_run_log_dir,
    make_log_file_timestamp,
)
from genmanip.core.evaluator.progress_manager import (
    ProgressManager,
    HEARTBEAT_INTERVAL_SECONDS,
)
from genmanip.core.evaluator.isaac_worker import IsaacWorker
from genmanip.core.evaluator.utils import parse_configs_and_benchmark_id
from genmanip.utils.standalone.file_utils import load_default_config, make_dir
from genmanip.utils.standalone.utils import parse_eval_config
from genmanip.utils.standalone.version_utils import process_archived_config

GPU_MEMORY = torch.cuda.get_device_properties(0).total_memory
JOB_MEMORY_GB = (
    10  # Approximate memory per job in GB, adjust this to maximize GPU utilization
)
NUM_GPUS_REQUIRED_PER_JOB = 1.0 / max(
    1, int(GPU_MEMORY / 1024 / 1024 / 1024 / JOB_MEMORY_GB)
)


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


class IsaacWorkerPool:
    """
    A pool of Isaac workers for parallel evaluation.

    This class is purely functional - it only handles:
    - Worker creation and destruction
    - Step execution

    All task lifecycle management (configs, seeds, results, progress)
    is delegated to ProgressManager.

    Args:
        args: Command line arguments.
        current_dir: Current working directory.
        world_size: Number of GPUs available.
    """

    def __init__(self, args, current_dir, world_size=None):
        self.lock = threading.Lock()
        self.workers: Dict[str, Any] = {}
        self._reset_executor = ThreadPoolExecutor(
            max_workers=32, thread_name_prefix="episode-reset"
        )
        self._pending_reset_futures: Dict[str, Future] = {}

        self.args = args
        self.current_dir = current_dir
        self.workspace_root = Path(self.current_dir).resolve()
        self.pool_log_id = make_log_file_timestamp()
        self.logger: logging.Logger | None = None
        self.world_size = (
            world_size if world_size is not None else torch.cuda.device_count()
        )
        self.max_workers = int(self.world_size / NUM_GPUS_REQUIRED_PER_JOB)

        self.default_config = load_default_config(
            self.current_dir, "__None__.json", "local" if self.args.local else "default"
        )
        # worker env timeout
        self.step_call_timeout = 600
        self.reset_call_timeout = 120
        self.benchmark_id: str | None = None
        self.progress_manager: ProgressManager | None = None
        self.worker_env_vars: dict[str, str] = {}
        self.configure_logging(getattr(self.args, "run_id", None))

    def configure_logging(self, run_id: str | None) -> None:
        log_dir = get_run_log_dir(self.current_dir, run_id)
        self.logger = build_file_logger(
            logger_name=f"IsaacWorkerPool[{run_id or 'default'}][{self.pool_log_id}]",
            log_path=f"{log_dir}/worker_pool_{self.pool_log_id}.log",
        )
        self.logger.info(
            "Configured worker pool logging. run_id=%s", run_id or "default"
        )

    def _create_progress_manager(
        self, benchmark_id: str, run_id: str
    ) -> ProgressManager:
        """Create a new ProgressManager instance."""
        return ProgressManager(
            result_base_dir=os.path.join(self.current_dir, "saved/eval_results"),
            benchmark_id=benchmark_id,
            run_id=run_id,
        )

    def _validate_run_id(self, run_id: str) -> str:
        if not isinstance(run_id, str) or run_id.strip() == "":
            raise ValueError("run_id must be a non-empty string")
        run_id_path = Path(run_id)
        if run_id_path.is_absolute():
            raise ValueError("run_id must not be an absolute path")
        if any(part in ("", ".", "..") for part in run_id_path.parts):
            raise ValueError("run_id contains invalid path segments")
        return run_id

    def _validate_run_output_dir(self, benchmark_id: str, run_id: str) -> None:
        result_base_dir = (self.workspace_root / "saved" / "eval_results").resolve()
        run_dir = (result_base_dir / benchmark_id / run_id).resolve()
        if not _is_relative_to(run_dir, result_base_dir):
            raise ValueError(
                f"run output path escapes workspace: benchmark_id={benchmark_id}, run_id={run_id}"
            )

    def _parse_task_config(
        self, config: dict
    ) -> tuple[list[dict], dict[str, list[str]], dict[str, int]]:
        """Parse evaluation config into task lists."""
        task_config_list = parse_eval_config(config)
        task_config_list = [process_archived_config(cfg) for cfg in task_config_list]

        task_seed_list = {}
        task_num_test_list = {}
        for cfg in task_config_list:
            task_seed_list[cfg["task_name"]] = [
                str(i).zfill(3) for i in range(cfg["num_test"])
            ]
            task_num_test_list[cfg["task_name"]] = cfg["num_test"]

        return task_config_list, task_seed_list, task_num_test_list

    def _resolve_worker_env_vars(
        self, all_configs: list[tuple[list[dict], dict[str, list[str]], dict[str, int]]]
    ) -> dict[str, str]:
        env_vars_reference: dict[str, str] | None = None
        for task_config_list, _, _ in all_configs:
            for cfg in task_config_list:
                raw_env_vars = cfg.get("env_vars", None)
                if raw_env_vars is None:
                    continue
                if not isinstance(raw_env_vars, dict):
                    if self.logger is not None:
                        self.logger.warning(
                            "Ignore non-dict env_vars in task %s: %r",
                            cfg.get("task_name", "<unknown>"),
                            type(raw_env_vars),
                        )
                    continue

                env_vars: dict[str, str] = {}
                for key, value in raw_env_vars.items():
                    if not isinstance(key, str) or not isinstance(value, str):
                        if self.logger is not None:
                            self.logger.warning(
                                "Ignore invalid env var in task %s: %r=%r",
                                cfg.get("task_name", "<unknown>"),
                                key,
                                value,
                            )
                        continue
                    env_vars[key] = value.replace(
                        "{ASSETS_DIR}", self.default_config.get("ASSETS_DIR", "")
                    )

                if env_vars_reference is None:
                    env_vars_reference = env_vars
                elif env_vars != env_vars_reference:
                    if self.logger is not None:
                        self.logger.warning(
                            "Inconsistent env_vars across tasks. "
                            "Use the first discovered env_vars for worker init."
                        )

        return env_vars_reference if env_vars_reference is not None else {}

    def start_new_job(self, run_id: str, evaluation_config_path_list: list[str]):
        """
        Start a new evaluation job.

        Kills existing workers, initializes ProgressManager, and loads configs.

        Args:
            run_id: Run identifier (auto-generated if empty/None)
            evaluation_config_path_list: List of config file paths
        """
        if (
            not isinstance(evaluation_config_path_list, list)
            or not evaluation_config_path_list
        ):
            raise ValueError(
                "evaluation_config_path_list must be a non-empty list of strings"
            )
        if any(
            (not isinstance(config_path, str)) or (config_path.strip() == "")
            for config_path in evaluation_config_path_list
        ):
            raise ValueError(
                "evaluation_config_path_list must contain non-empty strings only"
            )

        self.kill_workers(list(self.workers.keys()))

        # Determine run_id
        effective_run_id = (
            run_id
            if (run_id != "") and (run_id is not None)
            else (
                self.args.run_id
                if getattr(self.args, "run_id", None) is not None
                else datetime.now().strftime("%Y-%m-%d_%H_%M_%S_%f")
            )
        )
        effective_run_id = self._validate_run_id(effective_run_id)
        self.args.run_id = effective_run_id
        self.configure_logging(effective_run_id)

        # Parse configs and determine benchmark_id
        self.benchmark_id = None
        all_configs: list[tuple[list[dict], dict[str, list[str]], dict[str, int]]] = []

        for evaluation_config_path_or_group in evaluation_config_path_list:
            evaluation_config_list, benchmark_id, is_genmanip_package = (
                parse_configs_and_benchmark_id(
                    evaluation_config_path_or_group, self.current_dir
                )
            )
            if is_genmanip_package:
                self.default_config["TASKS_DIR"] = os.path.join(
                    self.current_dir,
                    "saved/assets/collected_packages",
                    benchmark_id.split("/")[-1],
                    "tasks",
                )
            if self.benchmark_id is None:
                self.benchmark_id = benchmark_id
            else:
                assert (
                    self.benchmark_id == benchmark_id
                ), f"Only one benchmark is allowed at a time: {self.benchmark_id} vs {benchmark_id}"

            for evaluation_config in evaluation_config_list:
                parsed = self._parse_task_config(evaluation_config)
                all_configs.append(parsed)

        if self.benchmark_id is None:
            raise ValueError("Benchmark ID is not set")

        self.worker_env_vars = self._resolve_worker_env_vars(all_configs)
        self._validate_run_output_dir(self.benchmark_id, effective_run_id)
        # Create progress manager
        self.progress_manager = self._create_progress_manager(
            self.benchmark_id, effective_run_id
        )

        # Add all configs to progress manager
        for task_config_list, task_seed_list, task_num_test_list in all_configs:
            self.progress_manager.add_evaluation_config(
                task_config_list, task_seed_list, task_num_test_list
            )

        # Load existing progress from filesystem
        self.progress_manager.load_progress()
        self.progress_manager.print_progress()

    # ==================== Worker Management ====================

    def create_workers(self, worker_ids: List[str]):
        """Create new workers by ID."""
        with self.lock:
            new_worker_cnt = sum(1 for w_id in worker_ids if w_id not in self.workers)
            total_requested = len(self.workers) + new_worker_cnt
            if total_requested > self.max_workers:
                raise InsufficientResourcesError(
                    requested=total_requested, available=self.max_workers
                )

            for w_id in worker_ids:
                if w_id not in self.workers:
                    self.workers[w_id] = self._spawn_worker(w_id)

    def kill_workers(self, worker_ids: List[str]):
        """Kill workers and clean up their tasks."""
        with self.lock:
            for w_id in worker_ids:
                if w_id in self.workers:
                    ray.kill(self.workers[w_id], no_restart=True)
                    del self.workers[w_id]

                # Clean up worker's tasks via progress manager
                if self.progress_manager is not None:
                    self.progress_manager.cleanup_worker(str(w_id))

        if self.progress_manager is not None:
            self.progress_manager.print_progress()

    def get_active_workers(self) -> List[str]:
        """Get list of active worker IDs."""
        with self.lock:
            return list(self.workers.keys())

    # ==================== Evaluation Execution ====================

    def _refresh_locks(self, worker_ids: List[str]) -> set[str]:
        """Refresh locks for a list of workers (best-effort)."""
        if self.progress_manager is None:
            return set()
        lost: set[str] = set()
        for w_id in worker_ids:
            ok = self.progress_manager.refresh_worker_lock(str(w_id))
            if not ok:
                if self.logger is not None:
                    self.logger.warning("Lost lock for worker %s", w_id)
                else:
                    print(f"[lock] lost lock for worker {w_id}")
                lost.add(str(w_id))
        return lost

    def _reset_worker(
        self,
        w_id: str,
        task_seed: str,
        config: dict[str, Any],
        include_default_config: bool = False,
    ) -> Any:
        """Reset one worker and raise a context-rich error on failure."""
        task_name = (
            config.get("task_name", "<unknown>")
            if isinstance(config, dict)
            else "<unknown>"
        )

        def _invoke_reset() -> Any:
            worker = self.workers[w_id]
            if include_default_config:
                return worker.reset.remote(task_seed, config, self.default_config)
            return worker.reset.remote(task_seed, config)

        def _should_retry_reset(error: Exception) -> bool:
            return isinstance(error, TimeoutError) or self._is_worker_unavailable_error(
                error
            )

        def _on_retry_reset(error: Exception, attempt_idx: int) -> bool:
            if self.logger is not None:
                self.logger.warning(
                    "Reset attempt %s failed for worker=%s task=%s seed=%s: %s. "
                    "Replacing worker and retrying.",
                    attempt_idx + 1,
                    w_id,
                    task_name,
                    task_seed,
                    error,
                )
            self._replace_worker(w_id, reason=error)
            return True

        try:
            return self._ray_get_with_timeout(
                call_remote=_invoke_reset,
                timeout=self.reset_call_timeout,
                context=f"Worker {w_id} reset task={task_name} seed={task_seed}",
                max_attempts=5,
                should_retry=_should_retry_reset,
                on_retry=_on_retry_reset,
            )
        except Exception as e:
            raise RuntimeError(
                f"Worker {w_id} reset failed for task={task_name} seed={task_seed}: "
                f"{type(e).__name__}: {e}"
            ) from e

    def reset(self, worker_ids: List[str] | None) -> Dict[str, Any]:
        """
        Reset workers and assign initial tasks.

        Args:
            worker_ids: List of worker IDs to reset

        Returns:
            Dict mapping worker_id to response dict
        """
        if self.progress_manager is None:
            raise ValueError("No job started. Call start_new_job first.")

        if worker_ids is None:
            worker_ids = self.get_active_workers()
            if not worker_ids:
                raise ValueError(
                    "worker_ids not provided and no active workers exist; create workers first"
                )
        if not isinstance(worker_ids, list) or not worker_ids:
            raise ValueError("worker_ids must be a non-empty list")
        worker_ids = [str(w_id) for w_id in worker_ids]
        if any(w_id.strip() == "" for w_id in worker_ids):
            raise ValueError("worker_ids must contain non-empty values")

        self.create_workers(worker_ids)
        if self.logger is not None:
            self.logger.info("Reset requested for workers=%s", worker_ids)

        response = {}
        for w_id in worker_ids:
            pending_resp = self._consume_pending_reset_if_ready(w_id)
            if pending_resp is not None:
                response[w_id] = pending_resp
                continue
            if self._has_pending_reset(w_id):
                response[w_id] = self._make_reset_pending_response()
                continue

            config, task_seed = self.progress_manager.get_next_task(str(w_id))

            if config is None:
                resp = {
                    "obs": None,
                    "metric": self.progress_manager.calculate_result(),
                    "episode_result": None,
                }
            else:
                self._refresh_locks([w_id])
                obs = self._reset_worker(
                    w_id,
                    task_seed,
                    config,
                    include_default_config=True,
                )
                self._refresh_locks([w_id])
                resp = {
                    "obs": obs,
                    "metric": self.progress_manager.calculate_result(),
                    "episode_result": None,
                }

            response[w_id] = resp
        return response

    def _make_reset_pending_response(self) -> dict[str, Any]:
        metric = None
        if self.progress_manager is not None:
            metric = self.progress_manager.calculate_result()
        return {
            "obs": {"reset": True, "reset_pending": True},
            "metric": metric,
            "episode_result": None,
            "reset_pending": True,
        }

    def _has_pending_reset(self, w_id: str) -> bool:
        with self.lock:
            future = self._pending_reset_futures.get(str(w_id))
        return future is not None and not future.done()

    def _consume_pending_reset_if_ready(self, w_id: str) -> dict[str, Any] | None:
        with self.lock:
            future = self._pending_reset_futures.get(str(w_id))
            if future is None or not future.done():
                return None
            del self._pending_reset_futures[str(w_id)]
        return future.result()

    def _spawn_worker(self, w_id: str):
        return IsaacWorker.options(
            runtime_env={"env_vars": self.worker_env_vars}
        ).remote(
            w_id,
            self.pool_log_id,
            self.args,
            self.default_config,
            self.current_dir,
            self.benchmark_id,
        )

    def _replace_worker(self, w_id: str, reason: Exception | None = None) -> None:
        reason_text = f"{type(reason).__name__}: {reason}" if reason is not None else ""
        if self.logger is not None:
            self.logger.warning("Replacing dead worker=%s reason=%s", w_id, reason_text)
        with self.lock:
            old_worker = self.workers.get(w_id)
            if old_worker is not None:
                try:
                    ray.kill(old_worker, no_restart=True)
                except Exception:
                    if self.logger is not None:
                        self.logger.exception(
                            "Failed to kill stale worker handle for worker=%s", w_id
                        )
            self.workers[w_id] = self._spawn_worker(w_id)

    def _ray_get_with_timeout(
        self,
        call_remote,
        timeout: float,
        context: str,
        max_attempts: int = 1,
        should_retry=None,
        on_retry=None,
    ) -> Any:
        attempts = max(1, int(max_attempts))
        last_error: Exception | None = None

        for attempt_idx in range(attempts):
            attempt_start = time.monotonic()
            try:
                ref = call_remote()
                result = ray.get(ref, timeout=timeout)
                return result
            except GetTimeoutError:
                last_error = TimeoutError(f"{context} timed out after {timeout}s")
            except Exception as e:
                last_error = e

            if attempt_idx >= attempts - 1:
                break

            retry_allowed = (
                should_retry(last_error) if should_retry is not None else False
            )
            if not retry_allowed:
                break
            if on_retry is not None and not on_retry(last_error, attempt_idx):
                break

        if last_error is None:
            raise RuntimeError(f"{context} failed without a captured exception")
        raise last_error

    def _is_worker_unavailable_error(self, error: Exception) -> bool:
        if isinstance(error, RayActorError):
            return True
        error_text = str(error)
        return any(
            token in error_text
            for token in (
                "ActorDiedError",
                "The actor died",
                "ray.kill",
                "actor is dead",
            )
        )

    def _start_pending_reset(self, w_id: str, info: dict[str, Any]) -> dict[str, Any]:
        if self.logger is not None:
            self.logger.info(
                "Starting background reset for worker=%s info=%s", w_id, info
            )
        with self.lock:
            future = self._pending_reset_futures.get(str(w_id))
            if future is None or future.done():
                self._pending_reset_futures[str(w_id)] = self._reset_executor.submit(
                    self._handle_done, w_id, info
                )
        return self._make_reset_pending_response()

    def get_pending_reset_results(self, worker_ids: List[str] | None) -> Dict[str, Any]:
        if worker_ids is None:
            with self.lock:
                worker_ids = list(self._pending_reset_futures.keys())
        if not isinstance(worker_ids, list) or not worker_ids:
            raise ValueError("worker_ids must be a non-empty list")

        response = {}
        for w_id in [str(w_id) for w_id in worker_ids]:
            pending_resp = self._consume_pending_reset_if_ready(w_id)
            if pending_resp is not None:
                response[w_id] = pending_resp
            elif self._has_pending_reset(w_id):
                response[w_id] = self._make_reset_pending_response()
            else:
                raise ValueError(f"worker {w_id} has no pending reset result")
        return response

    def step(self, action_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute one step for each worker.

        Args:
            action_dict: Dict mapping worker_id to action

        Returns:
            Dict mapping worker_id to response dict
        """
        if self.progress_manager is None:
            raise ValueError("No job started. Call start_new_job first.")

        response = {}
        actionable_dict: Dict[str, Any] = {}

        # Safety redundancy and backward compatibility for older clients that may step before reset polling completes.
        for w_id, action in action_dict.items():
            pending_resp = self._consume_pending_reset_if_ready(w_id)
            if pending_resp is not None:
                response[str(w_id)] = pending_resp
                continue
            if self._has_pending_reset(w_id):
                response[str(w_id)] = self._make_reset_pending_response()
                continue
            actionable_dict[str(w_id)] = action

        if not actionable_dict:
            return response

        # start to step actionable workers, but first refresh locks and record any
        lost = self._refresh_locks(list(actionable_dict.keys()))
        futures = []
        for w_id, action in actionable_dict.items():
            futures.append(self.workers[w_id].step.remote(action))

        results = ray.get(futures)
        lost.update(self._refresh_locks(list(actionable_dict.keys())))

        for i, w_id in enumerate(actionable_dict.keys()):
            obs, done, info = results[i]
            resp = {
                "obs": obs,
                "metric": self.progress_manager.calculate_result(),
                "episode_result": None,
            }

            if str(w_id) in lost:
                ray.get(self.workers[w_id].abort_episode.remote())
                # Requeue the task so it can be retried by any worker
                self.progress_manager.release_worker_task(str(w_id))
                resp = self._handle_done(w_id, {"error": "lock_lost", "info": "Done"})
                resp["lock_lost"] = True
                response[w_id] = resp
                continue

            if done:
                resp = self._start_pending_reset(w_id, info)

            response[w_id] = resp

        return response

    def step_chunk(self, action_chunk: List[Dict[str, Any]]) -> dict[str, Any]:
        """
        Execute multiple steps in one server call.

        Args:
            action_chunk: List of action_dict. Each element has the same format as `step`.

        Returns:
            {
                "obs": final_response_dict,
                "executed_steps": int,
                "stopped_early": bool,
            }
        """
        if self.progress_manager is None:
            raise ValueError("No job started. Call start_new_job first.")
        if not isinstance(action_chunk, list) or len(action_chunk) == 0:
            raise ValueError("action_chunk must be a non-empty list")

        final_response: Dict[str, Any] = {}
        executed_steps = 0
        stopped_early = False

        for step_action_dict in action_chunk:
            if not isinstance(step_action_dict, dict) or len(step_action_dict) == 0:
                raise ValueError("Each action in action_chunk must be a non-empty dict")

            final_response = self.step(step_action_dict)
            executed_steps += 1

            for worker_resp in final_response.values():
                if worker_resp.get("reset_pending"):
                    stopped_early = True
                    break
                obs = worker_resp.get("obs")
                if obs is None:
                    stopped_early = True
                    break
                if isinstance(obs, dict) and obs.get("reset"):
                    stopped_early = True
                    break
            if stopped_early:
                break

        return {
            "obs": final_response,
            "executed_steps": executed_steps,
            "stopped_early": stopped_early,
        }

    def _handle_done(self, w_id: str, info: dict) -> dict:
        """Handle episode completion for a worker."""
        if self.progress_manager is None:
            raise ValueError("No job started")

        # Get result from worker
        result = None
        if "error" not in info and "info" in info and info["info"] != "Done":
            try:
                result = self._ray_get_with_timeout(
                    call_remote=lambda: self.workers[w_id].post_episode_process.remote(),
                    timeout=self.step_call_timeout,
                    context=f"Worker {w_id} post_episode_process",
                )
            except Exception as e:
                if self._is_worker_unavailable_error(e):
                    self._replace_worker(w_id, reason=e)
                if self.logger is not None:
                    self.logger.exception(
                        "Post-episode processing failed for worker=%s", w_id
                    )

        # Record result via progress manager
        episode_result = self.progress_manager.record_result(str(w_id), result)

        # Get next task
        config, task_seed = self.progress_manager.get_next_task(str(w_id))
        if config is None:
            # No more tasks
            metric = self.progress_manager.calculate_result()
            self._save_final_result()
            return {"obs": None, "metric": metric, "episode_result": episode_result}

        # Reset worker for next task
        self._refresh_locks([w_id])
        obs = self._reset_worker(w_id, task_seed, config)
        self._refresh_locks([w_id])

        return {
            "obs": obs,
            "metric": self.progress_manager.calculate_result(),
            "episode_result": episode_result,
        }

    def _save_final_result(self):
        """Save final evaluation result."""
        if self.progress_manager is None or self.benchmark_id is None:
            return
        result_dir = os.path.join(
            self.current_dir,
            "saved/eval_results",
            self.benchmark_id,
            self.args.run_id,
        )
        make_dir(result_dir)
        self.progress_manager.save_final_result(result_dir)

    # ==================== Status API ====================

    def get_status(self) -> dict:
        """
        Get comprehensive job status.

        Returns:
            Status dict for the /status endpoint
        """
        active_workers = self.get_active_workers()

        if self.progress_manager is not None:
            return self.progress_manager.get_status(active_workers)

        # No job started
        return {
            "status": "idle",
            "benchmark_id": None,
            "run_id": None,
            "total_episodes": 0,
            "completed_episodes": 0,
            "in_progress_episodes": 0,
            "active_workers": active_workers,
            "results": {},
        }

    # ==================== Lifecycle ====================

    def close(self):
        """Close all workers."""
        futures = [worker.close.remote() for worker in self.workers.values()]
        ray.get(futures)
        self._reset_executor.shutdown(wait=False, cancel_futures=True)
