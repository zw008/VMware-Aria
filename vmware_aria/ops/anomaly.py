"""Aria Operations anomaly detection: list anomalies and get risk badge scores.

All API responses pass through _sanitize() to strip control characters and limit length.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vmware_aria.connection import AriaClient

_log = logging.getLogger("vmware-aria.ops.anomaly")

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _sanitize(text: str, max_len: int = 500) -> str:
    """Strip control characters and truncate to max_len."""
    if not text:
        return text
    return _CONTROL_CHAR_RE.sub("", text[:max_len])


# ---------------------------------------------------------------------------
# list_anomalies
# ---------------------------------------------------------------------------


def list_anomalies(
    client: AriaClient,
    resource_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List anomalies detected by Aria Operations.

    If resource_id is provided, returns anomalies scoped to that resource.
    Otherwise returns global anomalies across all monitored resources.

    Args:
        client: Authenticated Aria Operations API client.
        resource_id: Optional resource UUID to scope the query.
        limit: Maximum number of anomalies to return (1–200).

    Returns:
        List of anomaly dicts with metric, deviation, and resource info.
    """
    limit = max(1, min(limit, 200))
    params: dict[str, Any] = {"pageSize": limit}

    if resource_id:
        path = f"/resources/{resource_id}/anomalies"
    else:
        path = "/anomalies"

    data = client.get(path, params=params)
    items = data.get("anomalies", [])

    return [
        {
            "id": _sanitize(a.get("anomalyId", "")),
            "resource_id": _sanitize(a.get("resourceId", "")),
            "resource_name": _sanitize(a.get("resourceName", ""), max_len=300),
            "metric_key": _sanitize(a.get("metricKey", "")),
            "anomaly_type": _sanitize(a.get("anomalyType", "")),
            "start_time_ms": a.get("startTimeUTC", None),
            "end_time_ms": a.get("endTimeUTC", None),
            "observed_value": a.get("observedValue", None),
            "expected_value": a.get("expectedValue", None),
            "deviation": a.get("deviation", None),
            "severity": _sanitize(a.get("severity", "")),
            "description": _sanitize(a.get("description", ""), max_len=500),
        }
        for a in items
    ]


# ---------------------------------------------------------------------------
# get_resource_riskbadge
# ---------------------------------------------------------------------------


def get_resource_riskbadge(client: AriaClient, resource_id: str) -> dict:
    """Get the risk badge score and breakdown for a resource.

    The risk badge reflects the likelihood of a future performance or
    availability problem, scored 0–100 (higher = more risk).

    Args:
        client: Authenticated Aria Operations API client.
        resource_id: The resource UUID.

    Returns:
        Dict with overall risk score, color, and contributing risk factors.
    """
    if not resource_id:
        raise ValueError("resource_id must not be empty")

    data = client.get(f"/resources/{resource_id}/badge/risk")
    return {
        "resource_id": resource_id,
        "risk_score": data.get("score", None),
        "risk_color": _sanitize(data.get("color", "")),
        "risk_description": _sanitize(data.get("description", ""), max_len=500),
        "contributing_causes": [
            {
                "metric": _sanitize(c.get("metric", "")),
                "cause": _sanitize(c.get("cause", ""), max_len=300),
                "score": c.get("score", None),
            }
            for c in data.get("causes", [])
        ],
    }
