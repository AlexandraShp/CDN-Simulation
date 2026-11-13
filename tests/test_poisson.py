import pytest

from minicdn.models import Request
from minicdn.traffic.poisson import generate_poisson_trace


def test_generates_requested_number_of_requests():
    requests = generate_poisson_trace(5, 2.0, ["U1", "U2"], 100.0, seed=7)

    assert len(requests) == 5
    assert all(isinstance(request, Request) for request in requests)
    assert [request.request_id for request in requests] == [
        "R0001", "R0002", "R0003", "R0004", "R0005"
    ]


def test_same_seed_produces_same_trace():
    first = generate_poisson_trace(5, 2.0, ["U1", "U2"], 100.0, seed=42)
    second = generate_poisson_trace(5, 2.0, ["U1", "U2"], 100.0, seed=42)

    assert first == second


def test_arrival_times_are_chronological_and_start_at_given_time():
    requests = generate_poisson_trace(
        10, 3.0, ["U1"], 50.0, seed=9, start_time_s=4.0
    )
    arrival_times = [request.arrival_time_s for request in requests]

    assert arrival_times[0] == 4.0
    assert arrival_times == sorted(arrival_times)


def test_zero_requests_returns_empty_list():
    assert generate_poisson_trace(0, 2.0, ["U1"], 100.0, seed=1) == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"number_of_requests": -1},
        {"arrival_rate_per_s": 0.0},
        {"user_ids": []},
        {"processing_units": 0.0},
        {"start_time_s": -1.0},
    ],
)
def test_rejects_invalid_parameters(kwargs):
    parameters = {
        "number_of_requests": 3,
        "arrival_rate_per_s": 2.0,
        "user_ids": ["U1"],
        "processing_units": 100.0,
        "seed": 1,
        "start_time_s": 0.0,
    }
    parameters.update(kwargs)

    with pytest.raises(ValueError):
        generate_poisson_trace(**parameters)
