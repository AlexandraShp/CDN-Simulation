from experiments.run_experiment_campaign import RunRow


def test_run_row_keeps_failure_reason_in_raw_results():
    row = RunRow(
        network_scenario="low",
        network_multiplier=1.0,
        traffic_scenario="high",
        arrival_rate_per_s=24.0,
        request_count=200,
        repetition=1,
        seed=42,
        strategy="random",
        alpha=None,
        completed_requests=199,
        unserved_requests=0,
        failed_requests=1,
        average_response_ms=490.0,
        median_response_ms=289.0,
        p95_response_ms=1238.0,
        average_queue_wait_ms=248.0,
        average_network_ms=59.0,
        throughput_requests_per_s=22.4,
        average_server_utilization=0.68,
        simulation_end_time_s=8.85,
        failure_diagnostics=(
            "request=R0010; time_s=0.838557880263231; "
            "server=A; reason=example error"
        ),
    )

    exported = row.to_dict()

    assert exported["failed_requests"] == 1
    assert "R0010" in exported["failure_diagnostics"]
    assert "server=A" in exported["failure_diagnostics"]
    assert "example error" in exported["failure_diagnostics"]
