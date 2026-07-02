#!/usr/bin/env python3
"""Guard AAN package consumption against local package repair."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from standalone_tools.labutopia_poc.aan_consumer_check import _package_hash_summary


NEXT_ACTION = (
    "Discard the local package mutation and rerun from the retained ConvertAsset AAN package; "
    "if the source package is wrong, send a structured blocker back to ConvertAsset AAN."
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def build_snapshot_record(*, package_dir: Path, stage_label: str) -> dict[str, Any]:
    resolved_package = package_dir.resolve()
    return {
        "stage": "aan_no_local_repair_snapshot",
        "status": "PASS",
        "stage_label": stage_label,
        "package_dir": str(resolved_package),
        "package_hash": _package_hash_summary(resolved_package),
        "package_mutation_allowed": False,
        "local_usd_repair_allowed": False,
        "failure_owner": None,
        "producer_owner_action": None,
        "blocker_or_next_action": None,
        "blockers": [],
    }


def build_verify_record(
    *,
    package_dir: Path,
    baseline_record: dict[str, Any],
    stage_label: str,
) -> dict[str, Any]:
    resolved_package = package_dir.resolve()
    before_hash = baseline_record.get("package_hash")
    after_hash = _package_hash_summary(resolved_package)
    blockers: list[dict[str, Any]] = []
    if before_hash != after_hash:
        blockers.append(
            {
                "code": "source_package_mutated_after_consumer_step",
                "field": "package_hash.digest",
                "before": before_hash.get("digest") if isinstance(before_hash, dict) else None,
                "after": after_hash["digest"],
            }
        )

    blocked = bool(blockers)
    return {
        "stage": "aan_no_local_repair_verify",
        "status": "BLOCKED" if blocked else "PASS",
        "stage_label": stage_label,
        "package_dir": str(resolved_package),
        "baseline_stage_label": baseline_record.get("stage_label"),
        "package_hash_before": before_hash,
        "package_hash_after": after_hash,
        "package_mutation_allowed": False,
        "local_usd_repair_allowed": False,
        "failure_owner": "LabUtopia consumer" if blocked else None,
        "producer_owner_action": "not_required" if blocked else None,
        "blocker_or_next_action": NEXT_ACTION if blocked else None,
        "blockers": blockers,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Snapshot or verify a retained ConvertAsset AAN package to ensure "
            "LabUtopia / GenManip consumer steps do not repair package contents locally."
        )
    )
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Snapshot JSON to compare against. Omit to write a baseline snapshot.",
    )
    parser.add_argument("--stage-label", required=True)
    parser.add_argument("--json-out", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.package_dir.is_dir():
        raise SystemExit(f"package directory does not exist: {args.package_dir}")
    if args.baseline is not None and not args.baseline.is_file():
        raise SystemExit(f"baseline does not exist: {args.baseline}")

    if args.baseline is None:
        record = build_snapshot_record(
            package_dir=args.package_dir,
            stage_label=args.stage_label,
        )
    else:
        record = build_verify_record(
            package_dir=args.package_dir,
            baseline_record=_read_json(args.baseline),
            stage_label=args.stage_label,
        )
    _write_json(args.json_out, record)
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
