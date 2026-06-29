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
