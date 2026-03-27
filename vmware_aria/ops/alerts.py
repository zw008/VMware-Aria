"""Aria Operations alert management: list, get, acknowledge, cancel, list definitions.

Write operations (acknowledge, cancel) are audit-logged.
All API responses pass through _sanitize() to strip control characters.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vmware_aria.connection import AriaClient
    from vmware_aria.notify.audit import AuditLogger

_log = logging.getLogger("vmware-aria.ops.alerts")

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

_VALID_CRITICALITIES = {"INFORMATION", "WARNING", "IMMEDIATE", "CRITICAL"}


def _sanitize(text: str, max_len: int = 500) -> str:
    """Strip control characters and truncate to max_len."""
    if not text:
        return text
    return _CONTROL_CHAR_RE.sub("", text[:max_len])


# ---------------------------------------------------------------------------
# list_alerts
# ---------------------------------------------------------------------------


def list_alerts(
    client: AriaClient,
    active_only: bool = True,
    criticality: str | None = None,
    resource_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """List alerts from Aria Operations.

    Args:
        client: Authenticated Aria Operations API client.
        active_only: Return only active (non-cancelled) alerts.
        criticality: Filter by criticality: INFORMATION, WARNING, IMMEDIATE, CRITICAL.
        resource_id: Scope alerts to a specific resource UUID.
        limit: Maximum number of alerts to return (1–500).

    Returns:
        List of alert summary dicts.
    """
    if criticality and criticality.upper() not in _VALID_CRITICALITIES:
        raise ValueError(
            f"Invalid criticality '{criticality}'. "
            f"Must be one of: {', '.join(sorted(_VALID_CRITICALITIES))}"
        )

    limit = max(1, min(limit, 500))
    params: dict[str, Any] = {"pageSize": limit}
    if active_only:
        params["status"] = "ACTIVE"
    if criticality:
        params["criticality"] = criticality.upper()
    if resource_id:
        params["resourceId"] = resource_id

    data = client.get("/alerts", params=params)
    items = data.get("alerts", [])

    return [
        {
            "id": _sanitize(a.get("alertId", "")),
            "name": _sanitize(a.get("alertName", ""), max_len=300),
            "criticality": _sanitize(a.get("criticality", "")),
            "status": _sanitize(a.get("status", "")),
            "alert_impact": _sanitize(a.get("alertImpact", "")),
            "resource_id": _sanitize(a.get("resourceId", "")),
            "resource_name": _sanitize(a.get("resourceName", ""), max_len=300),
            "start_time_ms": a.get("startTimeUTC", None),
            "update_time_ms": a.get("updateTimeUTC", None),
            "alert_definition_id": _sanitize(a.get("alertDefinitionId", "")),
            "control_state": _sanitize(a.get("controlState", "")),
            "info": _sanitize(a.get("info", ""), max_len=500),
        }
        for a in items
    ]


# ---------------------------------------------------------------------------
# get_alert
# ---------------------------------------------------------------------------


def get_alert(client: AriaClient, alert_id: str) -> dict:
    """Get full details for a specific alert.

    Args:
        client: Authenticated Aria Operations API client.
        alert_id: The alert UUID.

    Returns:
        Dict with alert details, symptom list, and recommendation.
    """
    if not alert_id:
        raise ValueError("alert_id must not be empty")

    data = client.get(f"/alerts/{alert_id}")
    return {
        "id": _sanitize(data.get("alertId", "")),
        "name": _sanitize(data.get("alertName", ""), max_len=300),
        "criticality": _sanitize(data.get("criticality", "")),
        "status": _sanitize(data.get("status", "")),
        "alert_impact": _sanitize(data.get("alertImpact", "")),
        "resource_id": _sanitize(data.get("resourceId", "")),
        "resource_name": _sanitize(data.get("resourceName", ""), max_len=300),
        "start_time_ms": data.get("startTimeUTC", None),
        "update_time_ms": data.get("updateTimeUTC", None),
        "cancel_time_ms": data.get("cancelTimeUTC", None),
        "info": _sanitize(data.get("info", ""), max_len=500),
        "control_state": _sanitize(data.get("controlState", "")),
        "alert_definition_id": _sanitize(data.get("alertDefinitionId", "")),
        "alert_definition_name": _sanitize(data.get("alertDefinitionName", ""), max_len=300),
        "symptoms": [
            {
                "id": _sanitize(s.get("symptomId", "")),
                "name": _sanitize(s.get("symptomName", ""), max_len=300),
                "state": _sanitize(s.get("state", "")),
                "severity": _sanitize(s.get("severity", "")),
            }
            for s in data.get("alertSymptomList", [])
        ],
        "recommendations": [
            _sanitize(r.get("recommendationText", ""), max_len=1000)
            for r in data.get("alertRecommendationList", [])
        ],
    }


# ---------------------------------------------------------------------------
# acknowledge_alert
# ---------------------------------------------------------------------------


def acknowledge_alert(
    client: AriaClient,
    alert_id: str,
    audit_logger: AuditLogger | None = None,
    target_name: str = "default",
) -> dict:
    """Acknowledge an active alert (sets control state to ACKNOWLEDGED).

    Args:
        client: Authenticated Aria Operations API client.
        alert_id: The alert UUID to acknowledge.
        audit_logger: Optional audit logger; operation is logged if provided.
        target_name: Target name for audit log record.

    Returns:
        Dict confirming the acknowledgement with alert id and new control_state.
    """
    if not alert_id:
        raise ValueError("alert_id must not be empty")

    # Capture before state
    before = {}
    try:
        before = get_alert(client, alert_id)
    except Exception as exc:
        _log.warning("Could not retrieve before-state for alert %s: %s", alert_id, exc)

    client.post(f"/alerts/{alert_id}/acknowledge")

    result = {
        "alert_id": alert_id,
        "action": "acknowledged",
        "control_state": "ACKNOWLEDGED",
    }

    if audit_logger:
        audit_logger.log(
            target=target_name,
            operation="acknowledge",
            resource=f"alert/{alert_id}",
            skill="aria",
            parameters={"alert_id": alert_id},
            before_state=before,
            after_state=result,
            result="ok",
        )

    return result


# ---------------------------------------------------------------------------
# cancel_alert
# ---------------------------------------------------------------------------


def cancel_alert(
    client: AriaClient,
    alert_id: str,
    audit_logger: AuditLogger | None = None,
    target_name: str = "default",
) -> dict:
    """Cancel (dismiss) an active alert.

    Args:
        client: Authenticated Aria Operations API client.
        alert_id: The alert UUID to cancel.
        audit_logger: Optional audit logger; operation is logged if provided.
        target_name: Target name for audit log record.

    Returns:
        Dict confirming the cancellation.
    """
    if not alert_id:
        raise ValueError("alert_id must not be empty")

    before = {}
    try:
        before = get_alert(client, alert_id)
    except Exception as exc:
        _log.warning("Could not retrieve before-state for alert %s: %s", alert_id, exc)

    client.delete(f"/alerts/{alert_id}")

    result = {
        "alert_id": alert_id,
        "action": "cancelled",
        "status": "CANCELLED",
    }

    if audit_logger:
        audit_logger.log(
            target=target_name,
            operation="cancel",
            resource=f"alert/{alert_id}",
            skill="aria",
            parameters={"alert_id": alert_id},
            before_state=before,
            after_state=result,
            result="ok",
        )

    return result


# ---------------------------------------------------------------------------
# list_alert_definitions
# ---------------------------------------------------------------------------


def list_alert_definitions(
    client: AriaClient,
    name_filter: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """List alert definitions (templates that generate alerts).

    Args:
        client: Authenticated Aria Operations API client.
        name_filter: Optional substring filter on definition name (case-insensitive).
        limit: Maximum number of definitions to return (1–500).

    Returns:
        List of alert definition summary dicts.
    """
    limit = max(1, min(limit, 500))
    data = client.get("/alertdefinitions", params={"pageSize": limit})
    items = data.get("alertDefinitions", [])

    results = []
    for d in items:
        name = _sanitize(d.get("name", ""), max_len=300)
        if name_filter and name_filter.lower() not in name.lower():
            continue
        results.append(
            {
                "id": _sanitize(d.get("id", "")),
                "name": name,
                "description": _sanitize(d.get("description", ""), max_len=500),
                "adapter_kind": _sanitize(d.get("adapterKindKey", "")),
                "resource_kind": _sanitize(d.get("resourceKindKey", "")),
                "criticality": _sanitize(d.get("criticality", "")),
                "impact": _sanitize(d.get("impact", {}).get("impactType", "")),
                "type": _sanitize(d.get("type", "")),
                "sub_type": _sanitize(d.get("subType", "")),
                "enabled": d.get("active", True),
            }
        )
    return results
