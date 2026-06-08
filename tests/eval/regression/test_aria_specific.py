"""Aria-specific regression evals — 2026-06-08 external user report.

A user ran the MCP against a real Aria Operations instance: half the API
returned 404. Verification against the official suite-api spec confirmed
12 of their 14 claims plus 6 more invented endpoints in anomaly/capacity.
Each test below pins one fixed bug by exercising the real ops code with a
mocked AriaClient and asserting the request/parse shape the spec requires.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest


def _client() -> MagicMock:
    client = MagicMock(name="AriaClient")
    client.get.return_value = {}
    client.post.return_value = {}
    client.put.return_value = {}
    return client


# ── #1/#3: StatQuery statKey strings + intervalQuantifier ──────────────


def test_metrics_query_body_shape() -> None:
    from vmware_aria.ops.resources import get_resource_metrics

    client = _client()
    get_resource_metrics(client, "res-1", ["cpu|usage_average", "mem|usage_average"])

    path, = client.post.call_args.args
    body = client.post.call_args.kwargs["json_data"]
    assert path == "/resources/res-1/stats/query"
    assert body["statKey"] == ["cpu|usage_average", "mem|usage_average"], (
        "statKey must be an array of plain strings, not [{key: ...}] objects"
    )
    assert "intervalQuantifier" in body and "intervalQuantity" not in body


# ── #2: response parsing must traverse values[].stat-list.stat[] ───────


def test_metrics_response_parses_stat_list_nesting() -> None:
    from vmware_aria.ops.resources import get_resource_metrics

    client = _client()
    client.post.return_value = {
        "values": [
            {
                "resourceId": "res-1",
                "stat-list": {
                    "stat": [
                        {
                            "statKey": {"key": "cpu|usage_average"},
                            "timestamps": [1000, 2000],
                            "data": [1.5, 2.5],
                        }
                    ]
                },
            }
        ]
    }
    result = get_resource_metrics(client, "res-1", ["cpu|usage_average"])
    assert result["cpu|usage_average"] == [
        {"timestamp_ms": 1000, "value": 1.5},
        {"timestamp_ms": 2000, "value": 2.5},
    ]


# ── #4: topn must use GET /resources/stats/topn ────────────────────────


def test_top_consumers_uses_get_stats_topn() -> None:
    from vmware_aria.ops.resources import get_top_consumers

    client = _client()
    client.get.side_effect = [
        {"resourceList": [{"identifier": "vm-1", "resourceKey": {"name": "web-01"}}]},
        {
            "resourceStatGroups": [
                {
                    "groupKey": "vm-1",
                    # spec shape: data nests under `stat`
                    "resourceStats": [
                        {
                            "resourceId": "vm-1",
                            "stat": {"statKey": {"key": "cpu|usage_average"}, "data": [42.0]},
                        }
                    ],
                }
            ]
        },
    ]
    results = get_top_consumers(client, metric_key="cpu|usage_average", top_n=5)

    topn_call = client.get.call_args_list[1]
    assert topn_call.args[0] == "/resources/stats/topn"
    assert topn_call.kwargs["params"]["resourceId"] == ["vm-1"]
    assert "intervalQuantifier" in topn_call.kwargs["params"]
    client.post.assert_not_called()
    assert results[0] == {"id": "vm-1", "name": "web-01", "metric_key": "cpu|usage_average", "value": 42.0}


# ── #5: alert filtering must go through POST /alerts/query ─────────────


def test_list_alerts_uses_alert_query() -> None:
    from vmware_aria.ops.alerts import list_alerts

    client = _client()
    client.post.return_value = {"alerts": []}
    list_alerts(client, active_only=True, criticality="critical", resource_id="res-9")

    path, = client.post.call_args.args
    body = client.post.call_args.kwargs["json_data"]
    assert path == "/alerts/query"
    assert body["activeOnly"] is True
    assert body["alertCriticality"] == ["CRITICAL"]
    assert body["resource-query"] == {"resourceId": ["res-9"]}
    client.get.assert_not_called()


# ── #6/#7: alert actions via POST /alerts?action=... + uuids body ──────


def test_acknowledge_alert_uses_takeownership_action() -> None:
    from vmware_aria.ops.alerts import acknowledge_alert

    client = _client()
    client.get.return_value = {}
    result = acknowledge_alert(client, "alert-1")

    path, = client.post.call_args.args
    assert path == "/alerts"
    assert client.post.call_args.kwargs["params"] == {"action": "takeownership"}
    assert client.post.call_args.kwargs["json_data"] == {"uuids": ["alert-1"]}
    assert result["action"] == "takeownership"


def test_cancel_alert_uses_cancel_action() -> None:
    from vmware_aria.ops.alerts import cancel_alert

    client = _client()
    client.get.return_value = {}
    cancel_alert(client, "alert-2")

    path, = client.post.call_args.args
    assert path == "/alerts"
    assert client.post.call_args.kwargs["params"] == {"action": "cancel"}
    assert client.post.call_args.kwargs["json_data"] == {"uuids": ["alert-2"]}
    client.delete.assert_not_called()


# ── #8: alertdefinition enable/disable must be PUT ─────────────────────


def test_set_alert_definition_state_uses_put() -> None:
    from vmware_aria.ops.alerts import set_alert_definition_state

    client = _client()
    set_alert_definition_state(client, "def-1", enabled=True)
    assert client.put.call_args.args[0] == "/alertdefinitions/def-1/enable"

    set_alert_definition_state(client, "def-1", enabled=False)
    assert client.put.call_args.args[0] == "/alertdefinitions/def-1/disable"
    client.post.assert_not_called()


# ── #9 (refuted — pin the CORRECT wire key) + relation fix ─────────────


def test_create_alert_definition_keeps_base_symptom_set() -> None:
    from vmware_aria.ops.alerts import create_alert_definition

    client = _client()
    client.post.return_value = {"id": "new-def"}
    create_alert_definition(
        client, "n", "d", "VirtualMachine", symptom_definition_ids=["s1"]
    )
    body = client.post.call_args.kwargs["json_data"]
    sset = body["states"][0]["base-symptom-set"]  # wire key, NOT "symptoms"
    assert sset["relation"] == "SELF"  # "ANY" is not a valid relation value
    assert sset["symptomDefinitionIds"] == ["s1"]


# ── #10/#11: report generation body + list filter ──────────────────────


def test_generate_report_body_shape_and_requires_resource() -> None:
    from vmware_aria.ops.reports import generate_report

    client = _client()
    client.post.return_value = {"id": "rep-1", "status": "PENDING"}
    generate_report(client, "rdef-1", resource_ids=["res-1"])

    body = client.post.call_args.kwargs["json_data"]
    assert body["reportDefinitionId"] == "rdef-1"
    assert body["resourceId"] == "res-1"
    assert "reportDefinition" not in body  # old invented nesting

    with pytest.raises(ValueError, match="resource_ids"):
        generate_report(client, "rdef-1", resource_ids=None)


def test_list_reports_filters_definition_client_side() -> None:
    from vmware_aria.ops.reports import list_reports

    client = _client()
    client.get.return_value = {
        "reports": [
            {"id": "r1", "reportDefinitionId": "want"},
            {"id": "r2", "reportDefinitionId": "other"},
        ]
    }
    results = list_reports(client, definition_id="want")

    params = client.get.call_args.kwargs.get("params") or {}
    assert "reportDefinitionId" not in params  # not a valid API param
    assert [r["id"] for r in results] == ["r1"]


# ── #13: node status parsing ───────────────────────────────────────────


def test_aria_health_reads_status_field() -> None:
    from vmware_aria.ops.health import get_aria_health

    client = _client()
    client.get.return_value = {"status": "ONLINE", "systemTime": 1234}
    result = get_aria_health(client)
    assert result["overall_status"] == "ONLINE"
    assert result["healthy"] is True
    assert result["system_time_ms"] == 1234


# ── #14: token validity is an epoch-ms timestamp, not a duration ───────


def test_token_validity_treated_as_epoch_timestamp(monkeypatch) -> None:
    from vmware_aria.config import TargetConfig
    from vmware_aria.connection import AriaClient

    expiry_epoch_ms = int((time.time() + 6 * 3600) * 1000)

    class FakeResponse:
        status_code = 200
        content = b"{}"

        def raise_for_status(self):
            pass

        def json(self):
            return {"token": "tok", "validity": expiry_epoch_ms}

    monkeypatch.setattr("httpx.Client.post", lambda self, *a, **k: FakeResponse())
    target = TargetConfig(host="h", username="u")
    client = AriaClient(target, "pw")

    # Old bug: now + validity/1000 put expiry ~56 years out. Correct: ~6h.
    seconds_until_expiry = client._token_expires_at - time.time()
    assert 0 < seconds_until_expiry < 7 * 3600, (
        f"token expiry {seconds_until_expiry:.0f}s out — validity must be "
        "parsed as an epoch-ms timestamp, not a duration"
    )


# ── invented capacity/anomaly endpoints replaced by stats calls ────────


def test_capacity_uses_stats_latest_not_invented_endpoints() -> None:
    from vmware_aria.ops.capacity import get_remaining_capacity, get_time_remaining

    client = _client()
    client.get.return_value = {"values": []}
    get_remaining_capacity(client, "cl-1")
    get_time_remaining(client, "cl-1")

    for call in client.get.call_args_list:
        path = call.args[0]
        assert path == "/resources/cl-1/stats/latest", f"unexpected path {path}"
        for key in call.kwargs["params"]["statKey"]:
            assert key.startswith("OnlineCapacityAnalytics|")


def test_anomaly_uses_stats_latest_not_invented_endpoints() -> None:
    from vmware_aria.ops.anomaly import get_resource_riskbadge, list_anomalies

    client = _client()
    client.get.return_value = {
        "badges": [{"type": "RISK", "score": 25, "color": "GREEN"}]
    }
    result = get_resource_riskbadge(client, "res-1")
    assert client.get.call_args.args[0] == "/resources/res-1"  # no /badge/risk
    assert result["risk_score"] == 25

    client.get.reset_mock()
    client.get.return_value = {"values": []}
    list_anomalies(client, resource_id="res-1")
    assert client.get.call_args.args[0] == "/resources/res-1/stats/latest"
