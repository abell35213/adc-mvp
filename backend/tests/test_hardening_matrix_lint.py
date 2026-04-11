from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO_ROOT / "docs/production-hardening/control-matrix.md"
SCRIPT_PATH = REPO_ROOT / "scripts/check_hardening_matrix_updates.py"


def _load_lint_module():
    spec = importlib.util.spec_from_file_location("check_hardening_matrix_updates", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MATRIX_PATH = str(MATRIX_PATH)
    return module


def test_matrix_contains_required_scope_rows() -> None:
    lint = _load_lint_module()
    errors = lint._validate_scope_rows()
    assert errors == []


def test_hardening_paths_are_detected() -> None:
    lint = _load_lint_module()
    assert lint._is_hardening_path("backend/app/core/security.py")
    assert lint._is_hardening_path("infra/production/backend-deployment.yaml")
    assert not lint._is_hardening_path("frontend/app/page.tsx")


def test_changed_hardening_file_requires_matrix_update() -> None:
    lint = _load_lint_module()
    changed_files = ["backend/app/core/security.py"]
    hardening_changes = [
        path for path in changed_files if path != lint.MATRIX_PATH and lint._is_hardening_path(path)
    ]
    matrix_touched = lint.MATRIX_PATH in changed_files

    assert hardening_changes == ["backend/app/core/security.py"]
    assert matrix_touched is False


def test_matrix_file_exists() -> None:
    assert MATRIX_PATH.exists()
