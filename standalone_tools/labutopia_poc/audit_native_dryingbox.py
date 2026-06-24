#!/usr/bin/env python3
"""Read-only USD audit for the native LabUtopia DryingBox asset."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pxr import Usd, UsdGeom, UsdPhysics


DEFAULT_LABUTOPIA_ROOT = Path("/cpfs/shared/simulation/zhuzihou/dev/LabUtopia")
DEFAULT_SOURCE_SCENE_RELATIVE = Path("assets/chemistry_lab/lab_001/lab_001.usd")
DEFAULT_SOURCE_PRIM_PATH = "/World/DryingBox_01"
MOVABLE_JOINT_TYPES = {"PhysicsRevoluteJoint", "PhysicsPrismaticJoint"}
EXPECTED_NATIVE_JOINT_TYPES = {"PhysicsFixedJoint", "PhysicsRevoluteJoint"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_float(value: float) -> float | str:
    number = float(value)
    if math.isnan(number):
        return "NaN"
    if math.isinf(number):
        return "Infinity" if number > 0 else "-Infinity"
    return number


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return _json_float(value)
    if hasattr(value, "GetReal") and hasattr(value, "GetImaginary"):
        imaginary = _json_value(value.GetImaginary())
        if not isinstance(imaginary, list):
            imaginary = [imaginary]
        return [_json_value(value.GetReal()), *imaginary]
    if hasattr(value, "__len__") and hasattr(value, "__getitem__"):
        try:
            return [_json_value(value[index]) for index in range(len(value))]
        except (IndexError, TypeError):
            pass
    if hasattr(value, "__iter__"):
        try:
            return [_json_value(item) for item in value]
        except TypeError:
            pass
    return str(value)


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _finite_sequence(value: Any) -> bool:
    converted = _json_value(value)
    if not isinstance(converted, list):
        return False
    return all(_is_finite_number(item) for item in converted)


def _sequence_all_zero(value: Any) -> bool:
    converted = _json_value(value)
    if not isinstance(converted, list):
        return False
    return bool(converted) and all(
        isinstance(item, (int, float)) and float(item) == 0.0 for item in converted
    )


def _quat_invalid(value: Any) -> bool:
    converted = _json_value(value)
    if not isinstance(converted, list) or not converted:
        return False
    if not all(_is_finite_number(item) for item in converted):
        return True
    return math.isclose(sum(float(item) * float(item) for item in converted), 0.0)


def _attr_value(attr: Any) -> Any:
    if not attr:
        return None
    return _json_value(attr.Get())


def _xform_ops(prim: Usd.Prim) -> list[dict[str, Any]]:
    xformable = UsdGeom.Xformable(prim)
    if not xformable:
        return []
    ops = []
    for op in xformable.GetOrderedXformOps():
        ops.append(
            {
                "name": op.GetOpName(),
                "type": str(op.GetOpType()).replace("UsdGeom.XformOp.", ""),
                "value": _json_value(op.Get()),
            }
        )
    return ops


def _visibility(prim: Usd.Prim) -> Any:
    imageable = UsdGeom.Imageable(prim)
    if not imageable:
        return None
    return _attr_value(imageable.GetVisibilityAttr())


def _prim_report(prim: Usd.Prim) -> dict[str, Any]:
    return {
        "path": str(prim.GetPath()),
        "type": prim.GetTypeName(),
        "applied_api_schemas": list(prim.GetAppliedSchemas()),
        "xformOps": _xform_ops(prim),
        "visibility": _visibility(prim),
    }


def _mass_report(prim: Usd.Prim) -> dict[str, Any]:
    mass_api = UsdPhysics.MassAPI(prim)
    return {
        "has_mass_api": prim.HasAPI(UsdPhysics.MassAPI),
        "mass": _attr_value(mass_api.GetMassAttr()),
        "diagonal_inertia": _attr_value(mass_api.GetDiagonalInertiaAttr()),
        "center_of_mass": _attr_value(mass_api.GetCenterOfMassAttr()),
        "principal_axes": _attr_value(mass_api.GetPrincipalAxesAttr()),
    }


def _rigid_body_report(prim: Usd.Prim) -> dict[str, Any]:
    report = _prim_report(prim)
    report["mass_api"] = _mass_report(prim)
    return report


def _joint_schema(prim: Usd.Prim) -> Any:
    for schema in (
        UsdPhysics.RevoluteJoint,
        UsdPhysics.PrismaticJoint,
        UsdPhysics.FixedJoint,
    ):
        joint = schema(prim)
        if joint:
            return joint
    return UsdPhysics.Joint(prim)


def _relationship_report(
    stage: Usd.Stage, rel: Any, *, empty_targets_valid: bool = False
) -> dict[str, Any]:
    targets = [str(target) for target in rel.GetTargets()]
    target_reports = []
    for target in targets:
        target_prim = stage.GetPrimAtPath(target)
        target_reports.append(
            {
                "path": target,
                "exists": bool(target_prim and target_prim.IsValid()),
                "has_rigid_body_api": bool(
                    target_prim
                    and target_prim.IsValid()
                    and target_prim.HasAPI(UsdPhysics.RigidBodyAPI)
                ),
            }
        )
    valid = empty_targets_valid if not target_reports else all(
        item["exists"] and item["has_rigid_body_api"] for item in target_reports
    )
    return {"targets": targets, "target_reports": target_reports, "valid": valid}


def _joint_report(stage: Usd.Stage, prim: Usd.Prim) -> dict[str, Any]:
    joint = _joint_schema(prim)
    axis = None
    lower_limit = None
    upper_limit = None
    if prim.IsA(UsdPhysics.RevoluteJoint):
        typed = UsdPhysics.RevoluteJoint(prim)
        axis = _attr_value(typed.GetAxisAttr())
        lower_limit = _attr_value(typed.GetLowerLimitAttr())
        upper_limit = _attr_value(typed.GetUpperLimitAttr())
    elif prim.IsA(UsdPhysics.PrismaticJoint):
        typed = UsdPhysics.PrismaticJoint(prim)
        axis = _attr_value(typed.GetAxisAttr())
        lower_limit = _attr_value(typed.GetLowerLimitAttr())
        upper_limit = _attr_value(typed.GetUpperLimitAttr())
    report = {
        "path": str(prim.GetPath()),
        "type": prim.GetTypeName(),
        "applied_api_schemas": list(prim.GetAppliedSchemas()),
        "axis": axis,
        "limits": {
            "lower": lower_limit,
            "upper": upper_limit,
        },
        "physics:body0": _relationship_report(
            stage, joint.GetBody0Rel(), empty_targets_valid=True
        ),
        "physics:body1": _relationship_report(stage, joint.GetBody1Rel()),
        "local_frame": {
            "local_pos0": _attr_value(joint.GetLocalPos0Attr()),
            "local_rot0": _attr_value(joint.GetLocalRot0Attr()),
            "local_pos1": _attr_value(joint.GetLocalPos1Attr()),
            "local_rot1": _attr_value(joint.GetLocalRot1Attr()),
        },
    }
    return report


def _is_joint(prim: Usd.Prim) -> bool:
    type_name = prim.GetTypeName()
    return type_name.startswith("Physics") and type_name.endswith("Joint")


def _resolve_stage_path(labutopia_root: str | Path) -> Path:
    root = Path(labutopia_root)
    stage_path = root / DEFAULT_SOURCE_SCENE_RELATIVE
    if not stage_path.exists():
        raise FileNotFoundError(f"native LabUtopia stage not found: {stage_path}")
    return stage_path


def _root_scale_risks(source_prim: Usd.Prim) -> list[dict[str, Any]]:
    risks = []
    for op in _xform_ops(source_prim):
        if op["type"] != "TypeScale":
            continue
        value = op["value"]
        if value != [1.0, 1.0, 1.0]:
            risks.append({"path": str(source_prim.GetPath()), "scale": value})
    return risks


def _rigid_body_risks(rigid_bodies: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    risks = {
        "zero_mass": [],
        "zero_inertia": [],
        "invalid_com": [],
        "invalid_principal_axes": [],
    }
    for body in rigid_bodies:
        path = body["path"]
        mass_api = body["mass_api"]
        if not mass_api["has_mass_api"]:
            continue
        mass = mass_api["mass"]
        if isinstance(mass, (int, float)) and float(mass) <= 0.0:
            risks["zero_mass"].append({"path": path, "mass": mass})
        inertia = mass_api["diagonal_inertia"]
        if _sequence_all_zero(inertia):
            risks["zero_inertia"].append({"path": path, "diagonal_inertia": inertia})
        center_of_mass = mass_api["center_of_mass"]
        if center_of_mass is not None and not _finite_sequence(center_of_mass):
            risks["invalid_com"].append(
                {"path": path, "center_of_mass": center_of_mass}
            )
        principal_axes = mass_api["principal_axes"]
        if principal_axes is not None and _quat_invalid(principal_axes):
            risks["invalid_principal_axes"].append(
                {"path": path, "principal_axes": principal_axes}
            )
    return risks


def _joint_risks(joints: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    invalid_body_targets = []
    unexpected_types = []
    active_dofs = []
    for joint in joints:
        for rel_name in ("physics:body0", "physics:body1"):
            rel_report = joint[rel_name]
            if not rel_report["valid"]:
                invalid_body_targets.append(
                    {
                        "path": joint["path"],
                        "relationship": rel_name,
                        "target_reports": rel_report["target_reports"],
                    }
                )
        if joint["type"] not in EXPECTED_NATIVE_JOINT_TYPES:
            unexpected_types.append({"path": joint["path"], "type": joint["type"]})
        if joint["type"] in MOVABLE_JOINT_TYPES:
            active_dofs.append(
                {
                    "path": joint["path"],
                    "type": joint["type"],
                    "axis": joint.get("axis"),
                    "limits": joint.get("limits"),
                }
            )

    multiple_active_dofs = []
    if len(active_dofs) > 1:
        multiple_active_dofs.append(
            {
                "count": len(active_dofs),
                "joints": active_dofs,
            }
        )
    return {
        "invalid_joint_body_target": invalid_body_targets,
        "unexpected_joint_type": unexpected_types,
        "multiple_active_dofs": multiple_active_dofs,
    }


def audit_native_dryingbox(
    *,
    labutopia_root: str | Path = DEFAULT_LABUTOPIA_ROOT,
    source_prim_path: str = DEFAULT_SOURCE_PRIM_PATH,
    stage_path: str | Path | None = None,
) -> dict[str, Any]:
    stage_file = Path(stage_path) if stage_path else _resolve_stage_path(labutopia_root)
    stage = Usd.Stage.Open(str(stage_file), Usd.Stage.LoadNone)
    if not stage:
        raise RuntimeError(f"failed to open USD stage: {stage_file}")
    source_prim = stage.GetPrimAtPath(source_prim_path)
    if not source_prim or not source_prim.IsValid():
        raise ValueError(f"source prim not found in {stage_file}: {source_prim_path}")

    prims = [_prim_report(prim) for prim in Usd.PrimRange(source_prim)]
    articulation_roots = [
        _prim_report(prim)
        for prim in Usd.PrimRange(source_prim)
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI)
    ]
    rigid_bodies = [
        _rigid_body_report(prim)
        for prim in Usd.PrimRange(source_prim)
        if prim.HasAPI(UsdPhysics.RigidBodyAPI)
    ]
    joints = [
        _joint_report(stage, prim)
        for prim in Usd.PrimRange(source_prim)
        if _is_joint(prim)
    ]
    handle_candidates = [
        _prim_report(prim)
        for prim in Usd.PrimRange(source_prim)
        if "handle" in str(prim.GetPath()).lower()
    ]

    risk_flags = {
        "non_identity_root_scale": _root_scale_risks(source_prim),
        **_rigid_body_risks(rigid_bodies),
        **_joint_risks(joints),
    }
    report = {
        "schema_version": 1,
        "labutopia_root": str(Path(labutopia_root)),
        "stage_path": str(stage_file),
        "stage_sha256": _sha256(stage_file),
        "source_prim_path": source_prim_path,
        "prims": prims,
        "articulation_roots": articulation_roots,
        "rigid_bodies": rigid_bodies,
        "joints": joints,
        "handle_candidates": handle_candidates,
        "risk_flags": risk_flags,
        "summary": {
            "prim_count": len(prims),
            "articulation_root_count": len(articulation_roots),
            "rigid_body_count": len(rigid_bodies),
            "joint_count": len(joints),
            "handle_candidate_count": len(handle_candidates),
            "risk_count": sum(len(items) for items in risk_flags.values()),
        },
    }
    json.dumps(report, allow_nan=False)
    return report


def _default_output_root() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("saved/diagnostics") / f"native_dryingbox_audit_{stamp}"


def write_audit_report(report: dict[str, Any], output_root: str | Path) -> Path:
    output_path = Path(output_root) / "audit.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit the native LabUtopia DryingBox_01 USD asset."
    )
    parser.add_argument(
        "--labutopia-root",
        default=str(DEFAULT_LABUTOPIA_ROOT),
        help="Path to the LabUtopia repository.",
    )
    parser.add_argument(
        "--source-prim-path",
        default=DEFAULT_SOURCE_PRIM_PATH,
        help="Native DryingBox prim path to audit.",
    )
    parser.add_argument(
        "--stage-path",
        default=None,
        help="Optional explicit USD stage path. Defaults to LabUtopia lab_001.",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Directory where audit.json should be written.",
    )
    args = parser.parse_args()

    report = audit_native_dryingbox(
        labutopia_root=args.labutopia_root,
        source_prim_path=args.source_prim_path,
        stage_path=args.stage_path,
    )
    output_path = write_audit_report(report, args.output_root or _default_output_root())
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
