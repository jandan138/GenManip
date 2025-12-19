import os
import sys
import ray
import argparse

current_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(current_dir)

from genmanip.core.evaluator.eval_server import EvalServer
from genmanip.core.evaluator.isaac_worker_pool import IsaacWorkerPool
from genmanip.core.evaluator.utils import (
    parse_config_and_benchmark_id,
)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-cfg",
        "--config",
        type=str,
        default="configs/tasks/minimal.yml",
        help="Path to the YAML config file",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for the FastAPI server",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8087,
        help="Port for the FastAPI server",
    )
    parser.add_argument(
        "-w",
        "--num_workers",
        type=int,
        default=1,
        help="The number of workers for the FastAPI server, not for the evaluator workers",
    )
    parser.add_argument(
        "-l",
        "--local",
        action="store_true",
        help="Run in local mode, a quick command to enable Isaac Sim GUI",
    )
    parser.add_argument(
        "-n",
        "--num_steps",
        type=int,
        default=600,
        help="Number of steps to run the evaluation",
    )
    parser.add_argument(
        "-wor",
        "--without_render",
        action="store_true",
        help="Run in without render mode, only record the data",
    )
    parser.add_argument(
        "-rr",
        "--random_randomization",
        action="store_true",
        help="Run in random randomization mode, enable randomization configs in eval config",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    config, benchmark_id = parse_config_and_benchmark_id(args.config, current_dir)

    print("Starting Ray Eval Server...")
    ray.init()
    print(ray.cluster_resources())
    server = EvalServer(args.host, args.port, args.num_workers)

    print("Creating Worker Pool...")
    pool = IsaacWorkerPool(args, config, current_dir, benchmark_id)
    server.register_worker_pool(pool)

    server.run()
