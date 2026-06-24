from pathlib import Path
import json

import pytest

from genmanip.core.evaluator.labutopia_assets import (
    resolve_labutopia_poc_assets_override,
)


def _write_manifest(repo_root: Path, overlay_root: Path, runtime_usd_name: str) -> None:
    manifest_path = (
        repo_root
        / "configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "overlay_root": str(overlay_root),
                "runtime_usd_name": runtime_usd_name,
            }
        ),
        encoding="utf-8",
    )


def test_assets_override_ignores_non_labutopia_config(tmp_path):
    override = resolve_labutopia_poc_assets_override(
        tmp_path, "ebench/some_other_package/config.json"
    )

    assert override is None


def test_assets_override_resolves_overlay_runtime_scene(tmp_path):
    runtime_usd_name = "scene_usds/labutopia/level1_poc/lab_001/scene"
    overlay_root = tmp_path / "overlay/assets"
    runtime_scene = overlay_root / f"{runtime_usd_name}.usda"
    runtime_scene.parent.mkdir(parents=True)
    runtime_scene.write_text("#usda 1.0\n", encoding="utf-8")
    _write_manifest(tmp_path, overlay_root, runtime_usd_name)

    override = resolve_labutopia_poc_assets_override(
        tmp_path, "ebench/labutopia_lab_poc/franka_poc/franka_poc.json"
    )

    assert override is not None
    assert override.overlay_root == str(overlay_root)
    assert override.runtime_scene == str(runtime_scene)


def test_assets_override_allows_env_overlay_root_for_isolated_runs(
    tmp_path,
    monkeypatch,
):
    runtime_usd_name = "scene_usds/labutopia/level1_poc/lab_001/scene"
    manifest_overlay_root = tmp_path / "shared_overlay/assets"
    env_overlay_root = tmp_path / "isolated_retake_overlay/assets"
    runtime_scene = env_overlay_root / f"{runtime_usd_name}.usda"
    runtime_scene.parent.mkdir(parents=True)
    runtime_scene.write_text("#usda 1.0\n", encoding="utf-8")
    _write_manifest(tmp_path, manifest_overlay_root, runtime_usd_name)
    monkeypatch.setenv(
        "LABUTOPIA_POC_ASSETS_OVERLAY_ROOT",
        str(env_overlay_root),
    )

    override = resolve_labutopia_poc_assets_override(
        tmp_path, "ebench/labutopia_lab_poc/franka_poc/franka_poc.json"
    )

    assert override is not None
    assert override.overlay_root == str(env_overlay_root)
    assert override.runtime_scene == str(runtime_scene)


def test_assets_override_rejects_missing_runtime_scene(tmp_path):
    runtime_usd_name = "scene_usds/labutopia/level1_poc/lab_001/scene"
    overlay_root = tmp_path / "overlay/assets"
    _write_manifest(tmp_path, overlay_root, runtime_usd_name)

    with pytest.raises(FileNotFoundError, match="runtime scene"):
        resolve_labutopia_poc_assets_override(
            tmp_path, "ebench/labutopia_lab_poc/lift2_candidate/lift2_candidate.json"
        )
