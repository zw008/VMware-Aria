"""Aria Operations platform health: node status and collector group status.

All API responses pass through sanitize() to strip control characters and limit length.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vmware_policy import sanitize

if TYPE_CHECKING:
    from vmware_aria.connection import AriaClient

_log = logging.getLogger("vmware-aria.ops.health")


# ---------------------------------------------------------------------------
# get_aria_health
# ---------------------------------------------------------------------------


def get_aria_health(client: AriaClient) -> dict:
    """Check the health status of the Aria Operations platform itself.

    Queries the deployment node status endpoint to determine if all
    Aria Ops internal services are running correctly.

    Args:
        client: Authenticated Aria Operations API client.

    Returns:
        Dict with overall_status (ONLINE/OFFLINE), healthy bool,
        system_time_ms, and details. Note: the endpoint itself returns
        HTTP 503 when the node is offline.
    """
    # NodeStatus per spec contains exactly: status ("ONLINE" when all
    # services run, else "OFFLINE"), systemTime, and optional details /
    # humanlyReadableSystemTime. The old code read invented fields
    # (clusterStatus.clusterVipAddress as "overall_status" — an IP address,
    # and a services[] array that does not exist). 2026-06-08 user report.
    data = client.get("/deployment/node/status")

    status = sanitize(data.get("status", ""))
    return {
        "overall_status": status,
        "healthy": status == "ONLINE",
        "system_time_ms": data.get("systemTime", None),
        "details": sanitize(str(data.get("details", "")), max_len=500),
    }


# ---------------------------------------------------------------------------
# list_collector_groups
# ---------------------------------------------------------------------------


def list_collector_groups(client: AriaClient) -> list[dict]:
    """List collector groups and their member collector status.

    Collector groups manage the remote collection agents (vRealize Operations
    Collector) that gather metrics from monitored environments.

    Args:
        client: Authenticated Aria Operations API client.

    Returns:
        List of collector group dicts with name, id, and member collector status.
    """
    data = client.get("/collectorgroups")
    groups = data.get("collectorGroups", [])

    return [
        {
            "id": sanitize(g.get("id", "")),
            "name": sanitize(g.get("name", "")),
            "description": sanitize(g.get("description", ""), max_len=300),
            "collector_count": len(g.get("collectors", [])),
            "collectors": [
                {
                    "id": sanitize(c.get("id", "")),
                    "name": sanitize(c.get("name", "")),
                    "state": sanitize(c.get("state", "")),
                    "type": sanitize(c.get("collectorType", "")),
                    "host": sanitize(c.get("hostname", "")),
                }
                for c in g.get("collectors", [])
            ],
        }
        for g in groups
    ]
