from minicdn.simulation.metrics import build_summary
from minicdn.simulation.results import RequestResult


def test_summary_uses_completed_requests_and_includes_drain_window():
    outcomes = [
        RequestResult(
            request_id="R1", user_id="U1", status="completed",
            strategy_name="test", selected_server_id="S1", arrival_time_s=0.0,
            network_time_s=0.2, queue_wait_s=0.0, processing_time_s=1.0,
            response_time_s=1.2,
        ),
        RequestResult(
            request_id="R2", user_id="U1", status="completed",
            strategy_name="test", selected_server_id="S1", arrival_time_s=0.0,
            network_time_s=0.2, queue_wait_s=0.5, processing_time_s=1.0,
            response_time_s=1.7,
        ),
        RequestResult(
            request_id="R3", user_id="U1", status="unserved",
            strategy_name="test", selected_server_id=None, arrival_time_s=2.0,
        ),
    ]

    summary = build_summary(outcomes, {"S1": 2}, simulation_end_time_s=4.0)

    assert summary.total_requests == 3
    assert summary.completed_requests == 2
    assert summary.unserved_requests == 1
    assert summary.failed_requests == 0
    assert summary.average_response_time_s == 1.45
    assert summary.median_response_time_s == 1.45
    assert summary.p95_response_time_s == 1.7
    assert summary.average_queue_wait_s == 0.25
    assert summary.throughput_requests_per_s == 0.5
    assert summary.utilization_by_server["S1"] == 0.25
    assert summary.observation_window_s == 4.0
    assert summary.drain_period_included is True


def test_summary_marks_response_metrics_unavailable_when_none_complete():
    outcome = RequestResult(
        request_id="R1", user_id="U1", status="unserved",
        strategy_name="test", selected_server_id=None, arrival_time_s=1.0,
    )

    summary = build_summary([outcome], {}, simulation_end_time_s=1.0)

    assert summary.failed_requests == 0
    assert summary.average_response_time_s is None
    assert summary.median_response_time_s is None
    assert summary.p95_response_time_s is None
    assert summary.throughput_requests_per_s == 0.0
