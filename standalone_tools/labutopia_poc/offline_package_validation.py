from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any


REMOTE_URI_PREFIXES = ("http://", "https://", "omniverse://", "s3://")
CACHE_PATH_MARKERS = ("/.cache/", "/ov/pkg/", "/kit/cache/")


@dataclass(frozen=True)
class OfflineDependencyRoots:
    package_root: Path
    overlay_root: Path | None = None
    staged_roots: tuple[Path, ...] = ()


@dataclass(frozen=True)
class OfflineDependencyExpectation:
    allowed_location_statuses: set[str]
    local_path_fields: set[str]
    remote_checked_fields: set[str]
    informational_uri_fields: set[str]


def assert_offline_dependency_records(
    manifest_path: object,
    records: object,
    roots: OfflineDependencyRoots,
    expectation: OfflineDependencyExpectation,
) -> None:
    prefix = str(manifest_path)
    if not isinstance(records, list):
        raise AssertionError(f"{prefix}: offline dependency records must be a list")
    for index, record in enumerate(records):
        _assert_record(prefix, record, index, roots, expectation)


def _assert_record(
    prefix: str,
    record: object,
    index: int,
    roots: OfflineDependencyRoots,
    expectation: OfflineDependencyExpectation,
) -> None:
    if not isinstance(record, dict):
        raise AssertionError(
            f"{prefix}: offline dependency record {index} must be a mapping"
        )
    identity = _record_identity(record, index)
    _assert_remote_fields(prefix, identity, record, roots, expectation)
    _assert_waiver_boundary(prefix, identity, record)
    status = record.get("dependency_location_status")
    resolution_mode = record.get("resolution_mode")
    requires_local = (
        status in expectation.allowed_location_statuses
        or resolution_mode == "local_mirror"
    )
    if requires_local:
        _assert_local_evidence(prefix, identity, record)
        if not any(field in record for field in expectation.local_path_fields):
            raise AssertionError(
                f"{prefix}: {identity} must include one local path field"
            )
        for field in expectation.local_path_fields:
            if field in record:
                _assert_local_path_field(prefix, identity, record, field, roots)
    for nested in record.get("texture_dependency_records", []) or []:
        _assert_record(prefix, nested, index, roots, expectation)


def _assert_remote_fields(
    prefix: str,
    identity: str,
    record: dict[str, Any],
    roots: OfflineDependencyRoots,
    expectation: OfflineDependencyExpectation,
) -> None:
    for field in expectation.remote_checked_fields:
        value = record.get(field)
        if isinstance(value, str) and _is_remote_or_cache_path(value):
            raise AssertionError(
                f"{prefix}: {identity} {field} must not point to a remote URI"
            )
        if isinstance(value, str) and value:
            path = _resolve_allowed_path(value, roots)
            if path is None:
                raise AssertionError(
                    f"{prefix}: {identity} {field} must stay under an allowed root"
                )
            if not path.exists():
                raise AssertionError(
                    f"{prefix}: {identity} {field} file does not exist"
                )
    for field, value in record.items():
        if field in expectation.informational_uri_fields:
            continue
        if isinstance(value, str) and _is_cache_path(value):
            raise AssertionError(
                f"{prefix}: {identity} {field} must not point to user cache"
            )


def _assert_waiver_boundary(
    prefix: str,
    identity: str,
    record: dict[str, Any],
) -> None:
    if record.get("resolution_mode") != "explicit_waiver":
        return
    if any(
        record.get(field) is True
        for field in (
            "closure_claim_allowed",
            "full_material_closure_claim_allowed",
            "native_material_closure_claim_allowed",
            "full_native_material_closure_claim_allowed",
        )
    ):
        raise AssertionError(
            f"{prefix}: {identity} explicit waiver must not allow closure claims"
        )


def _assert_local_evidence(
    prefix: str,
    identity: str,
    record: dict[str, Any],
) -> None:
    digest = record.get("sha256") or record.get("local_mirror_sha256")
    byte_count = record.get("bytes") or record.get("local_mirror_bytes")
    if not (isinstance(digest, str) and len(digest) == 64):
        raise AssertionError(f"{prefix}: {identity} must record sha256")
    if not (isinstance(byte_count, int) and byte_count > 0):
        raise AssertionError(f"{prefix}: {identity} must record positive byte count")


def _assert_local_path_field(
    prefix: str,
    identity: str,
    record: dict[str, Any],
    field: str,
    roots: OfflineDependencyRoots,
) -> None:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise AssertionError(f"{prefix}: {identity} {field} is missing")
    path = _resolve_allowed_path(value, roots)
    if path is None:
        raise AssertionError(
            f"{prefix}: {identity} {field} must stay under an allowed root"
        )
    if not path.exists():
        raise AssertionError(f"{prefix}: {identity} {field} file does not exist")
    digest = record.get("sha256") or record.get("local_mirror_sha256")
    byte_count = record.get("bytes") or record.get("local_mirror_bytes")
    if _sha256(path) != digest:
        raise AssertionError(f"{prefix}: {identity} {field} hash mismatch")
    if path.stat().st_size != byte_count:
        raise AssertionError(f"{prefix}: {identity} {field} byte count mismatch")


def _resolve_allowed_path(value: str, roots: OfflineDependencyRoots) -> Path | None:
    raw = value.replace("{ASSETS_DIR}/", "")
    candidate = Path(raw)
    allowed_roots = [roots.package_root.resolve()]
    if roots.overlay_root is not None:
        allowed_roots.append(roots.overlay_root.resolve())
    allowed_roots.extend(root.resolve() for root in roots.staged_roots)
    if candidate.is_absolute():
        candidates = [candidate]
    else:
        candidates = [roots.package_root / raw]
        if roots.overlay_root is not None:
            candidates.append(roots.overlay_root / raw)
        candidates.extend(root / raw for root in roots.staged_roots)
    allowed_candidates: list[Path] = []
    for item in candidates:
        resolved = item.resolve()
        if any(_is_relative_to(resolved, root) for root in allowed_roots):
            if resolved.exists():
                return resolved
            allowed_candidates.append(resolved)
    if allowed_candidates:
        return allowed_candidates[0]
    return None


def _is_remote_or_cache_path(value: str) -> bool:
    normalized = value.lower()
    return normalized.startswith(REMOTE_URI_PREFIXES) or _is_cache_path(normalized)


def _is_cache_path(value: str) -> bool:
    normalized = value.lower()
    return any(marker in normalized for marker in CACHE_PATH_MARKERS)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _record_identity(record: dict[str, Any], index: int) -> str:
    return str(
        record.get("material_name")
        or record.get("relative_path")
        or record.get("local_mirror_path")
        or f"record[{index}]"
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
