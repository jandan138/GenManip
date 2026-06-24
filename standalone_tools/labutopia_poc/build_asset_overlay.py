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
    "unit_policy": "override_root_scale_to_identity",
    "fixed_base_policy": "world_fixed_joint_body0_removed",
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


def _render_override_tree(
    name: str,
    node: dict[str, object],
    *,
    indent_level: int,
) -> str:
    indent = " " * indent_level
    attr_indent = " " * (indent_level + 4)
    mass = node.get("mass")
    if mass is None:
        header = f'{indent}over "{name}"'
    else:
        header = (
            f'{indent}over "{name}" (\n'
            f'{indent}    prepend apiSchemas = ["PhysicsMassAPI"]\n'
            f"{indent})"
        )
    body_lines: list[str] = []
    display_color = node.get("display_color")
    if display_color is not None:
        body_lines.append(_display_color_attr(display_color, attr_indent))  # type: ignore[arg-type]
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
        f"            double3 xformOp:scale = (1, 1, 1)\n"
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
    override_tree: dict[str, dict[str, object]] = {}
    contract = RENDER_OBJECT_CONTRACTS.get(runtime_key)
    if contract is not None:
        display_color = contract["display_color"]
        for override_path in contract["display_override_paths"]:
            _add_display_override(override_tree, override_path, display_color)
    if runtime_key == "obj_DryingBox_01":
        handle_contract = RENDER_OBJECT_CONTRACTS["obj_DryingBox_01_handle"]
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
) -> dict[str, object]:
    drying_box_strategy = _normalize_drying_box_strategy(drying_box_strategy)
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
    _write_scene_wrapper(scene_usda, drying_box_strategy=drying_box_strategy)

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
    parser.add_argument(
        "--drying-box-strategy",
        choices=DRYING_BOX_STRATEGY_CHOICES,
        default=DRYING_BOX_STRATEGY_SURROGATE,
        help=(
            "DryingBox runtime asset strategy. "
            "Use native_complex to payload the original LabUtopia DryingBox_01."
        ),
    )
    return parser.parse_args()


def main() -> None:
    outputs = build_asset_overlay(**vars(parse_args()))
    print(json.dumps(outputs, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
