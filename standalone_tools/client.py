import time
import argparse

from genmanip_client import EvalClient, fake_action

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--worker_ids",
        type=lambda s: s.split(","),
        default=["0"],
        help="List of worker IDs, i.e. --worker_ids 0,1,2",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8087)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("-a", "--arm_type", type=str, default="franka")
    parser.add_argument("-g", "--gripper_type", type=str, default="panda_hand")
    parser.add_argument("-c", "--control_type", type=str, default="joint_position")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    host = args.host
    port = args.port
    worker_ids = args.worker_ids
    base_url = f"http://{host}:{port}"

    # Create workers on server here, make sure they are created before stepping
    client = EvalClient(base_url, worker_ids)
    print(f"Created workers {worker_ids} on server {base_url}.")

    # wrap the eval loop in a try-finally to ensure cleanup
    try:

        obs = client.reset()

        while True:

            action = {
                i: fake_action(args.arm_type, args.gripper_type, args.control_type)
                for i in worker_ids
            }

            start = time.time()
            obs, done = client.step(action)
            print(f"workers {worker_ids} Step time: {time.time() - start:.4f} seconds")

            if done:
                # finished all evaluations
                break
            if obs is None:
                break
            if obs[worker_ids[0]]["obs"]["reset"]:  # type: ignore
                # model.reset()
                pass
    finally:
        client.kill_workers()
        print("Client cleaned.")
