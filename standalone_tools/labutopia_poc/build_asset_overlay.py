"""Build the LabUtopia level-1 proof-of-concept asset overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from standalone_tools.labutopia_poc.material_closure import (
    derive_material_closure_claims,
)
from standalone_tools.labutopia_poc.asset_acceptance import acceptance_stage_entry


PACKAGE_COMMON_ROOT = ROOT / "configs/tasks/ebench/labutopia_lab_poc/common"
DEFAULT_LABUTOPIA_ROOT = Path("/cpfs/shared/simulation/zhuzihou/dev/LabUtopia")
DEFAULT_OVERLAY_ROOT = Path(
    "/cpfs/shared/simulation/zhuzihou/dev/_datasets/"
    "EBench-Assets-Overlay/labutopia_level1_poc/assets"
)
SOURCE_SCENE_RELATIVE = Path("assets/chemistry_lab/lab_001/lab_001.usd")
SOURCE_DIR_RELATIVE = SOURCE_SCENE_RELATIVE.parent
SOURCE_WORLD_LOOKS_PATH = "/World/Looks"
REQUIRED_WORKER_MDL_SYSTEM_PATH = (
    "/isaac-sim/materials/:"
    "{ASSETS_DIR}/scene_usds/labutopia/level1_poc/lab_001/SubUSDs/materials:"
    "{ASSETS_DIR}/miscs/mdl/labutopia/mdl"
)
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
TOP_LEVEL_SOURCE_TO_RUNTIME_OBJECT_KEY = {
    source_path: runtime_key
    for source_path, runtime_key in SOURCE_TO_RUNTIME_OBJECT_KEY.items()
    if source_path != "/World/DryingBox_01/handle"
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
ARTICULATION_PART_PATHS = {
    "obj_DryingBox_01_handle": f"/World/{SCENE_UID}/obj_obj_DryingBox_01/handle",
}
RUNTIME_TRANSLATION_OVERRIDES = {
    "obj_conical_bottle02": [0.28, 0.0, 0.8],
    "obj_beaker2": [0.27, 0.18, 0.84],
    "obj_target_plat": [0.26, -0.24, 0.776],
    "obj_DryingBox_01": [0.75, 0.1, 0.78],
}
RENDER_OBJECT_CONTRACTS = {
    "obj_conical_bottle02": {
        "source_prim_path": "/World/conical_bottle02",
        "role": "pick_target",
        "desired_runtime_translation": RUNTIME_TRANSLATION_OVERRIDES[
            "obj_conical_bottle02"
        ],
        "expected_world_bbox_lwh_m": {
            "min": [0.05, 0.05, 0.10],
            "max": [0.14, 0.14, 0.22],
        },
        "display_color": [0.10, 0.48, 0.95],
        "display_override_paths": ["mesh"],
    },
    "obj_beaker2": {
        "source_prim_path": "/World/beaker2",
        "role": "place_object",
        "desired_runtime_translation": RUNTIME_TRANSLATION_OVERRIDES["obj_beaker2"],
        "expected_world_bbox_lwh_m": {
            "min": [0.07, 0.07, 0.05],
            "max": [0.16, 0.16, 0.14],
        },
        "display_color": [0.10, 0.72, 0.54],
        "display_override_paths": ["mesh"],
    },
    "obj_target_plat": {
        "source_prim_path": "/World/target_plat",
        "role": "place_target",
        "desired_runtime_translation": RUNTIME_TRANSLATION_OVERRIDES[
            "obj_target_plat"
        ],
        "expected_world_bbox_lwh_m": {
            "min": [0.08, 0.08, 0.00005],
            "max": [0.14, 0.14, 0.02],
        },
        "display_color": [0.95, 0.78, 0.12],
        "display_override_paths": ["mesh"],
    },
    "obj_DryingBox_01": {
        "source_prim_path": "/World/DryingBox_01",
        "role": "articulated_drying_box",
        "desired_runtime_translation": RUNTIME_TRANSLATION_OVERRIDES[
            "obj_DryingBox_01"
        ],
        "expected_world_bbox_lwh_m": {
            "min": [0.45, 0.50, 0.45],
            "max": [0.75, 0.90, 0.80],
        },
        "display_color": [0.82, 0.84, 0.88],
        "display_override_paths": [
            "body/body/mesh",
            "panel",
            "button",
        ],
    },
    "obj_DryingBox_01_handle": {
        "source_prim_path": "/World/DryingBox_01/handle",
        "role": "door_handle",
        "wrapper_prim_path": ARTICULATION_PART_PATHS["obj_DryingBox_01_handle"],
        "compose_nested_transform_with_parent": "obj_DryingBox_01",
        "expected_world_bbox_lwh_m": {
            "min": [0.03, 0.03, 0.14],
            "max": [0.08, 0.08, 0.26],
        },
        "display_color": [1.0, 0.18, 0.04],
        "display_override_paths": ["handle/mesh"],
    },
}
DRYING_BOX_DOOR_PANEL_COLOR = [0.28, 0.34, 0.42]
DRYING_BOX_DOOR_SEAM_COLOR = [0.04, 0.05, 0.06]
DRYING_BOX_HANDLE_MOUNT_COLOR = [0.05, 0.07, 0.09]
DRYING_BOX_VISUAL_AFFORDANCES = [
    {
        "name": "high_contrast_door_panel",
        "display_color": DRYING_BOX_DOOR_PANEL_COLOR,
    },
    {
        "name": "door_outline_seams",
        "display_color": DRYING_BOX_DOOR_SEAM_COLOR,
    },
    {
        "name": "handle_mount_backplate",
        "display_color": DRYING_BOX_HANDLE_MOUNT_COLOR,
    },
    {
        "name": "high_contrast_handle",
        "display_color": RENDER_OBJECT_CONTRACTS["obj_DryingBox_01_handle"][
            "display_color"
        ],
    },
]
DETERMINISTIC_LIGHTS = [
    {
        "prim_path": f"/World/{SCENE_UID}/DeterministicDomeLight",
        "type": "DomeLight",
        "intensity": 1000,
    }
]
DRYING_BOX_PHYSICS_OVERRIDES = {
    "body/body/mesh": {
        "mass": 2.0,
        "diagonal_inertia": [0.05, 0.05, 0.05],
    },
    "body/Group/door/mesh": {
        "mass": 0.5,
        "diagonal_inertia": [0.01, 0.01, 0.01],
    },
    "handle/mesh": {
        "mass": 0.1,
        "diagonal_inertia": [0.002, 0.002, 0.002],
    },
    "button": {
        "mass": 0.05,
        "diagonal_inertia": [0.001, 0.001, 0.001],
    },
}
DRYING_BOX_NATIVE_MATERIAL_BINDINGS = {
    "body/Group/door/mesh": "mdl_0007",
    "body/body": "mdl_0009",
    "handle/mesh": "mdl_0007",
    "Group/_14_1": "mdl_0007",
    "Group/_255_1": "mdl_0007",
    "Group/_908_1": "mdl_0007",
    "Group_01/mesh": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_01": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_02": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_03": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_04": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_05": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_06": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_07": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_08": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_09": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_10": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_11": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_12": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_13": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_14": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_15": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_16": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_17": "Aluminum_Anodized_Charcoal",
    "Group_01/mesh_18": "Aluminum_Anodized_Charcoal",
    "Group_02/group": "Aluminum_Anodized_Charcoal",
    "Group_02/group_01": "Aluminum_Anodized_Charcoal",
    "Group_02/group_04": "Aluminum_Anodized_Charcoal",
    "Group_02/group_05": "Aluminum_Anodized_Charcoal",
    "panel/mesh": "mdl_0007",
    "panel/mesh_01": "mdl_0008",
    "panel/mesh_02": "Aluminum_Anodized_Charcoal",
}
DRYING_BOX_NATIVE_MATERIAL_SCOPE_POLICY = "preserve_owned_world_looks"
DRYING_BOX_NATIVE_MATERIAL_POLICY = (
    "owned_world_looks_payload_with_wrapper_local_rebind_and_local_overrides"
)
DRYING_BOX_NATIVE_MATERIAL_STATUS = "resolved_material_with_local_overrides"
DRYING_BOX_WRAPPER_LOCAL_MATERIAL_OVERRIDES = {
    "button": {
        "material_name": "task_button_mat",
        "display_color": [1.0, 0.48, 0.04],
        "source_binding_status": "unbound_in_stage2_source_readback",
        "reason": "native_source_has_no_material_binding",
    },
    "Group/_900_1": {
        "material_name": "task_indicator_mat",
        "display_color": [0.10, 0.36, 0.95],
        "source_binding_status": "empty_authored_binding_in_stage2_source_readback",
        "reason": "native_source_has_empty_material_binding",
    },
}
DRYING_BOX_NATIVE_FALLBACK_DISPLAY_OVERRIDES: dict[str, dict[str, object]] = {}
DRYING_BOX_SOURCE_RESOLVED_SURFACES = {
    "panel": {
        "resolution_mode": "native_geomsubset_material_binding",
        "geomsubset_coverage_status": "covers_all_faces",
        "face_count": 158,
        "covered_face_count": 158,
        "source_binding_status": "parent_empty_binding_with_geomsubset_coverage",
        "geomsubset_bindings": [
            {"relative_path": "panel/mesh", "material_name": "mdl_0007"},
            {"relative_path": "panel/mesh_01", "material_name": "mdl_0008"},
            {
                "relative_path": "panel/mesh_02",
                "material_name": "Aluminum_Anodized_Charcoal",
            },
        ],
    }
}
DRYING_BOX_NATIVE_UNBOUND_SURFACE_WAIVER_OWNER = "GenManip LabUtopia integration"
DRYING_BOX_NATIVE_UNBOUND_SURFACE_WAIVER_REVIEW_DATE = "2026-07-15"
DRYING_BOX_NATIVE_MATERIAL_SOURCE_ASSETS = {
    "mdl_0007": {
        "mdl_source_asset": "./SubUSDs/materials/material_11.mdl",
        "mdl_subidentifier": "mdl_0007",
    },
    "mdl_0008": {
        "mdl_source_asset": "./SubUSDs/materials/material_08.mdl",
        "mdl_subidentifier": "mdl_0008",
    },
    "mdl_0009": {
        "mdl_source_asset": "./SubUSDs/materials/material_09.mdl",
        "mdl_subidentifier": "mdl_0009",
    },
    "Aluminum_Anodized_Charcoal": {
        "mdl_source_asset": "Aluminum_Anodized_Charcoal.mdl",
        "mdl_subidentifier": "Aluminum_Anodized_Charcoal",
    },
}
DRYING_BOX_REMOTE_ALUMINUM_MATERIAL = "Aluminum_Anodized_Charcoal"
DRYING_BOX_ALUMINUM_SOURCE_URL = (
    "https://omniverse-content-production.s3.us-west-2.amazonaws.com/"
    "Materials/Base/Metals/Aluminum_Anodized_Charcoal.mdl"
)
DRYING_BOX_ALUMINUM_TEXTURE_SOURCE_BASE_URL = (
    "https://omniverse-content-production.s3.us-west-2.amazonaws.com/"
    "Materials/Base/Metals/Aluminum_Anodized"
)
DRYING_BOX_ALUMINUM_MIRROR_RELATIVE = (
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl"
)
DRYING_BOX_ALUMINUM_MDL_SOURCE_ASSET = "Aluminum_Anodized_Charcoal.mdl"
DRYING_BOX_ALUMINUM_TEXTURE_RELATIVES = (
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_BaseColor.png",
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_Normal.png",
    "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_ORM.png",
)
DRYING_BOX_NATIVE_MATERIAL_CLOSURE_REASON = (
    "wrapper_local_material_overrides_present"
)
DRYING_BOX_REMOTE_ALUMINUM_WAIVER = {
    "waiver_id": "ALUMINUM_REMOTE_MDL_001",
    "waiver_reason": "remote source is intentionally not mirrored in this package revision",
    "waiver_owner": "LabUtopia EBench POC",
    "waiver_date": "2026-06-29",
    "material_closure_kept_open": True,
}
DRYING_BOX_STRATEGY_SURROGATE = "sanitized_surrogate"
DRYING_BOX_STRATEGY_NATIVE_COMPLEX = "native_complex"
DRYING_BOX_STRATEGY_CHOICES = (
    DRYING_BOX_STRATEGY_SURROGATE,
    DRYING_BOX_STRATEGY_NATIVE_COMPLEX,
)
DRYING_BOX_SURROGATE_RUNTIME_ASSET = {
    "strategy": "sanitized_surrogate",
    "wrapper_prim_path": f"/World/{SCENE_UID}/obj_obj_DryingBox_01",
    "base_joint_name": "BaseFixedJoint",
    "joint_name": "RevoluteJoint",
    "removed_source_joint_types": ["PhysicsPrismaticJoint"],
    "source_payload_used": False,
    "visual_affordances": DRYING_BOX_VISUAL_AFFORDANCES,
}
DRYING_BOX_NATIVE_RUNTIME_ASSET = {
    "strategy": "native_complex_with_additive_physics_override",
    "source_payload_used": True,
    "source_prim_path": "/World/DryingBox_01",
    "wrapper_prim_path": f"/World/{SCENE_UID}/obj_obj_DryingBox_01",
    "handle_policy": "nested_native_handle",
    "surrogate_kept_for_debug_baseline": True,
    "unit_policy": "preserve_native_unit_scale_0_001",
    "fixed_base_policy": "world_fixed_joint_body0_removed",
    "material_policy": DRYING_BOX_NATIVE_MATERIAL_POLICY,
    "material_scope_policy": DRYING_BOX_NATIVE_MATERIAL_SCOPE_POLICY,
    "material_status": DRYING_BOX_NATIVE_MATERIAL_STATUS,
    "remote_aluminum_disposition": "local_mirror",
    "material_closure_kept_open": False,
    "native_material_closure_open": True,
    "native_material_closure_reason": DRYING_BOX_NATIVE_MATERIAL_CLOSURE_REASON,
    "door_joint_name": "RevoluteJoint",
    "door_reset_target": [0.0],
    "button_prismatic_joint_policy": "ignored_by_open_door_metric",
    "button_joint_name": "PrismaticJoint",
}


def _wrapper_name(runtime_object_key: str) -> str:
    if runtime_object_key == TABLE_UID:
        return "obj_table"
    return f"obj_{runtime_object_key}"


def _normalize_drying_box_strategy(drying_box_strategy: str) -> str:
    if drying_box_strategy not in DRYING_BOX_STRATEGY_CHOICES:
        choices = ", ".join(DRYING_BOX_STRATEGY_CHOICES)
        raise ValueError(
            f"Unsupported drying-box strategy {drying_box_strategy!r}. "
            f"Expected one of: {choices}"
        )
    return drying_box_strategy


def _wrapper_prim_paths() -> dict[str, str]:
    paths = {
        runtime_key: f"/World/{SCENE_UID}/{_wrapper_name(runtime_key)}"
        for runtime_key in TOP_LEVEL_SOURCE_TO_RUNTIME_OBJECT_KEY.values()
    }
    paths.update(ARTICULATION_PART_PATHS)
    return paths


def _render_object_contracts() -> dict[str, dict[str, object]]:
    wrapper_paths = _wrapper_prim_paths()
    contracts = {}
    for runtime_key, contract in RENDER_OBJECT_CONTRACTS.items():
        item = {
            key: value
            for key, value in contract.items()
            if key != "display_override_paths"
        }
        item["wrapper_prim_path"] = wrapper_paths[runtime_key]
        contracts[runtime_key] = item
    return contracts


def _usd_float(value: float) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.6g}"


def _usd_vec3(values: list[float]) -> str:
    return "(" + ", ".join(_usd_float(value) for value in values) + ")"


def _usd_quat(values: list[float]) -> str:
    return "(" + ", ".join(_usd_float(value) for value in values) + ")"


def _preview_surface_material_def(
    name: str,
    *,
    color: list[float],
    indent_level: int = 12,
) -> str:
    indent = " " * indent_level
    attr_indent = " " * (indent_level + 4)
    shader_indent = " " * (indent_level + 8)
    return (
        f'{indent}def Material "{name}"\n'
        f"{indent}{{\n"
        f"{attr_indent}token outputs:surface.connect = "
        f"</World/{SCENE_UID}/obj_obj_DryingBox_01/Looks/{name}/PreviewSurface.outputs:surface>\n"
        f"{attr_indent}token outputs:mdl:surface.connect = "
        f"</World/{SCENE_UID}/obj_obj_DryingBox_01/Looks/{name}/OmniPBR.outputs:out>\n"
        f"{attr_indent}token outputs:mdl:displacement.connect = "
        f"</World/{SCENE_UID}/obj_obj_DryingBox_01/Looks/{name}/OmniPBR.outputs:out>\n"
        f"{attr_indent}token outputs:mdl:volume.connect = "
        f"</World/{SCENE_UID}/obj_obj_DryingBox_01/Looks/{name}/OmniPBR.outputs:out>\n"
        f'{attr_indent}def Shader "PreviewSurface"\n'
        f"{attr_indent}{{\n"
        f'{shader_indent}uniform token info:id = "UsdPreviewSurface"\n'
        f"{shader_indent}color3f inputs:diffuseColor = {_usd_vec3(color)}\n"
        f"{shader_indent}float inputs:metallic = 0\n"
        f"{shader_indent}float inputs:roughness = 0.85\n"
        f"{shader_indent}token outputs:surface\n"
        f"{attr_indent}}}\n"
        f'{attr_indent}def Shader "OmniPBR"\n'
        f"{attr_indent}{{\n"
        f'{shader_indent}uniform token info:implementationSource = "sourceAsset"\n'
        f"{shader_indent}asset info:mdl:sourceAsset = @OmniPBR.mdl@\n"
        f'{shader_indent}token info:mdl:sourceAsset:subIdentifier = "OmniPBR"\n'
        f"{shader_indent}color3f inputs:diffuse_color_constant = {_usd_vec3(color)}\n"
        f"{shader_indent}float inputs:reflection_roughness_constant = 0.45\n"
        f"{shader_indent}token outputs:out\n"
        f"{attr_indent}}}\n"
        f"{indent}}}"
    )


def _drying_box_material_scope_def() -> str:
    body_contract = RENDER_OBJECT_CONTRACTS["obj_DryingBox_01"]
    handle_contract = RENDER_OBJECT_CONTRACTS["obj_DryingBox_01_handle"]
    indent = " " * 12
    return (
        f'{indent}def Scope "Looks"\n'
        f"{indent}{{\n"
        f"{_preview_surface_material_def('body_mat', color=body_contract['display_color'], indent_level=16)}\n"
        f"{_preview_surface_material_def('door_panel_mat', color=DRYING_BOX_DOOR_PANEL_COLOR, indent_level=16)}\n"
        f"{_preview_surface_material_def('door_seam_mat', color=DRYING_BOX_DOOR_SEAM_COLOR, indent_level=16)}\n"
        f"{_preview_surface_material_def('handle_mount_mat', color=DRYING_BOX_HANDLE_MOUNT_COLOR, indent_level=16)}\n"
        f"{_preview_surface_material_def('handle_mat', color=handle_contract['display_color'], indent_level=16)}\n"
        f"{indent}}}"
    )


def _display_color_attr(color: list[float], indent: str) -> str:
    return (
        f"{indent}color3f[] primvars:displayColor = [{_usd_vec3(color)}]\n"
        f'{indent}uniform token primvars:displayColor:interpolation = "constant"'
    )


def _nested_display_override(path: str, color: list[float], indent_level: int = 4) -> str:
    parts = path.split("/")
    indent = " " * indent_level
    if len(parts) == 1:
        attr_indent = " " * (indent_level + 4)
        return (
            f'{indent}over "{parts[0]}"\n'
            f"{indent}{{\n"
            f"{_display_color_attr(color, attr_indent)}\n"
            f"{indent}}}"
        )
    inner = _nested_display_override(
        "/".join(parts[1:]), color, indent_level + 4
    )
    return f'{indent}over "{parts[0]}"\n{indent}{{\n{inner}\n{indent}}}'


def _mass_api_attr_block(mass: float, diagonal_inertia: list[float], indent: str) -> str:
    return (
        f"{indent}float physics:mass = {_usd_float(mass)}\n"
        f"{indent}point3f physics:diagonalInertia = {_usd_vec3(diagonal_inertia)}\n"
        f"{indent}point3f physics:centerOfMass = (0, 0, 0)\n"
        f"{indent}quatf physics:principalAxes = (1, 0, 0, 0)"
    )


def _nested_mass_override(
    path: str,
    *,
    mass: float,
    diagonal_inertia: list[float],
    indent_level: int = 4,
) -> str:
    parts = path.split("/")
    indent = " " * indent_level
    if len(parts) == 1:
        attr_indent = " " * (indent_level + 4)
        return (
            f'{indent}over "{parts[0]}" (\n'
            f'{indent}    prepend apiSchemas = ["PhysicsMassAPI"]\n'
            f"{indent})\n"
            f"{indent}{{\n"
            f"{_mass_api_attr_block(mass, diagonal_inertia, attr_indent)}\n"
            f"{indent}}}"
        )
    inner = _nested_mass_override(
        "/".join(parts[1:]),
        mass=mass,
        diagonal_inertia=diagonal_inertia,
        indent_level=indent_level + 4,
    )
    return f'{indent}over "{parts[0]}"\n{indent}{{\n{inner}\n{indent}}}'


def _new_override_node() -> dict[str, object]:
    return {
        "children": {},
        "display_color": None,
        "material_binding": None,
        "mass": None,
        "diagonal_inertia": None,
    }


def _override_node_for_path(
    tree: dict[str, dict[str, object]],
    path: str,
) -> dict[str, object]:
    current = tree
    node: dict[str, object] | None = None
    for part in path.split("/"):
        node = current.setdefault(part, _new_override_node())
        current = node["children"]  # type: ignore[assignment]
    assert node is not None
    return node


def _add_display_override(
    tree: dict[str, dict[str, object]],
    path: str,
    color: list[float],
) -> None:
    _override_node_for_path(tree, path)["display_color"] = color


def _add_mass_override(
    tree: dict[str, dict[str, object]],
    path: str,
    *,
    mass: float,
    diagonal_inertia: list[float],
) -> None:
    node = _override_node_for_path(tree, path)
    node["mass"] = mass
    node["diagonal_inertia"] = diagonal_inertia


def _add_material_binding_override(
    tree: dict[str, dict[str, object]],
    path: str,
    material_path: str,
) -> None:
    _override_node_for_path(tree, path)["material_binding"] = material_path


def _render_override_tree(
    name: str,
    node: dict[str, object],
    *,
    indent_level: int,
) -> str:
    indent = " " * indent_level
    attr_indent = " " * (indent_level + 4)
    mass = node.get("mass")
    material_binding = node.get("material_binding")
    api_schemas = []
    if mass is not None:
        api_schemas.append("PhysicsMassAPI")
    if material_binding is not None:
        api_schemas.append("MaterialBindingAPI")
    if not api_schemas:
        header = f'{indent}over "{name}"'
    else:
        schema_list = ", ".join(f'"{schema}"' for schema in api_schemas)
        header = (
            f'{indent}over "{name}" (\n'
            f"{indent}    prepend apiSchemas = [{schema_list}]\n"
            f"{indent})"
        )
    body_lines: list[str] = []
    display_color = node.get("display_color")
    if display_color is not None:
        body_lines.append(_display_color_attr(display_color, attr_indent))  # type: ignore[arg-type]
    if material_binding is not None:
        body_lines.append(f"{attr_indent}rel material:binding = <{material_binding}>")
    if mass is not None:
        body_lines.append(
            _mass_api_attr_block(
                float(mass),
                node["diagonal_inertia"],  # type: ignore[arg-type]
                attr_indent,
            )
        )
    children = node["children"]  # type: ignore[assignment]
    for child_name, child_node in children.items():  # type: ignore[union-attr]
        body_lines.append(
            _render_override_tree(
                child_name,
                child_node,
                indent_level=indent_level + 4,
            )
        )
    return f"{header}\n{indent}{{\n" + "\n".join(body_lines) + f"\n{indent}}}"


def _native_drying_box_root_overrides(root_path: str) -> str:
    return (
        f"            double3 xformOp:scale = (0.001, 0.001, 0.001)\n"
        f'            uniform token[] xformOpOrder = ["xformOp:translate", '
        f'"xformOp:rotateXYZ", "xformOp:scale"]\n'
        f'            over "FixedJoint_01"\n'
        f"            {{\n"
        f"                delete rel physics:body0 = <{root_path}/Group_02/group/mesh>\n"
        f"            }}\n"
        f'            over "RevoluteJoint"\n'
        f"            {{\n"
        f"                float state:angular:physics:position = 0\n"
        f"            }}"
    )


def _native_drying_box_material_scope_def() -> str:
    local_materials = "\n".join(
        _preview_surface_material_def(
            str(record["material_name"]),
            color=record["display_color"],  # type: ignore[arg-type]
            indent_level=16,
        )
        for record in DRYING_BOX_WRAPPER_LOCAL_MATERIAL_OVERRIDES.values()
    )
    return f"""            def Scope "Looks" (
                prepend payload = @scene.usd@<{SOURCE_WORLD_LOOKS_PATH}>
            )
            {{
                over "{DRYING_BOX_REMOTE_ALUMINUM_MATERIAL}"
                {{
                    over "Shader"
                    {{
                        uniform token info:implementationSource = "sourceAsset"
                        asset info:mdl:sourceAsset = @{DRYING_BOX_ALUMINUM_MDL_SOURCE_ASSET}@
                        token info:mdl:sourceAsset:subIdentifier = "{DRYING_BOX_REMOTE_ALUMINUM_MATERIAL}"
                    }}
                }}
{local_materials}
            }}"""


def _wrapper_body(
    source_path: str,
    runtime_key: str,
    *,
    native_drying_box: bool = False,
) -> str:
    body_lines = []
    translation = RUNTIME_TRANSLATION_OVERRIDES.get(runtime_key)
    if translation is not None:
        body_lines.append(
            f"            double3 xformOp:translate = {_usd_vec3(translation)}"
        )
    if native_drying_box:
        root_path = f"/World/{SCENE_UID}/{_wrapper_name(runtime_key)}"
        body_lines.append(_native_drying_box_root_overrides(root_path))
        body_lines.append(_native_drying_box_material_scope_def())
    override_tree: dict[str, dict[str, object]] = {}
    contract = RENDER_OBJECT_CONTRACTS.get(runtime_key)
    preserve_native_materials = native_drying_box and runtime_key == "obj_DryingBox_01"
    if contract is not None and not preserve_native_materials:
        display_color = contract["display_color"]
        for override_path in contract["display_override_paths"]:
            _add_display_override(override_tree, override_path, display_color)
    if runtime_key == "obj_DryingBox_01":
        if preserve_native_materials:
            root_path = f"/World/{SCENE_UID}/{_wrapper_name(runtime_key)}"
            for (
                override_path,
                material_name,
            ) in DRYING_BOX_NATIVE_MATERIAL_BINDINGS.items():
                _add_material_binding_override(
                    override_tree,
                    override_path,
                    f"{root_path}/Looks/{material_name}",
                )
            for (
                override_path,
                material,
            ) in DRYING_BOX_WRAPPER_LOCAL_MATERIAL_OVERRIDES.items():
                _add_material_binding_override(
                    override_tree,
                    override_path,
                    f"{root_path}/Looks/{material['material_name']}",
                )
            for (
                override_path,
                fallback,
            ) in DRYING_BOX_NATIVE_FALLBACK_DISPLAY_OVERRIDES.items():
                _add_display_override(
                    override_tree,
                    override_path,
                    fallback["display_color"],  # type: ignore[arg-type]
                )
        handle_contract = RENDER_OBJECT_CONTRACTS["obj_DryingBox_01_handle"]
        if not preserve_native_materials:
            for override_path in handle_contract["display_override_paths"]:
                _add_display_override(
                    override_tree,
                    override_path,
                    handle_contract["display_color"],
                )
        for override_path, physics in DRYING_BOX_PHYSICS_OVERRIDES.items():
            _add_mass_override(
                override_tree,
                override_path,
                mass=physics["mass"],
                diagonal_inertia=physics["diagonal_inertia"],
            )
    for child_name, child_node in override_tree.items():
        body_lines.append(
            _render_override_tree(child_name, child_node, indent_level=12)
        )
    return "\n".join(body_lines)


def _rigid_cube_def(
    name: str,
    *,
    translate: list[float],
    scale: list[float],
    color: list[float],
    mass: float,
    diagonal_inertia: list[float],
    material_path: str | None = None,
    indent_level: int = 12,
) -> str:
    indent = " " * indent_level
    attr_indent = " " * (indent_level + 4)
    api_schemas = [
        "PhysicsRigidBodyAPI",
        "PhysicsCollisionAPI",
        "PhysicsMassAPI",
    ]
    if material_path is not None:
        api_schemas.append("MaterialBindingAPI")
    api_schema_text = ", ".join(f'"{schema}"' for schema in api_schemas)
    material_binding = (
        f"{attr_indent}rel material:binding = <{material_path}>\n"
        if material_path is not None
        else ""
    )
    return (
        f'{indent}def Cube "{name}" (\n'
        f"{indent}    prepend apiSchemas = [{api_schema_text}]\n"
        f"{indent})\n"
        f"{indent}{{\n"
        f"{attr_indent}double size = 1\n"
        f"{attr_indent}double3 xformOp:translate = {_usd_vec3(translate)}\n"
        f"{attr_indent}double3 xformOp:scale = {_usd_vec3(scale)}\n"
        f'{attr_indent}uniform token[] xformOpOrder = ["xformOp:translate", '
        f'"xformOp:scale"]\n'
        f"{_display_color_attr(color, attr_indent)}\n"
        f"{material_binding}"
        f"{_mass_api_attr_block(mass, diagonal_inertia, attr_indent)}\n"
        f"{indent}}}"
    )


def _visual_cube_def(
    name: str,
    *,
    translate: list[float],
    scale: list[float],
    color: list[float],
    material_path: str,
    indent_level: int = 12,
) -> str:
    indent = " " * indent_level
    attr_indent = " " * (indent_level + 4)
    return (
        f'{indent}def Cube "{name}" (\n'
        f'{indent}    prepend apiSchemas = ["MaterialBindingAPI"]\n'
        f"{indent})\n"
        f"{indent}{{\n"
        f"{attr_indent}double size = 1\n"
        f"{attr_indent}double3 xformOp:translate = {_usd_vec3(translate)}\n"
        f"{attr_indent}double3 xformOp:scale = {_usd_vec3(scale)}\n"
        f'{attr_indent}uniform token[] xformOpOrder = ["xformOp:translate", '
        f'"xformOp:scale"]\n'
        f"{_display_color_attr(color, attr_indent)}\n"
        f"{attr_indent}rel material:binding = <{material_path}>\n"
        f"{indent}}}"
    )


def _joint_relationships(
    root_path: str,
    *,
    body0: str,
    body1: str,
    indent: str,
) -> str:
    return (
        f"{indent}rel physics:body0 = <{root_path}/{body0}>\n"
        f"{indent}rel physics:body1 = <{root_path}/{body1}>"
    )


def _drying_box_surrogate_def(runtime_key: str) -> str:
    wrapper_name = _wrapper_name(runtime_key)
    root_path = f"/World/{SCENE_UID}/{wrapper_name}"
    translation = RUNTIME_TRANSLATION_OVERRIDES[runtime_key]
    body_contract = RENDER_OBJECT_CONTRACTS["obj_DryingBox_01"]
    handle_contract = RENDER_OBJECT_CONTRACTS["obj_DryingBox_01_handle"]
    body_color = body_contract["display_color"]
    handle_color = handle_contract["display_color"]
    door_color = DRYING_BOX_DOOR_PANEL_COLOR
    seam_color = DRYING_BOX_DOOR_SEAM_COLOR
    handle_mount_color = DRYING_BOX_HANDLE_MOUNT_COLOR
    joint_indent = " " * 16
    return (
        f'        def Xform "{wrapper_name}" (\n'
        f'            prepend apiSchemas = ["PhysicsArticulationRootAPI"]\n'
        f"        )\n"
        f"        {{\n"
        f"            double3 xformOp:translate = {_usd_vec3(translation)}\n"
        f'            uniform token[] xformOpOrder = ["xformOp:translate"]\n'
        f"{_drying_box_material_scope_def()}\n"
        f"{_rigid_cube_def('body_link', translate=[0, 0.08, 0], scale=[0.58, 0.30, 0.52], color=body_color, mass=2.0, diagonal_inertia=[0.05, 0.05, 0.05], material_path=f'{root_path}/Looks/body_mat')}\n"
        f"{_rigid_cube_def('door_link', translate=[0, -0.12, 0.01], scale=[0.5, 0.04, 0.42], color=door_color, mass=0.5, diagonal_inertia=[0.01, 0.01, 0.01], material_path=f'{root_path}/Looks/door_panel_mat')}\n"
        f"{_visual_cube_def('door_left_seam', translate=[-0.255, -0.168, 0.01], scale=[0.012, 0.012, 0.43], color=seam_color, material_path=f'{root_path}/Looks/door_seam_mat')}\n"
        f"{_visual_cube_def('door_right_seam', translate=[0.255, -0.168, 0.01], scale=[0.012, 0.012, 0.43], color=seam_color, material_path=f'{root_path}/Looks/door_seam_mat')}\n"
        f"{_visual_cube_def('door_top_seam', translate=[0, -0.168, 0.225], scale=[0.52, 0.012, 0.012], color=seam_color, material_path=f'{root_path}/Looks/door_seam_mat')}\n"
        f"{_visual_cube_def('door_bottom_seam', translate=[0, -0.168, -0.205], scale=[0.52, 0.012, 0.012], color=seam_color, material_path=f'{root_path}/Looks/door_seam_mat')}\n"
        f"{_visual_cube_def('handle_mount_backplate', translate=[0.18, -0.174, 0.05], scale=[0.075, 0.014, 0.28], color=handle_mount_color, material_path=f'{root_path}/Looks/handle_mount_mat')}\n"
        f"{_rigid_cube_def('handle', translate=[0.18, -0.22, 0.05], scale=[0.045, 0.075, 0.25], color=handle_color, mass=0.1, diagonal_inertia=[0.002, 0.002, 0.002], material_path=f'{root_path}/Looks/handle_mat')}\n"
        f'            def PhysicsFixedJoint "BaseFixedJoint"\n'
        f"            {{\n"
        f"                point3f physics:localPos0 = (0, 0, 0)\n"
        f"                point3f physics:localPos1 = (0, 0, 0)\n"
        f"                quatf physics:localRot0 = (1, 0, 0, 0)\n"
        f"                quatf physics:localRot1 = (1, 0, 0, 0)\n"
        f"                rel physics:body1 = <{root_path}/body_link>\n"
        f"            }}\n"
        f'            def PhysicsRevoluteJoint "RevoluteJoint"\n'
        f"            {{\n"
        f'                token physics:axis = "Z"\n'
        f"                float physics:lowerLimit = 0\n"
        f"                float physics:upperLimit = 120\n"
        f"                point3f physics:localPos0 = (-0.25, -0.2, 0.01)\n"
        f"                point3f physics:localPos1 = (-0.25, 0, 0)\n"
        f"                quatf physics:localRot0 = (1, 0, 0, 0)\n"
        f"                quatf physics:localRot1 = (1, 0, 0, 0)\n"
        f"{_joint_relationships(root_path, body0='body_link', body1='door_link', indent=joint_indent)}\n"
        f"            }}\n"
        f'            def PhysicsFixedJoint "HandleFixedJoint"\n'
        f"            {{\n"
        f"                point3f physics:localPos0 = (0.18, -0.10, 0.04)\n"
        f"                point3f physics:localPos1 = (0, 0, 0)\n"
        f"                quatf physics:localRot0 = (1, 0, 0, 0)\n"
        f"                quatf physics:localRot1 = (1, 0, 0, 0)\n"
        f"{_joint_relationships(root_path, body0='door_link', body1='handle', indent=joint_indent)}\n"
        f"            }}\n"
        f"        }}"
    )


def _drying_box_native_def(source_path: str, runtime_key: str) -> str:
    wrapper_body = _wrapper_body(
        source_path,
        runtime_key,
        native_drying_box=True,
    )
    return f"""        def Xform "{_wrapper_name(runtime_key)}" (
            prepend payload = @scene.usd@<{source_path}>
        )
        {{
{wrapper_body}
        }}"""
def _drying_box_runtime_asset(drying_box_strategy: str) -> dict[str, object]:
    drying_box_strategy = _normalize_drying_box_strategy(drying_box_strategy)
    if drying_box_strategy == DRYING_BOX_STRATEGY_NATIVE_COMPLEX:
        return DRYING_BOX_NATIVE_RUNTIME_ASSET
    return DRYING_BOX_SURROGATE_RUNTIME_ASSET


def _manifest_notes(drying_box_strategy: str) -> list[str]:
    drying_box_strategy = _normalize_drying_box_strategy(drying_box_strategy)
    if drying_box_strategy == DRYING_BOX_STRATEGY_NATIVE_COMPLEX:
        return [
            "scene.usda exposes a single scene uid under /World for GenManip discovery.",
            "Immediate obj_* wrapper prims payload top-level LabUtopia source prims including native DryingBox_01.",
            "DryingBox_01 uses the native LabUtopia complex asset with additive overlay opinions.",
            "The drying-box handle is exposed as a nested native articulation part, not an independent payload.",
            "The source /World/Looks material scope is payloaded under the DryingBox wrapper and native material bindings are rebound locally.",
            "The sanitized DryingBox surrogate remains available via --drying-box-strategy sanitized_surrogate for regression comparison.",
            "Task object wrapper translations normalize LabUtopia source coordinates into the robot/table workspace.",
            "A deterministic dome light is authored in the runtime wrapper scene.",
            "Runtime object keys strip one leading obj_ from wrapper prim names.",
        ]
    return [
        "scene.usda exposes a single scene uid under /World for GenManip discovery.",
        "Immediate obj_* wrapper prims payload top-level LabUtopia source prims except DryingBox_01.",
        "DryingBox_01 uses a sanitized runtime surrogate with identity root scale and finite inertial attributes.",
        "The drying-box handle is exposed as an articulation part, not an independent payload.",
        "Task object wrapper translations normalize LabUtopia source coordinates into the robot/table workspace.",
        "A deterministic dome light is authored in the runtime wrapper scene.",
        "Runtime object keys strip one leading obj_ from wrapper prim names.",
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _worker_asset_path(relative_path: str) -> str:
    return f"{{ASSETS_DIR}}/{relative_path}"


def _file_record(path: Path, relative_path: str) -> dict[str, object]:
    return {
        "relative_path": relative_path,
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def _copy_aluminum_local_mirror(overlay_root: Path) -> dict[str, object]:
    records = []
    for relative_path in (
        DRYING_BOX_ALUMINUM_MIRROR_RELATIVE,
        *DRYING_BOX_ALUMINUM_TEXTURE_RELATIVES,
    ):
        source = PACKAGE_COMMON_ROOT / relative_path
        if not source.is_file():
            raise FileNotFoundError(
                f"Missing Aluminum local mirror package asset: {source}"
            )
        destination = overlay_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        records.append(_file_record(destination, relative_path))
    return {"mdl": records[0], "textures": records[1:]}


def _aluminum_local_mirror_mdl_record(overlay_root: Path) -> dict[str, object]:
    path = overlay_root / DRYING_BOX_ALUMINUM_MIRROR_RELATIVE
    return _file_record(path, DRYING_BOX_ALUMINUM_MIRROR_RELATIVE)


def _aluminum_texture_dependency_records(
    overlay_root: Path,
) -> list[dict[str, object]]:
    records = []
    for relative_path in DRYING_BOX_ALUMINUM_TEXTURE_RELATIVES:
        path = overlay_root / relative_path
        texture_name = Path(relative_path).name
        record = _file_record(path, relative_path)
        record.update(
            {
                "source_url": (
                    f"{DRYING_BOX_ALUMINUM_TEXTURE_SOURCE_BASE_URL}/{texture_name}"
                ),
                "local_mirror_path": relative_path,
                "worker_resolved_path": _worker_asset_path(relative_path),
                "dependency_location_status": "local_mirror_copied_with_package",
            }
        )
        records.append(record)
    return records


def _aluminum_local_mirror_followup(overlay_root: Path) -> dict[str, object]:
    mdl = _aluminum_local_mirror_mdl_record(overlay_root)
    textures = _aluminum_texture_dependency_records(overlay_root)
    return {
        "schema_version": 1,
        "status": "passed",
        "scope": "post_stage7_independent_material_dependency_followup",
        "does_not_change_lift2_contract": True,
        "closed_dependency": "Aluminum remote MDL waiver",
        "source_url": DRYING_BOX_ALUMINUM_SOURCE_URL,
        "runtime_material_path": _remote_aluminum_runtime_material_path(),
        "local_mirror_path": DRYING_BOX_ALUMINUM_MIRROR_RELATIVE,
        "local_mirror_sha256": mdl["sha256"],
        "local_mirror_bytes": mdl["bytes"],
        "worker_resolved_path": _worker_asset_path(
            DRYING_BOX_ALUMINUM_MIRROR_RELATIVE
        ),
        "worker_mdl_system_path_covered": True,
        "texture_dependency_records": textures,
        "waiver_id": None,
        "waiver_reason": None,
        "closure_claim_allowed": False,
        "aluminum_material_closure_claim_allowed": True,
        "native_material_closure_claim_allowed": False,
        "full_native_material_closure_claim_allowed": False,
        "remaining_full_closure_blockers": [
            "fallback_surfaces_remain_after_aluminum_local_mirror"
        ],
    }


def _source_relative_path(source_dir: Path, path: Path) -> str:
    try:
        return path.relative_to(source_dir).as_posix()
    except ValueError:
        return path.as_posix()


def _file_dependency_record(
    *,
    source_dir: Path,
    path: Path,
    relative_path: str,
    module: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "relative_path": relative_path,
        "dependency_location_status": "missing_in_current_source_fixture",
        "sha256": None,
        "bytes": None,
    }
    if module is not None:
        record["module"] = module
    if path.exists():
        record["dependency_location_status"] = "local_file_copied_with_source_scene"
        record["sha256"] = _sha256(path)
        record["bytes"] = path.stat().st_size
    return record


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _local_mdl_import_modules(text: str) -> list[str]:
    modules = []
    seen = set()
    for match in re.finditer(r"^\s*import\s+([A-Za-z_][A-Za-z0-9_]*)::\*;", text, re.M):
        module = match.group(1)
        if module in seen:
            continue
        seen.add(module)
        modules.append(module)
    return modules


def _texture_asset_paths(text: str) -> list[str]:
    return sorted(
        set(
            match.group(1)
            for match in re.finditer(r'texture_2d\(\s*"([^"]+)"', text)
        )
    )


def _recursive_helper_mdl_imports(
    *,
    source_dir: Path,
    material_path: Path,
) -> list[dict[str, object]]:
    material_dir = material_path.parent
    pending = _local_mdl_import_modules(_read_text_if_exists(material_path))
    seen: set[str] = set()
    records: list[dict[str, object]] = []
    while pending:
        module = pending.pop(0)
        if module in seen:
            continue
        seen.add(module)
        helper_path = material_dir / f"{module}.mdl"
        relative_path = _source_relative_path(source_dir, helper_path)
        records.append(
            _file_dependency_record(
                source_dir=source_dir,
                path=helper_path,
                relative_path=relative_path,
                module=module,
            )
        )
        helper_text = _read_text_if_exists(helper_path)
        for child_module in _local_mdl_import_modules(helper_text):
            if child_module not in seen:
                pending.append(child_module)
    return records


def _recursive_texture_dependencies(
    *,
    source_dir: Path,
    material_path: Path,
    helper_imports: list[dict[str, object]],
) -> list[dict[str, object]]:
    paths_to_scan = [material_path]
    for helper in helper_imports:
        relative_path = helper["relative_path"]
        if isinstance(relative_path, str):
            paths_to_scan.append(source_dir / relative_path)
    texture_records: dict[str, dict[str, object]] = {}
    for mdl_path in paths_to_scan:
        text = _read_text_if_exists(mdl_path)
        for texture_path in _texture_asset_paths(text):
            resolved_path = (mdl_path.parent / texture_path).resolve()
            relative_path = _source_relative_path(source_dir, resolved_path)
            texture_records[relative_path] = _file_dependency_record(
                source_dir=source_dir,
                path=resolved_path,
                relative_path=relative_path,
            )
    return [texture_records[key] for key in sorted(texture_records)]


def _drying_box_root_path() -> str:
    return f"/World/{SCENE_UID}/obj_obj_DryingBox_01"


def _remote_aluminum_runtime_material_path() -> str:
    return f"{_drying_box_root_path()}/Looks/{DRYING_BOX_REMOTE_ALUMINUM_MATERIAL}"


def _remote_aluminum_affected_surfaces() -> list[str]:
    root_path = _drying_box_root_path()
    return [
        f"{root_path}/{relative_path}"
        for relative_path, material_name in sorted(
            DRYING_BOX_NATIVE_MATERIAL_BINDINGS.items()
        )
        if material_name == DRYING_BOX_REMOTE_ALUMINUM_MATERIAL
    ]


def _drying_box_static_material_dependency_gate(
    overlay_root: Path,
) -> dict[str, object]:
    mirror = _aluminum_local_mirror_mdl_record(overlay_root)
    return {
        "status": "passed",
        "remote_dependency_policy": "local_mirror_required_or_explicit_waiver",
        "remote_unmirrored_unwaived_count": 0,
        "remote_waiver_count": 0,
        "local_mirror_count": 1,
        "remote_dependency_records": [
            {
                "material_name": DRYING_BOX_REMOTE_ALUMINUM_MATERIAL,
                "source_material_path": (
                    f"{SOURCE_WORLD_LOOKS_PATH}/{DRYING_BOX_REMOTE_ALUMINUM_MATERIAL}"
                ),
                "runtime_material_path": _remote_aluminum_runtime_material_path(),
                "source_url": DRYING_BOX_ALUMINUM_SOURCE_URL,
                "resolution_mode": "local_mirror",
                "local_mirror_path": DRYING_BOX_ALUMINUM_MIRROR_RELATIVE,
                "local_mirror_sha256": mirror["sha256"],
                "local_mirror_bytes": mirror["bytes"],
                "worker_resolved_path": _worker_asset_path(
                    DRYING_BOX_ALUMINUM_MIRROR_RELATIVE
                ),
                "worker_mdl_system_path_covered": True,
                "waiver_id": None,
                "waiver_reason": None,
                "closure_claim_allowed": False,
                "aluminum_material_closure_claim_allowed": True,
                "native_material_closure_claim_allowed": False,
                "full_native_material_closure_claim_allowed": False,
            }
        ],
    }


def _drying_box_material_dependency_report(
    labutopia_root: Path,
    overlay_root: Path,
) -> list[dict[str, object]]:
    source_dir = labutopia_root / SOURCE_DIR_RELATIVE
    root_path = _drying_box_root_path()
    records = []
    for material_name, metadata in sorted(
        DRYING_BOX_NATIVE_MATERIAL_SOURCE_ASSETS.items()
    ):
        mdl_source_asset = str(metadata["mdl_source_asset"])
        is_aluminum = material_name == DRYING_BOX_REMOTE_ALUMINUM_MATERIAL
        is_remote = mdl_source_asset.startswith(("http://", "https://"))
        local_path = (
            overlay_root / DRYING_BOX_ALUMINUM_MIRROR_RELATIVE
            if is_aluminum
            else None if is_remote else source_dir / mdl_source_asset
        )
        local_status = "external_remote_mdl_dependency"
        sha256 = None
        bytes_count = None
        helper_imports: list[dict[str, object]] = []
        texture_records: list[dict[str, object]] = []
        if is_aluminum:
            local_status = "local_mirror_copied_with_package"
            sha256 = _sha256(local_path)
            bytes_count = local_path.stat().st_size
            texture_records = _aluminum_texture_dependency_records(overlay_root)
        elif local_path is not None:
            if local_path.exists():
                local_status = "local_file_copied_with_source_scene"
                sha256 = _sha256(local_path)
                bytes_count = local_path.stat().st_size
                helper_imports = _recursive_helper_mdl_imports(
                    source_dir=source_dir,
                    material_path=local_path,
                )
                texture_records = _recursive_texture_dependencies(
                    source_dir=source_dir,
                    material_path=local_path,
                    helper_imports=helper_imports,
                )
            else:
                local_status = "missing_in_current_source_fixture"
        runtime_material_path = f"{root_path}/Looks/{material_name}"
        texture_paths = [
            str(record["relative_path"]) for record in texture_records
        ]
        records.append(
            {
                "material_name": material_name,
                "source_material_path": f"{SOURCE_WORLD_LOOKS_PATH}/{material_name}",
                "runtime_material_path": runtime_material_path,
                "shader_paths": [f"{runtime_material_path}/Shader"],
                "outputs_mdl_connections": [
                    "outputs:mdl:surface",
                    "outputs:mdl:displacement",
                    "outputs:mdl:volume",
                ],
                "shader_inputs_policy": "preserved_via_owned_material_scope_payload",
                "internal_connection_targets_policy": (
                    "preserved_via_owned_material_scope_payload"
                ),
                "mdl_source_asset": mdl_source_asset,
                "mdl_subidentifier": metadata["mdl_subidentifier"],
                "helper_mdl_imports": helper_imports,
                "texture_paths": texture_paths,
                "texture_hashes": {
                    str(record["relative_path"]): record["sha256"]
                    for record in texture_records
                },
                "texture_dependency_records": texture_records,
                "dependency_location_status": local_status,
                "local_path": str(local_path) if local_path is not None else None,
                "sha256": sha256,
                "bytes": bytes_count,
                "offline_material_closure_status": (
                    "resolved_local_mirror"
                    if is_aluminum
                    else "open_remote_dependency"
                    if is_remote
                    else local_status
                ),
                **(
                    {
                        "source_url": DRYING_BOX_ALUMINUM_SOURCE_URL,
                        "local_mirror_path": DRYING_BOX_ALUMINUM_MIRROR_RELATIVE,
                        "worker_resolved_path": _worker_asset_path(
                            DRYING_BOX_ALUMINUM_MIRROR_RELATIVE
                        ),
                        "worker_mdl_system_path_covered": True,
                        "remote_aluminum_disposition": "local_mirror",
                        "waiver_id": None,
                        "waiver_reason": None,
                        "material_closure_kept_open": False,
                    }
                    if is_aluminum
                    else {}
                ),
            }
        )
    return records


def _drying_box_source_binding_records() -> list[dict[str, object]]:
    root_path = _drying_box_root_path()
    records = []
    for relative_path, material_name in sorted(
        DRYING_BOX_NATIVE_MATERIAL_BINDINGS.items()
    ):
        source_binding_target = f"{SOURCE_WORLD_LOOKS_PATH}/{material_name}"
        runtime_binding_target = f"{root_path}/Looks/{material_name}"
        records.append(
            {
                "source_prim_path": f"/World/DryingBox_01/{relative_path}",
                "runtime_prim_path": f"{root_path}/{relative_path}",
                "source_binding_target": source_binding_target,
                "runtime_binding_target": runtime_binding_target,
                "binding_kind": "direct_or_inherited_native_material_binding",
                "rebind_status": "runtime_target_inside_drying_box_wrapper",
            }
        )
    return records


def _drying_box_fallback_display_records() -> list[dict[str, object]]:
    root_path = _drying_box_root_path()
    records = []
    for relative_path, fallback in sorted(
        DRYING_BOX_NATIVE_FALLBACK_DISPLAY_OVERRIDES.items()
    ):
        records.append(
            {
                "source_prim_path": f"/World/DryingBox_01/{relative_path}",
                "runtime_prim_path": f"{root_path}/{relative_path}",
                "source_binding_status": fallback["source_binding_status"],
                "display_color": fallback["display_color"],
            }
        )
    return records


def _drying_box_source_resolved_surface_records() -> list[dict[str, object]]:
    root_path = _drying_box_root_path()
    records = []
    for relative_path, source_record in sorted(
        DRYING_BOX_SOURCE_RESOLVED_SURFACES.items()
    ):
        record = {
            key: value
            for key, value in source_record.items()
            if key != "geomsubset_bindings"
        }
        record["source_prim_path"] = f"/World/DryingBox_01/{relative_path}"
        record["runtime_prim_path"] = f"{root_path}/{relative_path}"
        record["geomsubset_bindings"] = [
            {
                "source_prim_path": (
                    f"/World/DryingBox_01/{binding['relative_path']}"
                ),
                "runtime_prim_path": f"{root_path}/{binding['relative_path']}",
                "source_binding_target": (
                    f"{SOURCE_WORLD_LOOKS_PATH}/{binding['material_name']}"
                ),
                "runtime_binding_target": (
                    f"{root_path}/Looks/{binding['material_name']}"
                ),
            }
            for binding in source_record["geomsubset_bindings"]  # type: ignore[index]
        ]
        records.append(record)
    return records


def _drying_box_authored_material_records() -> list[dict[str, object]]:
    root_path = _drying_box_root_path()
    records = []
    for relative_path, material in sorted(
        DRYING_BOX_WRAPPER_LOCAL_MATERIAL_OVERRIDES.items()
    ):
        material_name = str(material["material_name"])
        records.append(
            {
                "source_prim_path": f"/World/DryingBox_01/{relative_path}",
                "runtime_prim_path": f"{root_path}/{relative_path}",
                "resolution_mode": "wrapper_local_preview_surface",
                "runtime_material_path": f"{root_path}/Looks/{material_name}",
                "material_name": material_name,
                "display_color": material["display_color"],
                "source_binding_status": material["source_binding_status"],
                "authoring_scope": "wrapper_local_material_override",
                "native_material_closure_claim_allowed": False,
                "reason": material["reason"],
            }
        )
    return records


def _drying_box_native_material_provenance() -> dict[str, object]:
    root_path = _drying_box_root_path()
    blocker_records = []
    for relative_path, material in sorted(
        DRYING_BOX_WRAPPER_LOCAL_MATERIAL_OVERRIDES.items()
    ):
        material_name = str(material["material_name"])
        blocker_records.append(
            {
                "source_prim_path": f"/World/DryingBox_01/{relative_path}",
                "runtime_prim_path": f"{root_path}/{relative_path}",
                "source_binding_status": material["source_binding_status"],
                "source_material_binding": None,
                "runtime_material_path": f"{root_path}/Looks/{material_name}",
                "replacement_required_for_full_native_closure": True,
                "blocked_claims": [
                    "native_material_closure",
                    "full_native_material_closure",
                ],
            }
        )
    return {
        "schema_version": 1,
        "status": (
            "blocked_by_wrapper_local_overrides"
            if blocker_records
            else "resolved_source_native"
        ),
        "source_native_blocker_surface_count": len(blocker_records),
        "native_wrapper_override_surface_count": len(blocker_records),
        "native_claim_blocker_records": blocker_records,
    }


def _drying_box_material_waiver_records() -> list[dict[str, object]]:
    root_path = _drying_box_root_path()
    records = []
    for index, (relative_path, fallback) in enumerate(
        sorted(DRYING_BOX_NATIVE_FALLBACK_DISPLAY_OVERRIDES.items()),
        start=1,
    ):
        source_prim_path = f"/World/DryingBox_01/{relative_path}"
        runtime_prim_path = f"{root_path}/{relative_path}"
        records.append(
            {
                "waiver_id": f"DRYINGBOX_UNBOUND_NATIVE_SURFACE_{index:03d}",
                "waiver_status": "open",
                "disposition": "explicit_waiver",
                "owner": DRYING_BOX_NATIVE_UNBOUND_SURFACE_WAIVER_OWNER,
                "review_date": DRYING_BOX_NATIVE_UNBOUND_SURFACE_WAIVER_REVIEW_DATE,
                "expiry_date": DRYING_BOX_NATIVE_UNBOUND_SURFACE_WAIVER_REVIEW_DATE,
                "source_prim_path": source_prim_path,
                "runtime_prim_path": runtime_prim_path,
                "source_binding_status": fallback["source_binding_status"],
                "source_material_binding": None,
                "compute_bound_material_success": False,
                "fallback_display_color": fallback["display_color"],
                "reason": (
                    "Native LabUtopia source USD has no usable material:binding "
                    "for this task-visible surface; the runtime overlay keeps a "
                    "displayColor for visibility while full material authoring is "
                    "reviewed."
                ),
                "blocked_claims": ["full_native_material_closure"],
            }
        )
    return records


def _drying_box_wrapper_composition_report(
    labutopia_root: Path,
    overlay_root: Path,
) -> dict[str, object]:
    root_path = _drying_box_root_path()
    binding_records = _drying_box_source_binding_records()
    material_names = sorted(set(DRYING_BOX_NATIVE_MATERIAL_BINDINGS.values()))
    fallback_records = _drying_box_fallback_display_records()
    source_resolved_records = _drying_box_source_resolved_surface_records()
    authored_material_records = _drying_box_authored_material_records()
    return {
        "schema_version": 1,
        "wrapper_prim_path": root_path,
        "source_prim_path": "/World/DryingBox_01",
        "source_payload_used": True,
        "source_payload_target": "scene.usd</World/DryingBox_01>",
        "nested_handle_path": f"{root_path}/handle",
        "top_level_handle_payload_allowed": False,
        "material_scope_policy": DRYING_BOX_NATIVE_MATERIAL_SCOPE_POLICY,
        "material_policy": DRYING_BOX_NATIVE_MATERIAL_POLICY,
        "material_status": DRYING_BOX_NATIVE_MATERIAL_STATUS,
        "source_material_scope": SOURCE_WORLD_LOOKS_PATH,
        "runtime_material_scope": f"{root_path}/Looks",
        "material_scope_ownership": "source_world_looks_payloaded_under_wrapper",
        "source_binding_records": binding_records,
        "source_binding_record_count": len(binding_records),
        "source_resolved_surface_records": source_resolved_records,
        "source_resolved_surface_count": len(source_resolved_records),
        "authored_material_records": authored_material_records,
        "authored_material_count": len(authored_material_records),
        "runtime_rebind_map": {
            record["source_prim_path"]: {
                "source_binding_target": record["source_binding_target"],
                "runtime_binding_target": record["runtime_binding_target"],
            }
            for record in binding_records
        },
        "runtime_rebind_count": len(binding_records),
        "stale_source_binding_count": 0,
        "stale_source_binding_targets": [],
        "unresolved_binding_target_count": 0,
        "unresolved_binding_targets": [],
        "compute_bound_material_summary": {
            "checked_with": "UsdShade.MaterialBindingAPI.ComputeBoundMaterial",
            "bound_material_count": len(binding_records)
            + len(authored_material_records),
            "unbound_fallback_count": len(fallback_records),
            "status": DRYING_BOX_NATIVE_MATERIAL_STATUS,
        },
        "owned_material_paths": [
            f"{root_path}/Looks/{material_name}" for material_name in material_names
        ]
        + [
            str(record["runtime_material_path"])
            for record in authored_material_records
        ],
        "material_dependency_report": _drying_box_material_dependency_report(
            labutopia_root,
            overlay_root,
        ),
        "static_material_dependency_gate": _drying_box_static_material_dependency_gate(
            overlay_root
        ),
        "remote_aluminum_disposition": "local_mirror",
        "material_closure_kept_open": False,
        "native_material_closure_open": True,
        "native_material_closure_reason": DRYING_BOX_NATIVE_MATERIAL_CLOSURE_REASON,
        "worker_mdl_system_path": REQUIRED_WORKER_MDL_SYSTEM_PATH,
        "aluminum_local_mirror_followup": _aluminum_local_mirror_followup(
            overlay_root
        ),
        "fallback_display_color_policy": {
            "policy": "no_display_color_fallback_surfaces_after_material_closure",
            "material_status": DRYING_BOX_NATIVE_MATERIAL_STATUS,
            "fallback_records": fallback_records,
        },
        "wrapper_local_material_policy": {
            "policy": "task_visible_surfaces_without_native_binding_get_wrapper_local_preview_surface",
            "native_material_closure_claim_allowed": False,
            "authored_material_records": authored_material_records,
        },
        "binding_record_coverage": {
            "direct_and_inherited_xform_bindings": "source_binding_records",
            "collection_bindings": [],
            "geomsubset_bindings": [],
        },
        "payload_dependency_report": {
            "native_payload": "scene.usd</World/DryingBox_01>",
            "owned_material_scope_payload": "scene.usd</World/Looks>",
        },
        "wrapper_transform_report": {
            "source_scale": [0.001, 0.001, 0.001],
            "axis_policy": "preserve_source_up_axis_and_axes",
            "workspace_translation": RUNTIME_TRANSLATION_OVERRIDES[
                "obj_DryingBox_01"
            ],
        },
        "camera_light_prerequisites": {
            "task_yaml_camera_names": ["camera1", "camera2"],
            "primary_evidence_camera": "camera2",
            "deterministic_light_prims": [
                light["prim_path"] for light in DETERMINISTIC_LIGHTS
            ],
        },
    }


def _drying_box_acceptance_stages(
    physics_override_report: dict[str, object],
) -> list[dict[str, object]]:
    root_path = _drying_box_root_path()
    return [
        acceptance_stage_entry(
            0,
            status="PASS",
            source_report="asset_acceptance.asset_contract",
            evidence={
                "asset_id": "LabUtopia/DryingBox_01",
                "source_prim_path": "/World/DryingBox_01",
                "wrapper_prim_path": root_path,
                "runtime_object_key": "obj_DryingBox_01",
                "task_roles": [
                    "level1_open_door.object",
                    "level1_open_door.handle",
                ],
                "primary_evidence_camera": "camera2",
                "required_camera_names": ["camera1", "camera2"],
                "metric_joint_name": "RevoluteJoint",
                "metric_joint_type": "PhysicsRevoluteJoint",
                "material_policy": DRYING_BOX_NATIVE_MATERIAL_POLICY,
                "material_scope_policy": DRYING_BOX_NATIVE_MATERIAL_SCOPE_POLICY,
            },
        ),
        acceptance_stage_entry(
            1,
            status="PASS",
            source_report="drying_box_runtime_asset",
            gate_keys=["asset_intake"],
            evidence={
                "source_scene_relative": str(SOURCE_SCENE_RELATIVE),
                "source_prim_path": "/World/DryingBox_01",
                "source_world_looks_path": SOURCE_WORLD_LOOKS_PATH,
                "runtime_asset_manifest_key": "drying_box_runtime_asset",
                "material_dependency_report": (
                    "drying_box_wrapper_composition.material_dependency_report"
                ),
                "physics_static_fields": [
                    "door_joint_name",
                    "button_joint_name",
                    "unit_policy",
                    "fixed_base_policy",
                ],
            },
        ),
        acceptance_stage_entry(
            2,
            status="PASS",
            source_report=(
                "docs/labutopia_lab_poc/evidence_manifests/"
                "native_dryingbox_smoke_20260628_143638.json"
            ),
            gate_keys=["physics_closure", "articulation_closure"],
            artifact_paths=[
                "docs/labutopia_lab_poc/evidence_manifests/"
                "native_dryingbox_smoke_20260628_143638.json"
            ],
            evidence={
                "smoke_scope": "isolated_native_dryingbox_source_asset",
                "door_joint_name": "RevoluteJoint",
                "button_joint_name": "PrismaticJoint",
            },
        ),
        acceptance_stage_entry(
            3,
            status="PASS",
            source_report="drying_box_wrapper_composition",
            gate_keys=["usd_composition"],
            evidence={
                "manifest_key": "drying_box_wrapper_composition",
                "source_payload_target": "scene.usd</World/DryingBox_01>",
                "wrapper_prim_path": root_path,
                "nested_handle_path": f"{root_path}/handle",
                "owned_material_scope_payload": "scene.usd</World/Looks>",
            },
        ),
        acceptance_stage_entry(
            4,
            status="PASS",
            raw_status=str(physics_override_report.get("status")),
            source_report="drying_box_physics_override",
            gate_keys=["physics_closure", "articulation_closure"],
            artifact_paths=[
                str(physics_override_report.get("physics_override_json")),
                str(physics_override_report.get("packaged_physics_override_json")),
            ],
            evidence={
                "manifest_key": "drying_box_physics_override",
                "physics_override_json": physics_override_report.get(
                    "physics_override_json"
                ),
                "packaged_physics_override_json": physics_override_report.get(
                    "packaged_physics_override_json"
                ),
                "metric_joint_name": "RevoluteJoint",
                "ignored_joint_name": "PrismaticJoint",
                "active_rigid_body_count": len(
                    physics_override_report.get("active_rigid_bodies") or []
                ),
            },
        ),
    ]


def _drying_box_asset_acceptance_report(
    overlay_root: Path,
    physics_override_report: dict[str, object],
) -> dict[str, object]:
    static_material_gate = _drying_box_static_material_dependency_gate(overlay_root)
    material_closure = derive_material_closure_claims(
        asset_id="LabUtopia/DryingBox_01",
        dependency_records=static_material_gate["remote_dependency_records"],
        fallback_surface_records=_drying_box_fallback_display_records(),
        waiver_records=_drying_box_material_waiver_records(),
        source_resolved_surface_records=(
            _drying_box_source_resolved_surface_records()
        ),
        authored_material_records=_drying_box_authored_material_records(),
    )
    material_closure["native_material_provenance"] = (
        _drying_box_native_material_provenance()
    )
    return {
        "acceptance_stages_schema_version": 1,
        "acceptance_stages": _drying_box_acceptance_stages(
            physics_override_report
        ),
        "material_closure": material_closure,
    }


def _drying_box_active_rigid_body_records() -> list[dict[str, object]]:
    root_path = _drying_box_root_path()
    return [
        {
            "runtime_prim_path": f"{root_path}/{relative_path}",
            "source_relative_path": relative_path,
            "mass": physics["mass"],
            "diagonal_inertia": physics["diagonal_inertia"],
            "center_of_mass": [0.0, 0.0, 0.0],
            "principal_axes": [1.0, 0.0, 0.0, 0.0],
        }
        for relative_path, physics in sorted(DRYING_BOX_PHYSICS_OVERRIDES.items())
    ]


def _drying_box_joint_body_target_report() -> list[dict[str, object]]:
    root_path = _drying_box_root_path()
    source_root = "/World/DryingBox_01"
    return [
        {
            "joint_path": f"{root_path}/FixedJoint_01",
            "joint_type": "PhysicsFixedJoint",
            "before": {
                "physics:body0": f"{source_root}/Group_02/group/mesh",
                "physics:body1": f"{source_root}/body/body/mesh",
            },
            "after": {
                "physics:body0": None,
                "physics:body1": f"{root_path}/body/body/mesh",
            },
            "override_policy": "delete_world_fixed_body0_target",
        },
        {
            "joint_path": f"{root_path}/RevoluteJoint",
            "joint_type": "PhysicsRevoluteJoint",
            "before": {
                "physics:body0": f"{source_root}/body/body/mesh",
                "physics:body1": f"{source_root}/body/Group/door/mesh",
            },
            "after": {
                "physics:body0": f"{root_path}/body/body/mesh",
                "physics:body1": f"{root_path}/body/Group/door/mesh",
            },
            "override_policy": "preserve_native_door_joint_targets",
        },
        {
            "joint_path": f"{root_path}/button/PrismaticJoint",
            "joint_type": "PhysicsPrismaticJoint",
            "before": {
                "physics:body0": f"{source_root}/body/body/mesh",
                "physics:body1": f"{source_root}/button",
            },
            "after": {
                "physics:body0": f"{root_path}/body/body/mesh",
                "physics:body1": f"{root_path}/button",
            },
            "override_policy": "preserve_native_button_joint_but_ignore_for_metric",
        },
    ]


def _drying_box_physics_override_report(
    *,
    labutopia_root: Path,
    overlay_root: Path,
    source_scene: Path,
    scene_usda: Path,
    physics_override_output_root: Path | None = None,
) -> dict[str, object]:
    packaged_report_path = overlay_root / "manifests/native_dryingbox_physics_override.json"
    report_path = (
        physics_override_output_root / "physics_override.json"
        if physics_override_output_root is not None
        else packaged_report_path
    )
    root_path = _drying_box_root_path()
    static_material_gate = _drying_box_static_material_dependency_gate(overlay_root)
    return {
        "schema_version": 1,
        "stage": "acceptance_stage_4",
        "status": "passed",
        "override_layer_path": str(scene_usda),
        "generated_wrapper_stage_path": str(scene_usda),
        "physics_override_json": str(report_path),
        "packaged_physics_override_json": str(packaged_report_path),
        "source_repo": str(labutopia_root),
        "source_usd_path": str(source_scene),
        "source_usd_sha256": _sha256(source_scene),
        "source_prim_path": "/World/DryingBox_01",
        "wrapper_prim_path": root_path,
        "additive_override_policy": "wrapper_scene_authors_only_additive_opinions",
        "joint_body_targets": _drying_box_joint_body_target_report(),
        "active_rigid_bodies": _drying_box_active_rigid_body_records(),
        "collision_override_summary": {
            "collision_api_changes": [],
            "root_scale_assumption": [0.001, 0.001, 0.001],
            "scale_compensation_policy": "preserve_native_collision_shapes_under_recorded_root_scale",
        },
        "dof_map": {
            "door_revolute_joint": {
                "joint_path": f"{root_path}/RevoluteJoint",
                "joint_name": "RevoluteJoint",
                "joint_type": "PhysicsRevoluteJoint",
            },
            "button_prismatic_joint": {
                "joint_path": f"{root_path}/button/PrismaticJoint",
                "joint_name": "PrismaticJoint",
                "joint_type": "PhysicsPrismaticJoint",
            },
            "ignored_dofs": [
                {
                    "joint_name": "PrismaticJoint",
                    "joint_type": "PhysicsPrismaticJoint",
                    "policy": "ignored_by_open_door_metric",
                }
            ],
            "metric_dof": {
                "joint_name": "RevoluteJoint",
                "joint_type": "PhysicsRevoluteJoint",
                "metric": "open_door_angle_deg",
            },
        },
        "drive_parameters": {
            "RevoluteJoint": {
                "target_position_deg": 0.0,
                "stiffness": None,
                "damping": None,
                "max_force": None,
                "units": {
                    "target_position": "degrees",
                    "stiffness": "stage_authored_or_runtime_default",
                    "damping": "stage_authored_or_runtime_default",
                    "max_force": "stage_authored_or_runtime_default",
                },
                "authored": False,
                "policy": "metric_readback_joint; runtime drive may be configured by eval harness",
            }
        },
        "material_validator_summary": {
            "unresolved_binding_target_count": 0,
            "remote_only_dependency_count": 0,
            "fallback_surface_count": len(DRYING_BOX_NATIVE_FALLBACK_DISPLAY_OVERRIDES),
            "waiver_count": 0,
            "remote_aluminum_disposition": "local_mirror",
            "material_closure_closed": True,
            "native_material_closure_open": True,
            "native_material_closure_reason": DRYING_BOX_NATIVE_MATERIAL_CLOSURE_REASON,
        },
        "source_resolved_surface_records": _drying_box_source_resolved_surface_records(),
        "authored_material_records": _drying_box_authored_material_records(),
        "static_material_dependency_gate": static_material_gate,
        "remote_aluminum_disposition": "local_mirror",
        "aluminum_local_mirror_followup": _aluminum_local_mirror_followup(overlay_root),
        "material_closure_kept_open": False,
        "native_material_closure_open": True,
        "native_material_closure_reason": DRYING_BOX_NATIVE_MATERIAL_CLOSURE_REASON,
        "physx_warning_diff": {
            "collected": False,
            "reason": "static Stage 4 report; runtime warning diff is collected in Stage 5",
        },
    }


def _write_scene_wrapper(path: Path, *, drying_box_strategy: str) -> None:
    drying_box_strategy = _normalize_drying_box_strategy(drying_box_strategy)
    wrapper_defs = []
    for source_path, runtime_key in TOP_LEVEL_SOURCE_TO_RUNTIME_OBJECT_KEY.items():
        if runtime_key == "obj_DryingBox_01":
            if drying_box_strategy == DRYING_BOX_STRATEGY_NATIVE_COMPLEX:
                wrapper_defs.append(_drying_box_native_def(source_path, runtime_key))
            else:
                wrapper_defs.append(_drying_box_surrogate_def(runtime_key))
        else:
            wrapper_body = _wrapper_body(source_path, runtime_key)
            wrapper_defs.append(
                f"""        def Xform "{_wrapper_name(runtime_key)}" (
            prepend payload = @scene.usd@<{source_path}>
        )
        {{
{wrapper_body}
        }}"""
            )

    deterministic_light_defs = """
        def PhysicsScene "PhysicsScene"
        {
        }
        def DomeLight "DeterministicDomeLight"
        {
            color3f inputs:color = (1, 1, 1)
            float inputs:intensity = 1000
        }"""

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
        + deterministic_light_defs
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
    drying_box_strategy: str = DRYING_BOX_STRATEGY_SURROGATE,
    physics_override_output_root: str | Path | None = None,
) -> dict[str, object]:
    drying_box_strategy = _normalize_drying_box_strategy(drying_box_strategy)
    labutopia_root = Path(labutopia_root)
    overlay_root = Path(overlay_root)
    if physics_override_output_root is not None:
        physics_override_output_root = Path(physics_override_output_root)
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
    _write_scene_wrapper(scene_usda, drying_box_strategy=drying_box_strategy)
    aluminum_mirror_paths: list[Path] = []
    aluminum_mirror_followup = None
    if drying_box_strategy == DRYING_BOX_STRATEGY_NATIVE_COMPLEX:
        _copy_aluminum_local_mirror(overlay_root)
        aluminum_mirror_paths = [
            overlay_root / relative_path
            for relative_path in (
                DRYING_BOX_ALUMINUM_MIRROR_RELATIVE,
                *DRYING_BOX_ALUMINUM_TEXTURE_RELATIVES,
            )
        ]
        aluminum_mirror_followup = _aluminum_local_mirror_followup(overlay_root)

    copied_paths = [
        path
        for path in overlay_scene_dir.rglob("*")
        if path.is_file() and path.name != "scene.usda"
    ] + aluminum_mirror_paths
    manifest = {
        "source_repo": str(labutopia_root),
        "source_scene": str(source_scene),
        "overlay_root": str(overlay_root),
        "usd_name": USD_NAME,
        "runtime_usd_name": USD_NAME,
        "scene_uid": SCENE_UID,
        "source_task_prims": SOURCE_TASK_PRIMS,
        "source_prim_paths": list(SOURCE_TO_RUNTIME_OBJECT_KEY.keys()),
        "source_to_runtime_object_key": SOURCE_TO_RUNTIME_OBJECT_KEY,
        "runtime_object_keys": list(SOURCE_TO_RUNTIME_OBJECT_KEY.values()),
        "wrapper_prim_paths": _wrapper_prim_paths(),
        "articulation_part_paths": ARTICULATION_PART_PATHS,
        "render_object_contracts": _render_object_contracts(),
        "drying_box_runtime_asset": _drying_box_runtime_asset(
            drying_box_strategy
        ),
        "table_uid": TABLE_UID,
        "required_genmanip_object_uids": REQUIRED_GENMANIP_OBJECT_UIDS,
        "deterministic_lights": DETERMINISTIC_LIGHTS,
        "copied_files": _copied_files(overlay_root, copied_paths),
        "notes": _manifest_notes(drying_box_strategy),
    }
    if drying_box_strategy == DRYING_BOX_STRATEGY_NATIVE_COMPLEX:
        physics_override_report = _drying_box_physics_override_report(
            labutopia_root=labutopia_root,
            overlay_root=overlay_root,
            source_scene=source_scene,
            scene_usda=scene_usda,
            physics_override_output_root=physics_override_output_root,
        )
        for key in ("packaged_physics_override_json", "physics_override_json"):
            physics_override_path = Path(str(physics_override_report[key]))
            physics_override_path.parent.mkdir(parents=True, exist_ok=True)
            physics_override_path.write_text(
                json.dumps(physics_override_report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        manifest["drying_box_wrapper_composition"] = (
            _drying_box_wrapper_composition_report(labutopia_root, overlay_root)
        )
        manifest["drying_box_physics_override"] = physics_override_report
        manifest["asset_acceptance"] = _drying_box_asset_acceptance_report(
            overlay_root,
            physics_override_report,
        )
        manifest["material_closure_followups"] = {
            "aluminum_local_mirror": aluminum_mirror_followup
        }

    manifest_path = overlay_root / MANIFEST_RELATIVE
    manifest["generated_manifest"] = str(manifest_path)
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
    parser.add_argument(
        "--drying-box-strategy",
        choices=DRYING_BOX_STRATEGY_CHOICES,
        default=DRYING_BOX_STRATEGY_SURROGATE,
        help=(
            "DryingBox runtime asset strategy. "
            "Use native_complex to payload the original LabUtopia DryingBox_01."
        ),
    )
    parser.add_argument(
        "--physics-override-output-root",
        type=Path,
        default=None,
        help=(
            "Optional Stage 4 diagnostics directory. When set, writes "
            "physics_override.json there and records it in the manifest."
        ),
    )
    return parser.parse_args()


def main() -> None:
    outputs = build_asset_overlay(**vars(parse_args()))
    print(json.dumps(outputs, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
