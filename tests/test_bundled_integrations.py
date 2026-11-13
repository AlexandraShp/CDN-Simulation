"""Smoke tests for teammate source snapshots bundled in this workspace."""

from minicdn.integrations.nirmin import (
    BASE_RTT_MATRIX,
    MinimumLatencyStrategy,
    NetworkModel,
    create_delay_scenario,
)
from minicdn.integrations.sasha import ServerWorkload, select_least_loaded
from minicdn.models import Request


def test_bundled_nirmin_network_and_minimum_latency_are_available_locally():
    network = NetworkModel(BASE_RTT_MATRIX)
    router = MinimumLatencyStrategy(network)

    assert network.get_rtt("U1", "A") == 0.020
    assert router.select_server("U1", ["A", "B", "C"]) == "A"


def test_bundled_nirmin_delay_scenarios_are_available_locally():
    low = create_delay_scenario("low")
    high = create_delay_scenario("high")

    assert high.get_rtt("U1", "A") == low.get_rtt("U1", "A") * 5


def test_bundled_sasha_workload_and_least_loaded_are_available_locally():
    servers = [
        ServerWorkload("A", capacity_units_per_s=10.0, worker_count=1),
        ServerWorkload("B", capacity_units_per_s=20.0, worker_count=1),
    ]
    request = Request("R001", "U1", 0.0, 10.0)

    result = select_least_loaded(request, servers, now_s=0.0)

    assert result.selected_server_id == "B"
    assert result.strategy_name == "least_loaded"
    assert result.candidate_scores["A"] == 1.0
    assert result.candidate_scores["B"] == 0.5
