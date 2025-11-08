import argparse
import os
import pathlib
import shutil
import zipfile

from huggingface_hub import snapshot_download


def find_filetree_depth(path, cnt=0) -> int:
    path_list = os.listdir(path)
    if "config.yaml" in path_list:
        return cnt
    for item in path_list:
        if os.path.isdir(os.path.join(path, item)):
            cnt = find_filetree_depth(os.path.join(path, item), cnt + 1)
    return cnt


def remove_huggingface_info(path):
    if os.path.exists(f"{path}/.collect.mapping.json"):
        os.remove(f"{path}/.collect.mapping.json")
    if os.path.exists(f"{path}/.gitattributes"):
        os.remove(f"{path}/.gitattributes")
    if os.path.exists(f"{path}/README.md"):
        os.remove(f"{path}/README.md")


def download_basic_dataset():
    repo_id = "Axi404/GenManip-Basic-Assets"
    snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        local_dir="saved/assets/scene_usds/base_scenes",
    )
    remove_huggingface_info("saved/assets/scene_usds/base_scenes")


def download_banana_dataset():
    repo_id = "Axi404/GenManip-Banana-Assets"
    snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        local_dir="saved/assets/scene_usds/debug_scenes/banana_plate_scenes",
    )
    remove_huggingface_info("saved/assets/scene_usds/debug_scenes/banana_plate_scenes")


def download_banana_layout_dataset():
    repo_id = "Axi404/GenManip-Banana-Layouts"
    snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        local_dir="saved/tasks/Minimal_Banana",
    )
    remove_huggingface_info("saved/tasks/Minimal_Banana")


def download_custom_benchmark_dataset(repo_id: str):
    pathlib.Path("saved/assets/collected_packages").mkdir(parents=True, exist_ok=True)
    pathlib.Path("saved/tasks").mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        local_dir=f"saved/assets/collected_packages/{repo_id.split('/')[-1]}",
    )
    remove_huggingface_info(f"saved/assets/collected_packages/{repo_id.split('/')[-1]}")

    src = f"saved/assets/collected_packages/{repo_id.split('/')[-1]}/tasks"
    dst = f"saved/tasks"
    for item in os.listdir(src):
        if os.path.isdir(os.path.join(src, item)):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            shutil.move(s, d)

    shutil.move(
        os.path.join(src, "config.yaml"),
        os.path.join("configs/tasks", f"{repo_id.split('/')[-1]}.yml"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, required=True)
    args = parser.parse_args()

    path = pathlib.Path("saved/assets")
    path.mkdir(parents=True, exist_ok=True)

    if args.dataset == "basic":
        download_basic_dataset()
    elif args.dataset == "banana":
        download_banana_dataset()
    elif args.dataset == "banana-layout":
        download_banana_layout_dataset()
    else:
        download_custom_benchmark_dataset(args.dataset)
