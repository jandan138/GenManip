from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any


LABUTOPIA_POC_CONFIG_PREFIX = "ebench/labutopia_lab_poc"
LABUTOPIA_POC_ASSETS_OVERLAY_ENV = "LABUTOPIA_POC_ASSETS_OVERLAY_ROOT"
LABUTOPIA_POC_MANIFEST = (
    "configs/tasks/ebench/labutopia_lab_poc/common/assets_manifest.json"
)


@dataclass(frozen=True)
class LabUtopiaAssetsOverride:
    overlay_root: str
    runtime_scene: str


def _is_labutopia_poc_config_ref(value: str) -> bool:
    normalized = value.strip().replace("\\", "/")
    return (
        normalized == LABUTOPIA_POC_CONFIG_PREFIX
        or normalized.startswith(f"{LABUTOPIA_POC_CONFIG_PREFIX}/")
        or f"/{LABUTOPIA_POC_CONFIG_PREFIX}/" in normalized
        or normalized.endswith(f"/{LABUTOPIA_POC_CONFIG_PREFIX}")
    )


def _manifest_string(manifest: dict[str, Any], key: str, manifest_path: Path) -> str:
    value = manifest.get(key)
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{manifest_path}: {key} must be a non-empty string")
    return value


def resolve_labutopia_poc_assets_override(
    current_dir: str | Path, config_path_or_group: str
) -> LabUtopiaAssetsOverride | None:
    """Return a LabUtopia POC ASSETS_DIR override for matching task packages."""
    if not _is_labutopia_poc_config_ref(config_path_or_group):
        return None

    repo_root = Path(current_dir)
    manifest_path = repo_root / LABUTOPIA_POC_MANIFEST
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"LabUtopia POC assets manifest does not exist: {manifest_path}"
        )

    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path}: expected JSON object")

    overlay_root_value = os.environ.get(LABUTOPIA_POC_ASSETS_OVERLAY_ENV)
    if not overlay_root_value:
        overlay_root_value = _manifest_string(manifest, "overlay_root", manifest_path)
    overlay_root = Path(overlay_root_value)
    if not overlay_root.is_absolute():
        overlay_root = repo_root / overlay_root
    overlay_root = overlay_root.expanduser()

    runtime_usd_name = _manifest_string(manifest, "runtime_usd_name", manifest_path)
    runtime_usd_path = (
        runtime_usd_name
        if runtime_usd_name.endswith(".usda")
        else f"{runtime_usd_name}.usda"
    )
    runtime_scene = overlay_root / runtime_usd_path
    if not runtime_scene.exists():
        raise FileNotFoundError(
            f"LabUtopia POC runtime scene does not exist: {runtime_scene}"
        )

    return LabUtopiaAssetsOverride(
        overlay_root=str(overlay_root),
        runtime_scene=str(runtime_scene),
    )
