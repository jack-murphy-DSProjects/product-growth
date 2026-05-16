from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "AGENTS.md",
    "AGENTS.override.md.example",
    ".gitignore",
    ".env.example",
    "Makefile",
    "pyproject.toml",
    "README.md",
    "docs/project_contract.md",
    "docs/context.md",
    "docs/packages.md",
    "docs/runbook.md",
    "docs/security.md",
    "docs/decisions.md",
    "docs/out_of_scope.md",
    "docs/training_strategy.md",
    "docs/evaluation_strategy.md",
    "docs/monitoring.md",
    "docs/deployment.md",
    "docs/revops_playbook.md",
    ".agent/current_execution_context.md.example",
    ".agent/package_gate.md.example",
    ".agent/agent_runbook.md.example",
    "scripts/check_public_repo_safety.py",
    "tests/test_public_repo_safety.py",
    "src/account_health/__init__.py",
]

FORBIDDEN_TRACKED_PATHS = {
    ".env",
    "AGENTS.override.md",
    ".agent/current_execution_context.md",
    ".agent/package_gate.md",
    ".agent/agent_runbook.md",
}

FORBIDDEN_PATH_PARTS = {
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "mlruns",
}

FORBIDDEN_PATH_PREFIXES = (
    "data/generated/",
    "data/warehouse/",
    "data/processed/",
    "data/outputs/",
    "artifacts/models/",
    "artifacts/tmp/",
)

FORBIDDEN_SUFFIXES = (
    ".duckdb",
    ".duckdb.wal",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".parquet",
    ".pkl",
    ".joblib",
    ".ipynb",
)

SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"(?i)(password|secret|token|api[_-]?key)\s*=\s*['\"][^'\"]+['\"]"),
]

PRIVATE_TEXT_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+"),
]


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def unignored_untracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def public_candidate_files() -> list[str]:
    return sorted(set(tracked_files()) | set(unignored_untracked_files()))


def text_for(path: str) -> str:
    try:
        return (ROOT / path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def check_required_files(errors: list[str]) -> None:
    for path in REQUIRED_FILES:
        full_path = ROOT / path
        if not full_path.is_file():
            errors.append(f"missing required file: {path}")
        elif full_path.stat().st_size == 0:
            errors.append(f"required file is empty: {path}")


def check_tracked_paths(errors: list[str]) -> None:
    for path in public_candidate_files():
        path_parts = set(Path(path).parts)
        if path in FORBIDDEN_TRACKED_PATHS:
            errors.append(f"forbidden tracked local-only file: {path}")
        if path.startswith(FORBIDDEN_PATH_PREFIXES):
            errors.append(f"forbidden generated/local path tracked: {path}")
        if path_parts & FORBIDDEN_PATH_PARTS:
            errors.append(f"forbidden generated/cache path tracked: {path}")
        if any(part.endswith(".egg-info") for part in path_parts):
            errors.append(f"forbidden package build metadata tracked: {path}")
        if path.endswith(FORBIDDEN_SUFFIXES):
            errors.append(f"forbidden generated artefact tracked: {path}")


def check_text_patterns(errors: list[str]) -> None:
    for path in public_candidate_files():
        if Path(path).suffix in {".pyc", ".png", ".jpg", ".jpeg", ".gif"}:
            continue
        text = text_for(path)
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible secret pattern in: {path}")
        for pattern in PRIVATE_TEXT_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible private/local text in: {path}")


def main() -> int:
    errors: list[str] = []
    check_required_files(errors)
    check_tracked_paths(errors)
    check_text_patterns(errors)

    if errors:
        print("Public repo safety check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Public repo safety check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
