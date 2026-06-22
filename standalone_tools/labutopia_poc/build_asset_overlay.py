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
SCENE_UID = "labutopia_level1_poc"

SOURCE_TO_RUNTIME_OBJECT_KEY = {
    "/World/conical_bottle02": "obj_conical_bottle02",
    "/World/beaker2": "obj_beaker2",
    "/World/target_plat": "obj_target_plat",
    "/World/DryingBox_01": "obj_DryingBox_01",
    "/World/DryingBox_01/handle": "obj_DryingBox_01_handle",
    "/World/table": "table",
}
SOURCE_TASK_PRIMS = {
    "level1_pick": ["/World/conical_bottle02"],
    "level1_place": ["/World/beaker2", "/World/target_plat"],
    "level1_open_door": [
        "/World/DryingBox_01",
        "/World/DryingBox_01/handle",
        "/World/DryingBox_01/RevoluteJoint",
    ],
}
REQUIRED_GENMANIP_OBJECT_UIDS = [
    "obj_conical_bottle02",
    "obj_beaker2",
    "obj_target_plat",
    "obj_DryingBox_01",
    "obj_DryingBox_01_handle",
    "obj_table",
]
TABLE_UID = "table"


def _wrapper_name(runtime_object_key: str) -> str:
    if runtime_object_key == TABLE_UID:
        return "obj_table"
    return f"obj_{runtime_object_key}"


def _wrapper_prim_paths() -> dict[str, str]:
    return {
        runtime_key: f"/World/{SCENE_UID}/{_wrapper_name(runtime_key)}"
        for runtime_key in SOURCE_TO_RUNTIME_OBJECT_KEY.values()
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_scene_wrapper(path: Path) -> None:
    wrapper_defs = []
    for source_path, runtime_key in SOURCE_TO_RUNTIME_OBJECT_KEY.items():
        wrapper_defs.append(
            f"""        def Xform "{_wrapper_name(runtime_key)}" (
            prepend payload = @scene.usd@<{source_path}>
        )
        {{
        }}"""
        )

    scene_text = (
        """#usda 1.0
(
    defaultPrim = "World"
)

def Xform "World"
{
"""
        + f'    def Xform "{SCENE_UID}"\n'
        + "    {\n"
        + "\n".join(wrapper_defs)
        + "\n    }\n}\n"
    )
    path.write_text(
        scene_text,
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
        "scene_uid": SCENE_UID,
        "source_task_prims": SOURCE_TASK_PRIMS,
        "source_prim_paths": list(SOURCE_TO_RUNTIME_OBJECT_KEY.keys()),
        "source_to_runtime_object_key": SOURCE_TO_RUNTIME_OBJECT_KEY,
        "runtime_object_keys": list(SOURCE_TO_RUNTIME_OBJECT_KEY.values()),
        "wrapper_prim_paths": _wrapper_prim_paths(),
        "table_uid": TABLE_UID,
        "required_genmanip_object_uids": REQUIRED_GENMANIP_OBJECT_UIDS,
        "copied_files": _copied_files(overlay_root, copied_paths),
        "notes": [
            "scene.usda exposes a single scene uid under /World for GenManip discovery.",
            "Immediate obj_* wrapper prims payload the selected LabUtopia source prims.",
            "Runtime object keys strip one leading obj_ from wrapper prim names.",
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
