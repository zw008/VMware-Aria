"""Safety boundary tests -- verify destructive ops have double_confirm guards.

Uses Python AST parsing to verify that every destructive function in the ops/
package contains a call to ``double_confirm`` (or ``_double_confirm``).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

OPS_DIR = Path(__file__).resolve().parent.parent / "vmware_aria" / "ops"

# (file_name, function_name) -- destructive / state-changing functions that
# MUST call double_confirm before executing the operation.
DESTRUCTIVE_FUNCTIONS: list[tuple[str, str]] = [
    # Alert management (write operations)
    ("alerts.py", "acknowledge_alert"),
    ("alerts.py", "cancel_alert"),
    ("alerts.py", "delete_alert_definition"),
    # Report management
    ("reports.py", "delete_report"),
]


def _has_double_confirm(file_path: Path, func_name: str) -> bool:
    """Return True if *func_name* in *file_path* references ``double_confirm``."""
    tree = ast.parse(file_path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            source = ast.dump(node)
            return "double_confirm" in source
    return False


@pytest.mark.unit
class TestDestructiveOpsSafety:
    """Every destructive / state-changing function must include a double_confirm safety guard."""

    @pytest.mark.parametrize("file_name,func_name", DESTRUCTIVE_FUNCTIONS)
    def test_has_double_confirm(self, file_name: str, func_name: str) -> None:
        path = OPS_DIR / file_name
        assert path.exists(), f"{path} not found"
        assert _has_double_confirm(path, func_name), (
            f"{func_name} in {file_name} lacks a double_confirm safety guard"
        )
