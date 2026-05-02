from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_repo_safety_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_public_repo_safety.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
