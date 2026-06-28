#!/usr/bin/env python3
"""Read-only USD audit for the native LabUtopia DryingBox asset."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pxr import Usd, UsdGeom, UsdPhysics, UsdShade


DEFAULT_LABUTOPIA_ROOT = Path("/cpfs/shared/simulation/zhuzihou/dev/LabUtopia")
DEFAULT_SOURCE_SCENE_RELATIVE = Path("assets/chemistry_lab/lab_001/lab_001.usd")
DEFAULT_SOURCE_PRIM_PATH = "/World/DryingBox_01"
MOVABLE_JOINT_TYPES = {"PhysicsRevoluteJoint", "PhysicsPrismaticJoint"}
EXPECTED_NATIVE_JOINT_TYPES = {"PhysicsFixedJoint", "PhysicsRevoluteJoint"}
REMOTE_ASSET_PREFIXES = ("http://", "https://", "omniverse://")
TEXTURE_REF_RE = re.compile(r'texture_2d\(\s*"([^"]+)"')
MDL_IMPORT_RE = re.compile(r"^\s*import\s+([^;]+);", re.MULTILINE)


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


def _asset_path_parts(value: Any) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    authored = getattr(value, "path", None)
    resolved = getattr(value, "resolvedPath", None)
    if authored is None:
        authored = str(value)
    if resolved == "":
        resolved = None
    return str(authored), str(resolved) if resolved else None


def _asset_dependency_report(
    asset_path: Any,
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    authored_path, resolved_path = _asset_path_parts(asset_path)
    report = {
        "asset_path": authored_path,
        "resolved_path": resolved_path,
        "asset_location": "absent",
        "sha256": None,
    }
    if not authored_path:
        return report

    if authored_path.startswith(REMOTE_ASSET_PREFIXES):
        report["asset_location"] = "remote"
        return report

    candidates = []
    if resolved_path:
        candidates.append(Path(resolved_path))
    authored_candidate = Path(authored_path)
    if authored_candidate.is_absolute():
        candidates.append(authored_candidate)
    elif base_dir is not None:
        candidates.append((base_dir / authored_candidate).resolve())

    for candidate in candidates:
        if candidate.exists():
            report["asset_location"] = "local"
            report["resolved_path"] = str(candidate)
            report["sha256"] = _sha256(candidate)
            return report

    report["asset_location"] = "missing"
    if candidates:
        report["resolved_path"] = str(candidates[0])
    return report


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


def _display_color_report(prim: Usd.Prim) -> dict[str, Any]:
    attr = prim.GetAttribute("primvars:displayColor")
    value = _attr_value(attr)
    authored = bool(attr and attr.HasAuthoredValueOpinion())
    report = {
        "authored": authored,
        "value": value,
        "fallback_status": "absent",
    }
    if value is None:
        return report

    colors = value if isinstance(value, list) else [value]
    flattened = []
    for color in colors:
        if isinstance(color, list):
            flattened.extend(
                float(channel)
                for channel in color
                if isinstance(channel, (int, float))
            )
        elif isinstance(color, (int, float)):
            flattened.append(float(color))

    if not flattened:
        report["fallback_status"] = "invalid"
    elif max(abs(channel) for channel in flattened) <= 0.05:
        report["fallback_status"] = "black_or_low_contrast"
    else:
        report["fallback_status"] = "usable"
    return report


def _prim_report(prim: Usd.Prim) -> dict[str, Any]:
    return {
        "path": str(prim.GetPath()),
        "type": prim.GetTypeName(),
        "applied_api_schemas": list(prim.GetAppliedSchemas()),
        "xformOps": _xform_ops(prim),
        "visibility": _visibility(prim),
    }


def _binding_scope_status(
    *,
    source_prim_path: str,
    source_binding_target: str | None,
    composed_binding_target: str | None,
) -> str:
    target = source_binding_target or composed_binding_target
    if target is None:
        return "unbound"
    if target == source_prim_path or target.startswith(f"{source_prim_path}/"):
        return "in_source_subtree"
    return "out_of_source_subtree"


def _read_mdl_text(path: str | None) -> str | None:
    if path is None:
        return None
    mdl_path = Path(path)
    if not mdl_path.exists():
        return None
    return mdl_path.read_text(encoding="utf-8-sig", errors="replace")


def _helper_import_reports(mdl_path: str | None) -> list[dict[str, Any]]:
    mdl_text = _read_mdl_text(mdl_path)
    if mdl_text is None or mdl_path is None:
        return []
    mdl_dir = Path(mdl_path).parent
    reports = []
    seen = set()
    for match in MDL_IMPORT_RE.finditer(mdl_text):
        module_expr = match.group(1).strip()
        if module_expr in seen:
            continue
        seen.add(module_expr)
        if module_expr.startswith("::"):
            reports.append(
                {
                    "module": module_expr,
                    "asset_path": None,
                    "resolved_path": None,
                    "asset_location": "builtin",
                    "sha256": None,
                }
            )
            continue
        module_name = module_expr.replace("::*", "").split("::", 1)[0]
        helper_path = f"{module_name}.mdl"
        dependency = _asset_dependency_report(helper_path, base_dir=mdl_dir)
        reports.append({"module": module_expr, **dependency})
    return reports


def _texture_dependency_reports(mdl_path: str | None) -> list[dict[str, Any]]:
    mdl_text = _read_mdl_text(mdl_path)
    if mdl_text is None or mdl_path is None:
        return []
    mdl_dir = Path(mdl_path).parent
    reports = []
    seen = set()
    for index, texture_path in enumerate(TEXTURE_REF_RE.findall(mdl_text)):
        if texture_path in seen:
            continue
        seen.add(texture_path)
        dependency = _asset_dependency_report(texture_path, base_dir=mdl_dir)
        reports.append(
            {
                "attribute_path": f"{mdl_path}:texture_2d:{index}",
                **dependency,
            }
        )
    return reports


def _material_shader_report(material_prim: Usd.Prim | None) -> dict[str, Any]:
    empty = {
        "source_asset": None,
        "sub_identifier": None,
        "resolved_path": None,
        "asset_location": "absent",
        "sha256": None,
        "helper_imports": [],
    }
    if material_prim is None or not material_prim.IsValid():
        return empty

    material = UsdShade.Material(material_prim)
    surface_shader, _, _ = material.ComputeSurfaceSource("mdl")
    shader_prims = []
    if surface_shader and surface_shader.GetPrim().IsValid():
        shader_prims.append(surface_shader.GetPrim())
    shader_prims.extend(
        prim
        for prim in Usd.PrimRange(material_prim)
        if prim.IsA(UsdShade.Shader) and prim not in shader_prims
    )
    for prim in shader_prims:
        source_attr = prim.GetAttribute("info:mdl:sourceAsset")
        if not source_attr:
            continue
        source_asset = source_attr.Get()
        if source_asset is None:
            continue
        source_report = _asset_dependency_report(
            source_asset,
            base_dir=Path(material_prim.GetStage().GetRootLayer().realPath).parent,
        )
        mdl_path = source_report["resolved_path"]
        return {
            "shader_path": str(prim.GetPath()),
            "source_asset": source_report["asset_path"],
            "sub_identifier": _attr_value(
                prim.GetAttribute("info:mdl:sourceAsset:subIdentifier")
            ),
            "resolved_path": mdl_path,
            "asset_location": source_report["asset_location"],
            "sha256": source_report["sha256"],
            "helper_imports": _helper_import_reports(mdl_path),
        }
    return empty


def _mesh_material_report(
    prim: Usd.Prim,
    *,
    source_prim_path: str,
) -> dict[str, Any]:
    binding_api = UsdShade.MaterialBindingAPI(prim)
    direct_rel = binding_api.GetDirectBindingRel()
    direct_targets = [str(target) for target in direct_rel.GetTargets()]
    material, binding_rel = binding_api.ComputeBoundMaterial()
    computed_binding_targets = (
        [str(target) for target in binding_rel.GetTargets()] if binding_rel else []
    )
    material_prim = material.GetPrim() if material else None
    material_path = (
        str(material_prim.GetPath())
        if material_prim is not None and material_prim.IsValid()
        else None
    )
    source_binding_targets = direct_targets or computed_binding_targets
    source_binding_target = source_binding_targets[0] if source_binding_targets else None
    binding_scope_status = _binding_scope_status(
        source_prim_path=source_prim_path,
        source_binding_target=source_binding_target,
        composed_binding_target=material_path,
    )
    mdl_report = _material_shader_report(material_prim)
    texture_reports = _texture_dependency_reports(mdl_report["resolved_path"])
    return {
        "mesh_path": str(prim.GetPath()),
        "direct_binding_targets": direct_targets,
        "source_binding_targets": source_binding_targets,
        "source_binding_target": source_binding_target,
        "source_binding_relationship_path": str(binding_rel.GetPath())
        if binding_rel
        else None,
        "composed_binding_target": material_path,
        "compute_bound_material": {
            "success": bool(material_path),
            "material_path": material_path,
            "relationship_path": str(binding_rel.GetPath()) if binding_rel else None,
        },
        "binding_scope_status": binding_scope_status,
        "material_prim_valid": bool(
            material_prim is not None and material_prim.IsValid()
        ),
        "material_prim_type": material_prim.GetTypeName()
        if material_prim is not None and material_prim.IsValid()
        else None,
        "mdl": mdl_report,
        "textures": texture_reports,
        "displayColor": _display_color_report(prim),
    }


def _dedupe_reports(
    reports: list[dict[str, Any]], keys: tuple[str, ...]
) -> list[dict[str, Any]]:
    deduped = {}
    for report in reports:
        dedupe_key = tuple(report.get(key) for key in keys)
        if all(item is None for item in dedupe_key):
            dedupe_key = json.dumps(report, sort_keys=True)
        deduped.setdefault(dedupe_key, report)
    return list(deduped.values())


def _material_closure_report(
    source_prim: Usd.Prim,
    *,
    source_prim_path: str,
) -> dict[str, Any]:
    mesh_materials = [
        _mesh_material_report(prim, source_prim_path=source_prim_path)
        for prim in Usd.PrimRange(source_prim)
        if prim.IsA(UsdGeom.Mesh)
    ]
    bound_meshes = [
        item for item in mesh_materials if item["compute_bound_material"]["success"]
    ]
    texture_dependencies = _dedupe_reports(
        [
            texture
            for item in mesh_materials
            for texture in item.get("textures", [])
        ],
        ("asset_path", "resolved_path", "attribute_path"),
    )
    helper_mdl_dependencies = _dedupe_reports(
        [
            helper
            for item in mesh_materials
            for helper in item["mdl"].get("helper_imports", [])
        ],
        ("module", "asset_path", "resolved_path"),
    )
    mdl_dependencies = _dedupe_reports(
        [
            {
                "asset_path": item["mdl"]["source_asset"],
                "resolved_path": item["mdl"]["resolved_path"],
                "asset_location": item["mdl"]["asset_location"],
                "sha256": item["mdl"]["sha256"],
                "sub_identifier": item["mdl"]["sub_identifier"],
            }
            for item in mesh_materials
            if item["mdl"]["source_asset"]
        ],
        ("asset_path", "resolved_path", "sub_identifier"),
    )
    return {
        "source_prim_path": source_prim_path,
        "mesh_count": len(mesh_materials),
        "bound_mesh_count": len(bound_meshes),
        "out_of_scope_binding_count": sum(
            1
            for item in bound_meshes
            if item["binding_scope_status"] == "out_of_source_subtree"
        ),
        "unique_source_binding_targets": sorted(
            {
                target
                for item in mesh_materials
                for target in item["source_binding_targets"]
            }
        ),
        "unique_composed_binding_targets": sorted(
            {
                item["composed_binding_target"]
                for item in bound_meshes
                if item["composed_binding_target"]
            }
        ),
        "mdl_dependencies": mdl_dependencies,
        "helper_mdl_dependencies": helper_mdl_dependencies,
        "texture_dependencies": texture_dependencies,
        "mesh_materials": mesh_materials,
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


def _material_risks(
    material_closure: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    out_of_scope_material_binding = []
    missing_mdl = []
    remote_only_mdl = []
    black_or_low_contrast_fallback = []

    for item in material_closure["mesh_materials"]:
        if item["binding_scope_status"] == "out_of_source_subtree":
            out_of_scope_material_binding.append(
                {
                    "mesh_path": item["mesh_path"],
                    "source_binding_target": item["source_binding_target"],
                    "composed_binding_target": item["composed_binding_target"],
                }
            )
        mdl = item["mdl"]
        if mdl["source_asset"] and mdl["asset_location"] == "missing":
            missing_mdl.append(
                {
                    "mesh_path": item["mesh_path"],
                    "source_asset": mdl["source_asset"],
                    "resolved_path": mdl["resolved_path"],
                    "sub_identifier": mdl["sub_identifier"],
                }
            )
        elif mdl["source_asset"] and mdl["asset_location"] == "remote":
            remote_only_mdl.append(
                {
                    "mesh_path": item["mesh_path"],
                    "source_asset": mdl["source_asset"],
                    "sub_identifier": mdl["sub_identifier"],
                }
            )

        display_color = item["displayColor"]
        if display_color["fallback_status"] in {
            "absent",
            "black_or_low_contrast",
            "invalid",
        }:
            black_or_low_contrast_fallback.append(
                {
                    "mesh_path": item["mesh_path"],
                    "fallback_status": display_color["fallback_status"],
                    "value": display_color["value"],
                }
            )

    for helper in material_closure["helper_mdl_dependencies"]:
        if helper["asset_location"] == "missing":
            missing_mdl.append(
                {
                    "mesh_path": None,
                    "module": helper["module"],
                    "source_asset": helper["asset_path"],
                    "resolved_path": helper["resolved_path"],
                    "sub_identifier": None,
                }
            )
        elif helper["asset_location"] == "remote":
            remote_only_mdl.append(
                {
                    "mesh_path": None,
                    "module": helper["module"],
                    "source_asset": helper["asset_path"],
                    "sub_identifier": None,
                }
            )

    missing_texture = [
        {
            "attribute_path": texture["attribute_path"],
            "asset_path": texture["asset_path"],
            "resolved_path": texture["resolved_path"],
        }
        for texture in material_closure["texture_dependencies"]
        if texture["asset_location"] == "missing"
    ]
    remote_only_texture = [
        {
            "attribute_path": texture["attribute_path"],
            "asset_path": texture["asset_path"],
        }
        for texture in material_closure["texture_dependencies"]
        if texture["asset_location"] == "remote"
    ]
    return {
        "out_of_scope_material_binding": out_of_scope_material_binding,
        "missing_mdl": missing_mdl,
        "missing_texture": missing_texture,
        "remote_only_mdl": remote_only_mdl,
        "remote_only_texture": remote_only_texture,
        "black_or_low_contrast_fallback": black_or_low_contrast_fallback,
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
    material_closure = _material_closure_report(
        source_prim, source_prim_path=source_prim_path
    )

    risk_flags = {
        "non_identity_root_scale": _root_scale_risks(source_prim),
        **_rigid_body_risks(rigid_bodies),
        **_joint_risks(joints),
        **_material_risks(material_closure),
    }
    report = {
        "schema_version": 1,
        "labutopia_root": str(Path(labutopia_root)),
        "stage_path": str(stage_file),
        "stage_sha256": _sha256(stage_file),
        "source_prim_path": source_prim_path,
        "material_closure": material_closure,
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
