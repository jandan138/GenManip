from __future__ import annotations

import hashlib

import pytest

from standalone_tools.labutopia_poc.offline_package_validation import (
    OfflineDependencyExpectation,
    OfflineDependencyRoots,
    assert_offline_dependency_records,
)


def _write(path, content: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _expectation() -> OfflineDependencyExpectation:
    return OfflineDependencyExpectation(
        allowed_location_statuses={
            "local_mirror_copied_with_package",
            "local_file_copied_with_source_scene",
        },
        local_path_fields={"local_mirror_path", "relative_path"},
        remote_checked_fields={
            "local_mirror_path",
            "relative_path",
            "worker_resolved_path",
        },
        informational_uri_fields={"source_url"},
    )


def test_offline_dependency_records_accept_local_mdl_and_texture(tmp_path):
    package_root = tmp_path / "package/common"
    mdl_hash = _write(package_root / "miscs/mdl/test.mdl", b"mdl")
    texture_hash = _write(package_root / "textures/test.png", b"texture")
    records = [
        {
            "material_name": "TestMaterial",
            "dependency_location_status": "local_mirror_copied_with_package",
            "local_mirror_path": "miscs/mdl/test.mdl",
            "sha256": mdl_hash,
            "bytes": 3,
            "source_url": "https://example.invalid/source.mdl",
            "worker_resolved_path": "{ASSETS_DIR}/miscs/mdl/test.mdl",
            "texture_dependency_records": [
                {
                    "relative_path": "textures/test.png",
                    "dependency_location_status": "local_mirror_copied_with_package",
                    "sha256": texture_hash,
                    "bytes": 7,
                    "source_url": "https://example.invalid/texture.png",
                    "worker_resolved_path": "{ASSETS_DIR}/textures/test.png",
                }
            ],
        }
    ]

    assert_offline_dependency_records(
        "assets_manifest.json",
        records,
        OfflineDependencyRoots(package_root=package_root),
        _expectation(),
    )


def test_offline_dependency_records_reject_remote_runtime_uri(tmp_path):
    package_root = tmp_path / "package/common"
    digest = _write(package_root / "test.mdl", b"mdl")
    records = [
        {
            "material_name": "RemoteRuntime",
            "dependency_location_status": "local_mirror_copied_with_package",
            "local_mirror_path": "test.mdl",
            "sha256": digest,
            "bytes": 3,
            "worker_resolved_path": "https://example.invalid/test.mdl",
        }
    ]

    with pytest.raises(
        AssertionError,
        match="worker_resolved_path must not point to a remote URI",
    ):
        assert_offline_dependency_records(
            "assets_manifest.json",
            records,
            OfflineDependencyRoots(package_root=package_root),
            _expectation(),
        )


def test_offline_dependency_records_reject_missing_file(tmp_path):
    records = [
        {
            "material_name": "Missing",
            "dependency_location_status": "local_mirror_copied_with_package",
            "local_mirror_path": "missing.mdl",
            "sha256": "0" * 64,
            "bytes": 3,
        }
    ]

    with pytest.raises(AssertionError, match="local_mirror_path file does not exist"):
        assert_offline_dependency_records(
            "assets_manifest.json",
            records,
            OfflineDependencyRoots(package_root=tmp_path),
            _expectation(),
        )


def test_offline_dependency_records_reject_hash_mismatch(tmp_path):
    package_root = tmp_path / "package/common"
    _write(package_root / "test.mdl", b"mdl")
    records = [
        {
            "material_name": "HashMismatch",
            "dependency_location_status": "local_mirror_copied_with_package",
            "local_mirror_path": "test.mdl",
            "sha256": "0" * 64,
            "bytes": 3,
        }
    ]

    with pytest.raises(AssertionError, match="local_mirror_path hash mismatch"):
        assert_offline_dependency_records(
            "assets_manifest.json",
            records,
            OfflineDependencyRoots(package_root=package_root),
            _expectation(),
        )


def test_offline_dependency_records_reject_byte_mismatch(tmp_path):
    package_root = tmp_path / "package/common"
    digest = _write(package_root / "test.mdl", b"mdl")
    records = [
        {
            "material_name": "ByteMismatch",
            "dependency_location_status": "local_mirror_copied_with_package",
            "local_mirror_path": "test.mdl",
            "sha256": digest,
            "bytes": 99,
        }
    ]

    with pytest.raises(AssertionError, match="local_mirror_path byte count mismatch"):
        assert_offline_dependency_records(
            "assets_manifest.json",
            records,
            OfflineDependencyRoots(package_root=package_root),
            _expectation(),
        )


def test_offline_dependency_records_reject_absolute_outside_root(tmp_path):
    outside_file = tmp_path / "outside/test.mdl"
    digest = _write(outside_file, b"mdl")
    records = [
        {
            "material_name": "Outside",
            "dependency_location_status": "local_mirror_copied_with_package",
            "local_mirror_path": str(outside_file),
            "sha256": digest,
            "bytes": 3,
        }
    ]

    with pytest.raises(
        AssertionError,
        match="local_mirror_path must stay under an allowed root",
    ):
        assert_offline_dependency_records(
            "assets_manifest.json",
            records,
            OfflineDependencyRoots(package_root=tmp_path / "package/common"),
            _expectation(),
        )


def test_offline_dependency_records_reject_waiver_overclaim(tmp_path):
    records = [
        {
            "material_name": "Waived",
            "resolution_mode": "explicit_waiver",
            "waiver_id": "REMOTE_001",
            "closure_claim_allowed": True,
        }
    ]

    with pytest.raises(
        AssertionError,
        match="explicit waiver must not allow closure claims",
    ):
        assert_offline_dependency_records(
            "assets_manifest.json",
            records,
            OfflineDependencyRoots(package_root=tmp_path),
            _expectation(),
        )
