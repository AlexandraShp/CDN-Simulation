import pytest

from minicdn.models import Request
from minicdn.traffic.fixed_trace import generate_fixed_trace


def test_generates_requests_in_the_supplied_order():
    specifications = [
        {
            "request_id": "R001",
            "user_id": "U1",
            "arrival_time_s": 0.0,
            "processing_units": 100.0,
        },
        {
            "request_id": "R002",
            "user_id": "U2",
            "arrival_time_s": 1.5,
            "processing_units": 200.0,
        },
        {
            "request_id": "R003",
            "user_id": "U1",
            "arrival_time_s": 1.5,
            "processing_units": 150.0,
        },
    ]

    requests = generate_fixed_trace(specifications)

    assert len(requests) == 3
    assert all(isinstance(request, Request) for request in requests)
    assert [request.request_id for request in requests] == ["R001", "R002", "R003"]
    assert [request.arrival_time_s for request in requests] == [0.0, 1.5, 1.5]


def test_empty_trace_returns_empty_list():
    assert generate_fixed_trace([]) == []


def test_rejects_duplicate_request_ids():
    specifications = [
        {"request_id": "R1", "user_id": "U1", "arrival_time_s": 0.0, "processing_units": 10.0},
        {"request_id": "R1", "user_id": "U2", "arrival_time_s": 1.0, "processing_units": 20.0},
    ]

    with pytest.raises(ValueError, match="Duplicate request_id"):
        generate_fixed_trace(specifications)


def test_rejects_out_of_order_arrival_times():
    specifications = [
        {"request_id": "R1", "user_id": "U1", "arrival_time_s": 2.0, "processing_units": 10.0},
        {"request_id": "R2", "user_id": "U2", "arrival_time_s": 1.0, "processing_units": 20.0},
    ]

    with pytest.raises(ValueError, match="ordered by non-decreasing"):
        generate_fixed_trace(specifications)


def test_reports_missing_fields_clearly():
    specifications = [
        {"request_id": "R1", "user_id": "U1", "arrival_time_s": 0.0},
    ]

    with pytest.raises(ValueError, match="missing required field: processing_units"):
        generate_fixed_trace(specifications)


def test_rejects_invalid_request_values():
    specifications = [
        {"request_id": "R1", "user_id": "U1", "arrival_time_s": -1.0, "processing_units": 10.0},
    ]

    with pytest.raises(ValueError, match="arrival_time_s"):
        generate_fixed_trace(specifications)
