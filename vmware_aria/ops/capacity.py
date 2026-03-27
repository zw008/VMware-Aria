"""Aria Operations capacity planning: overview, remaining capacity, time remaining, rightsizing.

All API responses pass through _sanitize() to strip control characters and limit length.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vmware_aria.connection import AriaClient

_log = logging.getLogger("vmware-aria.ops.capacity")

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _sanitize(text: str, max_len: int = 500) -> str:
    """Strip control characters and truncate to max_len."""
    if not text:
        return text
    return _CONTROL_CHAR_RE.sub("", text[:max_len])


# ---------------------------------------------------------------------------
# get_capacity_overview
# ---------------------------------------------------------------------------


def get_capacity_overview(client: AriaClient, cluster_id: str) -> dict:
    """Get capacity recommendations and utilization overview for a cluster.

    Args:
        client: Authenticated Aria Operations API client.
        cluster_id: The cluster resource UUID.

    Returns:
        Dict with capacity recommendations, demand, and waste metrics.
    """
    if not cluster_id:
        raise ValueError("cluster_id must not be empty")

    data = client.get(f"/resources/{cluster_id}/recommendations")
    recs = data.get("recommendation", [])
    return {
        "resource_id": cluster_id,
        "recommendation_count": len(recs),
        "recommendations": [
            {
                "id": _sanitize(r.get("recommendationId", "")),
                "type": _sanitize(r.get("type", "")),
                "description": _sanitize(r.get("description", ""), max_len=1000),
                "impact": _sanitize(r.get("impact", "")),
                "reasoning": _sanitize(r.get("reasoning", ""), max_len=1000),
            }
            for r in recs
        ],
    }


# ---------------------------------------------------------------------------
# get_remaining_capacity
# ---------------------------------------------------------------------------


def get_remaining_capacity(client: AriaClient, resource_id: str) -> dict:
    """Get remaining capacity metrics for a resource (cluster or host).

    Reports how much additional workload can be added before running out of
    CPU, memory, disk, or network capacity.

    Args:
        client: Authenticated Aria Operations API client.
        resource_id: The resource UUID (typically a ClusterComputeResource).

    Returns:
        Dict with remaining capacity values per resource dimension.
    """
    if not resource_id:
        raise ValueError("resource_id must not be empty")

    data = client.get(f"/resources/{resource_id}/remainingcapacity")
    capacities = data.get("remainingCapacity", [])
    return {
        "resource_id": resource_id,
        "remaining_capacity": [
            {
                "metric": _sanitize(c.get("metric", "")),
                "remaining_value": c.get("remainingValue", None),
                "unit": _sanitize(c.get("unit", "")),
                "usable_capacity": c.get("usableCapacity", None),
                "used_capacity": c.get("usedCapacity", None),
                "demand": c.get("demandValue", None),
            }
            for c in capacities
        ],
    }


# ---------------------------------------------------------------------------
# get_time_remaining
# ---------------------------------------------------------------------------


def get_time_remaining(client: AriaClient, resource_id: str) -> dict:
    """Get time-remaining-until-full predictions for a resource.

    Aria Operations projects when each capacity dimension (CPU, memory, disk)
    will be exhausted based on current usage trends.

    Args:
        client: Authenticated Aria Operations API client.
        resource_id: The resource UUID (typically a ClusterComputeResource).

    Returns:
        Dict with predicted exhaustion time per capacity dimension.
    """
    if not resource_id:
        raise ValueError("resource_id must not be empty")

    data = client.get(f"/resources/{resource_id}/timeremaining")
    predictions = data.get("timeRemaining", [])
    return {
        "resource_id": resource_id,
        "time_remaining": [
            {
                "metric": _sanitize(p.get("metric", "")),
                "time_remaining_days": p.get("timeRemainingInDays", None),
                "confidence": p.get("confidence", None),
                "projected_full_date_ms": p.get("projectedFullDate", None),
            }
            for p in predictions
        ],
    }


# ---------------------------------------------------------------------------
# list_rightsizing_recommendations
# ---------------------------------------------------------------------------


def list_rightsizing_recommendations(
    client: AriaClient,
    resource_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List VM rightsizing recommendations (over-provisioned or under-provisioned).

    Args:
        client: Authenticated Aria Operations API client.
        resource_id: Optional VM resource UUID to scope recommendations.
        limit: Maximum number of recommendations to return (1–200).

    Returns:
        List of rightsizing recommendation dicts with VM name, current config,
        and recommended config changes.
    """
    limit = max(1, min(limit, 200))
    params: dict = {"pageSize": limit}
    if resource_id:
        params["resourceId"] = resource_id

    data = client.get("/recommendations/rightsizing", params=params)
    items = data.get("recommendations", [])

    return [
        {
            "id": _sanitize(r.get("id", "")),
            "resource_id": _sanitize(r.get("resourceId", "")),
            "resource_name": _sanitize(r.get("resourceName", ""), max_len=300),
            "recommendation_type": _sanitize(r.get("type", "")),
            "description": _sanitize(r.get("description", ""), max_len=500),
            "current_cpu_count": r.get("currentCpuCount", None),
            "recommended_cpu_count": r.get("recommendedCpuCount", None),
            "current_memory_mb": r.get("currentMemoryMB", None),
            "recommended_memory_mb": r.get("recommendedMemoryMB", None),
            "projected_waste_cpu": r.get("projectedCpuWaste", None),
            "projected_waste_memory_mb": r.get("projectedMemoryWasteMB", None),
            "confidence": r.get("confidence", None),
        }
        for r in items
    ]
