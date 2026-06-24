#!/usr/bin/env python3
"""Native-only Isaac smoke for the LabUtopia DryingBox asset."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LABUTOPIA_ROOT = Path("/cpfs/shared/simulation/zhuzihou/dev/LabUtopia")
DEFAULT_SOURCE_SCENE_RELATIVE = Path("assets/chemistry_lab/lab_001/lab_001.usd")
DEFAULT_SOURCE_PRIM_PATH = "/World/DryingBox_01"
DEFAULT_SMOKE_PRIM_PATH = "/World/DryingBox_01"
DEFAULT_HANDLE_PRIM_PATH = "/World/DryingBox_01/handle/mesh"
DEFAULT_STEP_COUNT = 90
REQUIRED_SMOKE_KEYS = {
    "stage_path",
    "source_prim_path",
    "joint_names",
    "initial_joint_positions",
    "post_step_joint_positions",
    "root_pose_finite",
    "handle_pose_finite",
    "runtime_physics_stable",
    "physx_warnings",
}


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    if hasattr(value, "GetReal") and hasattr(value, "GetImaginary"):
        imaginary = _jsonable(value.GetImaginary())
        if not isinstance(imaginary, list):
            imaginary = [imaginary]
        return [_jsonable(value.GetReal()), *imaginary]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    try:
        return [_jsonable(item) for item in value]
    except TypeError:
        return str(value)


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _finite_number_list(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    return all(_is_finite_number(item) for item in value)


def _flatten_numbers(value: Any) -> list[Any]:
    converted = _jsonable(value)
    if isinstance(converted, list):
        flattened: list[Any] = []
        for item in converted:
            flattened.extend(_flatten_numbers(item))
        return flattened
    return [converted]


def _pose_is_finite(pose: dict[str, Any] | None) -> bool:
    if not pose:
        return False
    values = _flatten_numbers([pose.get("position"), pose.get("orientation")])
    return bool(values) and all(_is_finite_number(item) for item in values)


def _resolve_source_stage(labutopia_root: str | Path) -> Path:
    stage_path = Path(labutopia_root) / DEFAULT_SOURCE_SCENE_RELATIVE
    if not stage_path.exists():
        raise FileNotFoundError(f"native LabUtopia stage not found: {stage_path}")
    return stage_path


def _default_output_root() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("saved/diagnostics") / f"native_dryingbox_smoke_{stamp}"


def build_minimal_native_stage(
    *,
    labutopia_root: str | Path = DEFAULT_LABUTOPIA_ROOT,
    output_root: str | Path,
    source_prim_path: str = DEFAULT_SOURCE_PRIM_PATH,
    smoke_prim_path: str = DEFAULT_SMOKE_PRIM_PATH,
) -> Path:
    output_dir = Path(output_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    stage_path = output_dir / "native_dryingbox.usda"
    source_stage = _resolve_source_stage(labutopia_root)
    smoke_prim_name = smoke_prim_path.rstrip("/").split("/")[-1]
    if not smoke_prim_path.startswith("/World/") or "/" in smoke_prim_name:
        raise ValueError(f"smoke_prim_path must be a direct /World child: {smoke_prim_path}")
    stage_path.write_text(
        "\n".join(
            [
                "#usda 1.0",
                "(",
                '    defaultPrim = "World"',
                "    metersPerUnit = 1",
                '    upAxis = "Z"',
                ")",
                "",
                'def Xform "World"',
                "{",
                f'    def Xform "{smoke_prim_name}" (',
                f"        prepend references = @{source_stage}@<{source_prim_path}>",
                "    )",
                "    {",
                "    }",
                "}",
                "",
                'def PhysicsScene "physicsScene"',
                "{",
                "    vector3f physics:gravityDirection = (0, 0, -1)",
                "    float physics:gravityMagnitude = 9.81",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return stage_path


def validate_smoke_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_SMOKE_KEYS.difference(report))
    if missing:
        errors.append(f"missing required keys: {missing}")
        return errors

    if report.get("errors"):
        errors.append(f"runtime reported errors: {report['errors']}")
    if report.get("traceback"):
        errors.append("runtime reported traceback")
    if report.get("root_prim_exists") is not True:
        errors.append("root_prim_exists must be true")
    if report.get("handle_prim_exists") is not True:
        errors.append("handle_prim_exists must be true")
    if report.get("root_articulation_api_present") is not True:
        errors.append("root_articulation_api_present must be true")
    if not isinstance(report["joint_names"], list):
        errors.append("joint_names must be a list")
    elif not report["joint_names"]:
        errors.append("joint_names must not be empty")
    if not _finite_number_list(report["initial_joint_positions"]):
        errors.append("initial_joint_positions must contain only finite numbers")
    if not _finite_number_list(report["post_step_joint_positions"]):
        errors.append("post_step_joint_positions must contain only finite numbers")
    if isinstance(report["joint_names"], list) and isinstance(
        report["initial_joint_positions"], list
    ):
        if len(report["joint_names"]) != len(report["initial_joint_positions"]):
            errors.append("joint_names and initial_joint_positions length mismatch")
    if isinstance(report["joint_names"], list) and isinstance(
        report["post_step_joint_positions"], list
    ):
        if len(report["joint_names"]) != len(report["post_step_joint_positions"]):
            errors.append("joint_names and post_step_joint_positions length mismatch")
    if report["root_pose_finite"] is not True:
        errors.append("root_pose_finite must be true")
    if report["handle_pose_finite"] is not True:
        errors.append("handle_pose_finite must be true")
    if report["runtime_physics_stable"] is not True:
        errors.append("runtime_physics_stable must be true")
    if not isinstance(report["physx_warnings"], list):
        errors.append("physx_warnings must be a list")
    if "step_count" in report:
        step_count = report["step_count"]
        if not isinstance(step_count, int) or not 60 <= step_count <= 120:
            errors.append("step_count must be an integer between 60 and 120")
    return errors


def write_smoke_report(report: dict[str, Any], output_root: str | Path) -> Path:
    output_path = Path(output_root) / "smoke.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return output_path


class PhysxWarningCollector:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self._subscription: Any = None

    def __enter__(self) -> "PhysxWarningCollector":
        try:
            import omni.kit.app  # type: ignore

            stream = omni.kit.app.get_app().get_log_event_stream()
            self._subscription = stream.create_subscription_to_pop(self._on_log_event)
        except Exception:
            self._subscription = None
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._subscription = None

    def _on_log_event(self, event: Any) -> None:
        payload = getattr(event, "payload", None) or {}
        if not isinstance(payload, dict):
            return
        message = str(
            payload.get("message")
            or payload.get("msg")
            or payload.get("text")
            or payload
        )
        level = str(payload.get("level") or payload.get("severity") or "").lower()
        lowered = message.lower()
        if "physx" in lowered and ("warn" in level or "warning" in lowered):
            self.warnings.append(message[:1000])


def _pose_from_prim(prim: Any) -> dict[str, Any] | None:
    try:
        position, orientation = prim.get_world_pose()
    except Exception:
        return None
    return {
        "position": _jsonable(position),
        "orientation": _jsonable(orientation),
    }


def _dof_names(articulation: Any) -> list[str]:
    names = getattr(articulation, "dof_names", None)
    if names is None:
        articulation_view = getattr(articulation, "_articulation_view", None)
        names = getattr(articulation_view, "dof_names", None)
    if names is None:
        return []
    return [str(name) for name in _jsonable(names)]


def _joint_positions(articulation: Any) -> list[Any]:
    return _jsonable(articulation.get_joint_positions())


def _candidate_isaac_log_roots() -> list[Path]:
    site_packages = (
        Path(sys.prefix)
        / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    )
    roots = [
        site_packages / "omni/logs/Kit/Isaac-Sim",
        Path("/isaac-sim/kit/logs/Kit/Isaac-Sim"),
        Path.home() / ".nvidia-omniverse/logs/Kit/Isaac-Sim",
    ]
    for env_name in ("ISAAC_PATH", "EXP_PATH", "CARB_APP_PATH"):
        env_path = os.environ.get(env_name)
        if env_path:
            roots.append(Path(env_path) / "logs/Kit/Isaac-Sim")
    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.expanduser()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(resolved)
    return deduped


def _isaac_log_candidates(
    started_at: float | None = None,
    log_roots: list[Path] | None = None,
) -> list[Path]:
    candidates: list[Path] = []
    for log_root in log_roots or _candidate_isaac_log_roots():
        if log_root.exists():
            candidates.extend(log_root.glob("*/kit_*.log"))
            candidates.extend(log_root.glob("kit_*.log"))
    if started_at is not None:
        candidates = [
            path
            for path in candidates
            if path.exists() and path.stat().st_mtime >= started_at - 2.0
        ]
    return sorted(candidates, key=lambda path: path.stat().st_mtime)


def _extract_physx_warnings_from_log(log_path: str | Path) -> list[str]:
    path = Path(log_path)
    if not path.exists():
        return []
    warnings: list[str] = []
    warning_pattern = re.compile(r"\[(warning|warn)\]|(?:^|\s)(warning|warn)(?:\s|:)", re.IGNORECASE)
    physics_needles = (
        "physx",
        "physics",
        "articulation",
        "duplicate link name",
    )
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        lowered = line.lower()
        if not warning_pattern.search(line):
            continue
        if not any(needle in lowered for needle in physics_needles):
            continue
        warnings.append(line.strip()[:1000])
    return warnings


def _runtime_smoke(
    *,
    stage_path: Path,
    smoke_prim_path: str,
    handle_prim_path: str,
    step_count: int,
) -> dict[str, Any]:
    started_at = time.time()
    from isaacsim import SimulationApp  # type: ignore

    simulation_app = SimulationApp({"headless": True, "multi_gpu": False})
    warning_collector = PhysxWarningCollector()
    root_prim_exists = False
    handle_prim_exists = False
    root_articulation_api_present = False
    initial_joint_positions: list[Any] = []
    post_step_joint_positions: list[Any] = []
    root_pose = None
    post_root_pose = None
    handle_pose = None
    post_handle_pose = None
    joint_names: list[str] = []
    from omni.isaac.core import World  # type: ignore
    from omni.isaac.core.articulations import Articulation  # type: ignore
    from omni.isaac.core.prims import XFormPrim  # type: ignore
    from omni.isaac.core.utils.stage import open_stage  # type: ignore
    import omni.usd  # type: ignore
    from pxr import UsdPhysics  # type: ignore

    open_stage(str(stage_path))
    simulation_app.update()
    stage = omni.usd.get_context().get_stage()
    root_prim = stage.GetPrimAtPath(smoke_prim_path)
    handle_prim = stage.GetPrimAtPath(handle_prim_path)
    root_prim_exists = bool(root_prim and root_prim.IsValid())
    handle_prim_exists = bool(handle_prim and handle_prim.IsValid())
    root_articulation_api_present = bool(
        root_prim_exists and root_prim.HasAPI(UsdPhysics.ArticulationRootAPI)
    )
    if not root_prim_exists:
        raise RuntimeError(f"root prim not found in smoke stage: {smoke_prim_path}")
    if not handle_prim_exists:
        raise RuntimeError(f"handle prim not found in smoke stage: {handle_prim_path}")
    if not root_articulation_api_present:
        raise RuntimeError(
            f"root prim lacks PhysicsArticulationRootAPI: {smoke_prim_path}"
        )

    world = World(stage_units_in_meters=1.0)
    root = Articulation(prim_path=smoke_prim_path, name="native_dryingbox")
    handle = XFormPrim(prim_path=handle_prim_path, name="native_dryingbox_handle")
    world.scene.add(root)
    world.scene.add(handle)

    with warning_collector:
        world.reset()
        root.initialize()
        world.initialize_physics()
        initial_joint_positions = _joint_positions(root)
        root_pose = _pose_from_prim(root)
        handle_pose = _pose_from_prim(handle)
        for _ in range(step_count):
            world.step(render=False)
        post_step_joint_positions = _joint_positions(root)
        post_root_pose = _pose_from_prim(root)
        post_handle_pose = _pose_from_prim(handle)
        joint_names = _dof_names(root)
    simulation_app.update()

    isaac_log_path = None
    log_candidates = _isaac_log_candidates(started_at)
    log_warnings: list[str] = []
    if log_candidates:
        isaac_log_path = str(log_candidates[-1])
        log_warnings = _extract_physx_warnings_from_log(log_candidates[-1])

    root_pose_finite = _pose_is_finite(root_pose) and _pose_is_finite(post_root_pose)
    handle_pose_finite = _pose_is_finite(handle_pose) and _pose_is_finite(
        post_handle_pose
    )
    joint_positions_finite = _finite_number_list(initial_joint_positions) and (
        _finite_number_list(post_step_joint_positions)
    )
    physx_warnings = sorted(set(warning_collector.warnings + log_warnings))
    return {
        "root_prim_exists": root_prim_exists,
        "handle_prim_exists": handle_prim_exists,
        "root_articulation_api_present": root_articulation_api_present,
        "joint_names": joint_names,
        "initial_joint_positions": initial_joint_positions,
        "post_step_joint_positions": post_step_joint_positions,
        "root_pose": root_pose,
        "post_step_root_pose": post_root_pose,
        "handle_pose": handle_pose,
        "post_step_handle_pose": post_handle_pose,
        "root_pose_finite": root_pose_finite,
        "handle_pose_finite": handle_pose_finite,
        "runtime_physics_stable": bool(
            root_pose_finite and handle_pose_finite and joint_positions_finite
        ),
        "physx_warnings": physx_warnings,
        "physx_warning_sources": {
            "log_event_stream_count": len(set(warning_collector.warnings)),
            "isaac_log_count": len(set(log_warnings)),
        },
        "simulation_app_close_policy": (
            "not_called_in_isaacsim41_conda_smoke;"
            " SimulationApp.close() segfaulted in this runtime before smoke.json could be written"
        ),
        "isaac_log_path": isaac_log_path,
    }


def run_native_dryingbox_smoke(
    *,
    labutopia_root: str | Path = DEFAULT_LABUTOPIA_ROOT,
    output_root: str | Path,
    source_prim_path: str = DEFAULT_SOURCE_PRIM_PATH,
    smoke_prim_path: str = DEFAULT_SMOKE_PRIM_PATH,
    handle_prim_path: str = DEFAULT_HANDLE_PRIM_PATH,
    step_count: int = DEFAULT_STEP_COUNT,
) -> tuple[dict[str, Any], Path]:
    output_dir = Path(output_root)
    stage_path = output_dir / "native_dryingbox.usda"
    report: dict[str, Any] = {
        "schema_version": 1,
        "labutopia_root": str(Path(labutopia_root)),
        "stage_path": str(stage_path),
        "source_prim_path": source_prim_path,
        "smoke_prim_path": smoke_prim_path,
        "handle_prim_path": handle_prim_path,
        "step_count": step_count,
        "root_prim_exists": False,
        "handle_prim_exists": False,
        "root_articulation_api_present": False,
        "joint_names": [],
        "initial_joint_positions": [],
        "post_step_joint_positions": [],
        "root_pose": None,
        "post_step_root_pose": None,
        "handle_pose": None,
        "post_step_handle_pose": None,
        "root_pose_finite": False,
        "handle_pose_finite": False,
        "runtime_physics_stable": False,
        "physx_warnings": [],
        "physx_warning_policy": "capture_only_for_task4_triage",
        "physx_warning_sources": {
            "log_event_stream_count": 0,
            "isaac_log_count": 0,
        },
        "simulation_app_close_policy": (
            "not_called_in_isaacsim41_conda_smoke;"
            " SimulationApp.close() segfaulted in this runtime before smoke.json could be written"
        ),
        "isaac_log_path": None,
        "errors": [],
    }
    try:
        stage_path = build_minimal_native_stage(
            labutopia_root=labutopia_root,
            output_root=output_dir,
            source_prim_path=source_prim_path,
            smoke_prim_path=smoke_prim_path,
        )
        report["stage_path"] = str(stage_path)
        runtime_report = _runtime_smoke(
            stage_path=stage_path,
            smoke_prim_path=smoke_prim_path,
            handle_prim_path=handle_prim_path,
            step_count=step_count,
        )
        report.update(runtime_report)
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        report["traceback"] = traceback.format_exc()

    output_path = write_smoke_report(report, output_dir)
    return report, output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a native-only Isaac smoke for LabUtopia DryingBox_01."
    )
    parser.add_argument(
        "--labutopia-root",
        default=str(DEFAULT_LABUTOPIA_ROOT),
        help="Path to the LabUtopia repository.",
    )
    parser.add_argument(
        "--source-prim-path",
        default=DEFAULT_SOURCE_PRIM_PATH,
        help="Native DryingBox prim path in the source LabUtopia stage.",
    )
    parser.add_argument(
        "--smoke-prim-path",
        default=DEFAULT_SMOKE_PRIM_PATH,
        help="DryingBox prim path to create and read in the smoke stage.",
    )
    parser.add_argument(
        "--handle-prim-path",
        default=DEFAULT_HANDLE_PRIM_PATH,
        help="Native handle prim path to read world pose from.",
    )
    parser.add_argument(
        "--step-count",
        type=int,
        default=DEFAULT_STEP_COUNT,
        help="Number of post-reset physics steps to run.",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Directory where native_dryingbox.usda and smoke.json should be written.",
    )
    args = parser.parse_args()

    output_root = args.output_root or _default_output_root()
    report, output_path = run_native_dryingbox_smoke(
        labutopia_root=args.labutopia_root,
        output_root=output_root,
        source_prim_path=args.source_prim_path,
        smoke_prim_path=args.smoke_prim_path,
        handle_prim_path=args.handle_prim_path,
        step_count=args.step_count,
    )
    errors = validate_smoke_report(report)
    print(output_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
