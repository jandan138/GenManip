import copy
import json
import math
import subprocess
import sys
import types

import pytest
import yaml

from standalone_tools.labutopia_poc import validate_task_package


EXPECTED_TOP_INDEX = [
    "ebench/labutopia_lab_poc/franka_poc/franka_poc.json",
    "ebench/labutopia_lab_poc/lift2_candidate/lift2_candidate.json",
]
EXPECTED_TASKS = ["level1_pick", "level1_place", "level1_open_door"]
EXPECTED_RENDER_OBJECTS = {
    "level1_pick": ["obj_conical_bottle02"],
    "level1_place": ["obj_beaker2", "obj_target_plat"],
    "level1_open_door": ["obj_DryingBox_01", "obj_DryingBox_01_handle"],
}
EXPECTED_TASK_CAMERA_CONFIGS = {
    "level1_pick": "configs/cameras/labutopia_franka_poc_pick.yml",
    "level1_place": "configs/cameras/labutopia_franka_poc_place.yml",
    "level1_open_door": "configs/cameras/labutopia_franka_poc_open_door.yml",
}
CAMERA_CLEANUP_FLAGS = {
    "with_bbox2d",
    "with_bbox3d",
    "with_motion_vector",
    "with_semantic",
    "with_distance",
}
BASE_FRANKA_CAMERAS = {
    "camera1": {
        "position": [2.0, 0.0, 2.0],
        "orientation": [0.61237, 0.35355, 0.35355, 0.61237],
        "camera_axes": "usd",
        **{flag: False for flag in CAMERA_CLEANUP_FLAGS},
    },
    "camera2": {
        "position": [0.45, -1.1, 1.55],
        "orientation": [0.87184, 0.4898, 0.0, 0.0],
        "camera_axes": "usd",
        **{flag: False for flag in CAMERA_CLEANUP_FLAGS},
    },
}
BASE_LIFT2_CAMERAS = {
    "camera1": {
        "position": [0.0, 0.0, 0.0],
        "orientation": [1.0, 0.0, 0.0, 0.0],
        **{flag: False for flag in CAMERA_CLEANUP_FLAGS},
    },
    "left_camera": {
        "exists": True,
        "prim_path": "/lift2/lift2/lift2/fl/link6/Camera",
        "camera_axes": "usd",
        "resolution": [640, 480],
        **{flag: False for flag in CAMERA_CLEANUP_FLAGS},
    },
    "right_camera": {
        "exists": True,
        "prim_path": "/lift2/lift2/lift2/fr/link6/Camera",
        "camera_axes": "usd",
        "resolution": [640, 480],
        **{flag: False for flag in CAMERA_CLEANUP_FLAGS},
    },
    "top_camera": {
        "exists": True,
        "prim_path": "/lift2/lift2/lift2/h_link6/Camera",
        "camera_axes": "usd",
        "resolution": [1280, 720],
        **{flag: False for flag in CAMERA_CLEANUP_FLAGS},
    },
    "overlook_camera": {
        "exists": True,
        "prim_path": "/lift2/lift2/lift2/base_link/Camera_overlook",
        "camera_axes": "usd",
        "resolution": [1280, 720],
        **{flag: False for flag in CAMERA_CLEANUP_FLAGS},
    }
}


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_yaml(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def _write_minimal_native_drying_box_scene(
    path,
    *,
    include_button_joint=True,
    include_physics_scene=True,
    duplicate_physics_scene=False,
    include_collision_api=True,
    door_diagonal_inertia=(0.01, 0.01, 0.01),
):
    root_path = "/World/labutopia_level1_poc/obj_obj_DryingBox_01"
    physics_scene = (
        """
        def PhysicsScene "PhysicsScene"
        {
        }"""
        if include_physics_scene
        else ""
    )
    duplicate_scene = (
        """
        def PhysicsScene "PhysicsSceneExtra"
        {
        }"""
        if duplicate_physics_scene
        else ""
    )
    rigid_schemas = (
        '"PhysicsRigidBodyAPI", "PhysicsCollisionAPI", "PhysicsMassAPI"'
        if include_collision_api
        else '"PhysicsRigidBodyAPI", "PhysicsMassAPI"'
    )
    button_joint = (
        f"""
                    def PhysicsPrismaticJoint "PrismaticJoint"
                    {{
                        rel physics:body0 = <{root_path}/body/body/mesh>
                        rel physics:body1 = <{root_path}/button>
                    }}"""
        if include_button_joint
        else ""
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""#usda 1.0
def Xform "World"
{{
    def Xform "labutopia_level1_poc"
    {{
{physics_scene}
{duplicate_scene}
        def Xform "obj_obj_DryingBox_01" (
            prepend apiSchemas = ["PhysicsArticulationRootAPI"]
        )
        {{
            double3 xformOp:scale = (1, 1, 1)
            def Xform "body"
            {{
                def Xform "body"
                {{
                    def Mesh "mesh" (
                        prepend apiSchemas = [{rigid_schemas}]
                    )
                    {{
                        float physics:mass = 2
                        point3f physics:diagonalInertia = (0.05, 0.05, 0.05)
                        point3f physics:centerOfMass = (0, 0, 0)
                        quatf physics:principalAxes = (1, 0, 0, 0)
                    }}
                }}
                def Xform "Group"
                {{
                    def Xform "door"
                    {{
                        def Mesh "mesh" (
                            prepend apiSchemas = [{rigid_schemas}]
                        )
                        {{
                            float physics:mass = 0.5
                            point3f physics:diagonalInertia = {tuple(door_diagonal_inertia)}
                            point3f physics:centerOfMass = (0, 0, 0)
                            quatf physics:principalAxes = (1, 0, 0, 0)
                        }}
                    }}
                }}
            }}
            def Xform "handle"
            {{
                def Mesh "mesh" (
                    prepend apiSchemas = [{rigid_schemas}]
                )
                {{
                    float physics:mass = 0.1
                    point3f physics:diagonalInertia = (0.002, 0.002, 0.002)
                    point3f physics:centerOfMass = (0, 0, 0)
                    quatf physics:principalAxes = (1, 0, 0, 0)
                }}
            }}
            def Mesh "button" (
                prepend apiSchemas = [{rigid_schemas}]
            )
            {{
                float physics:mass = 0.05
                point3f physics:diagonalInertia = (0.001, 0.001, 0.001)
                point3f physics:centerOfMass = (0, 0, 0)
                quatf physics:principalAxes = (1, 0, 0, 0)
{button_joint}
            }}
            def PhysicsFixedJoint "FixedJoint_01"
            {{
                rel physics:body1 = <{root_path}/body/body/mesh>
            }}
            def PhysicsRevoluteJoint "RevoluteJoint"
            {{
                rel physics:body0 = <{root_path}/body/body/mesh>
                rel physics:body1 = <{root_path}/body/Group/door/mesh>
                float state:angular:physics:position = 0
            }}
        }}
    }}
}}
""",
        encoding="utf-8",
    )


def _write_stage3_wrapper_scene(
    path,
    *,
    material_binding_target="/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/mdl_0007",
):
    root_path = "/World/labutopia_level1_poc/obj_obj_DryingBox_01"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""#usda 1.0
def Xform "World"
{{
    def Xform "labutopia_level1_poc"
    {{
        def PhysicsScene "PhysicsScene"
        {{
        }}
        def Xform "obj_obj_DryingBox_01" (
            prepend payload = @scene.usd@</World/DryingBox_01>
        )
        {{
            double3 xformOp:translate = (0.75, 0.1, 0.78)
            double3 xformOp:scale = (0.001, 0.001, 0.001)
            def Scope "Looks" (
                prepend payload = @scene.usd@</World/Looks>
            )
            {{
                over "Aluminum_Anodized_Charcoal"
                {{
                    over "Shader"
                    {{
                        uniform token info:implementationSource = "sourceAsset"
                        asset info:mdl:sourceAsset = @Aluminum_Anodized_Charcoal.mdl@
                        token info:mdl:sourceAsset:subIdentifier = "Aluminum_Anodized_Charcoal"
                    }}
                }}
            }}
            over "FixedJoint_01"
            {{
                delete rel physics:body0 = <{root_path}/Group_02/group/mesh>
            }}
            over "RevoluteJoint"
            {{
                float state:angular:physics:position = 0
            }}
            over "handle"
            {{
                over "mesh" (
                    prepend apiSchemas = ["MaterialBindingAPI", "PhysicsMassAPI"]
                )
                {{
                    rel material:binding = <{material_binding_target}>
                    float physics:mass = 0.1
                    point3f physics:diagonalInertia = (0.002, 0.002, 0.002)
                    point3f physics:centerOfMass = (0, 0, 0)
                    quatf physics:principalAxes = (1, 0, 0, 0)
                }}
            }}
            over "button"
            {{
                color3f[] primvars:displayColor = [(1, 0.48, 0.04)]
                uniform token primvars:displayColor:interpolation = "constant"
            }}
        }}
        def DomeLight "DeterministicDomeLight"
        {{
            float inputs:intensity = 1000
        }}
    }}
}}
""",
        encoding="utf-8",
    )


def _write_generated_manifest_from_common(manifest):
    generated = {
        "usd_name": manifest["runtime_usd_name"],
        "scene_uid": manifest["scene_uid"],
        "runtime_object_keys": manifest["runtime_object_keys"],
        "wrapper_prim_paths": manifest["wrapper_prim_paths"],
        "source_to_runtime_object_key": manifest["source_to_runtime_object_key"],
        "deterministic_lights": manifest["deterministic_lights"],
        "articulation_part_paths": manifest["articulation_part_paths"],
        "render_object_contracts": manifest["render_object_contracts"],
        "drying_box_runtime_asset": manifest["drying_box_runtime_asset"],
    }
    if "drying_box_wrapper_composition" in manifest:
        generated["drying_box_wrapper_composition"] = manifest[
            "drying_box_wrapper_composition"
        ]
    if "drying_box_physics_override" in manifest:
        generated["drying_box_physics_override"] = manifest[
            "drying_box_physics_override"
        ]
    if "asset_acceptance" in manifest:
        generated["asset_acceptance"] = manifest["asset_acceptance"]
    _write_json(validate_task_package.Path(manifest["generated_manifest"]), generated)


def _write_task_files(task_root):
    for profile in ("franka_poc", "lift2_candidate"):
        profile_root = task_root / "ebench/labutopia_lab_poc" / profile
        profile_root.mkdir(parents=True, exist_ok=True)
        for task_name in EXPECTED_TASKS:
            (profile_root / f"{task_name}.yml").write_text("{}", encoding="utf-8")


def _write_valid_indexes(task_root):
    package_root = task_root / "ebench/labutopia_lab_poc"
    _write_json(package_root / "labutopia_lab_poc.json", EXPECTED_TOP_INDEX)
    for profile in ("franka_poc", "lift2_candidate"):
        _write_json(
            package_root / profile / f"{profile}.json",
            [
                f"ebench/labutopia_lab_poc/{profile}/{task}.yml"
                for task in EXPECTED_TASKS
            ],
        )


def _write_camera_config_fixture(tmp_root, franka_cameras):
    _write_yaml(tmp_root / "configs/cameras/labutopia_franka_poc.yml", franka_cameras)
    _write_yaml(
        tmp_root / "configs/cameras/fixed_camera_lift2_simbox.yml",
        BASE_LIFT2_CAMERAS,
    )
    for (
        task_name,
        config_path,
    ) in validate_task_package.EXPECTED_FRANKA_TASK_CAMERA_CONFIGS.items():
        task_cameras = {
            camera_name: dict(camera)
            for camera_name, camera in BASE_FRANKA_CAMERAS.items()
        }
        task_cameras["camera2"].update(
            validate_task_package.EXPECTED_FRANKA_TASK_CAMERA2_CONTRACTS[task_name]
        )
        task_cameras["camera2"]["task_view"] = task_name
        _write_yaml(tmp_root / config_path, task_cameras)


def test_indexed_task_yaml_paths_rejects_duplicate_profile_entries(tmp_path, monkeypatch):
    task_root = tmp_path / "tasks"
    _write_task_files(task_root)
    _write_valid_indexes(task_root)
    package_root = task_root / "ebench/labutopia_lab_poc"
    _write_json(
        package_root / "franka_poc/franka_poc.json",
        [
            "ebench/labutopia_lab_poc/franka_poc/level1_pick.yml",
            "ebench/labutopia_lab_poc/franka_poc/level1_pick.yml",
            "ebench/labutopia_lab_poc/franka_poc/level1_place.yml",
        ],
    )
    monkeypatch.setattr(validate_task_package, "TASK_ROOT", task_root)
    monkeypatch.setattr(validate_task_package, "PACKAGE_ROOT", package_root)

    with pytest.raises(AssertionError, match="franka_poc.json"):
        validate_task_package._indexed_task_yaml_paths()


def test_metrics_manager_lazy_registration_does_not_keep_metrics_package_imported():
    sys.modules["genmanip.extensions.metrics"] = types.ModuleType(
        "genmanip.extensions.metrics"
    )
    try:
        validate_task_package._validate_metrics_manager_lazy_registration()
        assert "genmanip.extensions.metrics" not in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "genmanip.extensions.metrics" or module_name.startswith(
                "genmanip.extensions.metrics."
            ):
                del sys.modules[module_name]


def test_validate_task_package_cli_reports_success():
    result = subprocess.run(
        [sys.executable, "standalone_tools/labutopia_poc/validate_task_package.py"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "LabUtopia task package validation OK" in result.stdout


def test_assets_manifest_rejects_missing_overlay_runtime_scene(tmp_path, monkeypatch):
    package_root = tmp_path / "tasks/ebench/labutopia_lab_poc"
    common_root = package_root / "common"
    common_root.mkdir(parents=True)
    overlay_root = tmp_path / "overlay/assets"
    generated_manifest = tmp_path / "generated_manifest.json"
    generated_manifest.write_text(
        json.dumps(
            {
                "usd_name": validate_task_package.RUNTIME_USD_NAME,
                "scene_uid": validate_task_package.SCENE_UID,
                "runtime_object_keys": [],
                "wrapper_prim_paths": validate_task_package.EXPECTED_WRAPPER_PRIM_PATHS,
                "source_to_runtime_object_key": {},
            }
        ),
        encoding="utf-8",
    )
    _write_json(
        common_root / "assets_manifest.json",
        {
            "overlay_root": str(overlay_root),
            "runtime_usd_name": validate_task_package.RUNTIME_USD_NAME,
            "generated_manifest": str(generated_manifest),
            "scene_uid": validate_task_package.SCENE_UID,
            "runtime_object_keys": [],
            "wrapper_prim_paths": validate_task_package.EXPECTED_WRAPPER_PRIM_PATHS,
            "source_to_runtime_object_key": {},
        },
    )
    monkeypatch.setattr(validate_task_package, "PACKAGE_ROOT", package_root)

    with pytest.raises(FileNotFoundError, match="runtime scene"):
        validate_task_package._validate_assets_manifest()


def test_assets_manifest_rejects_missing_native_drying_box_payload(
    tmp_path,
    monkeypatch,
):
    package_root = tmp_path / "tasks/ebench/labutopia_lab_poc"
    common_root = package_root / "common"
    common_root.mkdir(parents=True)
    overlay_root = tmp_path / "overlay/assets"
    runtime_scene = overlay_root / f"{validate_task_package.RUNTIME_USD_NAME}.usda"
    runtime_scene.parent.mkdir(parents=True)
    runtime_scene.write_text(
        """
#usda 1.0
def Xform "World"
{
    def Xform "labutopia_level1_poc"
    {
        def Xform "obj_obj_DryingBox_01" (
            prepend payload = @scene.usd@</World/not_the_native_drying_box>
        )
        {
        }
        def DomeLight "DeterministicDomeLight"
        {
            float inputs:intensity = 1000
        }
    }
}
""",
        encoding="utf-8",
    )
    real_manifest = validate_task_package._load_json(
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = copy.deepcopy(real_manifest)
    manifest["overlay_root"] = str(overlay_root)
    manifest["generated_manifest"] = str(tmp_path / "generated_manifest.json")
    generated = {
        "usd_name": manifest["runtime_usd_name"],
        "scene_uid": manifest["scene_uid"],
        "runtime_object_keys": manifest["runtime_object_keys"],
        "wrapper_prim_paths": manifest["wrapper_prim_paths"],
        "source_to_runtime_object_key": manifest["source_to_runtime_object_key"],
        "deterministic_lights": manifest["deterministic_lights"],
        "articulation_part_paths": manifest["articulation_part_paths"],
        "render_object_contracts": manifest["render_object_contracts"],
        "drying_box_runtime_asset": manifest["drying_box_runtime_asset"],
    }
    _write_json(validate_task_package.Path(manifest["generated_manifest"]), generated)
    _write_json(common_root / "assets_manifest.json", manifest)
    monkeypatch.setattr(validate_task_package, "PACKAGE_ROOT", package_root)

    with pytest.raises(AssertionError, match="native DryingBox_01 payload"):
        validate_task_package._validate_assets_manifest()


def test_assets_manifest_rejects_missing_stage3_wrapper_composition_report(
    tmp_path,
    monkeypatch,
):
    package_root = tmp_path / "tasks/ebench/labutopia_lab_poc"
    common_root = package_root / "common"
    common_root.mkdir(parents=True)
    overlay_root = tmp_path / "overlay/assets"
    runtime_scene = overlay_root / f"{validate_task_package.RUNTIME_USD_NAME}.usda"
    _write_stage3_wrapper_scene(runtime_scene)
    real_manifest = validate_task_package._load_json(
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = copy.deepcopy(real_manifest)
    manifest["overlay_root"] = str(overlay_root)
    manifest["generated_manifest"] = str(tmp_path / "generated_manifest.json")
    manifest.pop("drying_box_wrapper_composition", None)
    _write_generated_manifest_from_common(manifest)
    _write_json(common_root / "assets_manifest.json", manifest)
    monkeypatch.setattr(validate_task_package, "PACKAGE_ROOT", package_root)

    with pytest.raises(AssertionError, match="drying_box_wrapper_composition"):
        validate_task_package._validate_assets_manifest()


def test_assets_manifest_rejects_stale_world_looks_material_binding(
    tmp_path,
    monkeypatch,
):
    package_root = tmp_path / "tasks/ebench/labutopia_lab_poc"
    common_root = package_root / "common"
    common_root.mkdir(parents=True)
    overlay_root = tmp_path / "overlay/assets"
    runtime_scene = overlay_root / f"{validate_task_package.RUNTIME_USD_NAME}.usda"
    _write_stage3_wrapper_scene(runtime_scene, material_binding_target="/World/Looks/mdl_0007")
    real_manifest = validate_task_package._load_json(
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = copy.deepcopy(real_manifest)
    manifest["overlay_root"] = str(overlay_root)
    manifest["generated_manifest"] = str(tmp_path / "generated_manifest.json")
    _write_generated_manifest_from_common(manifest)
    _write_json(common_root / "assets_manifest.json", manifest)
    monkeypatch.setattr(validate_task_package, "PACKAGE_ROOT", package_root)

    with pytest.raises(AssertionError, match="stale /World/Looks material binding"):
        validate_task_package._validate_assets_manifest()


def test_assets_manifest_rejects_missing_asset_acceptance(
    tmp_path,
    monkeypatch,
):
    package_root = tmp_path / "tasks/ebench/labutopia_lab_poc"
    common_root = package_root / "common"
    common_root.mkdir(parents=True)
    real_manifest = validate_task_package._load_json(
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = copy.deepcopy(real_manifest)
    manifest["generated_manifest"] = str(tmp_path / "generated_manifest.json")
    manifest.pop("asset_acceptance", None)
    _write_generated_manifest_from_common(manifest)
    _write_json(common_root / "assets_manifest.json", manifest)
    monkeypatch.setattr(validate_task_package, "PACKAGE_ROOT", package_root)

    with pytest.raises(AssertionError, match="missing asset_acceptance"):
        validate_task_package._validate_assets_manifest()


def test_assets_manifest_rejects_full_material_closure_overclaim(
    tmp_path,
    monkeypatch,
):
    package_root = tmp_path / "tasks/ebench/labutopia_lab_poc"
    common_root = package_root / "common"
    common_root.mkdir(parents=True)
    real_manifest = validate_task_package._load_json(
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = copy.deepcopy(real_manifest)
    manifest["generated_manifest"] = str(tmp_path / "generated_manifest.json")
    material = manifest["asset_acceptance"]["material_closure"]
    material["closure_claim_allowed"] = True
    material["native_material_closure_claim_allowed"] = True
    material["full_native_material_closure_claim_allowed"] = True
    _write_generated_manifest_from_common(manifest)
    _write_json(common_root / "assets_manifest.json", manifest)
    monkeypatch.setattr(validate_task_package, "PACKAGE_ROOT", package_root)

    with pytest.raises(AssertionError, match="full material closure overclaim"):
        validate_task_package._validate_assets_manifest()


def test_asset_acceptance_material_closure_rejects_malformed_waiver_record():
    manifest = copy.deepcopy(
        validate_task_package._load_json(
            validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
        )
    )
    material = manifest["asset_acceptance"]["material_closure"]
    material["waiver_records"][0] = "not-a-record"

    with pytest.raises(AssertionError, match="explicit material waivers"):
        validate_task_package._validate_asset_acceptance_material_closure(
            validate_task_package.Path("assets_manifest.json"),
            manifest,
        )


def test_labutopia_tasks_define_runtime_articulation_contract():
    for path in validate_task_package._indexed_task_yaml_paths():
        data = validate_task_package._load_yaml(path)
        cfg = data["evaluation_configs"][0]

        assert "articulation" in cfg["generation_config"], str(path)


def test_labutopia_assets_manifest_declares_p1_render_object_contracts():
    manifest_path = (
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = validate_task_package._load_json(manifest_path)

    contracts = manifest["render_object_contracts"]
    for uid in {
        uid
        for required in EXPECTED_RENDER_OBJECTS.values()
        for uid in required
    }:
        contract = contracts[uid]
        assert contract["wrapper_prim_path"] == manifest["wrapper_prim_paths"][uid]
        assert contract["display_color"] != [0.5, 0.5, 0.5]
        assert contract["expected_world_bbox_lwh_m"]["min"]
        assert contract["expected_world_bbox_lwh_m"]["max"]

    assert manifest["wrapper_prim_paths"]["obj_DryingBox_01_handle"] == (
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle"
    )
    assert manifest["articulation_part_paths"] == {
        "obj_DryingBox_01_handle": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle"
    }
    assert (
        manifest["drying_box_runtime_asset"]
        == validate_task_package.EXPECTED_DRYING_BOX_RUNTIME_ASSET
    )
    report = manifest["drying_box_wrapper_composition"]
    assert report["schema_version"] == 1
    assert report["material_scope_policy"] == "preserve_owned_world_looks"
    assert (
        report["material_policy"]
        == "owned_world_looks_payload_with_wrapper_local_rebind"
    )
    assert report["material_status"] == "mixed_native_and_fallback"
    assert report["source_binding_record_count"] == 32
    assert report["runtime_rebind_count"] == 32
    assert report["stale_source_binding_count"] == 0
    assert report["unresolved_binding_target_count"] == 0
    assert set(report["owned_material_paths"]) == (
        validate_task_package.EXPECTED_DRYING_BOX_MATERIAL_PATHS
    )
    material_dependencies = {
        item["material_name"]: item
        for item in report["material_dependency_report"]
    }
    assert material_dependencies["mdl_0007"]["helper_mdl_imports"]
    assert material_dependencies["mdl_0008"]["helper_mdl_imports"]
    assert material_dependencies["mdl_0009"]["helper_mdl_imports"]
    assert material_dependencies["mdl_0008"]["texture_paths"] == [
        "SubUSDs/textures/image4.jpg"
    ]
    assert material_dependencies["mdl_0009"]["texture_paths"] == [
        "SubUSDs/textures/image1.JPG"
    ]
    assert material_dependencies["mdl_0008"]["texture_hashes"][
        "SubUSDs/textures/image4.jpg"
    ]
    assert material_dependencies["mdl_0009"]["texture_hashes"][
        "SubUSDs/textures/image1.JPG"
    ]
    aluminum = material_dependencies["Aluminum_Anodized_Charcoal"]
    assert aluminum["dependency_location_status"] == "local_mirror_copied_with_package"
    assert aluminum["offline_material_closure_status"] == "resolved_local_mirror"
    assert aluminum["remote_aluminum_disposition"] == "local_mirror"
    assert aluminum["material_closure_kept_open"] is False
    assert aluminum["local_mirror_path"] == (
        "miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl"
    )
    assert aluminum["sha256"] == (
        "640855d3890c6faaae6346a850ef9f366d4b397c0f4313e25c7ac0b9230c106a"
    )
    assert aluminum["texture_hashes"][
        "miscs/mdl/labutopia/mdl/Aluminum_Anodized/Aluminum_Anodized_Normal.png"
    ] == "6dc1cb1b23a9abd766188a85ccbad1a2639d0a9a334f284e359c6c5d4438608e"

    runtime_scene = (
        validate_task_package.Path(manifest["overlay_root"])
        / f"{manifest['runtime_usd_name']}.usda"
    )
    scene_text = runtime_scene.read_text(encoding="utf-8")
    assert 'def Xform "obj_obj_DryingBox_01_handle" (' not in scene_text
    assert "prepend payload = @scene.usd@</World/DryingBox_01>" in scene_text
    assert "double3 xformOp:scale = (0.001, 0.001, 0.001)" in scene_text
    assert "delete rel physics:body0" in scene_text
    assert "prepend payload = @scene.usd@</World/Looks>" in scene_text
    assert "rel material:binding = </World/Looks/" not in scene_text
    assert "primvars:displayColor" in scene_text
    assert 'def Cube "body_link"' not in scene_text
    assert 'def Cube "door_link"' not in scene_text
    assert 'def Cube "handle"' not in scene_text


def test_assets_manifest_declares_stage4_physics_override_and_material_gate():
    manifest_path = (
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = validate_task_package._load_json(manifest_path)

    runtime_asset = manifest["drying_box_runtime_asset"]
    assert runtime_asset["remote_aluminum_disposition"] == "local_mirror"
    assert runtime_asset["material_closure_kept_open"] is True
    assert runtime_asset["native_material_closure_reason"] == (
        "fallback_surfaces_remain_after_aluminum_local_mirror"
    )

    wrapper_gate = manifest["drying_box_wrapper_composition"][
        "static_material_dependency_gate"
    ]
    report = manifest["drying_box_physics_override"]
    assert report["stage"] == "acceptance_stage_4"
    assert report["status"] == "passed"
    assert report["generated_wrapper_stage_path"] == report["override_layer_path"]
    assert report["remote_aluminum_disposition"] == "local_mirror"
    assert report["material_closure_kept_open"] is True
    assert report["native_material_closure_reason"] == (
        "fallback_surfaces_remain_after_aluminum_local_mirror"
    )
    assert report["static_material_dependency_gate"] == wrapper_gate

    report_path = validate_task_package.Path(report["physics_override_json"])
    assert report_path.exists()
    assert "saved/diagnostics/native_dryingbox_physics_override_" in report_path.as_posix()
    assert report_path.name == "physics_override.json"
    assert validate_task_package.Path(report["packaged_physics_override_json"]).exists()
    saved_report = validate_task_package._load_json(report_path)
    assert saved_report == report

    gate = report["static_material_dependency_gate"]
    assert gate["status"] == "passed"
    assert gate["remote_dependency_policy"] == (
        "local_mirror_required_or_explicit_waiver"
    )
    assert gate["remote_unmirrored_unwaived_count"] == 0
    assert gate["remote_waiver_count"] == 0
    assert gate["local_mirror_count"] == 1
    aluminum_records = gate["remote_dependency_records"]
    assert len(aluminum_records) == 1
    assert aluminum_records[0]["material_name"] == "Aluminum_Anodized_Charcoal"
    assert aluminum_records[0]["resolution_mode"] == "local_mirror"
    assert aluminum_records[0]["local_mirror_path"] == (
        "miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl"
    )
    assert aluminum_records[0]["local_mirror_sha256"] == (
        "640855d3890c6faaae6346a850ef9f366d4b397c0f4313e25c7ac0b9230c106a"
    )
    assert aluminum_records[0]["waiver_id"] is None
    assert aluminum_records[0]["closure_claim_allowed"] is False
    assert aluminum_records[0]["aluminum_material_closure_claim_allowed"] is True
    assert aluminum_records[0]["native_material_closure_claim_allowed"] is False
    assert aluminum_records[0]["full_native_material_closure_claim_allowed"] is False
    assert report["material_validator_summary"][
        "remote_aluminum_disposition"
    ] == "local_mirror"
    assert report["material_validator_summary"][
        "native_material_closure_open"
    ] is True
    assert report["material_validator_summary"][
        "native_material_closure_reason"
    ] == "fallback_surfaces_remain_after_aluminum_local_mirror"
    assert report["dof_map"]["metric_dof"]["joint_name"] == "RevoluteJoint"
    assert report["dof_map"]["ignored_dofs"][0]["joint_name"] == "PrismaticJoint"


def test_stage4_validator_rejects_wrong_joint_body_target_evidence(tmp_path):
    manifest = copy.deepcopy(
        validate_task_package._load_json(
            validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
        )
    )
    report = manifest["drying_box_physics_override"]
    report["joint_body_targets"][1]["after"]["physics:body1"] = (
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/button"
    )
    report_path = tmp_path / "physics_override.json"
    packaged_path = tmp_path / "packaged_physics_override.json"
    report["physics_override_json"] = str(report_path)
    report["packaged_physics_override_json"] = str(packaged_path)
    _write_json(report_path, report)
    _write_json(packaged_path, report)
    runtime_scene = (
        validate_task_package.Path(manifest["overlay_root"])
        / f"{manifest['runtime_usd_name']}.usda"
    )

    with pytest.raises(AssertionError, match="joint_body_targets"):
        validate_task_package._validate_drying_box_physics_override_report(
            tmp_path / "assets_manifest.json",
            manifest,
            runtime_scene,
        )


def test_static_material_dependency_gate_accepts_local_mirror_disposition(tmp_path):
    gate = {
        "status": "passed",
        "remote_dependency_policy": "local_mirror_required_or_explicit_waiver",
        "remote_unmirrored_unwaived_count": 0,
        "remote_waiver_count": 0,
        "local_mirror_count": 1,
        "remote_dependency_records": [
            {
                "material_name": "Aluminum_Anodized_Charcoal",
                "source_material_path": "/World/Looks/Aluminum_Anodized_Charcoal",
                "runtime_material_path": (
                    "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/"
                    "Aluminum_Anodized_Charcoal"
                ),
                "source_url": (
                    "https://omniverse-content-production.s3.us-west-2.amazonaws.com/"
                    "Materials/Base/Metals/Aluminum_Anodized_Charcoal.mdl"
                ),
                "resolution_mode": "local_mirror",
                "local_mirror_path": (
                    "miscs/mdl/labutopia/mdl/Aluminum_Anodized_Charcoal.mdl"
                ),
                "local_mirror_sha256": "a" * 64,
                "local_mirror_bytes": 12345,
                "worker_resolved_path": (
                    "{ASSETS_DIR}/miscs/mdl/labutopia/mdl/"
                    "Aluminum_Anodized_Charcoal.mdl"
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

    validate_task_package._validate_drying_box_static_material_dependency_gate(
        tmp_path / "assets_manifest.json",
        gate,
        "resolved_native_material",
    )


def test_franka_tasks_define_render_validation_contract():
    for task_name, required_objects in EXPECTED_RENDER_OBJECTS.items():
        path = (
            validate_task_package.PACKAGE_ROOT
            / "franka_poc"
            / f"{task_name}.yml"
        )
        cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]
        validation = cfg["labutopia_render_validation"]
        camera_config_path = cfg["domain_randomization"]["cameras"]["config_path"]
        camera_path = validate_task_package.ROOT / camera_config_path
        cameras = validate_task_package._load_yaml(camera_path)

        assert validation["schema_version"] == 1
        assert validation["primary_camera"] == "camera2"
        assert validation["required_visible_objects"] == required_objects
        assert validation["evidence_policy"] == {"direct_render": False}
        assert set(validation["required_camera_names"]).issubset(cameras)
        assert {
            "black_frame",
            "low_texture",
            "required_object_missing",
            "severe_clipping",
        }.issubset(set(validation["reject_frame_if"]))


def test_franka_tasks_use_task_specific_evidence_camera_configs():
    seen_configs = set()
    for task_name, expected_config in EXPECTED_TASK_CAMERA_CONFIGS.items():
        path = (
            validate_task_package.PACKAGE_ROOT
            / "franka_poc"
            / f"{task_name}.yml"
        )
        cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]
        camera_config_path = cfg["domain_randomization"]["cameras"]["config_path"]
        validation = cfg["labutopia_render_validation"]

        assert camera_config_path == expected_config
        seen_configs.add(camera_config_path)
        assert validation["primary_camera"] == "camera2"
        assert validation["evidence_camera_config"] == expected_config

        cameras = validate_task_package._load_yaml(
            validate_task_package.ROOT / camera_config_path
        )
        assert cameras["camera2"]["camera_axes"] == "usd"
        assert cameras["camera2"]["resolution"] == [512, 512]
        assert cameras["camera2"]["task_view"] == task_name

    assert len(seen_configs) == len(EXPECTED_TASK_CAMERA_CONFIGS)


def test_open_door_evidence_camera_is_close_to_handle_for_visual_qa():
    camera_path = (
        validate_task_package.ROOT
        / "configs/cameras/labutopia_franka_poc_open_door.yml"
    )
    cameras = validate_task_package._load_yaml(camera_path)
    camera2 = cameras["camera2"]

    position = camera2["position"]
    handle_anchor = [0.455607, 0.248763, 1.108592]

    distance_to_handle = math.dist(position, handle_anchor)

    assert 0.98 <= distance_to_handle <= 1.10
    assert 0.58 <= position[0] <= 0.66
    assert 1.15 <= position[1] <= 1.35
    assert 1.30 <= position[2] <= 1.40
    assert camera2["orientation"] == [0.87184, -0.4898, 0.0, 0.0]
    assert 3.8 <= camera2["focal_length"] <= 4.2
    assert 9.0 <= camera2["horizontal_aperture"] <= 11.0


def test_franka_render_validation_declares_object_pixel_readability_thresholds():
    expected_minimums = {
        "level1_pick": {
            "obj_conical_bottle02": {"min_width_px": 36, "min_height_px": 48},
        },
        "level1_place": {
            "obj_beaker2": {"min_width_px": 34, "min_height_px": 34},
            "obj_target_plat": {"min_width_px": 42, "min_height_px": 24},
        },
        "level1_open_door": {
            "obj_DryingBox_01": {"min_width_px": 160, "min_height_px": 150},
            "obj_DryingBox_01_handle": {
                "min_width_px": 18,
                "min_height_px": 64,
            },
        },
    }

    for task_name, object_thresholds in expected_minimums.items():
        path = (
            validate_task_package.PACKAGE_ROOT
            / "franka_poc"
            / f"{task_name}.yml"
        )
        cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]
        thresholds = cfg["labutopia_render_validation"]["object_pixel_thresholds"]

        for uid, minimums in object_thresholds.items():
            actual = thresholds[uid]
            assert actual["min_width_px"] >= minimums["min_width_px"]
            assert actual["min_height_px"] >= minimums["min_height_px"]
            assert actual["min_bbox_area_fraction"] > 0.0


def test_franka_tasks_hide_non_task_objects_for_evidence_readability():
    expected_hidden = {
        "level1_pick": [
            "obj_beaker2",
            "obj_target_plat",
            "obj_DryingBox_01",
        ],
        "level1_place": ["obj_conical_bottle02", "obj_DryingBox_01"],
        "level1_open_door": [
            "obj_conical_bottle02",
            "obj_beaker2",
            "obj_target_plat",
        ],
    }

    for task_name, hidden_uids in expected_hidden.items():
        path = (
            validate_task_package.PACKAGE_ROOT
            / "franka_poc"
            / f"{task_name}.yml"
        )
        cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]
        active_rules = [
            item
            for item in cfg["preprocess_config"]
            if item.get("type") == "set_object_active"
        ]

        assert active_rules == [
            {"type": "set_object_active", "config": {"active": False, "uids": hidden_uids}}
        ]
        assert cfg["labutopia_render_validation"]["hidden_non_task_objects"] == hidden_uids


def test_open_door_uses_nested_handle_articulation_part_contract():
    path = (
        validate_task_package.PACKAGE_ROOT
        / "franka_poc"
        / "level1_open_door.yml"
    )
    cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]

    drying_box = cfg["object_config"]["obj_DryingBox_01"]
    assert drying_box["type"] == "existed_object"
    assert drying_box["uid_list"] == ["obj_DryingBox_01"]
    assert drying_box["is_articulated"] is True
    assert drying_box["articulation_info"]["is_articulated"] is True
    assert drying_box["articulation_info"]["part"]["handle"] == "/handle"

    metric = cfg["generation_config"]["goal"][0][0][0]
    assert metric["type"] == "manip/default/check_joint_angle"
    assert metric["articulation_obj_uid"] == "obj_DryingBox_01"
    assert metric["joint_name"] == "RevoluteJoint"


def test_open_door_records_native_button_joint_metric_policy():
    path = (
        validate_task_package.PACKAGE_ROOT
        / "franka_poc"
        / "level1_open_door.yml"
    )
    cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]

    policy = cfg["labutopia_native_drying_box"]
    assert policy == {
        "strategy": "native_complex_with_additive_physics_override",
        "door_joint_name": "RevoluteJoint",
        "handle_part_path": "/handle",
        "button_joint_name": "PrismaticJoint",
        "button_prismatic_joint_policy": "ignored_by_open_door_metric",
    }


def test_open_door_initializes_drying_box_closed_for_eval_start():
    for profile in ("franka_poc", "lift2_candidate"):
        path = validate_task_package.PACKAGE_ROOT / profile / "level1_open_door.yml"
        cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]
        drying_box = cfg["object_config"]["obj_DryingBox_01"]

        assert drying_box["target_positions"] == [0.0], str(path)


def test_lift2_candidate_tasks_declare_stage7_contract_boundary():
    expected_observation_keys = [
        "instruction",
        "state.joints",
        "state.gripper",
        "state.base",
        "state.ee_pose",
        "video.overlook_camera_view",
        "video.left_camera_view",
        "video.right_camera_view",
        "timestep",
        "reset",
        "robot_id",
    ]
    expected_action_contract = {
        "required_fields": [
            "action",
            "base_motion",
            "control_type",
            "is_rel",
            "base_is_rel",
        ],
        "action_shape": [16],
        "base_motion_shape": [3],
        "control_type": "joint_position",
    }

    for task_name in EXPECTED_TASKS:
        path = validate_task_package.PACKAGE_ROOT / "lift2_candidate" / f"{task_name}.yml"
        cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]
        contract = cfg["labutopia_lift2_contract"]

        assert contract["schema_version"] == 1
        assert contract["baseline_robot"] == "manip/lift2/R5a"
        assert contract["required_observation_keys"] == expected_observation_keys
        assert contract["baseline_camera_input_keys"] == [
            "video.overlook_camera_view",
            "video.left_camera_view",
            "video.right_camera_view",
        ]
        assert contract["camera_config_to_observation_key"] == {
            "overlook_camera": "video.overlook_camera_view",
            "left_camera": "video.left_camera_view",
            "right_camera": "video.right_camera_view",
        }
        assert contract["action_contract"] == expected_action_contract
        assert contract["reward_success_source"] == "genmanip_ebench_metric_output"
        assert contract["material_boundary"] == "stage7_consumes_stage5_6_material_status_only"


def test_lift2_contract_validator_rejects_action_contract_drift():
    path = (
        validate_task_package.PACKAGE_ROOT
        / "lift2_candidate"
        / "level1_open_door.yml"
    )
    cfg = validate_task_package._load_yaml(path)["evaluation_configs"][0]
    cfg["labutopia_lift2_contract"]["action_contract"]["required_fields"].remove(
        "base_is_rel"
    )

    with pytest.raises(AssertionError, match="action_contract"):
        validate_task_package._validate_lift2_baseline_contract(cfg, path)


def test_lift2_camera_config_declares_baseline_input_views():
    path = validate_task_package.ROOT / "configs/cameras/fixed_camera_lift2_simbox.yml"
    cameras = validate_task_package._load_yaml(path)

    for camera_name, obs_key in {
        "overlook_camera": "video.overlook_camera_view",
        "left_camera": "video.left_camera_view",
        "right_camera": "video.right_camera_view",
    }.items():
        camera = cameras[camera_name]
        assert camera["exists"] is True
        assert camera["camera_axes"] == "usd"
        assert camera["prim_path"].startswith("/lift2/lift2/lift2/")
        assert camera["resolution"]
        assert validate_task_package.LIFT2_CAMERA_CONFIG_TO_OBSERVATION_KEY[
            camera_name
        ] == obs_key


def test_drying_box_articulation_physics_is_sanitized_for_runtime():
    manifest_path = (
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = validate_task_package._load_json(manifest_path)
    runtime_scene = (
        validate_task_package.Path(manifest["overlay_root"])
        / f"{manifest['runtime_usd_name']}.usda"
    )

    report = validate_task_package._inspect_drying_box_articulation_physics(
        runtime_scene
    )

    assert report["root_path"] == manifest["wrapper_prim_paths"]["obj_DryingBox_01"]
    assert report["root_has_articulation_api"] is True
    assert report["zero_mass_links"] == []
    assert report["missing_mass_links"] == []
    assert report["zero_inertia_links"] == []
    assert report["missing_inertia_links"] == []
    assert report["sanitized_for_physx"] is True


def test_drying_box_material_bindings_resolve_inside_wrapper():
    manifest_path = (
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = validate_task_package._load_json(manifest_path)
    runtime_scene = (
        validate_task_package.Path(manifest["overlay_root"])
        / f"{manifest['runtime_usd_name']}.usda"
    )

    report = validate_task_package._inspect_drying_box_wrapper_materials(
        runtime_scene,
        manifest["drying_box_wrapper_composition"],
    )

    assert report["stage_opened"] is True
    assert report["bound_material_count"] == 32
    assert report["unresolved_binding_target_count"] == 0
    assert report["stale_source_binding_paths"] == []
    assert report["expected_mismatch_paths"] == []
    assert report["authored_world_looks_binding_paths"] == []
    assert report["unexpected_unbound_mesh_paths"] == []
    assert report["unbound_fallback_paths"] == sorted(
        validate_task_package.EXPECTED_DRYING_BOX_FALLBACK_PATHS
    )
    assert report["invalid_fallback_display_color_paths"] == []
    assert report["material_status"] == "mixed_native_and_fallback"


def test_drying_box_material_readback_reports_runtime_rebind_map_drift():
    manifest_path = (
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = validate_task_package._load_json(manifest_path)
    runtime_scene = (
        validate_task_package.Path(manifest["overlay_root"])
        / f"{manifest['runtime_usd_name']}.usda"
    )
    wrapper_report = copy.deepcopy(manifest["drying_box_wrapper_composition"])
    record = wrapper_report["source_binding_records"][0]
    wrapper_report["runtime_rebind_map"][record["source_prim_path"]][
        "runtime_binding_target"
    ] = f"{wrapper_report['runtime_material_scope']}/mdl_0008"

    report = validate_task_package._inspect_drying_box_wrapper_materials(
        runtime_scene,
        wrapper_report,
    )

    assert report["runtime_rebind_map_mismatch_paths"] == [
        {
            "source_prim_path": record["source_prim_path"],
            "runtime_prim_path": record["runtime_prim_path"],
            "expected": f"{wrapper_report['runtime_material_scope']}/mdl_0008",
            "actual": record["runtime_binding_target"],
        }
    ]


def test_drying_box_material_readback_does_not_whitelist_fallback_descendants(
    tmp_path,
):
    root_path = "/World/labutopia_level1_poc/obj_obj_DryingBox_01"
    runtime_scene = tmp_path / "scene.usda"
    runtime_scene.write_text(
        f"""#usda 1.0
def Xform "World"
{{
    def Xform "labutopia_level1_poc"
    {{
        def Xform "obj_obj_DryingBox_01"
        {{
            def Xform "panel"
            {{
                color3f[] primvars:displayColor = [(0.88, 0.92, 0.96)]
                uniform token primvars:displayColor:interpolation = "constant"
                def Mesh "mesh"
                {{
                }}
            }}
        }}
    }}
}}
""",
        encoding="utf-8",
    )

    report = validate_task_package._inspect_drying_box_wrapper_materials(
        runtime_scene,
        {
            "wrapper_prim_path": root_path,
            "source_binding_records": [],
            "fallback_display_color_policy": {
                "fallback_records": [
                    {
                        "runtime_prim_path": f"{root_path}/panel",
                        "display_color": [0.88, 0.92, 0.96],
                    }
                ]
            },
            "runtime_rebind_map": {},
        },
    )

    assert report["unexpected_unbound_mesh_paths"] == [f"{root_path}/panel/mesh"]


def test_drying_box_material_readback_reports_unresolved_authored_bindings(
    tmp_path,
):
    root_path = "/World/labutopia_level1_poc/obj_obj_DryingBox_01"
    runtime_scene = tmp_path / "scene.usda"
    runtime_scene.write_text(
        f"""#usda 1.0
def Xform "World"
{{
    def Xform "labutopia_level1_poc"
    {{
        def Xform "obj_obj_DryingBox_01"
        {{
            def Mesh "extra_mesh" (
                prepend apiSchemas = ["MaterialBindingAPI"]
            )
            {{
                rel material:binding = <{root_path}/Looks/Missing>
            }}
        }}
    }}
}}
""",
        encoding="utf-8",
    )

    report = validate_task_package._inspect_drying_box_wrapper_materials(
        runtime_scene,
        {
            "wrapper_prim_path": root_path,
            "source_binding_records": [],
            "fallback_display_color_policy": {"fallback_records": []},
            "runtime_rebind_map": {},
        },
    )

    assert report["unresolved_authored_binding_paths"] == [
        {
            "prim_path": f"{root_path}/extra_mesh",
            "relationship": "material:binding",
            "targets": [f"{root_path}/Looks/Missing"],
        }
    ]


def test_validate_task_package_rejects_material_binding_target_mismatch(
    tmp_path,
    monkeypatch,
):
    package_root = tmp_path / "tasks/ebench/labutopia_lab_poc"
    common_root = package_root / "common"
    common_root.mkdir(parents=True)
    _write_json(
        common_root / "assets_manifest.json",
        {
            "overlay_root": str(tmp_path / "overlay/assets"),
            "runtime_usd_name": validate_task_package.RUNTIME_USD_NAME,
            "drying_box_wrapper_composition": {"schema_version": 1},
        },
    )
    monkeypatch.setattr(validate_task_package, "PACKAGE_ROOT", package_root)
    monkeypatch.setattr(validate_task_package, "_validate_assets_manifest", lambda: None)
    monkeypatch.setattr(
        validate_task_package,
        "_inspect_drying_box_articulation_physics",
        lambda _runtime_scene: {
            "sanitized_for_physx": True,
            "runtime_topology_ready": True,
        },
    )
    monkeypatch.setattr(
        validate_task_package,
        "_inspect_drying_box_wrapper_materials",
        lambda _runtime_scene, _wrapper_report: {
            "bound_material_count": validate_task_package.EXPECTED_DRYING_BOX_MATERIAL_BINDING_COUNT,
            "unresolved_binding_target_count": 0,
            "stale_source_binding_paths": [],
            "expected_mismatch_paths": [
                {
                    "runtime_prim_path": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle/mesh",
                    "expected": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/mdl_0007",
                    "actual": "/World/labutopia_level1_poc/obj_obj_DryingBox_01/Looks/mdl_0008",
                }
            ],
            "missing_fallback_display_color_paths": [],
            "unbound_fallback_paths": sorted(
                validate_task_package.EXPECTED_DRYING_BOX_FALLBACK_PATHS
            ),
            "material_status": "mixed_native_and_fallback",
        },
    )
    monkeypatch.setattr(validate_task_package, "_validate_task_semantics", lambda: None)
    monkeypatch.setattr(validate_task_package, "_validate_camera_configs", lambda: None)
    monkeypatch.setattr(validate_task_package, "_indexed_task_yaml_paths", lambda: [])
    monkeypatch.setattr(
        validate_task_package,
        "_validate_metrics_manager_lazy_registration",
        lambda: None,
    )

    with pytest.raises(AssertionError, match="material binding targets mismatch"):
        validate_task_package.validate_task_package()


def test_drying_box_topology_requires_native_button_prismatic_joint(tmp_path):
    runtime_scene = tmp_path / "scene.usda"
    _write_minimal_native_drying_box_scene(
        runtime_scene,
        include_button_joint=False,
    )

    report = validate_task_package._inspect_drying_box_articulation_physics(
        runtime_scene
    )

    assert report["ignored_prismatic_joint_paths"] == []
    assert report["runtime_topology_ready"] is False


def test_drying_box_physics_rejects_nonpositive_inertia_component(tmp_path):
    runtime_scene = tmp_path / "scene.usda"
    _write_minimal_native_drying_box_scene(
        runtime_scene,
        door_diagonal_inertia=(0.01, 0.0, 0.01),
    )

    report = validate_task_package._inspect_drying_box_articulation_physics(
        runtime_scene
    )

    assert (
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/body/Group/door/mesh"
        in report["zero_inertia_links"]
    )
    assert report["sanitized_for_physx"] is False


def test_drying_box_topology_requires_exactly_one_physics_scene(tmp_path):
    runtime_scene = tmp_path / "scene.usda"
    _write_minimal_native_drying_box_scene(
        runtime_scene,
        include_physics_scene=False,
    )

    report = validate_task_package._inspect_drying_box_articulation_physics(
        runtime_scene
    )

    assert report["physics_scene_paths"] == []
    assert report["physics_scene_ready"] is False
    assert report["runtime_topology_ready"] is False

    _write_minimal_native_drying_box_scene(
        runtime_scene,
        duplicate_physics_scene=True,
    )

    report = validate_task_package._inspect_drying_box_articulation_physics(
        runtime_scene
    )

    assert len(report["physics_scene_paths"]) == 2
    assert report["physics_scene_ready"] is False
    assert report["runtime_topology_ready"] is False


def test_drying_box_topology_requires_collision_api_on_rigid_bodies(tmp_path):
    runtime_scene = tmp_path / "scene.usda"
    _write_minimal_native_drying_box_scene(
        runtime_scene,
        include_collision_api=False,
    )

    report = validate_task_package._inspect_drying_box_articulation_physics(
        runtime_scene
    )

    assert sorted(report["missing_collision_api_links"]) == [
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/body/Group/door/mesh",
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/body/body/mesh",
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/button",
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/handle/mesh",
    ]
    assert report["collision_shapes_ready"] is False
    assert report["runtime_topology_ready"] is False


def test_drying_box_articulation_topology_is_ready_for_runtime():
    manifest_path = (
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = validate_task_package._load_json(manifest_path)
    runtime_scene = (
        validate_task_package.Path(manifest["overlay_root"])
        / f"{manifest['runtime_usd_name']}.usda"
    )

    report = validate_task_package._inspect_drying_box_articulation_physics(
        runtime_scene
    )

    assert report["root_scale"] == [0.001, 0.001, 0.001]
    assert report["native_handle_path_exists"] is True
    assert report["root_unit_scale_ready"] is True
    assert report["task_visible_workspace_ready"] is True
    assert report["duplicate_rigid_link_names"] == {}
    assert report["invalid_center_of_mass_links"] == []
    assert report["invalid_principal_axes_links"] == []
    assert report["invalid_joint_body_targets"] == []
    assert report["world_fixed_base_joint_paths"] == [
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/FixedJoint_01"
    ]
    assert report["door_revolute_joint_paths"] == [
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/RevoluteJoint"
    ]
    assert report["door_reset_positions"] == {"RevoluteJoint": 0.0}
    assert report["ignored_prismatic_joint_paths"] == [
        "/World/labutopia_level1_poc/obj_obj_DryingBox_01/button/PrismaticJoint"
    ]
    assert report["unexpected_joint_types"] == []
    assert report["runtime_topology_ready"] is True


def test_native_drying_box_units_keep_task_parts_in_workspace():
    manifest_path = (
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = validate_task_package._load_json(manifest_path)
    runtime_scene = (
        validate_task_package.Path(manifest["overlay_root"])
        / f"{manifest['runtime_usd_name']}.usda"
    )

    report = validate_task_package._inspect_drying_box_articulation_physics(
        runtime_scene
    )

    assert report["task_part_world_positions"]["handle"] == pytest.approx(
        [0.455607, 0.248763, 1.108592],
        abs=1e-3,
    )
    assert report["task_part_world_positions"]["door"] == pytest.approx(
        [0.536732, 0.022285, 1.110061],
        abs=1e-3,
    )
    assert report["task_visible_workspace_ready"] is True


def test_labutopia_camera_configs_define_cleanup_flags():
    for expectation in validate_task_package.PROFILE_EXPECTATIONS.values():
        camera_path = validate_task_package.ROOT / expectation["camera_config"]
        cameras = validate_task_package._load_yaml(camera_path)
        for camera_name, camera in cameras.items():
            missing = CAMERA_CLEANUP_FLAGS - set(camera)
            assert not missing, f"{camera_path}:{camera_name} missing {missing}"


def test_labutopia_franka_camera_config_declares_axes_and_task_view():
    camera_path = validate_task_package.ROOT / "configs/cameras/labutopia_franka_poc.yml"
    cameras = validate_task_package._load_yaml(camera_path)

    for camera_name, expected_axes in (
        validate_task_package.EXPECTED_FRANKA_CAMERA_AXES.items()
    ):
        assert cameras[camera_name]["camera_axes"] == expected_axes

    assert (
        cameras["camera2"]["position"]
        == validate_task_package.EXPECTED_FRANKA_CAMERA2_POSITION
    )
    assert (
        cameras["camera2"]["orientation"]
        == validate_task_package.EXPECTED_FRANKA_CAMERA2_ORIENTATION
    )


def test_labutopia_franka_primary_camera_is_over_runtime_workspace():
    camera_path = validate_task_package.ROOT / "configs/cameras/labutopia_franka_poc.yml"
    cameras = validate_task_package._load_yaml(camera_path)

    x, y, z = cameras["camera2"]["position"]
    assert 0.0 <= x <= 1.2
    assert -1.3 <= y <= 0.8
    assert 1.2 <= z <= 2.0
    assert cameras["camera2"]["position"] != [9.6, 0.0, 2.5]
    assert cameras["camera2"]["orientation"] == [0.87184, 0.4898, 0.0, 0.0]


def test_validate_camera_configs_rejects_franka_camera_axes_regression(
    tmp_path, monkeypatch
):
    franka_cameras = {
        camera_name: dict(camera)
        for camera_name, camera in BASE_FRANKA_CAMERAS.items()
    }
    franka_cameras["camera2"]["camera_axes"] = "world"
    _write_camera_config_fixture(tmp_path, franka_cameras)
    monkeypatch.setattr(validate_task_package, "ROOT", tmp_path)

    with pytest.raises(AssertionError, match="camera2: camera_axes must remain 'usd'"):
        validate_task_package._validate_camera_configs()


def test_validate_camera_configs_rejects_franka_camera2_position_regression(
    tmp_path, monkeypatch
):
    franka_cameras = {
        camera_name: dict(camera)
        for camera_name, camera in BASE_FRANKA_CAMERAS.items()
    }
    franka_cameras["camera2"]["position"] = [0.1, 0.0, 2.5]
    _write_camera_config_fixture(tmp_path, franka_cameras)
    monkeypatch.setattr(validate_task_package, "ROOT", tmp_path)

    with pytest.raises(AssertionError, match="camera2 position must remain"):
        validate_task_package._validate_camera_configs()


def test_validate_camera_configs_rejects_franka_camera2_orientation_regression(
    tmp_path, monkeypatch
):
    franka_cameras = {
        camera_name: dict(camera)
        for camera_name, camera in BASE_FRANKA_CAMERAS.items()
    }
    franka_cameras["camera2"]["orientation"] = [0.70711, 0.0, 0.0, -0.70711]
    _write_camera_config_fixture(tmp_path, franka_cameras)
    monkeypatch.setattr(validate_task_package, "ROOT", tmp_path)

    with pytest.raises(AssertionError, match="camera2 orientation must remain"):
        validate_task_package._validate_camera_configs()


def test_validate_camera_configs_rejects_open_door_lens_regression(
    tmp_path, monkeypatch
):
    franka_cameras = {
        camera_name: dict(camera)
        for camera_name, camera in BASE_FRANKA_CAMERAS.items()
    }
    _write_camera_config_fixture(tmp_path, franka_cameras)
    open_door_camera_path = (
        tmp_path / "configs/cameras/labutopia_franka_poc_open_door.yml"
    )
    open_door_cameras = yaml.safe_load(
        open_door_camera_path.read_text(encoding="utf-8")
    )
    del open_door_cameras["camera2"]["focal_length"]
    _write_yaml(open_door_camera_path, open_door_cameras)
    monkeypatch.setattr(validate_task_package, "ROOT", tmp_path)

    with pytest.raises(AssertionError, match="camera2 focal_length must be 4.0"):
        validate_task_package._validate_camera_configs()


def test_assets_manifest_declares_deterministic_runtime_light():
    manifest_path = (
        validate_task_package.PACKAGE_ROOT / "common/assets_manifest.json"
    )
    manifest = validate_task_package._load_json(manifest_path)

    assert manifest["deterministic_lights"] == [
        {
            "prim_path": "/World/labutopia_level1_poc/DeterministicDomeLight",
            "type": "DomeLight",
            "intensity": 1000,
        }
    ]

    runtime_scene = (
        validate_task_package.Path(manifest["overlay_root"])
        / f"{manifest['runtime_usd_name']}.usda"
    )
    scene_text = runtime_scene.read_text(encoding="utf-8")
    assert 'def DomeLight "DeterministicDomeLight"' in scene_text
    assert "float inputs:intensity = 1000" in scene_text
