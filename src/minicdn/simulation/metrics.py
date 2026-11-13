"""Pure metric calculations for completed simulation results."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping

from minicdn.simulation.results import RequestResult, SimulationSummary


def _average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _nearest_rank_percentile(values: list[float], percentile: float) -> float | None:
    """Return a nearest-rank percentile (e.g. P95) without interpolation."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def build_summary(
    request_results: Iterable[RequestResult],
    worker_counts: Mapping[str, int],
    simulation_end_time_s: float,
) -> SimulationSummary:
    """Calculate metrics over the complete run, including the drain period.

    Throughput uses completed requests divided by simulation end time. Server
    utilization uses summed worker processing time divided by worker_count ×
    that same observation window. The observation window starts at t=0 and
    includes the time needed for in-flight requests to finish (the drain).
    """
    if not math.isfinite(simulation_end_time_s) or simulation_end_time_s < 0:
        raise ValueError("simulation_end_time_s must be finite and >= 0")

    outcomes = tuple(request_results)
    completed = [item for item in outcomes if item.status == "completed"]
    unserved = [item for item in outcomes if item.status == "unserved"]
    failed = [item for item in outcomes if item.status == "failed"]

    response_times = [item.response_time_s for item in completed]
    queue_waits = [item.queue_wait_s for item in completed]
    network_times = [item.network_time_s for item in completed]

    # These values are guaranteed non-None for completed outcomes by the engine.
    response_values = [float(value) for value in response_times if value is not None]
    queue_values = [float(value) for value in queue_waits if value is not None]
    network_values = [float(value) for value in network_times if value is not None]

    busy_time_by_server: dict[str, float] = defaultdict(float)
    for item in completed:
        if item.selected_server_id is not None and item.processing_time_s is not None:
            busy_time_by_server[item.selected_server_id] += item.processing_time_s

    utilization: dict[str, float] = {}
    for server_id, worker_count in worker_counts.items():
        if isinstance(worker_count, bool) or not isinstance(worker_count, int) or worker_count <= 0:
            raise ValueError(f"worker_count for {server_id} must be a positive integer")
        available_worker_time = worker_count * simulation_end_time_s
        utilization[server_id] = (
            busy_time_by_server.get(server_id, 0.0) / available_worker_time
            if available_worker_time > 0
            else 0.0
        )

    throughput = (
        len(completed) / simulation_end_time_s
        if simulation_end_time_s > 0
        else None
    )

    return SimulationSummary(
        total_requests=len(outcomes),
        completed_requests=len(completed),
        unserved_requests=len(unserved),
        failed_requests=len(failed),
        average_response_time_s=_average(response_values),
        median_response_time_s=_median(response_values),
        p95_response_time_s=_nearest_rank_percentile(response_values, 0.95),
        average_queue_wait_s=_average(queue_values),
        average_network_time_s=_average(network_values),
        throughput_requests_per_s=throughput,
        utilization_by_server=utilization,
        observation_window_s=simulation_end_time_s,
        drain_period_included=True,
    )
