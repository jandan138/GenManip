from __future__ import annotations

import os
from pathlib import Path

from standalone_tools.labutopia_poc import cold_runtime_sandbox_probe as probe


def test_claim_boundary_keeps_broader_claims_false():
    boundary = probe.build_claim_boundary("PASS")

    assert boundary == {
        "cold_runtime_sandbox_probe_passed": True,
        "official_leaderboard_claim_allowed": False,
        "policy_success_claim_allowed": False,
        "pm_showcase_ready": False,
        "native_material_closure_claim_allowed": False,
        "full_native_material_closure_claim_allowed": False,
    }


def test_claim_boundary_is_false_when_probe_does_not_pass():
    assert probe.build_claim_boundary("FAIL")[
        "cold_runtime_sandbox_probe_passed"
    ] is False
    assert probe.build_claim_boundary("BLOCKED")[
        "cold_runtime_sandbox_probe_passed"
    ] is False


def test_status_derivation_blocks_static_validation_failure():
    status = probe.derive_parent_status(
        static_validation_status="FAIL",
        child_status="PASS",
        runtime_counts={
            "remote_uri_count": 0,
            "user_cache_path_count": 0,
            "unauthorized_outside_sandbox_runtime_path_count": 0,
            "non_allowlisted_search_path_count": 0,
            "missing_required_prim_count": 0,
        },
    )

    assert status == "FAIL"


def test_status_derivation_rejects_runtime_leakage():
    status = probe.derive_parent_status(
        static_validation_status="PASS",
        child_status="PASS",
        runtime_counts={
            "remote_uri_count": 1,
            "user_cache_path_count": 0,
            "unauthorized_outside_sandbox_runtime_path_count": 0,
            "non_allowlisted_search_path_count": 0,
            "missing_required_prim_count": 0,
        },
    )

    assert status == "FAIL"


def test_status_derivation_passes_only_clean_child_pass():
    status = probe.derive_parent_status(
        static_validation_status="PASS",
        child_status="PASS",
        runtime_counts={
            "remote_uri_count": 0,
            "user_cache_path_count": 0,
            "unauthorized_outside_sandbox_runtime_path_count": 0,
            "non_allowlisted_search_path_count": 0,
            "missing_required_prim_count": 0,
        },
    )

    assert status == "PASS"


def _write(path: Path, content: bytes = b"data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_build_sandbox_merges_common_runtime_files_at_assets_root(tmp_path):
    package_root = tmp_path / "package"
    overlay_root = tmp_path / "overlay"
    _write(package_root / "common/miscs/mdl/test.mdl", b"mdl")
    _write(package_root / "common/assets_manifest.json", b"{}")
    _write(
        overlay_root / "scene_usds/labutopia/level1_poc/lab_001/scene.usda",
        b"#usda 1.0\n",
    )

    layout = probe.build_sandbox_layout(
        sandbox_root=tmp_path / "sandbox",
        package_root=package_root,
        overlay_root=overlay_root,
    )

    assert (layout.assets_dir / "miscs/mdl/test.mdl").read_bytes() == b"mdl"
    assert (
        layout.assets_dir / "scene_usds/labutopia/level1_poc/lab_001/scene.usda"
    ).exists()
    assert not (layout.assets_dir / "common/miscs/mdl/test.mdl").exists()


def test_build_sandbox_rejects_nonidentical_common_overlay_collision(tmp_path):
    package_root = tmp_path / "package"
    overlay_root = tmp_path / "overlay"
    _write(package_root / "common/miscs/mdl/test.mdl", b"from-common")
    _write(overlay_root / "miscs/mdl/test.mdl", b"from-overlay")

    try:
        probe.build_sandbox_layout(
            sandbox_root=tmp_path / "sandbox",
            package_root=package_root,
            overlay_root=overlay_root,
        )
    except probe.SandboxBuildError as exc:
        assert "collision differs" in str(exc)
    else:
        raise AssertionError("expected SandboxBuildError")


def test_build_child_environment_rewrites_assets_and_cache_paths(
    tmp_path, monkeypatch
):
    sandbox = tmp_path / "sandbox"
    layout = probe.SandboxLayout(
        sandbox_root=sandbox,
        package_config_root=sandbox / "package_config",
        assets_dir=sandbox / "assets",
        home=sandbox / "home",
        cache=sandbox / "cache",
        reports=sandbox / "reports",
    )
    monkeypatch.setenv("MDL_SYSTEM_PATH", "/source/miscs/mdl")
    monkeypatch.setenv(
        "PXR_AR_DEFAULT_SEARCH_PATH",
        f"{{ASSETS_DIR}}/scene_usds{os.pathsep}/tmp/source",
    )

    env, report = probe.build_child_environment(
        layout,
        base_env=os.environ,
        task_env_vars={"MDL_SYSTEM_PATH": "{ASSETS_DIR}/miscs/mdl"},
        builtin_allowlist_roots=(Path("/isaac-sim/materials"),),
    )

    assert env["HOME"] == str(layout.home)
    assert env["XDG_CACHE_HOME"] == str(layout.cache)
    assert str(layout.assets_dir) in env["PXR_AR_DEFAULT_SEARCH_PATH"]
    assert env["MDL_SYSTEM_PATH"] == str(layout.assets_dir / "miscs/mdl")
    assert report["non_allowlisted_search_path_count"] == 1
    assert report["original_overlay_search_path_count"] == 0
    assert report["user_cache_env_count"] == 0


def test_classify_runtime_dependency_counts_remote_cache_outside_and_builtin(
    tmp_path,
):
    sandbox_assets = tmp_path / "sandbox/assets"
    sandbox_assets.mkdir(parents=True)

    records = [
        probe.classify_runtime_dependency(
            authored_value="HTTPS://example.invalid/material.mdl",
            resolved_path=None,
            dependency_type="mdl",
            assets_dir=sandbox_assets,
            builtin_allowlist_roots=(Path("/isaac-sim/materials"),),
        ),
        probe.classify_runtime_dependency(
            authored_value=str(tmp_path / ".cache/texture.png"),
            resolved_path=tmp_path / ".cache/texture.png",
            dependency_type="texture",
            assets_dir=sandbox_assets,
            builtin_allowlist_roots=(Path("/isaac-sim/materials"),),
        ),
        probe.classify_runtime_dependency(
            authored_value="/cpfs/source/scene.usd",
            resolved_path=Path("/cpfs/source/scene.usd"),
            dependency_type="usd",
            assets_dir=sandbox_assets,
            builtin_allowlist_roots=(Path("/isaac-sim/materials"),),
        ),
        probe.classify_runtime_dependency(
            authored_value="/isaac-sim/materials/Base.mdl",
            resolved_path=Path("/isaac-sim/materials/Base.mdl"),
            dependency_type="mdl",
            assets_dir=sandbox_assets,
            builtin_allowlist_roots=(Path("/isaac-sim/materials"),),
        ),
    ]

    counts = probe.summarize_dependency_records(records)

    assert counts["remote_uri_count"] == 1
    assert counts["user_cache_path_count"] == 1
    assert counts["unauthorized_outside_sandbox_runtime_path_count"] == 1
    assert counts["allowlisted_builtin_runtime_path_count"] == 1


def test_parse_mdl_dependencies_supports_quoted_module_and_textures(tmp_path):
    mdl = tmp_path / "materials/root.mdl"
    _write(
        mdl,
        b'''
import "helper.mdl";
import helper_module;
import ::pkg::other_helper;
export material Root() = material(
    surface: material_surface(scattering: df::diffuse_reflection_bsdf(
        tint: texture_2d("textures/base.png").mono))
);
''',
    )

    deps = probe.parse_mdl_dependency_values(mdl.read_text(encoding="utf-8"))

    assert deps == [
        ("mdl_import", "helper.mdl"),
        ("mdl_import", "helper_module"),
        ("mdl_import", "::pkg::other_helper"),
        ("texture", "textures/base.png"),
    ]


def test_expand_local_mdl_dependencies_rejects_nested_remote_texture(tmp_path):
    assets_dir = tmp_path / "assets"
    _write(assets_dir / "root.mdl", b'import "helper.mdl";')
    _write(
        assets_dir / "helper.mdl",
        b'texture_2d("https://example.invalid/t.png")',
    )

    records = probe.expand_local_mdl_dependencies(
        mdl_path=assets_dir / "root.mdl",
        assets_dir=assets_dir,
        mdl_search_paths=[assets_dir],
        builtin_allowlist_roots=(Path("/isaac-sim/materials"),),
    )

    counts = probe.summarize_dependency_records(records)
    assert counts["remote_uri_count"] == 1


def test_derive_required_prims_uses_wrapper_fallback_order():
    manifest = {
        "drying_box_runtime_asset": {
            "wrapper_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01"
        },
        "articulation_part_paths": {
            "obj_DryingBox_01_handle": (
                "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle"
            )
        },
    }
    task_config = {
        "metric_joint_path": (
            "/World/labutopia_level1_poc/obj_obj_DryingBox_01/RevoluteJoint"
        )
    }

    records = probe.derive_required_prim_paths(manifest, task_config)

    assert "/World/labutopia_level1_poc/obj_obj_DryingBox_01" in records
    assert "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle" in records
    assert (
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/RevoluteJoint"
        in records
    )
    assert "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks" in records


def test_child_pxr_compose_passes_tiny_usd(tmp_path):
    scene = tmp_path / "assets/scene.usda"
    _write(
        scene,
        b'''#usda 1.0
def Xform "World"
{
    def Xform "labutopia_level1_poc"
    {
        def Xform "obj_obj_DryingBox_01"
        {
            def Xform "handle" {}
            def Scope "Looks" {}
            def PhysicsRevoluteJoint "RevoluteJoint" {}
        }
    }
}
''',
    )

    report = probe.run_child_pxr_compose(
        runtime_scene=scene,
        assets_dir=tmp_path / "assets",
        required_prim_paths=[
            "/World/labutopia_level1_poc/obj_obj_DryingBox_01",
            "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle",
            "/World/labutopia_level1_poc/obj_obj_DryingBox_01/RevoluteJoint",
            "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks",
        ],
        environment_report={
            "non_allowlisted_search_path_count": 0,
            "effective_mdl_system_path_entries": [str(tmp_path / "assets")],
        },
    )

    assert report["status"] == "PASS"
    assert report["runtime"]["composition_ok"] is True
    assert report["runtime"]["missing_required_prim_paths"] == []
    assert any(
        record["resolved_path"] == str(scene)
        and record["is_under_assets_dir"] is True
        for record in report["runtime"]["resolved_runtime_dependency_records"]
    )


def test_child_pxr_compose_fails_missing_required_prim(tmp_path):
    scene = tmp_path / "assets/scene.usda"
    _write(scene, b'#usda 1.0\ndef Xform "World" {}\n')

    report = probe.run_child_pxr_compose(
        runtime_scene=scene,
        assets_dir=tmp_path / "assets",
        required_prim_paths=["/World/missing"],
        environment_report={
            "non_allowlisted_search_path_count": 0,
            "effective_mdl_system_path_entries": [str(tmp_path / "assets")],
        },
    )

    assert report["status"] == "FAIL"
    assert report["runtime"]["missing_required_prim_paths"] == ["/World/missing"]


def test_child_pxr_compose_resolves_relative_mdl_source_asset(tmp_path):
    assets = tmp_path / "assets"
    scene = assets / "scene.usda"
    _write(
        assets / "miscs/mdl/Aluminum_Anodized_Charcoal.mdl",
        b"export material M() = material();",
    )
    _write(
        scene,
        b'''#usda 1.0
def Xform "World"
{
    def Material "Looks"
    {
        def Shader "Shader"
        {
            uniform token info:implementationSource = "sourceAsset"
            asset info:mdl:sourceAsset = @Aluminum_Anodized_Charcoal.mdl@
        }
    }
}
''',
    )

    report = probe.run_child_pxr_compose(
        runtime_scene=scene,
        assets_dir=assets,
        required_prim_paths=["/World"],
        environment_report={
            "non_allowlisted_search_path_count": 0,
            "effective_mdl_system_path_entries": [str(assets / "miscs/mdl")],
        },
    )

    assert report["status"] == "PASS"
    assert any(
        record["authored_value"] == "Aluminum_Anodized_Charcoal.mdl"
        and record["resolved_path"]
        and record["resolved_path"].endswith("Aluminum_Anodized_Charcoal.mdl")
        for record in report["runtime"]["resolved_runtime_dependency_records"]
    )


def test_parent_runner_uses_injected_static_validation_for_tiny_fixture(tmp_path):
    package_root = tmp_path / "package"
    overlay_root = tmp_path / "overlay"
    _write(package_root / "common/assets_manifest.json", b'{"asset_id":"Tiny"}')
    _write(
        overlay_root / "scene.usda",
        b'''#usda 1.0
def Xform "World"
{
    def Xform "object" {}
}
''',
    )

    report = probe.run_parent_probe(
        manifest_path=package_root / "common/assets_manifest.json",
        package_root=package_root,
        overlay_root=overlay_root,
        runtime_scene_relative=Path("scene.usda"),
        required_prim_paths=["/World/object"],
        static_validation_runner=lambda: {"status": "PASS", "command": "stub"},
        mode="pxr-compose",
        sandbox_root=tmp_path / "sandbox",
    )

    assert report["status"] == "PASS"
    assert report["static_validation"]["command"] == "stub"
    assert Path(report["artifacts"]["stdout_path"]).exists()
    assert Path(report["artifacts"]["stderr_path"]).exists()
    assert Path(report["artifacts"]["child_report_path"]).exists()
    assert report["artifacts"]["sha256"]["child_report_path"]
    assert report["artifacts"]["child_exit_code"] == 0
    assert report["claim_boundary"]["cold_runtime_sandbox_probe_passed"] is True
    assert report["claim_boundary"]["official_leaderboard_claim_allowed"] is False


def test_parent_runner_static_validation_fail_prevents_pass(tmp_path):
    package_root = tmp_path / "package"
    overlay_root = tmp_path / "overlay"
    _write(package_root / "common/assets_manifest.json", b'{"asset_id":"Tiny"}')

    report = probe.run_parent_probe(
        manifest_path=package_root / "common/assets_manifest.json",
        package_root=package_root,
        overlay_root=overlay_root,
        runtime_scene_relative=Path("missing.usda"),
        required_prim_paths=[],
        static_validation_runner=lambda: {"status": "FAIL", "command": "stub"},
        mode="pxr-compose",
        sandbox_root=tmp_path / "sandbox",
    )

    assert report["status"] == "FAIL"
    assert report["started_at_utc"].endswith("Z")
    assert report["ended_at_utc"].endswith("Z")
    assert report["artifacts"]["sha256"] == {}
    assert report["claim_boundary"]["cold_runtime_sandbox_probe_passed"] is False


def test_parse_args_defaults_to_pxr_compose():
    args = probe.parse_args([])

    assert args.mode == "pxr-compose"
    assert args.child_timeout_seconds == 120


def test_child_cli_writes_report_for_tiny_fixture(tmp_path):
    scene = tmp_path / "assets/scene.usda"
    output = tmp_path / "child_report.json"
    env_report = tmp_path / "environment.json"
    required = tmp_path / "required_prims.json"
    _write(scene, b'#usda 1.0\ndef Xform "World" {}\n')
    env_report.write_text(
        '{"non_allowlisted_search_path_count":0,"effective_mdl_system_path_entries":[]}',
        encoding="utf-8",
    )
    required.write_text('["/World"]', encoding="utf-8")

    exit_code = probe.main(
        [
            "--child-pxr-compose",
            "--runtime-scene",
            str(scene),
            "--assets-dir",
            str(tmp_path / "assets"),
            "--required-prims-json",
            str(required),
            "--environment-report-json",
            str(env_report),
            "--child-report-output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert '"status": "PASS"' in output.read_text(encoding="utf-8")


def test_default_required_prims_include_dryingbox_contract_paths():
    manifest = {
        "drying_box_runtime_asset": {
            "wrapper_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01"
        },
        "articulation_part_paths": {
            "obj_DryingBox_01_handle": (
                "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle"
            )
        },
    }
    task_config = {}

    paths = probe.derive_required_prim_paths(manifest, task_config)

    assert "/World/labutopia_level1_poc/obj_obj_DryingBox_01" in paths
    assert "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle" in paths
    assert "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks" in paths


def test_isaac_mode_requires_explicit_heavy_flag(monkeypatch):
    monkeypatch.delenv("LABUTOPIA_RUN_HEAVY_ISAAC_TESTS", raising=False)

    exit_code = probe.main(["--mode", "isaac-python-smoke"])

    assert exit_code == 2


def test_extract_task_env_vars_reads_first_evaluation_config():
    task_config = {
        "evaluation_configs": [
            {
                "env_vars": {
                    "MDL_SYSTEM_PATH": "/isaac-sim/materials:{ASSETS_DIR}/miscs/mdl"
                }
            }
        ]
    }

    assert probe.extract_task_env_vars(task_config) == {
        "MDL_SYSTEM_PATH": "/isaac-sim/materials:{ASSETS_DIR}/miscs/mdl"
    }
