from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import scripts.check_public_repo_safety as safety

ROOT = Path(__file__).resolve().parents[1]


def test_public_repo_safety_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_public_repo_safety.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_public_repo_safety_allows_policy_mentions(tmp_path, monkeypatch) -> None:
    policy_doc = tmp_path / "policy.md"
    policy_doc.write_text("Do not use real customer data.\n", encoding="utf-8")

    monkeypatch.setattr(safety, "ROOT", tmp_path)
    monkeypatch.setattr(safety, "public_candidate_files", lambda: ["policy.md"])

    errors: list[str] = []
    safety.check_text_patterns(errors)

    assert errors == []


def test_public_repo_safety_flags_candidate_secret_text(tmp_path, monkeypatch) -> None:
    candidate_doc = tmp_path / "candidate.md"
    candidate_doc.write_text("api" + '_key = "not-a-real-key"\n', encoding="utf-8")

    monkeypatch.setattr(safety, "ROOT", tmp_path)
    monkeypatch.setattr(safety, "public_candidate_files", lambda: ["candidate.md"])

    errors: list[str] = []
    safety.check_text_patterns(errors)

    assert errors == ["possible secret pattern in: candidate.md"]


def test_public_repo_safety_flags_duckdb_wal_candidates(monkeypatch) -> None:
    errors: list[str] = []

    monkeypatch.setattr(
        safety,
        "public_candidate_files",
        lambda: ["warehouse/account_health.duckdb.wal"],
    )

    safety.check_tracked_paths(errors)

    assert errors == [
        "forbidden generated artefact tracked: warehouse/account_health.duckdb.wal"
    ]
