"""Spec-conformance regression eval — every API call must exist in suite-api.

2026-06-08 external user report: half of the Aria MCP API returned 404 —
multiple endpoints (anomalies, badge/*, remainingcapacity, timeremaining,
recommendations/rightsizing, resources/query/topn, alerts/{id}/acknowledge,
DELETE alerts/{id}) were never part of the vROps/Aria Operations suite-api.
Root cause: the API layer was written from memory and never validated
against the official specification.

This test AST-parses every ``client.<get|post|put|delete>("<path>")`` call
in vmware_aria/ (ops + connection) and asserts the (method, path) pair
exists in the official vROps 8.6 operation index stored at
tests/eval/spec/vrops86_operations.json (315 operations, parsed from the
official Swagger UI dump).

Any future invented endpoint fails here instead of 404-ing in production.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC_PATH = REPO_ROOT / "tests" / "eval" / "spec" / "vrops86_operations.json"
SCAN_DIRS = [REPO_ROOT / "vmware_aria"]

_HTTP_METHODS = {"get": "GET", "post": "POST", "put": "PUT", "delete": "DELETE"}


def _spec_matchers() -> list[tuple[str, re.Pattern]]:
    """Spec operations as (method, compiled path regex with {param} wildcards)."""
    spec = json.loads(SPEC_PATH.read_text())
    matchers = []
    for op in spec["operations"]:
        # /api/resources/{id}/stats -> ^/api/resources/[^/]+/stats$
        pattern = re.sub(r"\{[^}]+\}", r"[^/]+", op["path"])
        matchers.append((op["method"], re.compile(f"^{re.escape('')}{pattern}$")))
    return matchers


def _literal_path(node: ast.AST) -> str | None:
    """Extract a path template from a str constant or f-string argument."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(str(v.value))
            else:
                parts.append("{param}")
        return "".join(parts)
    return None


def _collect_api_calls() -> list[tuple[str, str, str]]:
    """All (location, METHOD, path) client/self._client HTTP calls under vmware_aria/."""
    calls = []
    for scan_dir in SCAN_DIRS:
        for py in sorted(scan_dir.rglob("*.py")):
            tree = ast.parse(py.read_text())
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                method = _HTTP_METHODS.get(node.func.attr)
                if method is None or not node.args:
                    continue
                path = _literal_path(node.args[0])
                if path is None or not path.startswith("/"):
                    continue
                # full URLs (token acquire uses base_url f-string) — keep tail
                calls.append((f"{py.relative_to(REPO_ROOT)}:{node.lineno}", method, path))
    return calls


def test_spec_index_is_loaded() -> None:
    spec = json.loads(SPEC_PATH.read_text())
    assert spec["operation_count"] >= 300, "spec index missing or truncated"


def test_every_api_call_exists_in_suite_api_spec() -> None:
    matchers = _spec_matchers()
    calls = _collect_api_calls()
    assert calls, "no API calls collected — AST scan broken?"

    violations = []
    for loc, method, path in calls:
        # ops paths omit the /api prefix (client base_url is /suite-api/api)
        candidate = path if path.startswith("/api/") else f"/api{path}"
        # normalize f-string params to a single segment placeholder
        candidate = re.sub(r"\{param\}", "PARAM", candidate)
        candidate = re.sub(r"PARAM[^/]*", "PARAM", candidate)
        if not any(m == method and rx.match(candidate) for m, rx in matchers):
            violations.append(f"{loc}: {method} {path}")

    assert not violations, (
        "API calls not present in the vROps 8.6 suite-api spec "
        "(invented endpoints WILL 404 in production):\n  " + "\n  ".join(violations)
    )
