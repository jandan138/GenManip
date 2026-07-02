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


def _config_ref_matches_prefix(normalized: str, prefix: str) -> bool:
    return (
        normalized == prefix
        or normalized.startswith(f"{prefix}/")
        or f"/{prefix}/" in normalized
        or normalized.endswith(f"/{prefix}")
    )


def _labutopia_config_parts(normalized: str) -> list[str]:
    prefix = LABUTOPIA_POC_CONFIG_PREFIX
    if normalized == prefix or normalized.endswith(f"/{prefix}"):
        return []
    marker = f"{prefix}/"
    if normalized.startswith(marker):
        suffix = normalized[len(marker) :]
    elif f"/{marker}" in normalized:
        suffix = normalized.split(f"/{marker}", 1)[1]
    else:
        return []
    return [part for part in suffix.split("/") if part]


def _aan_lane_name(config_path_or_group: str) -> str | None:
    normalized = config_path_or_group.strip().replace("\\", "/")
    parts = _labutopia_config_parts(normalized)
    if parts and parts[0].startswith("aan_"):
        return parts[0]
    return None


def _is_aan_config_ref(config_path_or_group: str) -> bool:
    return _aan_lane_name(config_path_or_group) is not None


def _manifest_path_for_config_ref(repo_root: Path, config_path_or_group: str) -> Path:
    lane_name = _aan_lane_name(config_path_or_group)
    if lane_name is not None:
        return (
            repo_root
            / "configs/tasks/ebench/labutopia_lab_poc"
            / lane_name
            / "assets_manifest.json"
        )
    return repo_root / LABUTOPIA_POC_MANIFEST


def resolve_labutopia_poc_assets_override(
    current_dir: str | Path, config_path_or_group: str
) -> LabUtopiaAssetsOverride | None:
    """Return a LabUtopia POC ASSETS_DIR override for matching task packages."""
    if not _is_labutopia_poc_config_ref(config_path_or_group):
        return None

    repo_root = Path(current_dir)
    manifest_path = _manifest_path_for_config_ref(repo_root, config_path_or_group)
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"LabUtopia POC assets manifest does not exist: {manifest_path}"
        )

    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path}: expected JSON object")

    overlay_root_value = None
    if not _is_aan_config_ref(config_path_or_group):
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
