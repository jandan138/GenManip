import importlib.util
import sys
import types
from pathlib import Path


def _load_physics_utils_with_fakes(monkeypatch, fake_usd_module, fake_physx_schema):
    monkeypatch.setitem(sys.modules, "omni", types.ModuleType("omni"))
    monkeypatch.setitem(sys.modules, "omni.isaac", types.ModuleType("omni.isaac"))
    monkeypatch.setitem(sys.modules, "omni.isaac.core", types.ModuleType("omni.isaac.core"))
    prims_module = types.ModuleType("omni.isaac.core.prims")
    prims_module.GeometryPrim = lambda prim_path: types.SimpleNamespace(
        prim_path=prim_path,
        apply_physics_material=lambda material: None,
    )
    monkeypatch.setitem(sys.modules, "omni.isaac.core.prims", prims_module)
    materials_module = types.ModuleType("omni.isaac.core.materials")
    materials_module.PhysicsMaterial = lambda **kwargs: kwargs
    monkeypatch.setitem(sys.modules, "omni.isaac.core.materials", materials_module)
    monkeypatch.setitem(sys.modules, "omni.usd", fake_usd_module)
    sys.modules["omni"].usd = fake_usd_module
    pxr_module = types.ModuleType("pxr")
    pxr_module.UsdPhysics = types.SimpleNamespace()
    pxr_module.PhysxSchema = fake_physx_schema
    monkeypatch.setitem(sys.modules, "pxr", pxr_module)

    module_path = (
        Path(__file__).resolve().parents[2]
        / "genmanip"
        / "utils"
        / "usd_utils"
        / "physics_utils.py"
    )
    spec = importlib.util.spec_from_file_location(
        "physics_utils_under_test",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_setup_physics_scene_uses_existing_world_physics_scene(monkeypatch):
    calls = {"physx_paths": [], "set_values": []}

    class FakePrim:
        def __init__(self, valid):
            self._valid = valid

        def IsValid(self):
            return self._valid

    class FakeStage:
        def GetPrimAtPath(self, path):
            return FakePrim(path == "/World/PhysicsScene")

    class FakeContext:
        def get_stage(self):
            return FakeStage()

    fake_usd_module = types.ModuleType("omni.usd")
    fake_usd_module.get_context = lambda: FakeContext()

    class FakeAttr:
        def Set(self, value):
            calls["set_values"].append(value)

    class FakeSceneAPI:
        def __init__(self, valid):
            self._valid = valid

        def GetGravityMagnitudeAttr(self):
            if not self._valid:
                raise RuntimeError("Accessed schema on invalid prim")
            return FakeAttr()

    class FakePhysxSceneAPI:
        @staticmethod
        def Get(stage, path):
            calls["physx_paths"].append(path)
            return FakeSceneAPI(stage.GetPrimAtPath(path).IsValid())

    module = _load_physics_utils_with_fakes(
        monkeypatch,
        fake_usd_module,
        types.SimpleNamespace(PhysxSceneAPI=FakePhysxSceneAPI),
    )

    module.setup_physics_scene({"GravityMagnitude": 9.8})

    assert calls["physx_paths"] == ["/World/PhysicsScene"]
    assert calls["set_values"] == [9.8]


def test_setup_physics_scene_finds_nested_wrapper_physics_scene(monkeypatch):
    calls = {"physx_paths": [], "set_values": []}

    class FakePrim:
        def __init__(self, path, type_name="Xform", valid=True):
            self._path = path
            self._type_name = type_name
            self._valid = valid

        def IsValid(self):
            return self._valid

        def GetPath(self):
            return self._path

        def GetTypeName(self):
            return self._type_name

    class FakeStage:
        def GetPrimAtPath(self, path):
            valid = path == "/World/labutopia_level1_poc/PhysicsScene"
            type_name = "PhysicsScene" if valid else "Xform"
            return FakePrim(path, type_name=type_name, valid=valid)

        def Traverse(self):
            return [
                FakePrim("/World", valid=True),
                FakePrim("/World/labutopia_level1_poc", valid=True),
                FakePrim(
                    "/World/labutopia_level1_poc/PhysicsScene",
                    type_name="PhysicsScene",
                    valid=True,
                ),
            ]

    class FakeContext:
        def get_stage(self):
            return FakeStage()

    fake_usd_module = types.ModuleType("omni.usd")
    fake_usd_module.get_context = lambda: FakeContext()

    class FakeAttr:
        def Set(self, value):
            calls["set_values"].append(value)

    class FakeSceneAPI:
        def __init__(self, valid):
            self._valid = valid

        def GetGravityMagnitudeAttr(self):
            if not self._valid:
                raise RuntimeError("Accessed schema on invalid prim")
            return FakeAttr()

    class FakePhysxSceneAPI:
        @staticmethod
        def Get(stage, path):
            calls["physx_paths"].append(path)
            return FakeSceneAPI(stage.GetPrimAtPath(path).IsValid())

    module = _load_physics_utils_with_fakes(
        monkeypatch,
        fake_usd_module,
        types.SimpleNamespace(PhysxSceneAPI=FakePhysxSceneAPI),
    )

    module.setup_physics_scene({"GravityMagnitude": 9.8})

    assert calls["physx_paths"] == ["/World/labutopia_level1_poc/PhysicsScene"]
    assert calls["set_values"] == [9.8]
