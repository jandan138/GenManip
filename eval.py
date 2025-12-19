"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import argparse
import os
import sys
import traceback

from isaacsim import SimulationApp  # type: ignore[import-untyped]

from genmanip.utils.standalone.file_utils import load_yaml

current_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(current_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-r",
        "--receive_port",
        type=int,
        default=10000,
        help="Receive port for the evaluator",
    )
    parser.add_argument(
        "-s",
        "--send_port",
        type=int,
        default=10001,
        help="Send port for the evaluator",
    )
    parser.add_argument(
        "-cfg",
        "--config",
        type=str,
        default="configs/tasks/minimal.yml",
        help="Path to the YAML config file",
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


args = parse_args()

simulation_app = SimulationApp({"headless": not args.local})

from genmanip.core.evaluator.env import IsaacEvalEnv
from genmanip.core.evaluator.utils import (
    parse_config_and_benchmark_id,
)

# 0. Basic Setup
# 0-0. Isaac Sim hacking to avoid stuck in cooking, https://forums.developer.nvidia.com/t/gpu-memory-usage/300922/8
simulation_app._carb_settings.set("/physics/cooking/ujitsoCollisionCooking", False)


def main():
    config, benchmark_id = parse_config_and_benchmark_id(args.config, current_dir)
    env = IsaacEvalEnv(args, simulation_app, current_dir, config, benchmark_id)

    try:
        while True:
            obs, info = env.reset()

            if info is None:
                print("All tasks completed!")
                break

            print(f"Running Task: {info['task']}, Seed: {info['seed']}")

            done = False
            while not done:
                action = env.get_remote_action(obs)
                obs, _, done, info = env.step(action)

            env.post_episode_process(None)
    except Exception as e:
        env.logger.error(f"Error: {e}")
        env.logger.error(traceback.format_exc())
    finally:
        env.close()


if __name__ == "__main__":
    main()
