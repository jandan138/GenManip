"""Build the LabUtopia level-1 proof-of-concept asset overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


DEFAULT_LABUTOPIA_ROOT = Path("/cpfs/shared/simulation/zhuzihou/dev/LabUtopia")
DEFAULT_OVERLAY_ROOT = Path(
    "/cpfs/shared/simulation/zhuzihou/dev/_datasets/"
    "EBench-Assets-Overlay/labutopia_level1_poc/assets"
)
SOURCE_SCENE_RELATIVE = Path("assets/chemistry_lab/lab_001/lab_001.usd")
SOURCE_DIR_RELATIVE = SOURCE_SCENE_RELATIVE.parent
OVERLAY_SCENE_RELATIVE = Path("scene_usds/labutopia/level1_poc/lab_001")
USD_NAME = "scene_usds/labutopia/level1_poc/lab_001/scene"
MANIFEST_RELATIVE = Path("manifests/labutopia_level1_poc.json")

PRIM_RENAME_MAP = {
    "conical_bottle02": "obj_conical_bottle02",
    "beaker2": "obj_beaker2",
    "target_plat": "obj_target_plat",
    "DryingBox_01_handle": "obj_DryingBox_01_handle",
}
TASK_PRIMS = {
    "level1_pick": {
        "object_uid": "obj_conical_bottle02",
        "prim_path": "/World/_scene/obj_conical_bottle02",
    },
    "level1_place": {
        "object_uid": "obj_beaker2",
        "target_uid": "obj_target_plat",
        "object_prim_path": "/World/_scene/obj_beaker2",
        "target_prim_path": "/World/_scene/obj_target_plat",
    },
    "level1_open_door": {
        "object_uid": "obj_DryingBox_01_handle",
        "prim_path": "/World/_scene/obj_DryingBox_01_handle",
    },
}
REQUIRED_GENMANIP_OBJECT_UIDS = [
    "obj_conical_bottle02",
    "obj_beaker2",
    "obj_target_plat",
    "obj_DryingBox_01_handle",
]
TABLE_UID = "table"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_scene_wrapper(path: Path) -> None:
    path.write_text(
        """#usda 1.0
(
    defaultPrim = "World"
)

def Xform "World"
{
    def Xform "_scene" (
        prepend payload = @scene.usd@</World>
    )
    {
    }
}
""",
        encoding="utf-8",
    )


def _copied_files(overlay_root: Path, paths: list[Path]) -> list[dict[str, object]]:
    entries = []
    for path in sorted(paths):
        entries.append(
            {
                "relative_path": path.relative_to(overlay_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return entries


def _reject_overlay_scene_inside_source(
    source_dir: Path, overlay_scene_dir: Path
) -> None:
    resolved_source_dir = source_dir.resolve()
    resolved_overlay_scene_dir = overlay_scene_dir.resolve()
    try:
        resolved_overlay_scene_dir.relative_to(resolved_source_dir)
    except ValueError:
        return
    raise ValueError(
        "Overlay scene directory must not be inside the LabUtopia source scene "
        f"directory: {resolved_overlay_scene_dir} is within {resolved_source_dir}"
    )


def build_asset_overlay(
    labutopia_root: str | Path = DEFAULT_LABUTOPIA_ROOT,
    overlay_root: str | Path = DEFAULT_OVERLAY_ROOT,
) -> dict[str, object]:
    labutopia_root = Path(labutopia_root)
    overlay_root = Path(overlay_root)
    source_dir = labutopia_root / SOURCE_DIR_RELATIVE
    source_scene = labutopia_root / SOURCE_SCENE_RELATIVE
    if not source_scene.is_file():
        raise FileNotFoundError(source_scene)

    overlay_scene_dir = overlay_root / OVERLAY_SCENE_RELATIVE
    _reject_overlay_scene_inside_source(source_dir, overlay_scene_dir)
    if overlay_scene_dir.exists():
        shutil.rmtree(overlay_scene_dir)
    overlay_scene_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, overlay_scene_dir)

    scene_usd = overlay_scene_dir / "scene.usd"
    shutil.copy2(source_scene, scene_usd)
    scene_usda = overlay_scene_dir / "scene.usda"
    _write_scene_wrapper(scene_usda)

    copied_paths = [
        path
        for path in overlay_scene_dir.rglob("*")
        if path.is_file() and path.name != "scene.usda"
    ]
    manifest = {
        "source_repo": str(labutopia_root),
        "source_scene": str(source_scene),
        "overlay_root": str(overlay_root),
        "usd_name": USD_NAME,
        "task_prims": TASK_PRIMS,
        "prim_rename_map": PRIM_RENAME_MAP,
        "table_uid": TABLE_UID,
        "required_genmanip_object_uids": REQUIRED_GENMANIP_OBJECT_UIDS,
        "copied_files": _copied_files(overlay_root, copied_paths),
        "notes": [
            "This overlay does not rewrite the LabUtopia USD stage.",
            "The obj_* names are the GenManip-facing contract; verify source prims before relying on automated rename assumptions.",
        ],
    }

    manifest_path = overlay_root / MANIFEST_RELATIVE
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "overlay_scene_dir": str(overlay_scene_dir),
        "scene_usd": str(scene_usd),
        "scene_usda": str(scene_usda),
        "manifest": str(manifest_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the LabUtopia level-1 proof-of-concept asset overlay."
    )
    parser.add_argument(
        "--labutopia-root",
        type=Path,
        default=DEFAULT_LABUTOPIA_ROOT,
        help=f"LabUtopia checkout root. Default: {DEFAULT_LABUTOPIA_ROOT}",
    )
    parser.add_argument(
        "--overlay-root",
        type=Path,
        default=DEFAULT_OVERLAY_ROOT,
        help=f"Overlay asset root. Default: {DEFAULT_OVERLAY_ROOT}",
    )
    return parser.parse_args()


def main() -> None:
    outputs = build_asset_overlay(**vars(parse_args()))
    print(json.dumps(outputs, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
