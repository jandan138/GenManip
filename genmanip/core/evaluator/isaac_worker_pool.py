from datetime import datetime
import os
import logging
import sys
import time
import threading
import json
from typing import Dict, Any, List

import ray
import torch

from genmanip.core.evaluator.utils import parse_config_and_benchmark_id
from genmanip.utils.standalone.file_utils import (
    load_default_config,
    make_dir,
    save_dict_to_json,
)
from genmanip.utils.standalone.utils import parse_eval_config
from genmanip.utils.standalone.version_utils import process_archived_config

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


@ray.remote(num_gpus=NUM_GPUS_REQUIRED_PER_JOB, max_restarts=3, max_task_retries=3)
class IsaacWorker:
    def __init__(self, worker_id: str, args, default_config, current_dir):
        self.worker_id = worker_id
        self.args = args

        if current_dir not in sys.path:
            sys.path.append(current_dir)

        # ---------- setup per-worker logger ----------
        log_dir = os.path.join(current_dir, "logs", "workers")
        os.makedirs(log_dir, exist_ok=True)

        log_path = os.path.join(log_dir, f"worker_{self.worker_id}.log")

        logger_name = f"IsaacWorker-{self.worker_id}"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)

        if not self.logger.handlers:
            fh = logging.FileHandler(log_path)
            fh.setLevel(logging.INFO)
            formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
            self.logger.propagate = False

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
            args, self.simulation_app, default_config, current_dir
        )
        self.current_task_info = None

        self.logger.info("IsaacWorker init finished.")

    def reset(
        self, seed: str, current_eval_config: dict, default_config: dict | None = None
    ):
        self.logger.info(f"Reset called with seed={seed}")
        obs, self.current_task_info = self.env.reset(
            seed, current_eval_config, default_config
        )

        if self.current_task_info is None:
            self.logger.info("No task info returned from env.reset()")
            return None

        self.logger.info(
            f"Running Task: {self.current_task_info['task']}, "
            f"Seed: {self.current_task_info['seed']}"
        )
        return obs

    def step(self, action):
        start_time = time.time()
        obs, _, done, info = self.env.step(action)
        self.logger.info(
            f"Env {self.worker_id} step time: {time.time() - start_time:.4f}"
        )
        if done:
            self.logger.info(f"Episode done. info={info}")
        return obs, done, info

    def post_episode_process(self):
        self.logger.info("post_episode_process called.")
        return self.env.post_episode_process(None)

    def close(self):
        self.logger.info("Closing IsaacWorker...")
        self.env.close()
        self.simulation_app.close()
        self.logger.info("IsaacWorker closed.")

    def is_done(self):
        return self.env.done


class IsaacWorkerPool:
    """
    Docstring for IsaacWorkerPool
    A pool of Isaac workers to manage multiple evaluation tasks in parallel.

    Args:
        args: Command line arguments.
        config: Evaluation configuration.
        current_dir: Current working directory.
        benchmark_id: Benchmark identifier.
        world_size: Number of GPUs avaliable.
    """

    def __init__(self, args, config, current_dir, benchmark_id=None, world_size=None):
        self.workers: Dict[str, Any] = {}
        self.args = args
        self.args.run_id = (
            args.run_id
            if args.run_id is not None
            else datetime.now().strftime("%Y-%m-%d_%H_%M_%S_%f")
        )
        self.config = config
        self.current_dir = current_dir
        self.world_size = (
            world_size if world_size is not None else torch.cuda.device_count()
        )
        self.lock = threading.Lock()
        self.default_config = load_default_config(
            self.current_dir, "__None__.json", "local" if self.args.local else "default"
        )
        if benchmark_id is not None:
            self.default_config["TASKS_DIR"] = os.path.join(
                self.current_dir,
                "saved/assets/collected_packages",
                benchmark_id.split("/")[-1],
                "tasks",
            )
        self.initialize()

    def initialize(self):
        self.config_list, self.task_seed_list = self.get_task_seed_list()
        self.result_list = {config["task_name"]: {} for config in self.config_list}
        self.worker_to_task_map = {}
        self.done = False

    def get_task_seed_list(self):
        task_seed_list = {}
        config_list = parse_eval_config(self.config)
        config_list = [process_archived_config(config) for config in config_list]

        for config in config_list:
            task_seed_list[config["task_name"]] = [
                str(i).zfill(3) for i in range(config["num_test"])
            ]
        return config_list, task_seed_list

    def load_config(self, config_path: str):
        config, benchmark_id = parse_config_and_benchmark_id(
            config_path, self.current_dir
        )
        self.config = config
        self.default_config = load_default_config(
            self.current_dir, "__None__.json", "local" if self.args.local else "default"
        )
        if benchmark_id is not None:
            self.default_config["TASKS_DIR"] = os.path.join(
                self.current_dir,
                "saved/assets/collected_packages",
                benchmark_id.split("/")[-1],
                "tasks",
            )
        self.initialize()

    def create_workers(self, worker_ids: List[str]):
        with self.lock:

            # check if enough resources are avaliable
            max_workers = int(self.world_size / NUM_GPUS_REQUIRED_PER_JOB)
            new_worker_cnt = 0
            for w_id in worker_ids:
                if w_id not in self.workers:
                    new_worker_cnt += 1
            if len(self.workers) + new_worker_cnt > max_workers:
                raise Exception("Insufficient resources to allocate for workers")

            for w_id in worker_ids:
                if w_id not in self.workers:
                    self.workers[w_id] = IsaacWorker.remote(
                        w_id, self.args, self.default_config, self.current_dir
                    )

    def kill_workers(self, worker_ids: List[str]):
        with self.lock:
            for w_id in worker_ids:
                if w_id in self.workers:
                    ray.kill(self.workers[w_id], no_restart=True)
                    del self.workers[w_id]
            # restore unfinished tasks
            self.config_list, self.task_seed_list = self.get_task_seed_list()
            for task_name, seed_list in self.task_seed_list.items():
                self.task_seed_list[task_name] = list(
                    filter(
                        lambda seed: seed not in self.result_list[task_name], seed_list
                    )
                )

    def reset(self, worker_ids: List[str]):
        response = {}
        for w_id in worker_ids:
            if w_id not in self.workers:
                raise ValueError(f"Worker {w_id} not found in pool during reset.")

            config, task_seed = self.get_next_task()

            if config is None:
                # No more tasks, return result
                resp = {"obs": None, "metric": self.calculate_result()}
            else:
                obs = ray.get(
                    self.workers[w_id].reset.remote(
                        task_seed, config, self.default_config
                    )
                )
                resp = {"obs": obs, "metric": None}
                self.worker_to_task_map[w_id] = (config["task_name"], task_seed)

            response[w_id] = resp
        return response

    def get_task_name(self, worker_id: str) -> str:
        return self.worker_to_task_map[worker_id][0]

    def get_task_seed(self, worker_id: str) -> str:
        return self.worker_to_task_map[worker_id][1]

    def step(self, action_dict: Dict[str, Any]) -> Dict[str, Any]:
        futures = []
        for w_id, action in action_dict.items():
            futures.append(self.workers[w_id].step.remote(action))

        results = ray.get(futures)

        response = {}
        for i, w_id in enumerate(action_dict.keys()):
            obs, done, info = results[i]
            resp = {"obs": obs, "metric": None}

            if done:
                resp = self.handle_done(w_id, info)

            response[w_id] = resp

        return response

    def handle_done(self, w_id, info):
        with self.lock:
            # Normal done, post_process and record result
            if "error" not in info and "info" in info and info["info"] != "Done":
                success_rate = ray.get(self.workers[w_id].post_episode_process.remote())
                self.result_list[self.get_task_name(w_id)][
                    self.get_task_seed(w_id)
                ] = success_rate

        # Get next task
        config, task_seed = self.get_next_task()
        if config is None:
            # No more tasks, return result
            resp = {"obs": None, "metric": self.calculate_result()}

            make_dir(
                os.path.join(self.current_dir, "saved/eval_results", self.args.run_id)
            )
            result_file = os.path.join(
                self.current_dir, "saved/eval_results", self.args.run_id, "result.json"
            )
            save_dict_to_json(resp["metric"], result_file)
        else:
            # More tasks, reset and get obs
            obs = ray.get(self.workers[w_id].reset.remote(task_seed, config))
            resp = {"obs": obs, "metric": None}
            self.worker_to_task_map[w_id] = (config["task_name"], task_seed)
        return resp

    def get_next_task(self):
        with self.lock:
            if len(self.config_list) == 0:
                self.done = True
                return None, None

            # remove empty task seed and task
            config = self.config_list[0]
            while len(self.task_seed_list[config["task_name"]]) == 0:
                self.config_list.pop(0)
                self.task_seed_list.pop(config["task_name"])
                if len(self.config_list) == 0:
                    self.done = True
                    return None, None
                config = self.config_list[0]
            # Caution: The task is popped out before get done, it is unsafe for interruption. We restore the unfinished tasks in kill_workers()
            task_seed = self.task_seed_list[config["task_name"]].pop(0)
            return config, task_seed

    def calculate_result(self):
        sr_per_task = {}
        for task_name, result in self.result_list.items():
            sr_per_task[task_name] = sum(result.values()) / len(result)
        return sr_per_task

    def close(self):
        futures = [worker.close.remote() for worker in self.workers.values()]
        ray.get(futures)
