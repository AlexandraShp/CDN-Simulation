from dataclasses import dataclass

import pytest

from minicdn.models import Request
from minicdn.strategies.minimum_latency_adapter import MinimumLatencyAdapter


@dataclass(frozen=True)
class FakeServer:
    server_id: str


class FakeNirminLatencyStrategy:
    """Test double matching Nirmin's published select_server signature."""

    def __init__(self, rtt_lookup):
        self.rtt_lookup = rtt_lookup

    def select_server(self, user_id, eligible_servers):
        server_ids = [getattr(server, "server_id", server) for server in eligible_servers]
        return min(server_ids, key=lambda server_id: (self.rtt_lookup(user_id, server_id), server_id))


def test_adapter_wraps_nirmin_result_in_selection_result():
    request = Request("R1", "U1", 0.0, 10.0)
    rtts = {"A": 0.04, "B": 0.01, "C": 0.03}
    get_rtt = lambda user_id, server_id: rtts[server_id]
    nirmin_strategy = FakeNirminLatencyStrategy(get_rtt)
    adapter = MinimumLatencyAdapter(nirmin_strategy, get_rtt)

    result = adapter.select_server(request, [FakeServer("A"), FakeServer("B"), FakeServer("C")])

    assert result.selected_server_id == "B"
    assert result.strategy_name == "minimum_latency"
    assert result.candidate_scores == rtts


def test_adapter_accepts_plain_server_ids():
    request = Request("R1", "U1", 0.0, 10.0)
    get_rtt = lambda user_id, server_id: {"A": 0.02, "B": 0.01}[server_id]
    adapter = MinimumLatencyAdapter(FakeNirminLatencyStrategy(get_rtt), get_rtt)

    result = adapter.select_server(request, ["A", "B"])
    assert result.selected_server_id == "B"


def test_adapter_returns_no_selection_for_empty_list():
    request = Request("R1", "U1", 0.0, 10.0)
    get_rtt = lambda user_id, server_id: 0.01
    adapter = MinimumLatencyAdapter(FakeNirminLatencyStrategy(get_rtt), get_rtt)

    result = adapter.select_server(request, [])
    assert result.selected_server_id is None
    assert not result.is_served


def test_adapter_rejects_strategy_result_outside_eligible_set():
    class IncorrectStrategy:
        def select_server(self, user_id, eligible_servers):
            return "NOT-ELIGIBLE"

    request = Request("R1", "U1", 0.0, 10.0)
    adapter = MinimumLatencyAdapter(IncorrectStrategy(), lambda user, server: 0.01)

    with pytest.raises(RuntimeError, match="not in the eligible set"):
        adapter.select_server(request, ["A", "B"])
