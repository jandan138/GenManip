import argparse
import os
import pathlib
import shutil
import zipfile

from huggingface_hub import snapshot_download


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
        raise ValueError(f"Dataset {args.dataset} not supported")
