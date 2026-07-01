#!/usr/bin/env python3
"""AAN package intake and consumer manifest checks for LabUtopia POC."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_SCHEMA_VERSION = "asset_application_normalizer.v1"
EXPECTED_RUNTIME_PROFILE = "isaac41"
EXPECTED_BENCHMARK_PROFILE = "ebench-lift2"
REQUIRED_GATE_STAGES = (
    "usd_closure",
    "material_closure",
    "physics_static",
    "runtime_smoke",
    "benchmark_contract",
)
REQUIRED_ENTRYPOINTS = (
    "root_usd",
    "task_config",
    "required_prims",
    "metric_evaluator",
)
RESOLVED_DEPENDENCY_STATUSES = {"packaged", "pass", "resolved"}
DEFAULT_EVIDENCE_DIR = Path("docs/labutopia_lab_poc/evidence_manifests")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_files(package_dir: Path) -> list[Path]:
    return sorted(path for path in package_dir.rglob("*") if path.is_file())


def _package_hash_summary(package_dir: Path) -> dict[str, Any]:
    files = _package_files(package_dir)
    tree_digest = hashlib.sha256()
    file_hashes: list[dict[str, str]] = []
    for path in files:
        relative = path.relative_to(package_dir).as_posix()
        file_sha = _sha256_file(path)
        tree_digest.update(relative.encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(file_sha.encode("ascii"))
        tree_digest.update(b"\n")
        file_hashes.append({"path": relative, "sha256": file_sha})
    return {
        "algorithm": "sha256(sorted_relative_path_nul_file_sha256)",
        "digest": tree_digest.hexdigest(),
        "files": file_hashes,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _default_intake_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return DEFAULT_EVIDENCE_DIR / f"aan_dryingbox_package_intake_{stamp}.json"


def _load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest root must be a JSON object")
    return data


def build_intake_record(package_dir: Path, manifest_path: Path) -> dict[str, Any]:
    resolved_package = package_dir.resolve()
    resolved_manifest = manifest_path.resolve()
    files = _package_files(resolved_package)
    return {
        "stage": "aan_package_intake",
        "status": "pass",
        "retained_package_root": str(resolved_package),
        "retained_manifest_path": str(resolved_manifest),
        "source_manifest_sha256": _sha256_file(resolved_manifest),
        "package_directory_file_count": len(files),
        "package_directory_hash_summary": _package_hash_summary(resolved_package),
        "package_owner": "ConvertAsset",
        "consumer_owner": "GenManip / LabUtopia POC",
        "package_consumption": {
            "read_only": True,
            "mode": "source_path_read_only_no_mutation",
            "symlink": resolved_package.is_symlink(),
            "generated_mount_namespace_copy": False,
        },
        "convertasset_package_mutation_allowed": False,
    }


def _status_is_pass(value: Any) -> bool:
    return isinstance(value, str) and value.lower() == "pass"


def _stage_gate_status(manifest: dict[str, Any], stage: str) -> Any:
    gates = manifest.get("stage_gates")
    if isinstance(gates, list):
        for gate in gates:
            if isinstance(gate, dict) and gate.get("stage") == stage:
                return gate.get("status")
    if isinstance(gates, dict):
        gate = gates.get(stage)
        if isinstance(gate, dict):
            return gate.get("status")
        return gate
    gate = manifest.get(stage)
    if isinstance(gate, dict):
        return gate.get("status")
    return None


def _path_inside_package(package_dir: Path, raw_path: Any) -> tuple[bool, Path | None]:
    if not isinstance(raw_path, str) or raw_path == "":
        return False, None
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return False, None
    resolved_package = package_dir.resolve()
    resolved = (resolved_package / candidate).resolve()
    try:
        resolved.relative_to(resolved_package)
    except ValueError:
        return False, resolved
    return True, resolved


def _waiver_id(waiver: Any, index: int) -> str:
    if isinstance(waiver, dict):
        for key in ("id", "waiver_id", "check_id", "reason"):
            value = waiver.get(key)
            if value:
                return str(value)
    return f"waiver[{index}]"


def _iter_dependency_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    closure = manifest.get("dependency_closure")
    if not isinstance(closure, dict):
        return []
    entries = closure.get("local_files", [])
    return [entry for entry in entries if isinstance(entry, dict)]


def validate_consumer_manifest(
    manifest: dict[str, Any],
    package_dir: Path,
    *,
    accepted_waivers: set[str],
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []

    def require_equal(field: str, actual: Any, expected: Any, code: str) -> None:
        if actual != expected:
            blockers.append(
                {
                    "code": code,
                    "field": field,
                    "expected": expected,
                    "actual": actual,
                }
            )

    require_equal(
        "schema_version",
        manifest.get("schema_version"),
        EXPECTED_SCHEMA_VERSION,
        "wrong_schema_version",
    )
    target = manifest.get("target") if isinstance(manifest.get("target"), dict) else {}
    require_equal(
        "target.target_runtime_profile",
        target.get("target_runtime_profile"),
        EXPECTED_RUNTIME_PROFILE,
        "wrong_target_profile",
    )
    require_equal(
        "target.target_benchmark_profile",
        target.get("target_benchmark_profile"),
        EXPECTED_BENCHMARK_PROFILE,
        "wrong_target_profile",
    )
    require_equal(
        "overall_status",
        manifest.get("overall_status"),
        "pass",
        "overall_status_not_pass",
    )

    gate_results: dict[str, Any] = {}
    for stage in REQUIRED_GATE_STAGES:
        status = _stage_gate_status(manifest, stage)
        gate_results[stage] = status
        if not _status_is_pass(status):
            blockers.append(
                {
                    "code": "gate_not_pass",
                    "field": f"stage_gates.{stage}",
                    "expected": "pass",
                    "actual": status,
                }
            )

    blocked_reasons = manifest.get("blocked_reasons", [])
    if blocked_reasons:
        reason_list = (
            blocked_reasons
            if isinstance(blocked_reasons, list)
            else [blocked_reasons]
        )
        for reason in reason_list:
            blockers.append(
                {
                    "code": "blocked_reason",
                    "field": "blocked_reasons",
                    "reason": reason,
                }
            )

    waivers = manifest.get("waivers", [])
    accepted = sorted(accepted_waivers)
    if waivers:
        waiver_list = waivers if isinstance(waivers, list) else [waivers]
        for index, waiver in enumerate(waiver_list):
            waiver_id = _waiver_id(waiver, index)
            if waiver_id not in accepted_waivers:
                blockers.append(
                    {
                        "code": "unaccepted_waiver",
                        "field": "waivers",
                        "waiver_id": waiver_id,
                    }
                )

    entrypoints = manifest.get("entrypoints")
    if not isinstance(entrypoints, dict):
        entrypoints = {}
        blockers.append(
            {
                "code": "missing_entrypoints",
                "field": "entrypoints",
                "expected": "mapping",
                "actual": type(manifest.get("entrypoints")).__name__,
            }
        )

    resolved_entrypoints: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_ENTRYPOINTS:
        raw_path = entrypoints.get(name)
        inside, resolved = _path_inside_package(package_dir, raw_path)
        exists = bool(inside and resolved and resolved.exists())
        resolved_entrypoints[name] = {
            "path": raw_path,
            "resolved_path": str(resolved) if resolved is not None else None,
            "resolved_inside_package": inside,
            "exists": exists,
        }
        if not inside:
            blockers.append(
                {
                    "code": "entrypoint_outside_package",
                    "field": f"entrypoints.{name}",
                    "path": raw_path,
                }
            )
        elif not exists:
            blockers.append(
                {
                    "code": "missing_entrypoint",
                    "field": f"entrypoints.{name}",
                    "path": raw_path,
                }
            )

    for index, entry in enumerate(_iter_dependency_entries(manifest)):
        status = entry.get("status")
        if status not in RESOLVED_DEPENDENCY_STATUSES:
            blockers.append(
                {
                    "code": "unresolved_dependency",
                    "field": f"dependency_closure.local_files[{index}].status",
                    "path": entry.get("package_path") or entry.get("raw_asset_path"),
                    "status": status,
                }
            )

    passed = not blockers
    return {
        "stage": "aan_consumer_manifest_check",
        "status": "pass" if passed else "blocked",
        "aan_consumer_manifest_ready": passed,
        "aan_package_mount_allowed": passed,
        "local_usd_repair_allowed": False,
        "package_dir": str(package_dir.resolve()),
        "gate_results": gate_results,
        "entrypoints": resolved_entrypoints,
        "accepted_waivers": accepted,
        "blockers": blockers,
        "forbidden_claims": ["ebench_task_execution_passed"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Record AAN package intake evidence and validate the retained "
            "ConvertAsset package manifest for LabUtopia consumer mounting."
        )
    )
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument(
        "--intake-json-out",
        type=Path,
        default=None,
        help=(
            "Optional Stage 1 evidence path. Defaults to "
            "docs/labutopia_lab_poc/evidence_manifests/"
            "aan_dryingbox_package_intake_YYYYMMDD_HHMM.json"
        ),
    )
    parser.add_argument(
        "--accept-waiver",
        action="append",
        default=[],
        help="Explicitly accepted downstream waiver id. May be repeated.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    package_dir = args.package_dir
    manifest_path = args.manifest
    if not package_dir.is_dir():
        raise SystemExit(f"package directory does not exist: {package_dir}")
    if not manifest_path.is_file():
        raise SystemExit(f"manifest does not exist: {manifest_path}")

    intake_path = args.intake_json_out or _default_intake_path()
    intake_record = build_intake_record(package_dir, manifest_path)
    _write_json(intake_path, intake_record)

    manifest = _load_manifest(manifest_path)
    consumer_record = validate_consumer_manifest(
        manifest,
        package_dir,
        accepted_waivers=set(args.accept_waiver),
    )
    consumer_record["package_intake_evidence"] = str(intake_path)
    consumer_record["manifest_path"] = str(manifest_path.resolve())
    consumer_record["source_manifest_sha256"] = intake_record["source_manifest_sha256"]
    _write_json(args.json_out, consumer_record)

    print(json.dumps(consumer_record, indent=2, sort_keys=True))
    return 0 if consumer_record["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
