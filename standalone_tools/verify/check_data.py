import os
import argparse
import glob
import tqdm

def check_episode(episode_dir):
    errors = {}  # 用于记录错误信息
    if not os.path.exists(episode_dir):
        errors["路径不存在"] = episode_dir
    if not os.path.exists(os.path.join(episode_dir, "meta_info.pkl")):
        errors["meta_info.pkl 不存在"] = episode_dir
    lmdb_path = os.path.join(episode_dir, "lmdb")
    if not os.path.exists(lmdb_path):
        errors["lmdb 路径不存在"] = lmdb_path
    if not os.path.exists(os.path.join(lmdb_path, "data.mdb")):
        errors["data.mdb 不存在"] = lmdb_path
    if not os.path.exists(os.path.join(lmdb_path, "lock.mdb")):
        errors["lock.mdb 不存在"] = lmdb_path
    if not os.path.exists(os.path.join(lmdb_path, "info.json")):
        errors["info.json 不存在"] = lmdb_path

    return errors

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, default="/ailab/user/wangfangjing/code/closedlooptest/data/scaling/GenManip_102k")
    args = parser.parse_args()

    data_dir = args.data_dir
    episodes_dir = glob.glob(os.path.join(data_dir, "*"))
    episodes_dir.sort()
    errors = []
    for episode_dir in tqdm.tqdm(episodes_dir):
        error = check_episode(episode_dir)
        if error:
            for error_type, episode_dir in error.items():
                errors.append(f"{error_type}: {episode_dir}")
    print("\n".join(errors))
