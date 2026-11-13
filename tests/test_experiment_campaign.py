from experiments.run_experiment_campaign import (
    RunRow,
    aggregate_rows,
    make_network_matrix,
)


def make_row(**overrides):
    values = {
        "network_scenario": "low",
        "network_multiplier": 1.0,
        "traffic_scenario": "low",
        "arrival_rate_per_s": 2.0,
        "request_count": 100,
        "repetition": 1,
        "seed": 42,
        "strategy": "random",
        "alpha": None,
        "completed_requests": 100,
        "unserved_requests": 0,
        "failed_requests": 0,
        "average_response_ms": 100.0,
        "median_response_ms": 90.0,
        "p95_response_ms": 150.0,
        "average_queue_wait_ms": 5.0,
        "average_network_ms": 40.0,
        "throughput_requests_per_s": 1.8,
        "average_server_utilization": 0.4,
        "simulation_end_time_s": 55.0,
    }
    values.update(overrides)
    return RunRow(**values)


def test_network_matrix_applies_nirmin_scenario_multiplier_without_mutating_base():
    low = make_network_matrix(1.0)
    high = make_network_matrix(5.0)

    assert low["U1"]["A"] == 0.020
    assert high["U1"]["A"] == 0.100
    assert low["U2"]["B"] == 0.025


def test_strategy_aggregation_groups_repetitions_and_calculates_mean_and_stdev():
    rows = [
        make_row(repetition=1, average_response_ms=100.0),
        make_row(repetition=2, seed=43, average_response_ms=120.0),
    ]

    summary = aggregate_rows(rows)

    assert len(summary) == 1
    assert summary[0]["repetitions"] == 2
    assert summary[0]["mean_average_response_ms"] == 110.0
    assert summary[0]["stdev_average_response_ms"] > 0


def test_hybrid_alpha_aggregation_keeps_alpha_values_separate():
    rows = [
        make_row(strategy="hybrid", alpha=0.0, average_response_ms=100.0),
        make_row(strategy="hybrid", alpha=0.5, average_response_ms=80.0),
        make_row(strategy="hybrid", alpha=1.0, average_response_ms=90.0),
    ]

    summary = aggregate_rows(rows, hybrid_only=True)

    assert len(summary) == 3
    assert {row["alpha"] for row in summary} == {0.0, 0.5, 1.0}


def test_run_row_exports_failure_diagnostics_for_raw_csv():
    row = make_row(
        completed_requests=199,
        failed_requests=1,
        failure_diagnostics=(
            "request=R0010; time_s=0.838557880263231; "
            "server=A; reason=completion boundary mismatch"
        ),
    )

    exported = row.to_dict()

    assert exported["failed_requests"] == 1
    assert "R0010" in exported["failure_diagnostics"]
    assert "server=A" in exported["failure_diagnostics"]
