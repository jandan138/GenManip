import os
import logging
import sys
import time

import ray
import torch

from genmanip.core.evaluator.logging_utils import (
    build_file_logger,
    get_run_log_dir,
    make_log_file_timestamp,
    redirect_std_streams,
)


GPU_MEMORY = torch.cuda.get_device_properties(0).total_memory
JOB_MEMORY_GB = (
    10  # Approximate memory per job in GB, adjust this to maximize GPU utilization
)
NUM_GPUS_REQUIRED_PER_JOB = 1.0 / max(
    1, int(GPU_MEMORY / 1024 / 1024 / 1024 / JOB_MEMORY_GB)
)


def import_modules():
    """
    Import modules that are used in the worker and avoid DLL Hell problem.
    """
    import pydantic
    import torch
    import numpy
    from pydantic import BaseModel, Field


def _read_proc_status_memory_kb() -> dict[str, int]:
    memory_fields = ("VmRSS", "RssAnon", "RssFile", "VmSize", "VmSwap")
    result: dict[str, int] = {}
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as f:
            for line in f:
                for field in memory_fields:
                    if line.startswith(f"{field}:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            result[field] = int(parts[1])
    except OSError:
        return {}
    return result


@ray.remote(num_gpus=NUM_GPUS_REQUIRED_PER_JOB, max_restarts=3, max_task_retries=3)
class IsaacWorker:
    def __init__(
        self,
        worker_id: str,
        pool_log_id: str,
        args,
        default_config,
        current_dir,
        benchmark_id,
    ):
        self.worker_id = worker_id
        self.pool_log_id = pool_log_id
        self.args = args
        self.benchmark_id = benchmark_id

        if current_dir not in sys.path:
            sys.path.append(current_dir)

        # ---------- setup per-worker logger ----------
        run_log_dir = get_run_log_dir(current_dir, getattr(args, "run_id", None))
        worker_log_dir = os.path.join(run_log_dir, "worker")
        os.makedirs(worker_log_dir, exist_ok=True)
        self.worker_log_id = make_log_file_timestamp()
        log_path = os.path.join(
            worker_log_dir,
            f"pool_{self.pool_log_id}_worker_{self.worker_id}_{self.worker_log_id}.log",
        )
        self.log_path = log_path

        logger_name = (
            f"IsaacWorker-{getattr(args, 'run_id', 'default')}-{self.worker_id}"
        )
        self.logger = build_file_logger(logger_name, log_path)
        redirect_std_streams(self.logger, self.logger)

        self.logger.info(f"===== IsaacWorker {self.worker_id} started =====")

        # ---------- GPU Info ----------
        cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES", None)
        self.logger.info(f"CUDA_VISIBLE_DEVICES = {cuda_visible}")

        self.logger.info(f"torch.cuda.device_count() = {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            self.logger.info(f"torch device {i}: {torch.cuda.get_device_name(i)}")

        # ---------- Isaac modules ----------
        import_modules()

        from isaacsim import SimulationApp  # type: ignore

        self.simulation_app = SimulationApp(
            {"headless": not args.local, "multi_gpu": False}
        )

        self.simulation_app._carb_settings.set(
            "/physics/cooking/ujitsoCollisionCooking", False
        )

        from genmanip.core.evaluator.env import IsaacEvalEnvRay

        self.env = IsaacEvalEnvRay(
            args,
            self.simulation_app,
            default_config,
            current_dir,
            benchmark_id=self.benchmark_id,
        )
        self.current_task_info = None

        self.logger.info("IsaacWorker init finished.")

    def _log_memory_snapshot(self, tag: str) -> None:
        mem = _read_proc_status_memory_kb()
        if not mem:
            self.logger.info("Memory snapshot unavailable tag=%s", tag)
            return
        self.logger.info(
            "Memory snapshot tag=%s VmRSS=%.2fGiB RssAnon=%.2fGiB "
            "RssFile=%.2fGiB VmSize=%.2fGiB VmSwap=%.2fGiB",
            tag,
            mem.get("VmRSS", 0) / 1024 / 1024,
            mem.get("RssAnon", 0) / 1024 / 1024,
            mem.get("RssFile", 0) / 1024 / 1024,
            mem.get("VmSize", 0) / 1024 / 1024,
            mem.get("VmSwap", 0) / 1024 / 1024,
        )

    def reset(
        self, seed: str, current_eval_config: dict, default_config: dict | None = None
    ):
        reset_start = time.perf_counter()
        try:
            self.logger.info(f"Reset called with seed={seed}")
            self._log_memory_snapshot("before_reset")
            obs, self.current_task_info = self.env.reset(
                seed, current_eval_config, default_config
            )
            self._log_memory_snapshot("after_reset")
            reset_elapsed = time.perf_counter() - reset_start

            if self.current_task_info is None:
                self.logger.info(
                    "No task info returned from env.reset(). reset_time=%.4fs",
                    reset_elapsed,
                )
                return None

            self.logger.info(
                "Running Task: %s, Seed: %s, reset_time=%.4fs",
                self.current_task_info["task"],
                self.current_task_info["seed"],
                reset_elapsed,
            )
            return obs
        except Exception:
            self.logger.exception("Worker %s reset failed", self.worker_id)
            raise

    def step(self, action):
        try:
            start_time = time.time()
            obs, _, done, info = self.env.step(action)
            step_time = time.time() - start_time
            self.logger.debug("Env %s step time: %.4f", self.worker_id, step_time)
            if done:
                self.logger.info(
                    "Episode done. last_step_time=%.4f info=%s", step_time, info
                )
            return obs, done, info
        except Exception:
            self.logger.exception("Worker %s step failed", self.worker_id)
            raise

    def post_episode_process(self):
        process_start = time.perf_counter()
        try:
            self.logger.info("post_episode_process called.")
            self._log_memory_snapshot("before_post_episode_process")
            result = self.env.post_episode_process(None)
            self._log_memory_snapshot("after_post_episode_process")
            self.logger.info(
                "post_episode_process finished result=%s elapsed=%.4fs",
                result,
                time.perf_counter() - process_start,
            )
            return result
        except Exception:
            self._log_memory_snapshot("post_episode_process_exception")
            self.logger.exception(
                "Worker %s post_episode_process failed", self.worker_id
            )
            raise

    def abort_episode(self):
        try:
            self.logger.info("abort_episode called.")
            self.env.abort_episode()
        except Exception:
            self.logger.exception("Worker %s abort_episode failed", self.worker_id)
            raise

    def close(self):
        try:
            self.logger.info("Closing IsaacWorker...")
            self.env.close()
            self.simulation_app.close()
            self.logger.info("IsaacWorker closed.")
        except Exception:
            self.logger.exception("Worker %s close failed", self.worker_id)
            raise

    def is_done(self):
        return self.env.done
