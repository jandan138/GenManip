import json
import hashlib
from pathlib import Path

import yaml

from standalone_tools.labutopia_poc import aan_runtime_adapter


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_yaml(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _write_usd(path, prim_paths):
    from pxr import Usd

    path.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(path))
    root = stage.DefinePrim("/World", "Xform")
    stage.SetDefaultPrim(root)
    for prim_path in prim_paths:
        stage.DefinePrim(prim_path, "Xform")
    stage.Save()


def _write_usd_with_default(path, default_prim_path, prim_paths):
    from pxr import Usd

    path.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(path))
    root = stage.DefinePrim(default_prim_path, "Xform")
    stage.SetDefaultPrim(root)
    for prim_path in prim_paths:
        stage.DefinePrim(prim_path, "Xform")
    stage.Save()


def _sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_hash_summary(package_dir):
    tree_digest = hashlib.sha256()
    files = []
    for path in sorted(item for item in package_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(package_dir).as_posix()
        file_sha = _sha256_file(path)
        tree_digest.update(relative.encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(file_sha.encode("ascii"))
        tree_digest.update(b"\n")
        files.append({"path": relative, "sha256": file_sha})
    return {
        "algorithm": "sha256(sorted_relative_path_nul_file_sha256)",
        "digest": tree_digest.hexdigest(),
        "files": files,
    }


def _write_source_lift2_config(path):
    _write_yaml(
        path,
        {
            "evaluation_configs": [
                {
                    "task_name": "ebench/labutopia_lab_poc/lift2_candidate/level1_open_door",
                    "instruction": "Open the door of the drying box.",
                    "usd_name": "scene_usds/labutopia/level1_poc/lab_001/scene",
                    "table_uid": "table",
                    "mode": "manual",
                    "num_test": 1,
                    "num_steps": 1000,
                    "robots": [{"type": "manip/lift2/R5a", "position": [0, 0, 0]}],
                    "domain_randomization": {
                        "cameras": {
                            "config_path": "configs/cameras/fixed_camera_lift2_simbox.yml",
                            "type": "fixed",
                        }
                    },
                    "labutopia_lift2_contract": {
                        "schema_version": 1,
                        "material_boundary": "stage7_consumes_stage5_6_material_status_only",
                    },
                    "generation_config": {"goal": [], "mode": "manual", "planner": "curobo"},
                    "object_config": {
                        "obj_DryingBox_01": {
                            "type": "existed_object",
                            "uid_list": ["obj_DryingBox_01"],
                            "is_articulated": True,
                        }
                    },
                    "preprocess_config": [],
                    "layout_config": {"ignored_objects": [], "type": None},
                    "env_vars": {
                        "MDL_SYSTEM_PATH": "/isaac-sim/materials/:{ASSETS_DIR}/old/materials"
                    },
                }
            ]
        },
    )


def _write_mount_record(path, composite_root, *, symlink_source_package=False):
    namespace = "labutopia_aan_packages/dryingbox_01_overlay"
    mounted_namespace = composite_root / namespace
    mounted_root_usd = mounted_namespace / "asset.usd"
    required_prims = [
        {
            "role": "asset_root",
            "path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
            "required": True,
            "exists": True,
        },
        {
            "role": "articulation_root",
            "path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
            "required": True,
            "exists": True,
        },
    ]
    if symlink_source_package:
        source_package = path.parent / "producer_package"
        _write_usd(source_package / "asset.usd", [row["path"] for row in required_prims])
        mounted_namespace.parent.mkdir(parents=True, exist_ok=True)
        mounted_namespace.symlink_to(source_package.resolve(), target_is_directory=True)
        package_dir = mounted_namespace
    else:
        _write_usd(
            mounted_root_usd,
            [row["path"] for row in required_prims],
        )
        package_dir = mounted_namespace
    package_hash = _package_hash_summary(package_dir)
    _write_json(
        path,
        {
            "stage": "aan_task_root_mount_dry_run_composition",
            "status": "pass",
            "composite_assets_root": str(composite_root),
            "namespace": namespace,
            "mounted_namespace": str(mounted_namespace),
            "mounted_root_usd": str(mounted_root_usd),
            "source_manifest": "/producer/dryingbox_runtime_ready_manifest.json",
            "dry_run_composition": {
                "usd_stage_opened": True,
                "all_required_prims_found": True,
                "runtime_execution": "not_run",
            },
            "required_prim_resolution_rows": required_prims,
            "source_package_hash_after": package_hash,
            "runtime_execution_passed": False,
            "local_usd_repair_allowed": False,
            "forbidden_claims": ["ebench_task_execution_passed"],
        },
    )
    return path


def _write_generic_mount_record(path, composite_root):
    namespace = "labutopia_aan_packages/stage6_codex_20260701_muffle_furnace"
    mounted_namespace = composite_root / namespace
    mounted_root_usd = mounted_namespace / "asset.usd"
    required_prims = [
        {
            "role": "asset_root",
            "path": "/group_002",
            "required": True,
            "exists": True,
        },
        {
            "role": "manipulated_body",
            "path": "/group_002/Group/mesh_000",
            "required": True,
            "exists": True,
        },
        {
            "role": "goal_target",
            "path": "N/A",
            "required": True,
            "exists": None,
            "status": "not_applicable",
        },
    ]
    _write_usd_with_default(
        mounted_root_usd,
        "/group_002",
        [row["path"] for row in required_prims if row["path"] != "N/A"],
    )
    package_hash = _package_hash_summary(mounted_namespace)
    _write_json(
        path,
        {
            "stage": "aan_task_root_mount_dry_run_composition",
            "status": "pass",
            "composite_assets_root": str(composite_root),
            "namespace": namespace,
            "mounted_namespace": str(mounted_namespace),
            "mounted_root_usd": str(mounted_root_usd),
            "source_manifest": "/producer/muffle_furnace_manifest.json",
            "dry_run_composition": {
                "usd_stage_opened": True,
                "all_required_prims_found": True,
                "runtime_execution": "not_run",
            },
            "required_prim_resolution_rows": required_prims,
            "source_package_hash_after": package_hash,
            "runtime_execution_passed": False,
            "local_usd_repair_allowed": False,
            "forbidden_claims": ["ebench_task_execution_passed"],
        },
    )
    return path


def test_writes_aan_wrapper_task_profile_manifest_and_preflight_evidence(tmp_path):
    repo_root = tmp_path / "repo"
    composite_root = tmp_path / "assets"
    source_config = repo_root / "configs/tasks/ebench/labutopia_lab_poc/lift2_candidate/level1_open_door.yml"
    mount_record = _write_mount_record(tmp_path / "mount_record.json", composite_root)
    _write_source_lift2_config(source_config)

    record = aan_runtime_adapter.build_runtime_adapter_record(
        repo_root=repo_root,
        mount_record_path=mount_record,
        source_task_config_path=source_config,
        json_out=tmp_path / "adapter_evidence.json",
    )

    wrapper_path = (
        composite_root / "scene_usds/labutopia/aan/dryingbox_01_overlay_scene.usda"
    )
    task_config_path = (
        repo_root
        / "configs/tasks/ebench/labutopia_lab_poc/aan_lift2_candidate/level1_open_door.yml"
    )
    index_path = (
        repo_root
        / "configs/tasks/ebench/labutopia_lab_poc/aan_lift2_candidate/aan_lift2_candidate.json"
    )
    assets_manifest_path = (
        repo_root
        / "configs/tasks/ebench/labutopia_lab_poc/aan_lift2_candidate/assets_manifest.json"
    )

    assert record["status"] == "pass"
    assert record["stage"] == "aan_runtime_adapter_preflight"
    assert record["legacy_overlay_used"] is False
    assert record["runtime_execution_passed"] is False
    assert record["runtime_usd_name"] == "scene_usds/labutopia/aan/dryingbox_01_overlay_scene"
    assert record["resolved_runtime_scene"] == str(wrapper_path)
    assert record["wrapper_references"] == [
        "../../../labutopia_aan_packages/dryingbox_01_overlay/asset.usd"
    ]
    expected_digest = json.loads(mount_record.read_text(encoding="utf-8"))[
        "source_package_hash_after"
    ]["digest"]
    assert record["package_tree_digest"] == expected_digest
    assert record["mounted_package_tree_digest"] == expected_digest
    assert record["required_prim_resolution_rows"] == [
        {**row, "exists_in_runtime_wrapper": True}
        for row in json.loads(mount_record.read_text(encoding="utf-8"))[
            "required_prim_resolution_rows"
        ]
    ]
    assert record["blockers"] == []
    assert "ebench_task_execution_passed" in record["forbidden_claims"]

    assert wrapper_path.is_file()
    assert "../../../labutopia_aan_packages/dryingbox_01_overlay/asset.usd" in wrapper_path.read_text(
        encoding="utf-8"
    )
    assert task_config_path.is_file()
    task_config = yaml.safe_load(task_config_path.read_text(encoding="utf-8"))
    evaluation = task_config["evaluation_configs"][0]
    assert evaluation["task_name"] == (
        "ebench/labutopia_lab_poc/aan_lift2_candidate/level1_open_door"
    )
    assert evaluation["usd_name"] == "scene_usds/labutopia/aan/dryingbox_01_overlay_scene"
    assert "labutopia_aan_packages/dryingbox_01_overlay/deps/mdl" in evaluation[
        "env_vars"
    ]["MDL_SYSTEM_PATH"]
    assert evaluation["labutopia_aan_consumer"]["legacy_overlay_used"] is False

    assert json.loads(index_path.read_text(encoding="utf-8")) == [
        "ebench/labutopia_lab_poc/aan_lift2_candidate/level1_open_door.yml"
    ]
    assets_manifest = json.loads(assets_manifest_path.read_text(encoding="utf-8"))
    assert assets_manifest["overlay_root"] == str(composite_root)
    assert (
        assets_manifest["runtime_usd_name"]
        == "scene_usds/labutopia/aan/dryingbox_01_overlay_scene"
    )
    assert assets_manifest["namespace"] == "labutopia_aan_packages/dryingbox_01_overlay"


def test_writes_generic_aan_smoke_lane_without_dryingbox_contract(tmp_path):
    repo_root = tmp_path / "repo"
    composite_root = tmp_path / "assets"
    source_config = repo_root / "configs/tasks/ebench/labutopia_lab_poc/lift2_candidate/level1_open_door.yml"
    mount_record = _write_generic_mount_record(
        tmp_path / "muffle_mount_record.json",
        composite_root,
    )
    _write_source_lift2_config(source_config)

    record = aan_runtime_adapter.build_runtime_adapter_record(
        repo_root=repo_root,
        mount_record_path=mount_record,
        source_task_config_path=source_config,
        task_group="ebench/labutopia_lab_poc/aan_stage6_muffle_furnace",
        task_name="level1_smoke",
        runtime_usd_name="scene_usds/labutopia/aan/stage6_muffle_furnace_scene",
        runtime_scene_uid="labutopia_aan_stage6_muffle_furnace",
        runtime_object_uid="muffle_furnace",
        generic_smoke=True,
    )

    wrapper_path = (
        composite_root / "scene_usds/labutopia/aan/stage6_muffle_furnace_scene.usda"
    )
    task_config_path = (
        repo_root
        / "configs/tasks/ebench/labutopia_lab_poc/aan_stage6_muffle_furnace/level1_smoke.yml"
    )
    index_path = (
        repo_root
        / "configs/tasks/ebench/labutopia_lab_poc/aan_stage6_muffle_furnace/aan_stage6_muffle_furnace.json"
    )
    assets_manifest_path = (
        repo_root
        / "configs/tasks/ebench/labutopia_lab_poc/aan_stage6_muffle_furnace/assets_manifest.json"
    )

    assert record["status"] == "pass"
    assert record["config_path"] == (
        "ebench/labutopia_lab_poc/aan_stage6_muffle_furnace/level1_smoke.yml"
    )
    assert (
        record["runtime_usd_name"]
        == "scene_usds/labutopia/aan/stage6_muffle_furnace_scene"
    )
    assert record["wrapper_references"] == [
        "../../../labutopia_aan_packages/stage6_codex_20260701_muffle_furnace/asset.usd"
    ]
    assert record["runtime_scene_uid"] == "labutopia_aan_stage6_muffle_furnace"
    assert record["runtime_object_uid"] == "muffle_furnace"
    assert record["required_prim_resolution_rows"][0]["runtime_path"] == (
        "/World/labutopia_aan_stage6_muffle_furnace/obj_muffle_furnace"
    )
    assert record["required_prim_resolution_rows"][1]["runtime_path"] == (
        "/World/labutopia_aan_stage6_muffle_furnace/obj_muffle_furnace/Group/mesh_000"
    )
    assert record["required_prim_resolution_rows"][2]["runtime_path"] == "N/A"
    assert record["blockers"] == []

    task_config = yaml.safe_load(task_config_path.read_text(encoding="utf-8"))
    evaluation = task_config["evaluation_configs"][0]
    assert evaluation["task_name"] == (
        "ebench/labutopia_lab_poc/aan_stage6_muffle_furnace/level1_smoke"
    )
    assert (
        evaluation["usd_name"]
        == "scene_usds/labutopia/aan/stage6_muffle_furnace_scene"
    )
    assert evaluation["generation_config"]["goal"] == []
    assert evaluation["object_config"] == {}
    assert evaluation["instruction"] == "Run AAN package reset/step smoke."
    assert "drying" not in task_config_path.read_text(encoding="utf-8").lower()

    assert json.loads(index_path.read_text(encoding="utf-8")) == [
        "ebench/labutopia_lab_poc/aan_stage6_muffle_furnace/level1_smoke.yml"
    ]
    assets_manifest = json.loads(assets_manifest_path.read_text(encoding="utf-8"))
    assert assets_manifest["runtime_usd_name"] == (
        "scene_usds/labutopia/aan/stage6_muffle_furnace_scene"
    )
    assert (
        assets_manifest["namespace"]
        == "labutopia_aan_packages/stage6_codex_20260701_muffle_furnace"
    )
    assert wrapper_path.is_file()
    assert 'def Xform "labutopia_aan_stage6_muffle_furnace"' in wrapper_path.read_text(
        encoding="utf-8"
    )
    assert 'def Xform "obj_muffle_furnace"' in wrapper_path.read_text(encoding="utf-8")


def test_symlink_mount_keeps_wrapper_reference_inside_composite_namespace(tmp_path):
    repo_root = tmp_path / "repo"
    composite_root = tmp_path / "assets"
    source_config = repo_root / "configs/tasks/ebench/labutopia_lab_poc/lift2_candidate/level1_open_door.yml"
    mount_record = _write_mount_record(
        tmp_path / "mount_record.json",
        composite_root,
        symlink_source_package=True,
    )
    _write_source_lift2_config(source_config)

    record = aan_runtime_adapter.build_runtime_adapter_record(
        repo_root=repo_root,
        mount_record_path=mount_record,
        source_task_config_path=source_config,
        json_out=tmp_path / "adapter_evidence.json",
    )

    expected_mounted_root = (
        composite_root / "labutopia_aan_packages/dryingbox_01_overlay/asset.usd"
    )
    wrapper_path = (
        composite_root / "scene_usds/labutopia/aan/dryingbox_01_overlay_scene.usda"
    )
    assert record["status"] == "pass"
    assert record["mounted_root_usd"] == str(expected_mounted_root.absolute())
    assert record["wrapper_references"] == [
        "../../../labutopia_aan_packages/dryingbox_01_overlay/asset.usd"
    ]
    assert "../../../labutopia_aan_packages/dryingbox_01_overlay/asset.usd" in wrapper_path.read_text(
        encoding="utf-8"
    )


def test_blocks_stale_mount_record_package_digest(tmp_path):
    repo_root = tmp_path / "repo"
    composite_root = tmp_path / "assets"
    source_config = repo_root / "configs/tasks/ebench/labutopia_lab_poc/lift2_candidate/level1_open_door.yml"
    mount_record = _write_mount_record(tmp_path / "mount_record.json", composite_root)
    _write_source_lift2_config(source_config)
    stale_record = json.loads(mount_record.read_text(encoding="utf-8"))
    stale_record["source_package_hash_after"]["digest"] = "stale-digest"
    _write_json(mount_record, stale_record)

    record = aan_runtime_adapter.build_runtime_adapter_record(
        repo_root=repo_root,
        mount_record_path=mount_record,
        source_task_config_path=source_config,
    )

    assert record["status"] == "blocked"
    assert record["mounted_package_tree_digest"] != "stale-digest"
    assert {
        "code": "mounted_package_tree_digest_mismatch",
        "field": "source_package_hash_after.digest",
        "actual": record["mounted_package_tree_digest"],
        "expected": "stale-digest",
    } in record["blockers"]


def test_blocks_mounted_root_usd_outside_composite_namespace(tmp_path):
    repo_root = tmp_path / "repo"
    composite_root = tmp_path / "assets"
    source_config = repo_root / "configs/tasks/ebench/labutopia_lab_poc/lift2_candidate/level1_open_door.yml"
    mount_record = _write_mount_record(tmp_path / "mount_record.json", composite_root)
    _write_source_lift2_config(source_config)
    stale_record = json.loads(mount_record.read_text(encoding="utf-8"))
    outside_root_usd = tmp_path / "outside_package/asset.usd"
    _write_usd(
        outside_root_usd,
        [row["path"] for row in stale_record["required_prim_resolution_rows"]],
    )
    stale_record["mounted_root_usd"] = str(outside_root_usd)
    _write_json(mount_record, stale_record)

    record = aan_runtime_adapter.build_runtime_adapter_record(
        repo_root=repo_root,
        mount_record_path=mount_record,
        source_task_config_path=source_config,
    )

    expected_root_usd = (
        composite_root / "labutopia_aan_packages/dryingbox_01_overlay/asset.usd"
    )
    assert record["status"] == "blocked"
    assert {
        "code": "mounted_root_usd_not_in_composite_namespace",
        "field": "mounted_root_usd",
        "actual": str(outside_root_usd.absolute()),
        "expected": str(expected_root_usd.absolute()),
    } in record["blockers"]


def test_blocks_wrapper_reference_that_only_appears_in_comment(tmp_path):
    repo_root = tmp_path / "repo"
    composite_root = tmp_path / "assets"
    source_config = repo_root / "configs/tasks/ebench/labutopia_lab_poc/lift2_candidate/level1_open_door.yml"
    mount_record = _write_mount_record(tmp_path / "mount_record.json", composite_root)
    _write_source_lift2_config(source_config)
    aan_runtime_adapter.build_runtime_adapter_record(
        repo_root=repo_root,
        mount_record_path=mount_record,
        source_task_config_path=source_config,
    )
    record_data = json.loads(mount_record.read_text(encoding="utf-8"))
    decoy_usd = composite_root / "labutopia_aan_packages/decoy/asset.usd"
    _write_usd(
        decoy_usd,
        [row["path"] for row in record_data["required_prim_resolution_rows"]],
    )
    wrapper_path = (
        composite_root / "scene_usds/labutopia/aan/dryingbox_01_overlay_scene.usda"
    )
    wrapper_path.write_text(
        "\n".join(
            [
                "#usda 1.0",
                "# ../../../labutopia_aan_packages/dryingbox_01_overlay/asset.usd",
                "(",
                '    defaultPrim = "World"',
                ")",
                "",
                'def Xform "World" (',
                "    references = @../../../labutopia_aan_packages/decoy/asset.usd@</World>",
                ")",
                "{",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    task_config_path = (
        repo_root
        / "configs/tasks/ebench/labutopia_lab_poc/aan_lift2_candidate/level1_open_door.yml"
    )

    record = aan_runtime_adapter.preflight_runtime_adapter(
        repo_root=repo_root,
        mount_record_path=mount_record,
        task_config_path=task_config_path,
    )

    assert record["status"] == "blocked"
    assert record["wrapper_references"] == [
        "../../../labutopia_aan_packages/decoy/asset.usd"
    ]
    assert {
        "code": "runtime_wrapper_missing_aan_reference",
        "field": "wrapper_references",
        "actual": ["../../../labutopia_aan_packages/decoy/asset.usd"],
        "expected": "../../../labutopia_aan_packages/dryingbox_01_overlay/asset.usd",
        "path": str(wrapper_path),
    } in record["blockers"]


def test_blocks_legacy_usd_name_in_generated_aan_task_profile(tmp_path):
    repo_root = tmp_path / "repo"
    composite_root = tmp_path / "assets"
    source_config = repo_root / "configs/tasks/ebench/labutopia_lab_poc/lift2_candidate/level1_open_door.yml"
    mount_record = _write_mount_record(tmp_path / "mount_record.json", composite_root)
    _write_source_lift2_config(source_config)
    aan_runtime_adapter.build_runtime_adapter_record(
        repo_root=repo_root,
        mount_record_path=mount_record,
        source_task_config_path=source_config,
        json_out=tmp_path / "adapter_evidence.json",
    )
    task_config_path = (
        repo_root
        / "configs/tasks/ebench/labutopia_lab_poc/aan_lift2_candidate/level1_open_door.yml"
    )
    task_config = yaml.safe_load(task_config_path.read_text(encoding="utf-8"))
    task_config["evaluation_configs"][0][
        "usd_name"
    ] = "scene_usds/labutopia/level1_poc/lab_001/scene"
    _write_yaml(task_config_path, task_config)

    record = aan_runtime_adapter.preflight_runtime_adapter(
        repo_root=repo_root,
        mount_record_path=mount_record,
        task_config_path=task_config_path,
    )

    assert record["status"] == "blocked"
    assert record["legacy_overlay_used"] is True
    assert {
        "code": "legacy_usd_name_used",
        "field": "evaluation_configs[0].usd_name",
        "actual": "scene_usds/labutopia/level1_poc/lab_001/scene",
        "expected": "scene_usds/labutopia/aan/dryingbox_01_overlay_scene",
    } in record["blockers"]


def test_cli_writes_runtime_adapter_evidence(tmp_path):
    repo_root = tmp_path / "repo"
    composite_root = tmp_path / "assets"
    source_config = repo_root / "configs/tasks/ebench/labutopia_lab_poc/lift2_candidate/level1_open_door.yml"
    json_out = tmp_path / "adapter_evidence.json"
    mount_record = _write_mount_record(tmp_path / "mount_record.json", composite_root)
    _write_source_lift2_config(source_config)

    exit_code = aan_runtime_adapter.main(
        [
            "--repo-root",
            str(repo_root),
            "--mount-record",
            str(mount_record),
            "--source-task-config",
            str(source_config),
            "--json-out",
            str(json_out),
        ]
    )

    assert exit_code == 0
    record = json.loads(json_out.read_text(encoding="utf-8"))
    assert record["status"] == "pass"
    assert record["config_path"] == (
        "ebench/labutopia_lab_poc/aan_lift2_candidate/level1_open_door.yml"
    )
