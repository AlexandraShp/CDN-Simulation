"""
Tests for the Minimum Latency routing strategy.

These tests verify that the strategy selects the correct server
based only on RTT, without considering server workload.
"""

import pytest

from src.network import NetworkModel
from src.strategies.latency import MinimumLatencyStrategy


@pytest.fixture
def strategy():
    # Create a network with different RTT values for three users.
    rtt_matrix = {
        "U1": {"A": 0.020, "B": 0.060, "C": 0.100},
        "U2": {"A": 0.080, "B": 0.025, "C": 0.050},
        "U3": {"A": 0.090, "B": 0.070, "C": 0.015},
    }

    network = NetworkModel(rtt_matrix)

    # The strategy uses the network model to compare server RTT values.
    return MinimumLatencyStrategy(network)


def test_selects_lowest_latency_server(strategy):
    # U1 should choose A because its RTT is the smallest.
    result = strategy.select_server("U1", ["A", "B", "C"])

    assert result == "A"


def test_different_users_choose_different_servers(strategy):
    # Each user has a different closest server.
    assert strategy.select_server("U1", ["A", "B", "C"]) == "A"
    assert strategy.select_server("U2", ["A", "B", "C"]) == "B"
    assert strategy.select_server("U3", ["A", "B", "C"]) == "C"


def test_selects_only_from_eligible_servers(strategy):
    # Even if A is the closest overall, it cannot be selected if unavailable.
    result = strategy.select_server("U1", ["B", "C"])

    assert result == "B"


def test_returns_none_when_no_server_is_eligible(strategy):
    # No available server means the request cannot be routed.
    assert strategy.select_server("U1", []) is None


def test_tie_breaking_uses_server_id():
    # A and B have equal RTT, so the strategy should select A.
    network = NetworkModel({
        "U1": {"B": 0.020, "A": 0.020, "C": 0.050}
    })

    strategy = MinimumLatencyStrategy(network)

    assert strategy.select_server("U1", ["B", "A", "C"]) == "A"


def test_updated_rtt_changes_server_selection(strategy):
    # Initially A is the closest server for U1.
    assert strategy.select_server("U1", ["A", "B", "C"]) == "A"

    # Increase A's RTT so B becomes the closest server.
    strategy.network_model.update_rtt("U1", "A", 0.090)

    assert strategy.select_server("U1", ["A", "B", "C"]) == "B"


def test_accepts_server_objects(strategy):
    # The shared server model may provide server objects instead of IDs.
    class FakeServer:
        def __init__(self, server_id):
            self.server_id = server_id

    servers = [
        FakeServer("A"),
        FakeServer("B"),
        FakeServer("C")
    ]

    assert strategy.select_server("U1", servers) == "A"


def test_unknown_user_raises_error(strategy):
    # An unknown user has no RTT information in the network model.
    with pytest.raises(KeyError):
        strategy.select_server("U4", ["A", "B", "C"])


def test_unknown_server_raises_error(strategy):
    # Every eligible server must have a corresponding RTT entry.
    with pytest.raises(KeyError):
        strategy.select_server("U1", ["A", "B", "D"])
