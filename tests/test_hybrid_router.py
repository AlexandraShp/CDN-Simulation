from dataclasses import dataclass

import pytest

from minicdn.models import Request, SelectionResult
from minicdn.strategies.hybrid_router import HybridRouter


@dataclass(frozen=True)
class FakeServer:
    server_id: str


@pytest.fixture
def request_obj():
    return Request("R001", "U1", 0.0, 100.0)


@pytest.fixture
def servers():
    return [FakeServer("S1"), FakeServer("S2"), FakeServer("S3")]


def make_rtt(values):
    return lambda user_id, server_id: values[server_id]


def make_workload(values):
    return lambda request_obj, server: values[server.server_id]


def make_router(alpha, rtt_values, workload_values):
    return HybridRouter(
        alpha=alpha,
        rtt_lookup=make_rtt(rtt_values),
        workload_estimator=make_workload(workload_values),
    )


def test_hybrid_selects_lowest_weighted_score(request_obj, servers):
    router = make_router(0.5, {"S1": 0.020, "S2": 0.050, "S3": 0.100},
                         {"S1": 0.200, "S2": 0.050, "S3": 0.030})
    result = router.select_server(request_obj, servers)

    assert result.selected_server_id == "S2"
    assert result.candidate_scores == {
        "S1": pytest.approx(0.110),
        "S2": pytest.approx(0.050),
        "S3": pytest.approx(0.065),
    }


def test_alpha_one_matches_minimum_latency(request_obj, servers):
    router = make_router(1.0, {"S1": 0.080, "S2": 0.020, "S3": 0.050},
                         {"S1": 0.001, "S2": 100.0, "S3": 0.002})
    assert router.select_server(request_obj, servers).selected_server_id == "S2"


def test_alpha_zero_matches_least_loaded(request_obj, servers):
    router = make_router(0.0, {"S1": 0.001, "S2": 100.0, "S3": 0.002},
                         {"S1": 0.080, "S2": 0.020, "S3": 0.050})
    assert router.select_server(request_obj, servers).selected_server_id == "S2"


def test_ties_are_broken_by_server_id(request_obj):
    servers = [FakeServer("S3"), FakeServer("S1"), FakeServer("S2")]
    router = make_router(0.5, {"S1": 1.0, "S2": 1.0, "S3": 1.0},
                         {"S1": 1.0, "S2": 1.0, "S3": 1.0})
    assert router.select_server(request_obj, servers).selected_server_id == "S1"


@pytest.mark.parametrize("alpha", [-0.01, 1.01, float("nan"), float("inf"), True, "0.5"])
def test_rejects_invalid_alpha(alpha):
    with pytest.raises(ValueError):
        HybridRouter(alpha, lambda user, server: 0.0, lambda request, server: 0.0)


def test_no_eligible_servers_returns_no_selection(request_obj):
    router = HybridRouter(0.5, lambda user, server: 0.0, lambda request, server: 0.0)
    result = router.select_server(request_obj, [])
    assert isinstance(result, SelectionResult)
    assert result.selected_server_id is None
    assert not result.is_served


@pytest.mark.parametrize("bad_value", [-1.0, float("nan"), float("inf")])
def test_rejects_invalid_rtt(request_obj, servers, bad_value):
    router = HybridRouter(0.5, make_rtt({"S1": bad_value, "S2": 0.1, "S3": 0.2}),
                          make_workload({"S1": 0.1, "S2": 0.1, "S3": 0.1}))
    with pytest.raises(ValueError):
        router.select_server(request_obj, servers)


def test_rejects_invalid_workload(request_obj, servers):
    router = HybridRouter(0.5, make_rtt({"S1": 0.1, "S2": 0.1, "S3": 0.1}),
                          make_workload({"S1": 0.1, "S2": -1.0, "S3": 0.1}))
    with pytest.raises(ValueError):
        router.select_server(request_obj, servers)


def test_alpha_one_does_not_call_workload_estimator(request_obj, servers):
    router = HybridRouter(1.0, make_rtt({"S1": 0.03, "S2": 0.01, "S3": 0.02}),
                          lambda request, server: pytest.fail("workload must not be called"))
    assert router.select_server(request_obj, servers).selected_server_id == "S2"


def test_alpha_zero_does_not_call_rtt_lookup(request_obj, servers):
    router = HybridRouter(0.0, lambda user, server: pytest.fail("RTT must not be called"),
                          make_workload({"S1": 0.03, "S2": 0.01, "S3": 0.02}))
    assert router.select_server(request_obj, servers).selected_server_id == "S2"
