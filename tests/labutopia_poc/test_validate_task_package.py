import json
import subprocess
import sys
import types

import pytest

from standalone_tools.labutopia_poc import validate_task_package


EXPECTED_TOP_INDEX = [
    "ebench/labutopia_lab_poc/franka_poc/franka_poc.json",
    "ebench/labutopia_lab_poc/lift2_candidate/lift2_candidate.json",
]
EXPECTED_TASKS = ["level1_pick", "level1_place", "level1_open_door"]


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_task_files(task_root):
    for profile in ("franka_poc", "lift2_candidate"):
        profile_root = task_root / "ebench/labutopia_lab_poc" / profile
        profile_root.mkdir(parents=True, exist_ok=True)
        for task_name in EXPECTED_TASKS:
            (profile_root / f"{task_name}.yml").write_text("{}", encoding="utf-8")


def _write_valid_indexes(task_root):
    package_root = task_root / "ebench/labutopia_lab_poc"
    _write_json(package_root / "labutopia_lab_poc.json", EXPECTED_TOP_INDEX)
    for profile in ("franka_poc", "lift2_candidate"):
        _write_json(
            package_root / profile / f"{profile}.json",
            [
                f"ebench/labutopia_lab_poc/{profile}/{task}.yml"
                for task in EXPECTED_TASKS
            ],
        )


def test_indexed_task_yaml_paths_rejects_duplicate_profile_entries(tmp_path, monkeypatch):
    task_root = tmp_path / "tasks"
    _write_task_files(task_root)
    _write_valid_indexes(task_root)
    package_root = task_root / "ebench/labutopia_lab_poc"
    _write_json(
        package_root / "franka_poc/franka_poc.json",
        [
            "ebench/labutopia_lab_poc/franka_poc/level1_pick.yml",
            "ebench/labutopia_lab_poc/franka_poc/level1_pick.yml",
            "ebench/labutopia_lab_poc/franka_poc/level1_place.yml",
        ],
    )
    monkeypatch.setattr(validate_task_package, "TASK_ROOT", task_root)
    monkeypatch.setattr(validate_task_package, "PACKAGE_ROOT", package_root)

    with pytest.raises(AssertionError, match="franka_poc.json"):
        validate_task_package._indexed_task_yaml_paths()


def test_metrics_manager_lazy_registration_does_not_keep_metrics_package_imported():
    sys.modules["genmanip.extensions.metrics"] = types.ModuleType(
        "genmanip.extensions.metrics"
    )
    try:
        validate_task_package._validate_metrics_manager_lazy_registration()
        assert "genmanip.extensions.metrics" not in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "genmanip.extensions.metrics" or module_name.startswith(
                "genmanip.extensions.metrics."
            ):
                del sys.modules[module_name]


def test_validate_task_package_cli_reports_success():
    result = subprocess.run(
        [sys.executable, "standalone_tools/labutopia_poc/validate_task_package.py"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "LabUtopia task package validation OK" in result.stdout
