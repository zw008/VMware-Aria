"""Aria Operations report management: list definitions, generate, list, get, delete.

Reports are generated from report definition templates.  Typical workflow:
  1. list_report_definitions() — find the template ID
  2. generate_report(definition_id, resource_ids) — trigger generation, get report_id
  3. get_report(report_id) — poll until status == COMPLETED, then use download_url
  4. delete_report(report_id) — clean up after download

All API responses pass through sanitize() to strip control characters.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vmware_policy import sanitize

if TYPE_CHECKING:
    from vmware_aria.connection import AriaClient
    from vmware_aria.notify.audit import AuditLogger

_log = logging.getLogger("vmware-aria.ops.reports")


# ---------------------------------------------------------------------------
# list_report_definitions
# ---------------------------------------------------------------------------


def list_report_definitions(
    client: AriaClient,
    name_filter: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """List available report definition templates.

    Args:
        client: Authenticated Aria Operations API client.
        name_filter: Optional substring to filter by definition name (case-insensitive).
        limit: Maximum number of definitions to return (1–500).

    Returns:
        List of report definition dicts with id, name, description, subject_type.
    """
    limit = max(1, min(limit, 500))
    data = client.get("/reportdefinitions", params={"pageSize": limit})
    items = data.get("reportDefinitions", [])

    results = []
    for d in items:
        name = sanitize(d.get("name", ""), max_len=300)
        if name_filter and name_filter.lower() not in name.lower():
            continue
        results.append({
            "id": sanitize(d.get("id", "")),
            "name": name,
            "description": sanitize(d.get("description", ""), max_len=500),
            "subject_type": sanitize(d.get("subject", {}).get("resourceKindKey", ""), max_len=200),
            "owner": sanitize(d.get("owner", ""), max_len=200),
        })
    return results


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


def generate_report(
    client: AriaClient,
    definition_id: str,
    resource_ids: list[str] | None = None,
    audit_logger: AuditLogger | None = None,
    target_name: str = "default",
) -> dict:
    """Trigger generation of a report from a report definition template.

    Args:
        client: Authenticated Aria Operations API client.
        definition_id: Report definition (template) UUID.
        resource_ids: Optional list of resource UUIDs to scope the report.
            If omitted, the report runs against all resources in the template scope.
        audit_logger: Optional audit logger.
        target_name: Target name for audit log.

    Returns:
        Dict with report_id, status, and definition_id.
    """
    if not definition_id:
        raise ValueError("definition_id must not be empty")

    payload: dict = {"reportDefinition": {"id": definition_id}}
    if resource_ids:
        payload["subject"] = {"resources": [{"resourceId": rid} for rid in resource_ids]}

    data = client.post("/reports", json_data=payload)
    report_id = sanitize(data.get("id", ""))

    result = {
        "report_id": report_id,
        "definition_id": definition_id,
        "status": sanitize(data.get("status", "PENDING")),
        "note": "Poll get_report(report_id) until status == COMPLETED, then use download_url.",
    }

    if audit_logger:
        audit_logger.log(
            target=target_name,
            operation="generate_report",
            resource=f"report/{report_id}",
            skill="aria",
            parameters={"definition_id": definition_id, "resource_ids": resource_ids},
            result="ok",
        )

    return result


# ---------------------------------------------------------------------------
# list_reports
# ---------------------------------------------------------------------------


def list_reports(
    client: AriaClient,
    definition_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List generated reports, optionally filtered by report definition.

    Args:
        client: Authenticated Aria Operations API client.
        definition_id: Optional report definition UUID to filter results.
        limit: Maximum number of reports to return (1–200).

    Returns:
        List of report summary dicts with id, name, status, generation_time.
    """
    limit = max(1, min(limit, 200))
    params: dict = {"pageSize": limit}
    if definition_id:
        params["reportDefinitionId"] = definition_id

    data = client.get("/reports", params=params)
    items = data.get("reports", [])

    return [
        {
            "id": sanitize(r.get("id", "")),
            "name": sanitize(r.get("name", ""), max_len=300),
            "status": sanitize(r.get("status", "")),
            "definition_id": sanitize(r.get("reportDefinitionId", "")),
            "generation_time_ms": r.get("generationTime"),
            "finish_time_ms": r.get("finishTime"),
            "owner": sanitize(r.get("owner", ""), max_len=200),
        }
        for r in items
    ]


# ---------------------------------------------------------------------------
# get_report
# ---------------------------------------------------------------------------


def get_report(
    client: AriaClient,
    report_id: str,
) -> dict:
    """Get status and download URL for a generated report.

    Args:
        client: Authenticated Aria Operations API client.
        report_id: The report UUID.

    Returns:
        Dict with id, name, status, download_url (PDF), csv_url.
        status values: PENDING, RUNNING, COMPLETED, FAILED.
    """
    if not report_id:
        raise ValueError("report_id must not be empty")

    data = client.get(f"/reports/{report_id}")
    base_url = client._base_url  # e.g. https://aria-host:443/suite-api/api

    download_url = f"{base_url}/reports/{report_id}/download?format=pdf"
    csv_url = f"{base_url}/reports/{report_id}/download?format=csv"

    return {
        "id": sanitize(data.get("id", "")),
        "name": sanitize(data.get("name", ""), max_len=300),
        "status": sanitize(data.get("status", "")),
        "definition_id": sanitize(data.get("reportDefinitionId", "")),
        "generation_time_ms": data.get("generationTime"),
        "finish_time_ms": data.get("finishTime"),
        "download_url": download_url,
        "csv_url": csv_url,
    }


# ---------------------------------------------------------------------------
# delete_report
# ---------------------------------------------------------------------------


def delete_report(
    client: AriaClient,
    report_id: str,
    audit_logger: AuditLogger | None = None,
    target_name: str = "default",
) -> dict:
    """Delete a generated report.

    Args:
        client: Authenticated Aria Operations API client.
        report_id: The report UUID to delete.
        audit_logger: Optional audit logger.
        target_name: Target name for audit log.

    Returns:
        Dict confirming deletion.
    """
    if not report_id:
        raise ValueError("report_id must not be empty")

    client.delete(f"/reports/{report_id}")

    result = {"report_id": report_id, "action": "deleted"}

    if audit_logger:
        audit_logger.log(
            target=target_name,
            operation="delete_report",
            resource=f"report/{report_id}",
            skill="aria",
            parameters={"report_id": report_id},
            result="ok",
        )

    return result
