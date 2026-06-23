from types import SimpleNamespace

import pytest


class _FakePrim:
    def __init__(self, active=True):
        self._active = active
        self.set_calls = []

    def IsActive(self):
        return self._active

    def SetActive(self, active):
        self._active = active
        self.set_calls.append(active)


def _fake_scene():
    bottle = SimpleNamespace(prim=_FakePrim(True), prim_path="/World/bottle")
    box = SimpleNamespace(prim=_FakePrim(True), prim_path="/World/box")
    handle = SimpleNamespace(prim=_FakePrim(True), prim_path="/World/box/handle")
    return SimpleNamespace(
        object_list={"obj_conical_bottle02": bottle},
        articulation_list={"obj_DryingBox_01": box},
        articulation_part_list={"obj_DryingBox_01_handle": handle},
        cache_library=SimpleNamespace(
            mesh_dict={
                "obj_conical_bottle02": object(),
                "obj_DryingBox_01": object(),
                "obj_DryingBox_01_handle": object(),
            }
        ),
    )


def test_set_scene_object_active_can_hide_objects_articulations_and_parts():
    from genmanip.utils.loader.preprocess_rules import set_scene_object_active

    scene = _fake_scene()

    set_scene_object_active(
        scene,
        ["obj_conical_bottle02", "obj_DryingBox_01", "obj_DryingBox_01_handle"],
        active=False,
    )

    assert scene.object_list["obj_conical_bottle02"].prim.IsActive() is False
    assert scene.articulation_list["obj_DryingBox_01"].prim.IsActive() is False
    assert scene.articulation_part_list["obj_DryingBox_01_handle"].prim.IsActive() is False
    assert scene.cache_library.mesh_dict == {}


def test_set_scene_object_active_fails_fast_for_unknown_uids():
    from genmanip.utils.loader.preprocess_rules import set_scene_object_active

    with pytest.raises(KeyError, match="missing_uid"):
        set_scene_object_active(_fake_scene(), ["missing_uid"], active=False)


def test_resettable_scene_object_uids_skip_articulations_and_parts():
    from genmanip.utils.loader.preprocess_rules import resettable_scene_object_uids

    scene = _fake_scene()
    scene.object_list["obj_beaker2"] = SimpleNamespace(
        prim=_FakePrim(True), prim_path="/World/beaker"
    )
    scene.object_list["obj_DryingBox_01_handle"] = scene.articulation_part_list[
        "obj_DryingBox_01_handle"
    ]
    scene.object_list["obj_DryingBox_01"] = scene.articulation_list["obj_DryingBox_01"]

    assert resettable_scene_object_uids(scene) == [
        "obj_beaker2",
        "obj_conical_bottle02",
    ]


class _FakeArticulationView:
    def __init__(self):
        self.positions = None
        self.velocities = None
        self.position_targets = None

    def set_joint_positions(self, positions):
        self.positions = list(positions)

    def set_joint_velocities(self, velocities):
        self.velocities = list(velocities)

    def set_joint_position_targets(self, positions):
        self.position_targets = list(positions)


def test_apply_articulation_initial_targets_replays_post_reset_target():
    from genmanip.utils.loader.preprocess_rules import apply_articulation_initial_targets

    articulation_view = _FakeArticulationView()
    scene = SimpleNamespace(
        articulation_list={
            "obj_DryingBox_01": SimpleNamespace(
                _articulation_view=articulation_view,
            ),
        },
        articulation_data={"obj_DryingBox_01": {"is_articulated": True}},
        scene_config=SimpleNamespace(
            generation_config=SimpleNamespace(
                articulation={
                    "obj_DryingBox_01": {"target_positions": [0.0]},
                    "obj_ignored": {"target_positions": [0.5]},
                },
            ),
        ),
    )

    applied = apply_articulation_initial_targets(scene)

    assert applied == {"obj_DryingBox_01": [0.0]}
    assert articulation_view.positions == [0.0]
    assert articulation_view.velocities == [0.0]
    assert articulation_view.position_targets == [0.0]
