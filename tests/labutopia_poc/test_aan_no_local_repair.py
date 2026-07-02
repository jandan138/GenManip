import json
import subprocess
import sys
from pathlib import Path

from standalone_tools.labutopia_poc import aan_no_local_repair


def _write_package(package_dir: Path) -> None:
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "asset.usd").write_text("#usda 1.0\n", encoding="utf-8")
    (package_dir / "task").mkdir()
    (package_dir / "task" / "task_config.yaml").write_text("task: fixture\n", encoding="utf-8")


def test_snapshot_records_package_hash_and_forbids_local_repair(tmp_path):
    package_dir = tmp_path / "package"
    _write_package(package_dir)

    record = aan_no_local_repair.build_snapshot_record(
        package_dir=package_dir,
        stage_label="before_stage4b_live_smoke",
    )

    assert record["stage"] == "aan_no_local_repair_snapshot"
    assert record["status"] == "PASS"
    assert record["stage_label"] == "before_stage4b_live_smoke"
    assert record["package_dir"] == str(package_dir.resolve())
    assert record["package_mutation_allowed"] is False
    assert record["local_usd_repair_allowed"] is False
    assert record["package_hash"]["digest"]
    assert {row["path"] for row in record["package_hash"]["files"]} == {
        "asset.usd",
        "task/task_config.yaml",
    }
    assert record["blockers"] == []


def test_verify_blocks_when_package_changed_after_snapshot(tmp_path):
    package_dir = tmp_path / "package"
    _write_package(package_dir)
    baseline = aan_no_local_repair.build_snapshot_record(
        package_dir=package_dir,
        stage_label="before_stage4b_live_smoke",
    )
    (package_dir / "asset.usd").write_text("#usda 1.0\n# local repair\n", encoding="utf-8")

    record = aan_no_local_repair.build_verify_record(
        package_dir=package_dir,
        baseline_record=baseline,
        stage_label="after_stage4b_live_smoke",
    )

    assert record["stage"] == "aan_no_local_repair_verify"
    assert record["status"] == "BLOCKED"
    assert record["stage_label"] == "after_stage4b_live_smoke"
    assert record["package_mutation_allowed"] is False
    assert record["local_usd_repair_allowed"] is False
    assert record["failure_owner"] == "LabUtopia consumer"
    assert record["producer_owner_action"] == "not_required"
    assert record["blocker_or_next_action"] == (
        "Discard the local package mutation and rerun from the retained ConvertAsset AAN package; "
        "if the source package is wrong, send a structured blocker back to ConvertAsset AAN."
    )
    assert {
        "code": "source_package_mutated_after_consumer_step",
        "field": "package_hash.digest",
        "before": baseline["package_hash"]["digest"],
        "after": record["package_hash_after"]["digest"],
    } in record["blockers"]


def test_cli_snapshot_and_verify_return_blocked_on_mutation(tmp_path):
    package_dir = tmp_path / "package"
    _write_package(package_dir)
    snapshot_path = tmp_path / "snapshot.json"
    verify_path = tmp_path / "verify.json"

    snapshot = subprocess.run(
        [
            sys.executable,
            "standalone_tools/labutopia_poc/aan_no_local_repair.py",
            "--package-dir",
            str(package_dir),
            "--stage-label",
            "before_stage4b_live_smoke",
            "--json-out",
            str(snapshot_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
    )
    assert snapshot.returncode == 0, snapshot.stderr

    (package_dir / "task" / "task_config.yaml").write_text(
        "task: locally_changed\n", encoding="utf-8"
    )
    verify = subprocess.run(
        [
            sys.executable,
            "standalone_tools/labutopia_poc/aan_no_local_repair.py",
            "--package-dir",
            str(package_dir),
            "--baseline",
            str(snapshot_path),
            "--stage-label",
            "after_stage4b_live_smoke",
            "--json-out",
            str(verify_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
    )

    assert verify.returncode == 1
    record = json.loads(verify_path.read_text(encoding="utf-8"))
    assert record["status"] == "BLOCKED"
    assert record["blockers"][0]["code"] == "source_package_mutated_after_consumer_step"
