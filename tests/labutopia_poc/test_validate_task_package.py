import subprocess
import sys


def test_validate_task_package_cli_reports_success():
    result = subprocess.run(
        [sys.executable, "standalone_tools/labutopia_poc/validate_task_package.py"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "LabUtopia task package validation OK" in result.stdout
