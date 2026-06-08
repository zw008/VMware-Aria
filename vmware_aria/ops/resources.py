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

# URL-length protection for GET /resources/stats/topn: each resourceId adds
# ~40 chars to the query string; >100 IDs risks HTTP 414 (URI Too Long).
_TOPN_MAX_RESOURCE_IDS = 100


def _badges_by_type(dto: dict) -> dict[str, dict]:
    """Index the ResourceDto badges[] array ({type, color, score}) by type.

    The wire field is ``badges`` (array, type enum HEALTH/RISK/EFFICIENCY) —
    there is no singular ``badge`` object (2026-06-08 spec audit).
    """
    return {b.get("type", ""): b for b in dto.get("badges") or []}



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
        health = _badges_by_type(r).get("HEALTH", {})
        results.append(
            {
                "id": sanitize(r.get("identifier", "")),
                "name": name,
                "kind": sanitize(r.get("resourceKey", {}).get("resourceKindKey", "")),
                "adapter_kind": sanitize(r.get("resourceKey", {}).get("adapterKindKey", "")),
                "health_color": sanitize(health.get("color", "")),
                "health_score": health.get("score", None),
                # guard: API may return "resourceStatusStates": [] (key present, empty)
                "status": sanitize((r.get("resourceStatusStates") or [{}])[0].get("resourceState", "")),
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
    badges = _badges_by_type(data)
    health = badges.get("HEALTH", {})
    risk = badges.get("RISK", {})
    efficiency = badges.get("EFFICIENCY", {})
    return {
        "id": sanitize(data.get("identifier", "")),
        "name": sanitize(key.get("name", "")),
        "kind": sanitize(key.get("resourceKindKey", "")),
        "adapter_kind": sanitize(key.get("adapterKindKey", "")),
        "description": sanitize(data.get("description", ""), max_len=1000),
        "health_color": sanitize(health.get("color", "")),
        "health_score": health.get("score", None),
        "risk_color": sanitize(risk.get("color", "")),
        "risk_score": risk.get("score", None),
        "efficiency_color": sanitize(efficiency.get("color", "")),
        "efficiency_score": efficiency.get("score", None),
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

    # Per StatQuery spec: statKey is an array of plain strings, and the
    # interval count field is `intervalQuantifier` (2026-06-08 user report:
    # we sent [{"key": ...}] objects and `intervalQuantity`, both rejected).
    payload: dict[str, Any] = {
        "resourceId": [resource_id],
        "statKey": list(metric_keys),
        "begin": begin_time_ms,
        "end": end_time_ms,
        "rollUpType": rollup_type.upper(),
        "intervalType": interval_type.upper(),
        "intervalQuantifier": interval_quantity,
    }

    data = client.post(f"/resources/{resource_id}/stats/query", json_data=payload)

    # Response nests stats under values[].stat-list.stat[] (hyphenated wire
    # key; some renderings show statList — parse both defensively).
    result: dict[str, list[dict]] = {}
    for value_entry in data.get("values", []):
        stat_container = value_entry.get("stat-list") or value_entry.get("statList") or {}
        for stat in stat_container.get("stat", []):
            key = sanitize(stat.get("statKey", {}).get("key", ""))
            timestamps = stat.get("timestamps", [])
            values = stat.get("data", [])
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

    # suite-api has no /resources/{id}/badge/* endpoints — badges come back
    # as the badges[] array on the ResourceDto (2026-06-08 spec audit).
    data = client.get(f"/resources/{resource_id}")
    badges = {b.get("type", ""): b for b in data.get("badges", [])}

    def _badge(kind: str) -> dict:
        b = badges.get(kind, {})
        return {"score": b.get("score", None), "color": sanitize(b.get("color", ""))}

    health = _badge("HEALTH")
    risk = _badge("RISK")
    efficiency = _badge("EFFICIENCY")
    return {
        "resource_id": resource_id,
        "health_score": health["score"],
        "health_color": health["color"],
        "risk_score": risk["score"],
        "risk_color": risk["color"],
        "efficiency_score": efficiency["score"],
        "efficiency_color": efficiency["color"],
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

    # POST /resources/query/topn does not exist in the suite-api (2026-06-08
    # user report). The real endpoint is GET /resources/stats/topn, which has
    # no resourceKind parameter — resolve candidate resource IDs first, then
    # rank them.
    listing = client.get(
        "/resources", params={"resourceKind": resource_kind, "pageSize": 200}
    )
    candidates = listing.get("resourceList", [])
    if not candidates:
        return []
    if len(candidates) > _TOPN_MAX_RESOURCE_IDS:
        _log.warning(
            "Truncating topn candidate list from %d to %d resources "
            "(URL length limit — HTTP 414 risk)",
            len(candidates),
            _TOPN_MAX_RESOURCE_IDS,
        )
        candidates = candidates[:_TOPN_MAX_RESOURCE_IDS]
    names = {
        r.get("identifier", ""): sanitize(r.get("resourceKey", {}).get("name", ""))
        for r in candidates
    }

    import time as _time

    end_ms = int(_time.time() * 1000)
    params: dict[str, Any] = {
        "resourceId": list(names.keys()),
        "statKey": metric_key,
        "topN": top_n,
        "begin": end_ms - 3_600_000,
        "end": end_ms,
        "rollUpType": "AVG",
        "intervalType": "MINUTES",
        "intervalQuantifier": 5,
        "sortOrder": "DESCENDING",
        "groupBy": "RESOURCE",
    }
    data = client.get("/resources/stats/topn", params=params)

    results = []
    for group in data.get("resourceStatGroups", []):
        rid = group.get("groupKey", "")
        latest_value = None
        # Each resourceStats[] element is {resourceId, stat: {statKey,
        # timestamps, data}} — the data array nests under `stat`.
        for entry in group.get("resourceStats", []):
            points = entry.get("stat", {}).get("data", [])
            if points:
                latest_value = points[-1]
        results.append(
            {
                "id": sanitize(rid),
                "name": names.get(rid, ""),
                "metric_key": metric_key,
                "value": latest_value,
            }
        )
    return results[:top_n]
