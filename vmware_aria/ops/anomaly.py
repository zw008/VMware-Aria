"""Aria Operations anomaly signals: per-resource anomaly metric and risk badge.

2026-06-08 spec audit: the suite-api has NO anomaly listing endpoints —
the previously used /anomalies and /resources/{id}/anomalies paths never
existed (the UI's "anomalous metrics" view is not part of the public API),
and /resources/{id}/badge/* endpoints don't exist either. The real signals
are the "System Attributes|anomaly" metric (active-anomaly count per
resource) and the badges[] array on the ResourceDto.

All API responses pass through sanitize() to strip control characters.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vmware_policy import sanitize

if TYPE_CHECKING:
    from vmware_aria.connection import AriaClient

_log = logging.getLogger("vmware-aria.ops.anomaly")

_ANOMALY_STAT_KEY = "System Attributes|anomaly"


# ---------------------------------------------------------------------------
# list_anomalies
# ---------------------------------------------------------------------------


def list_anomalies(
    client: AriaClient,
    resource_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Report per-resource anomaly counts from the System Attributes metric.

    The public suite-api does not expose the UI's anomalous-metrics list;
    the available signal is the "System Attributes|anomaly" metric (count of
    currently anomalous metrics per resource). With resource_id, returns the
    count for that resource; without it, scans up to ``limit`` VirtualMachine
    resources and returns those with a non-zero anomaly count, sorted
    descending. For root-cause detail, follow up with get_alert/list_alerts.

    Args:
        client: Authenticated Aria Operations API client.
        resource_id: Optional resource UUID to scope the query.
        limit: Maximum number of resources to scan when listing (1–100).

    Returns:
        List of dicts with resource id, name, and anomaly_count (latest value;
        None when the metric has no data for the resource).
    """
    limit = max(1, min(limit, 100))

    if resource_id:
        targets = {resource_id: ""}
    else:
        listing = client.get(
            "/resources", params={"resourceKind": "VirtualMachine", "pageSize": limit}
        )
        targets = {
            r.get("identifier", ""): sanitize(r.get("resourceKey", {}).get("name", ""))
            for r in listing.get("resourceList", [])
        }

    results = []
    for rid, name in targets.items():
        if not rid:
            continue
        data = client.get(
            f"/resources/{rid}/stats/latest", params={"statKey": _ANOMALY_STAT_KEY}
        )
        count = None
        for value_entry in data.get("values", []):
            stat_container = value_entry.get("stat-list") or value_entry.get("statList") or {}
            for stat in stat_container.get("stat", []):
                points = stat.get("data", [])
                if points:
                    count = points[-1]
        results.append(
            {
                "resource_id": sanitize(rid),
                "resource_name": name,
                "anomaly_count": count,
                "metric_key": _ANOMALY_STAT_KEY,
            }
        )

    if resource_id:
        return results
    flagged = [r for r in results if r["anomaly_count"]]
    flagged.sort(key=lambda r: r["anomaly_count"] or 0, reverse=True)
    return flagged


# ---------------------------------------------------------------------------
# get_resource_riskbadge
# ---------------------------------------------------------------------------


def get_resource_riskbadge(client: AriaClient, resource_id: str) -> dict:
    """Get the risk badge score for a resource.

    The risk badge reflects the likelihood of a future performance or
    availability problem, scored 0–100 (higher = more risk; -1 = unknown).
    Badges come from the badges[] array on the ResourceDto — there is no
    /badge/risk endpoint in the suite-api.

    Args:
        client: Authenticated Aria Operations API client.
        resource_id: The resource UUID.

    Returns:
        Dict with risk score and color. For contributing causes, inspect the
        resource's active alerts via list_alerts(resource_id=...).
    """
    if not resource_id:
        raise ValueError("resource_id must not be empty")

    data = client.get(f"/resources/{resource_id}")
    risk = next(
        (b for b in data.get("badges", []) if b.get("type") == "RISK"),
        {},
    )
    return {
        "resource_id": resource_id,
        "risk_score": risk.get("score", None),
        "risk_color": sanitize(risk.get("color", "")),
    }
