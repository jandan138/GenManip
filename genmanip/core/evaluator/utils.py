"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import os
import pathlib

from huggingface_hub import snapshot_download
from pydantic import BaseModel

from genmanip.utils.standalone.file_utils import load_yaml, check_benchmark_version


def parse_config_and_benchmark_id(
    config_or_benchmark_id: str, current_dir: str
) -> tuple[dict, str | None]:
    if str(config_or_benchmark_id).endswith(".yml") or str(
        config_or_benchmark_id
    ).endswith(".yaml"):
        config = load_yaml(config_or_benchmark_id)
        benchmark_id = None
    elif os.path.exists(
        os.path.join(
            current_dir,
            "saved/assets/collected_packages",
            str(config_or_benchmark_id).split("/")[-1],
            "tasks",
            "config.yaml",
        )
    ):
        print("Loading benchmark from local directory...")
        config = load_yaml(
            os.path.join(
                current_dir,
                "saved/assets/collected_packages",
                str(config_or_benchmark_id).split("/")[-1],
                "tasks",
                "config.yaml",
            )
        )
        benchmark_id = config_or_benchmark_id
    else:
        print("Downloading benchmark from HuggingFace...")
        if check_benchmark_version(config_or_benchmark_id):
            pathlib.Path("saved/assets/collected_packages").mkdir(
                parents=True, exist_ok=True
            )
            pathlib.Path("saved/tasks").mkdir(parents=True, exist_ok=True)
            snapshot_download(
                repo_id=config_or_benchmark_id,
                repo_type="dataset",
                local_dir=f"saved/assets/collected_packages/{config_or_benchmark_id.split('/')[-1]}",
            )
            if os.path.exists(
                os.path.join(
                    current_dir,
                    "saved/assets/collected_packages",
                    str(config_or_benchmark_id).split("/")[-1],
                    "tasks",
                    "config.yaml",
                )
            ):
                config = load_yaml(
                    os.path.join(
                        current_dir,
                        "saved/assets/collected_packages",
                        str(config_or_benchmark_id).split("/")[-1],
                        "tasks",
                        "config.yaml",
                    )
                )
                benchmark_id = config_or_benchmark_id
            else:
                raise ValueError(f"Config file {config_or_benchmark_id} not found")
        else:
            raise ValueError(f"Config file {config_or_benchmark_id} not found")
    return config, benchmark_id


class ActionRequest(BaseModel):
    data: dict


class ObsResponse(BaseModel):
    data: dict
