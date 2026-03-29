"""Aria Operations resource queries: list, get details, metrics, health, top consumers.

All API responses pass through sanitize() to strip control characters and limit length.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from vmware_policy import sanitize

if TYPE_CHECKING:
    from vmware_aria.connection import AriaClient

_log = logging.getLogger("vmware-aria.ops.resources")

# Valid resource kinds recognised by Aria Operations
_VALID_RESOURCE_KINDS = {
    "VirtualMachine",
    "HostSystem",
    "ClusterComputeResource",
    "Datastore",
    "Datacenter",
    "ResourcePool",
    "vSphere World",
}

_VALID_SORT_METRICS = {
    "cpu|usage_average",
    "mem|usage_average",
    "cpu|demand_average",
    "mem|workload",
    "disk|usage_average",
    "net|usage_average",
}



# ---------------------------------------------------------------------------
# list_resources
# ---------------------------------------------------------------------------


def list_resources(
    client: AriaClient,
    resource_kind: str = "VirtualMachine",
    limit: int = 100,
    name_filter: str | None = None,
) -> list[dict]:
    """List resources of a given kind from Aria Operations.

    Args:
        client: Authenticated Aria Operations API client.
        resource_kind: Resource kind to list (e.g. VirtualMachine, HostSystem).
        limit: Maximum number of results to return (1–500).
        name_filter: Optional substring filter on resource name (case-insensitive).

    Returns:
        List of resource summary dicts with id, name, kind, and health badge.
    """
    if resource_kind not in _VALID_RESOURCE_KINDS:
        _log.warning("Unknown resource_kind '%s', proceeding anyway", resource_kind)

    limit = max(1, min(limit, 500))
    params: dict[str, Any] = {"resourceKind": resource_kind, "pageSize": limit}
    data = client.get("/resources", params=params)

    items = data.get("resourceList", [])
    results = []
    for r in items:
        name = sanitize(r.get("resourceKey", {}).get("name", ""))
        if name_filter and name_filter.lower() not in name.lower():
            continue
        results.append(
            {
                "id": sanitize(r.get("identifier", "")),
                "name": name,
                "kind": sanitize(r.get("resourceKey", {}).get("resourceKindKey", "")),
                "adapter_kind": sanitize(r.get("resourceKey", {}).get("adapterKindKey", "")),
                "health_color": sanitize(r.get("badge", {}).get("health", {}).get("color", "")),
                "health_score": r.get("badge", {}).get("health", {}).get("score", None),
                "status": sanitize(r.get("resourceStatusStates", [{}])[0].get("resourceState", "")),
            }
        )
    return results


# ---------------------------------------------------------------------------
# get_resource
# ---------------------------------------------------------------------------


def get_resource(client: AriaClient, resource_id: str) -> dict:
    """Get full details for a specific resource.

    Args:
        client: Authenticated Aria Operations API client.
        resource_id: The resource UUID.

    Returns:
        Dict with resource key, identifiers, health badge, and relationships.
    """
    if not resource_id:
        raise ValueError("resource_id must not be empty")

    data = client.get(f"/resources/{resource_id}")
    key = data.get("resourceKey", {})
    badge = data.get("badge", {})
    return {
        "id": sanitize(data.get("identifier", "")),
        "name": sanitize(key.get("name", "")),
        "kind": sanitize(key.get("resourceKindKey", "")),
        "adapter_kind": sanitize(key.get("adapterKindKey", "")),
        "description": sanitize(data.get("description", ""), max_len=1000),
        "health_color": sanitize(badge.get("health", {}).get("color", "")),
        "health_score": badge.get("health", {}).get("score", None),
        "risk_color": sanitize(badge.get("risk", {}).get("color", "")),
        "risk_score": badge.get("risk", {}).get("score", None),
        "efficiency_color": sanitize(badge.get("efficiency", {}).get("color", "")),
        "efficiency_score": badge.get("efficiency", {}).get("score", None),
        "identifiers": {
            sanitize(ident.get("identifierType", {}).get("name", "")): sanitize(ident.get("value", ""))
            for ident in data.get("resourceKey", {}).get("resourceIdentifiers", [])
        },
        "status_states": [
            {
                "state": sanitize(s.get("resourceState", "")),
                "status": sanitize(s.get("resourceStatus", "")),
            }
            for s in data.get("resourceStatusStates", [])
        ],
    }


# ---------------------------------------------------------------------------
# get_resource_metrics
# ---------------------------------------------------------------------------


def get_resource_metrics(
    client: AriaClient,
    resource_id: str,
    metric_keys: list[str],
    begin_time_ms: int | None = None,
    end_time_ms: int | None = None,
    rollup_type: str = "AVG",
    interval_type: str = "MINUTES",
    interval_quantity: int = 5,
) -> dict:
    """Fetch time-series metric stats for a resource.

    Args:
        client: Authenticated Aria Operations API client.
        resource_id: The resource UUID.
        metric_keys: List of metric keys, e.g. ["cpu|usage_average", "mem|usage_average"].
        begin_time_ms: Start of query window (epoch ms). Defaults to 1 hour ago.
        end_time_ms: End of query window (epoch ms). Defaults to now.
        rollup_type: Aggregation type: AVG, MAX, MIN, SUM, COUNT, LATEST.
        interval_type: MINUTES, HOURS, DAYS, WEEKS, MONTHS.
        interval_quantity: Number of interval_type units per data point.

    Returns:
        Dict keyed by metric_key mapping to a list of {timestamp, value} points.
    """
    if not resource_id:
        raise ValueError("resource_id must not be empty")
    if not metric_keys:
        raise ValueError("metric_keys must not be empty")

    import time as _time

    if end_time_ms is None:
        end_time_ms = int(_time.time() * 1000)
    if begin_time_ms is None:
        begin_time_ms = end_time_ms - 3_600_000  # 1 hour

    payload: dict[str, Any] = {
        "resourceId": [resource_id],
        "statKey": [{"key": k} for k in metric_keys],
        "begin": begin_time_ms,
        "end": end_time_ms,
        "rollUpType": rollup_type.upper(),
        "intervalType": interval_type.upper(),
        "intervalQuantity": interval_quantity,
    }

    data = client.post(f"/resources/{resource_id}/stats/query", json_data=payload)

    result: dict[str, list[dict]] = {}
    for stat_list in data.get("values", []):
        key = sanitize(stat_list.get("statKey", {}).get("key", ""))
        timestamps = stat_list.get("timestamps", [])
        values = stat_list.get("data", [])
        result[key] = [
            {"timestamp_ms": ts, "value": v}
            for ts, v in zip(timestamps, values)
        ]
    return result


# ---------------------------------------------------------------------------
# get_resource_health
# ---------------------------------------------------------------------------


def get_resource_health(client: AriaClient, resource_id: str) -> dict:
    """Get health badge scores for a resource (health, risk, efficiency).

    Args:
        client: Authenticated Aria Operations API client.
        resource_id: The resource UUID.

    Returns:
        Dict with health, risk, and efficiency scores and colors.
    """
    if not resource_id:
        raise ValueError("resource_id must not be empty")

    data = client.get(f"/resources/{resource_id}/badge/health")
    return {
        "resource_id": resource_id,
        "health_score": data.get("score", None),
        "health_color": sanitize(data.get("color", "")),
        "health_description": sanitize(data.get("description", ""), max_len=500),
        "health_degraded_by": sanitize(data.get("degradedBy", ""), max_len=500),
    }


# ---------------------------------------------------------------------------
# get_top_consumers
# ---------------------------------------------------------------------------


def get_top_consumers(
    client: AriaClient,
    metric_key: str = "cpu|usage_average",
    resource_kind: str = "VirtualMachine",
    top_n: int = 10,
) -> list[dict]:
    """Query the resources with highest consumption of a given metric.

    Args:
        client: Authenticated Aria Operations API client.
        metric_key: The metric to rank by (e.g. cpu|usage_average, mem|usage_average).
        resource_kind: Resource kind to scope the query.
        top_n: Number of top consumers to return (max 50).

    Returns:
        List of dicts with resource id, name, and latest metric value, sorted descending.
    """
    top_n = max(1, min(top_n, 50))

    payload: dict[str, Any] = {
        "resourceKind": resource_kind,
        "statKey": metric_key,
        "maxResults": top_n,
        "rollupType": "AVG",
        "intervalType": "MINUTES",
        "intervalQuantity": 5,
    }

    data = client.post("/resources/query/topn", json_data=payload)

    results = []
    for item in data.get("resourceList", []):
        results.append(
            {
                "id": sanitize(item.get("identifier", "")),
                "name": sanitize(item.get("resourceKey", {}).get("name", "")),
                "metric_key": metric_key,
                "value": item.get("dtValue", None),
                "unit": sanitize(item.get("unit", "")),
            }
        )
    return results
