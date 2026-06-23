import ast
import importlib
import importlib.util
import sys
import types
from pathlib import Path


class _FakeCamera:
    def __init__(self):
        self.calls = []

    def initialize(self):
        self.calls.append(("initialize",))

    def set_focal_length(self, value):
        self.calls.append(("set_focal_length", value))

    def set_clipping_range(self, minimum, maximum):
        self.calls.append(("set_clipping_range", minimum, maximum))

    def set_vertical_aperture(self, value):
        self.calls.append(("set_vertical_aperture", value))

    def set_horizontal_aperture(self, value):
        self.calls.append(("set_horizontal_aperture", value))

    def set_local_pose(self, **kwargs):
        self.calls.append(("set_local_pose", kwargs))


def _ensure_module(name):
    module = sys.modules.setdefault(name, types.ModuleType(name))
    if "." in name:
        parent_name, child_name = name.rsplit(".", 1)
        parent = _ensure_module(parent_name)
        if not hasattr(parent, child_name):
            setattr(parent, child_name, module)
    return module


def _install_omni_camera_stubs():
    prims = _ensure_module("omni.isaac.core.prims")
    sensor = _ensure_module("omni.isaac.sensor")
    setattr(prims, "XFormPrim", object)
    setattr(sensor, "Camera", object)


def _install_camera_utils_dependency_stubs():
    importlib.import_module("genmanip.utils.standalone.camera_pose_utils")
    pc_utils = _ensure_module("genmanip.utils.standalone.pc_utils")
    transform_utils = _ensure_module("genmanip.utils.standalone.transform_utils")
    setattr(pc_utils, "get_world_corners_from_bbox3d", lambda *args, **kwargs: None)
    setattr(transform_utils, "pose_to_transform", lambda *args, **kwargs: None)


def _load_camera_utils():
    _install_omni_camera_stubs()
    _install_camera_utils_dependency_stubs()
    module_path = (
        Path(__file__).resolve().parents[2] / "genmanip/utils/usd_utils/camera_utils.py"
    )
    module_name = "_labutopia_camera_utils_under_test"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_setup_camera_genmanip_branch_applies_configured_pose_and_axes():
    camera_utils = _load_camera_utils()
    camera = _FakeCamera()

    camera_utils.setup_camera(
        camera,
        {
            "position": [9.6, 0.0, 2.5],
            "orientation": [0.70711, 0.0, 0.0, -0.70711],
            "camera_axes": "usd",
            "with_distance": False,
            "with_semantic": False,
            "with_bbox2d": False,
            "with_bbox3d": False,
            "with_motion_vector": False,
        },
        only_color_rep_for_camera=True,
    )

    local_pose_calls = [call for call in camera.calls if call[0] == "set_local_pose"]
    assert local_pose_calls == [
        (
            "set_local_pose",
            {
                "translation": [9.6, 0.0, 2.5],
                "orientation": [0.70711, 0.0, 0.0, -0.70711],
                "camera_axes": "usd",
            },
        )
    ]


def test_loader_free_camera_path_passes_full_config_to_setup_camera():
    scene_path = Path(__file__).resolve().parents[2] / "genmanip/utils/loader/scene.py"
    tree = ast.parse(scene_path.read_text(encoding="utf-8"))
    create_camera_list = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "create_camera_list"
    )

    setup_camera_calls = [
        node
        for node in ast.walk(create_camera_list)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "setup_camera"
    ]
    assert len(setup_camera_calls) == 1
    assert ast.unparse(setup_camera_calls[0].args[0]) == "camera_list[key]"
    setup_keywords = {
        keyword.arg: ast.unparse(keyword.value)
        for keyword in setup_camera_calls[0].keywords
    }
    assert setup_keywords["camera_cfg"] == "camera_data[key]"

    exists_branch = next(
        node
        for node in ast.walk(create_camera_list)
        if isinstance(node, ast.If) and ast.unparse(node.test) == "camera_data[key]['exists']"
    )
    free_camera_call = next(
        node
        for node in ast.walk(ast.Module(body=exists_branch.orelse, type_ignores=[]))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Camera"
    )
    free_camera_keywords = {
        keyword.arg: ast.unparse(keyword.value)
        for keyword in free_camera_call.keywords
    }
    assert free_camera_keywords["position"] == "camera_data[key]['position']"
    assert free_camera_keywords["orientation"] == "camera_data[key]['orientation']"
