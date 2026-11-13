from dataclasses import dataclass

import pytest

from minicdn.models import Request, SelectionResult
from minicdn.strategies.random_router import RandomRouter


@dataclass(frozen=True)
class FakeServer:
    server_id: str


@pytest.fixture
def request_obj():
    return Request("R001", "U1", 0.0, 100.0)


def test_random_router_returns_shared_selection_result(request_obj):
    router = RandomRouter(seed=42)
    result = router.select_server(request_obj, ["A", "B", "C"])

    assert isinstance(result, SelectionResult)
    assert result.selected_server_id in {"A", "B", "C"}
    assert result.strategy_name == "random"
    assert result.candidate_scores == {}


def test_random_router_returns_no_selection_for_empty_list(request_obj):
    result = RandomRouter(seed=42).select_server(request_obj, [])

    assert result.selected_server_id is None
    assert not result.is_served


def test_same_seed_and_same_calls_produce_same_sequence(request_obj):
    servers = ["A", "B", "C", "D"]
    first = RandomRouter(seed=123)
    second = RandomRouter(seed=123)

    first_sequence = [first.select_server(request_obj, servers).selected_server_id for _ in range(20)]
    second_sequence = [second.select_server(request_obj, servers).selected_server_id for _ in range(20)]

    assert first_sequence == second_sequence


def test_router_accepts_server_objects(request_obj):
    result = RandomRouter(seed=7).select_server(
        request_obj, [FakeServer("A"), FakeServer("B")]
    )

    assert result.selected_server_id in {"A", "B"}


def test_router_rejects_duplicate_server_ids(request_obj):
    with pytest.raises(ValueError, match="unique server IDs"):
        RandomRouter(seed=1).select_server(
            request_obj, [FakeServer("A"), FakeServer("A")]
        )


def test_router_rejects_invalid_server_id(request_obj):
    with pytest.raises(ValueError, match="server_id"):
        RandomRouter(seed=1).select_server(request_obj, [object()])


def test_router_rejects_non_integer_seed():
    with pytest.raises(ValueError, match="seed must be an integer"):
        RandomRouter(seed=1.5)
