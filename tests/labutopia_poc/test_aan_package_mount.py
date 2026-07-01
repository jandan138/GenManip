import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from standalone_tools.labutopia_poc import mount_aan_package


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_usd(path, prim_paths):
    from pxr import Usd

    path.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(path))
    for prim_path in prim_paths:
        stage.DefinePrim(prim_path, "Xform")
    stage.Save()


def _write_yaml(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _write_package(tmp_path, required_prim="/World/Asset"):
    package_dir = tmp_path / "package"
    _write_usd(package_dir / "asset.usd", [required_prim])
    _write_yaml(package_dir / "task" / "task_config.yaml", {"task_id": "fixture"})
    _write_yaml(
        package_dir / "task" / "required_prims.yaml",
        {
            "required_prims": [
                {
                    "role": "asset_root",
                    "path": required_prim,
                    "required": True,
                }
            ]
        },
    )
    _write_yaml(package_dir / "task" / "evaluator.yaml", {"metric": "fixture"})

    manifest_path = tmp_path / "manifest.json"
    _write_json(
        manifest_path,
        {
            "entrypoints": {
                "root_usd": "asset.usd",
                "task_config": "task/task_config.yaml",
                "required_prims": "task/required_prims.yaml",
                "metric_evaluator": "task/evaluator.yaml",
            }
        },
    )
    return package_dir, manifest_path


def _write_consumer_check(tmp_path, mount_allowed=True):
    path = tmp_path / "consumer_check.json"
    _write_json(
        path,
        {
            "stage": "aan_consumer_manifest_check",
            "status": "pass" if mount_allowed else "blocked",
            "aan_package_mount_allowed": mount_allowed,
        },
    )
    return path


def _run_mount(
    tmp_path,
    package_dir,
    manifest_path,
    consumer_check_path,
    composite_root,
    namespace="labutopia_aan_packages/dryingbox_01_overlay",
    *extra_args,
):
    json_out = tmp_path / "mount_manifest.json"
    exit_code = mount_aan_package.main(
        [
            "--package-dir",
            str(package_dir),
            "--manifest",
            str(manifest_path),
            "--consumer-check",
            str(consumer_check_path),
            "--composite-assets-root",
            str(composite_root),
            "--namespace",
            namespace,
            "--json-out",
            str(json_out),
            *extra_args,
        ]
    )
    return exit_code, json.loads(json_out.read_text(encoding="utf-8"))


def test_mounts_allowed_package_as_idempotent_symlink_and_records_sources(tmp_path):
    package_dir, manifest_path = _write_package(tmp_path)
    consumer_check_path = _write_consumer_check(tmp_path, mount_allowed=True)
    composite_root = tmp_path / "assets"

    exit_code, record = _run_mount(
        tmp_path, package_dir, manifest_path, consumer_check_path, composite_root
    )
    second_exit_code, second_record = _run_mount(
        tmp_path, package_dir, manifest_path, consumer_check_path, composite_root
    )

    mounted_namespace = composite_root / "labutopia_aan_packages/dryingbox_01_overlay"
    assert exit_code == 0
    assert second_exit_code == 0
    assert mounted_namespace.is_symlink()
    assert mounted_namespace.resolve() == package_dir.resolve()
    assert record["status"] == "pass"
    assert second_record["path_resolution_status"] == "already_mounted_same_source"
    assert record["symlink_or_copy_mode"] == "symlink"
    assert record["task_config_source"] == (
        "labutopia_aan_packages/dryingbox_01_overlay/task/task_config.yaml"
    )
    assert record["required_prims_source"] == (
        "labutopia_aan_packages/dryingbox_01_overlay/task/required_prims.yaml"
    )
    assert record["evaluator_source"] == (
        "labutopia_aan_packages/dryingbox_01_overlay/task/evaluator.yaml"
    )
    assert record["root_usd_source"] == (
        "labutopia_aan_packages/dryingbox_01_overlay/asset.usd"
    )
    assert record["mounted_root_usd"] == str((mounted_namespace / "asset.usd").absolute())
    assert record["dry_run_composition"]["usd_stage_opened"] is True
    assert record["dry_run_composition"]["all_required_prims_found"] is True
    assert record["required_prim_resolution_rows"] == [
        {
            "role": "asset_root",
            "path": "/World/Asset",
            "required": True,
            "exists": True,
        }
    ]
    assert record["source_package_hash_before"] == record["source_package_hash_after"]
    assert record["local_usd_repair_allowed"] is False
    assert record["runtime_execution_passed"] is False
    assert "ebench_task_execution_passed" in record["forbidden_claims"]


def test_blocks_when_consumer_check_does_not_allow_mount(tmp_path):
    package_dir, manifest_path = _write_package(tmp_path)
    consumer_check_path = _write_consumer_check(tmp_path, mount_allowed=False)
    composite_root = tmp_path / "assets"

    exit_code, record = _run_mount(
        tmp_path, package_dir, manifest_path, consumer_check_path, composite_root
    )

    assert exit_code == 1
    assert record["status"] == "blocked"
    assert record["path_resolution_status"] == "blocked"
    assert {
        "code": "consumer_check_not_mount_allowed",
        "field": "aan_package_mount_allowed",
        "actual": False,
        "expected": True,
    } in record["blockers"]
    assert not (composite_root / "labutopia_aan_packages").exists()


def test_blocks_namespace_conflict_without_replace(tmp_path):
    package_dir, manifest_path = _write_package(tmp_path)
    other_package, _other_manifest = _write_package(tmp_path / "other")
    consumer_check_path = _write_consumer_check(tmp_path, mount_allowed=True)
    composite_root = tmp_path / "assets"
    namespace_path = composite_root / "labutopia_aan_packages/dryingbox_01_overlay"
    namespace_path.parent.mkdir(parents=True)
    namespace_path.symlink_to(other_package.resolve(), target_is_directory=True)

    exit_code, record = _run_mount(
        tmp_path, package_dir, manifest_path, consumer_check_path, composite_root
    )

    assert exit_code == 1
    assert record["status"] == "blocked"
    assert record["path_resolution_status"] == "namespace_conflict"
    assert namespace_path.resolve() == other_package.resolve()
    assert record["blockers"][0]["code"] == "namespace_conflict"


def test_dry_run_blocks_when_required_prim_is_missing(tmp_path):
    package_dir, manifest_path = _write_package(tmp_path, required_prim="/World/Present")
    _write_yaml(
        package_dir / "task" / "required_prims.yaml",
        {
            "required_prims": [
                {
                    "role": "missing",
                    "path": "/World/Missing",
                    "required": True,
                }
            ]
        },
    )
    consumer_check_path = _write_consumer_check(tmp_path, mount_allowed=True)
    composite_root = tmp_path / "assets"

    exit_code, record = _run_mount(
        tmp_path, package_dir, manifest_path, consumer_check_path, composite_root
    )

    assert exit_code == 1
    assert record["status"] == "blocked"
    assert record["dry_run_composition"]["usd_stage_opened"] is True
    assert record["dry_run_composition"]["all_required_prims_found"] is False
    assert {
        "role": "missing",
        "path": "/World/Missing",
        "required": True,
        "exists": False,
    } in record["required_prim_resolution_rows"]
    assert {
        "code": "missing_required_prim",
        "field": "task.required_prims[0].path",
        "path": "/World/Missing",
        "role": "missing",
    } in record["blockers"]


def test_script_path_cli_runs_without_pythonpath(tmp_path):
    package_dir, manifest_path = _write_package(tmp_path)
    consumer_check_path = _write_consumer_check(tmp_path, mount_allowed=True)
    composite_root = tmp_path / "assets"
    json_out = tmp_path / "mount_manifest.json"

    result = subprocess.run(
        [
            sys.executable,
            "standalone_tools/labutopia_poc/mount_aan_package.py",
            "--package-dir",
            str(package_dir),
            "--manifest",
            str(manifest_path),
            "--consumer-check",
            str(consumer_check_path),
            "--composite-assets-root",
            str(composite_root),
            "--namespace",
            "labutopia_aan_packages/dryingbox_01_overlay",
            "--json-out",
            str(json_out),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(json_out.read_text(encoding="utf-8"))
    assert record["status"] == "pass"
