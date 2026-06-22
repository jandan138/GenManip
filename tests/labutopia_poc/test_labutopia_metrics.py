import numpy as np
import importlib
import sys
import types


class _StubGeometry:
    def __init__(self, *args, **kwargs):
        pass

    def buffer(self, *args, **kwargs):
        return self

    def contains(self, *args, **kwargs):
        return False


class _StubCollisionManager:
    def add_object(self, *args, **kwargs):
        pass

    def in_collision_internal(self, *args, **kwargs):
        return False


def _ensure_module(name):
    module = sys.modules.setdefault(name, types.ModuleType(name))
    if "." in name:
        parent_name, child_name = name.rsplit(".", 1)
        parent = _ensure_module(parent_name)
        if not hasattr(parent, child_name):
            setattr(parent, child_name, module)
    return module


def _set_missing_attr(module, name, value):
    if not hasattr(module, name):
        setattr(module, name, value)


def _install_open3d_stub():
    open3d = _ensure_module("open3d")
    geometry = _ensure_module("open3d.geometry")
    utility = _ensure_module("open3d.utility")
    io = _ensure_module("open3d.io")
    _set_missing_attr(open3d, "geometry", geometry)
    _set_missing_attr(open3d, "utility", utility)
    _set_missing_attr(open3d, "io", io)
    _set_missing_attr(geometry, "TriangleMesh", _StubGeometry)
    _set_missing_attr(geometry, "PointCloud", _StubGeometry)
    _set_missing_attr(geometry, "LineSet", _StubGeometry)
    _set_missing_attr(geometry, "AxisAlignedBoundingBox", _StubGeometry)
    _set_missing_attr(geometry, "KDTreeSearchParamHybrid", _StubGeometry)
    _set_missing_attr(utility, "Vector3dVector", lambda value=None: value)
    _set_missing_attr(utility, "Vector2iVector", lambda value=None: value)
    _set_missing_attr(io, "read_triangle_mesh", lambda *args, **kwargs: _StubGeometry())


def _install_shapely_stub():
    shapely = _ensure_module("shapely")
    shapely_geometry = _ensure_module("shapely.geometry")
    shapely_affinity = _ensure_module("shapely.affinity")
    shapely_base = _ensure_module("shapely.geometry.base")
    shapely_vectorized = _ensure_module("shapely.vectorized")
    _set_missing_attr(shapely, "geometry", shapely_geometry)
    _set_missing_attr(shapely, "affinity", shapely_affinity)
    _set_missing_attr(shapely, "vectorized", shapely_vectorized)
    _set_missing_attr(shapely_geometry, "Point", _StubGeometry)
    _set_missing_attr(shapely_geometry, "Polygon", _StubGeometry)
    _set_missing_attr(shapely_geometry, "MultiPolygon", _StubGeometry)
    _set_missing_attr(shapely_base, "BaseGeometry", _StubGeometry)
    _set_missing_attr(
        shapely_vectorized, "contains", lambda *args, **kwargs: np.array([])
    )
    _set_missing_attr(
        shapely_affinity, "translate", lambda polygon, *args, **kwargs: polygon
    )
    _set_missing_attr(
        shapely_affinity, "rotate", lambda polygon, *args, **kwargs: polygon
    )


def _install_omni_stub():
    core = _ensure_module("omni.isaac.core")
    articulations = _ensure_module("omni.isaac.core.articulations")
    materials = _ensure_module("omni.isaac.core.materials")
    objects = _ensure_module("omni.isaac.core.objects")
    omni_pbr = _ensure_module("omni.isaac.core.materials.omni_pbr")
    prims = _ensure_module("omni.isaac.core.prims")
    robots = _ensure_module("omni.isaac.core.robots.robot")
    sensor = _ensure_module("omni.isaac.sensor")
    semantics_utils = _ensure_module("omni.isaac.core.utils.semantics")
    prim_utils = _ensure_module("omni.isaac.core.utils.prims")
    stage_utils = _ensure_module("omni.isaac.core.utils.stage")
    types_utils = _ensure_module("omni.isaac.core.utils.types")
    usd = _ensure_module("omni.usd")
    _set_missing_attr(core, "World", _StubGeometry)
    _set_missing_attr(articulations, "Articulation", _StubGeometry)
    _set_missing_attr(materials, "PhysicsMaterial", _StubGeometry)
    _set_missing_attr(objects, "VisualCuboid", _StubGeometry)
    _set_missing_attr(omni_pbr, "OmniPBR", _StubGeometry)
    _set_missing_attr(prims, "GeometryPrim", _StubGeometry)
    _set_missing_attr(prims, "RigidPrim", _StubGeometry)
    _set_missing_attr(prims, "XFormPrim", _StubGeometry)
    _set_missing_attr(robots, "Robot", _StubGeometry)
    _set_missing_attr(sensor, "Camera", _StubGeometry)
    _set_missing_attr(types_utils, "JointsState", _StubGeometry)
    _set_missing_attr(usd, "get_context", lambda *args, **kwargs: _StubGeometry())
    _set_missing_attr(
        semantics_utils, "add_update_semantics", lambda *args, **kwargs: None
    )
    for name in (
        "create_prim",
        "delete_prim",
        "get_prim_at_path",
        "get_prim_parent",
        "get_prim_path",
        "is_prim_path_valid",
    ):
        _set_missing_attr(prim_utils, name, lambda *args, **kwargs: None)
    _set_missing_attr(
        stage_utils, "add_reference_to_stage", lambda *args, **kwargs: None
    )
    _set_missing_attr(stage_utils, "get_current_stage", lambda *args, **kwargs: None)


def _install_concave_hull_stub():
    concave_hull = _ensure_module("concave_hull")
    _set_missing_attr(
        concave_hull, "concave_hull", lambda points, *args, **kwargs: points
    )


def _install_trimesh_stub():
    trimesh = _ensure_module("trimesh")
    collision = _ensure_module("trimesh.collision")
    _set_missing_attr(trimesh, "Trimesh", _StubGeometry)
    _set_missing_attr(trimesh, "collision", collision)
    _set_missing_attr(collision, "CollisionManager", _StubCollisionManager)


def _install_missing_pxr_symbol_stub(import_error):
    message = str(import_error)
    prefix = "cannot import name '"
    suffix = "' from 'pxr'"
    if not message.startswith(prefix) or suffix not in message:
        return False
    missing_symbol = message[len(prefix) :].split("'", 1)[0]
    pxr = _ensure_module("pxr")
    _set_missing_attr(pxr, missing_symbol, _ensure_module(f"pxr.{missing_symbol}"))
    return True


def _install_stub_for_missing_module(missing_name):
    installers = {
        "concave_hull": _install_concave_hull_stub,
        "omni": _install_omni_stub,
        "open3d": _install_open3d_stub,
        "shapely": _install_shapely_stub,
        "trimesh": _install_trimesh_stub,
    }
    for prefix, installer in installers.items():
        if missing_name == prefix or missing_name.startswith(f"{prefix}."):
            installer()
            return True
    return False


def _import_metric_extensions(max_attempts=12):
    last_error = None
    for _ in range(max_attempts):
        try:
            return importlib.import_module("genmanip.extensions.metrics")
        except ModuleNotFoundError as exc:
            last_error = exc
            if exc.name is None or not _install_stub_for_missing_module(exc.name):
                raise
            sys.modules.pop("genmanip.extensions.metrics", None)
        except ImportError as exc:
            last_error = exc
            if not _install_missing_pxr_symbol_stub(exc):
                raise
            sys.modules.pop("genmanip.extensions.metrics", None)
    raise last_error


_import_metric_extensions()
from genmanip.core.metrics.utils import MetricFactory


class FakeObject:
    def __init__(self, position):
        self.position = np.array(position)

    def get_world_pose(self):
        return self.position, np.array([1.0, 0.0, 0.0, 0.0])


class FakeScene:
    def __init__(self, object_list=None, articulation_list=None):
        self.object_list = object_list or {}
        self.articulation_list = articulation_list or {}


def step_metric(metric, scene, times=1):
    for _ in range(times):
        metric.update(scene)
    return metric.status


def test_object_height_delta_uses_initial_pose_and_strict_threshold():
    obj = FakeObject([0.0, 0.0, 0.5])
    scene = FakeScene({"obj_conical_bottle02": obj})
    metric = MetricFactory.build(
        "manip/labutopia/object_height_delta",
        skip_steps=1,
        succ_cnts=0,
        sub_goal_setting={
            "obj_uid": "obj_conical_bottle02",
            "axis": "z",
            "min_delta": 0.125,
        },
    )

    assert step_metric(metric, scene) is False
    obj.position[2] = 0.625
    assert step_metric(metric, scene) is False
    obj.position[2] = 0.75
    assert step_metric(metric, scene) is True


def test_object_height_delta_requires_consecutive_success_frames():
    obj = FakeObject([0.0, 0.0, 0.5])
    scene = FakeScene({"obj_conical_bottle02": obj})
    metric = MetricFactory.build(
        "manip/labutopia/object_height_delta",
        skip_steps=1,
        succ_cnts=2,
        sub_goal_setting={
            "obj_uid": "obj_conical_bottle02",
            "axis": "z",
            "min_delta": 0.125,
        },
    )

    assert step_metric(metric, scene) is False
    obj.position[2] = 0.75
    assert step_metric(metric, scene) is False
    obj.position[2] = 0.5
    assert step_metric(metric, scene) is False
    obj.position[2] = 0.75
    assert step_metric(metric, scene) is False
    assert step_metric(metric, scene) is False
    assert step_metric(metric, scene) is True


def test_object_at_target_uses_radial_xy_and_initial_z():
    initial_z = 0.5
    obj = FakeObject([0.25, 0.25, initial_z])
    target = FakeObject([0.5, 0.5, 0.0])
    scene = FakeScene(
        {
            "obj_beaker2": obj,
            "obj_target_plat": target,
        }
    )
    metric = MetricFactory.build(
        "manip/labutopia/object_at_target",
        skip_steps=1,
        succ_cnts=0,
        sub_goal_setting={
            "obj_uid": "obj_beaker2",
            "target_uid": "obj_target_plat",
            "xy_radius": 0.25,
            "z_tolerance": 0.125,
        },
    )

    assert step_metric(metric, scene) is False
    obj.position = np.array([0.6875, 0.6875, initial_z])
    assert step_metric(metric, scene) is False
    obj.position = np.array([0.75, 0.5, initial_z])
    assert step_metric(metric, scene) is False
    obj.position = np.array([0.5, 0.5, 0.625])
    assert step_metric(metric, scene) is False
    obj.position = np.array([0.625, 0.5, initial_z])
    assert step_metric(metric, scene) is True
    obj.position = np.array([0.5, 0.5, initial_z + 0.25])
    assert step_metric(metric, scene) is False


def test_handle_displacement_uses_initial_pose_and_distance_threshold():
    obj = FakeObject([0.0, 0.0, 0.0])
    scene = FakeScene({"obj_DryingBox_01_handle": obj})
    metric = MetricFactory.build(
        "manip/labutopia/handle_displacement",
        skip_steps=1,
        succ_cnts=0,
        sub_goal_setting={
            "obj_uid": "obj_DryingBox_01_handle",
            "min_distance": 0.125,
        },
    )

    assert step_metric(metric, scene) is False
    obj.position = np.array([0.0625, 0.0625, 0.0])
    assert step_metric(metric, scene) is False
    obj.position = np.array([0.09375, 0.0625, 0.0])
    assert step_metric(metric, scene) is False
    obj.position = np.array([0.125, 0.0, 0.0])
    assert step_metric(metric, scene) is False
    obj.position = np.array([0.09375, 0.09375, 0.0])
    assert step_metric(metric, scene) is True
    obj.position = np.array([0.25, 0.0, 0.0])
    assert step_metric(metric, scene) is True
