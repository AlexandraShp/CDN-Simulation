"""Experiments that can be run before Sasha's server runtime is integrated.

These experiments evaluate network-only routing choices, generated traffic
characteristics, and Hybrid's decision rule with explicitly synthetic workload
estimates. They do not claim to measure server queues, processing performance,
response time, throughput, or utilization.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from minicdn.models import Request
from minicdn.strategies import HybridRouter, MinimumLatencyAdapter, RandomRouter
from minicdn.traffic import generate_poisson_trace


@dataclass(frozen=True, slots=True)
class NetworkRoutingObservation:
    scenario: str
    user_id: str
    trials: int
    minimum_latency_server_id: str
    minimum_latency_rtt_s: float
    random_average_rtt_s: float
    random_median_rtt_s: float
    random_p95_rtt_s: float
    random_to_minimum_improvement_pct: float


@dataclass(frozen=True, slots=True)
class TrafficObservation:
    arrival_rate_per_s: float
    request_count: int
    start_time_s: float | None
    end_time_s: float | None
    observed_span_s: float | None
    mean_interarrival_s: float | None
    observed_arrival_rate_per_s: float | None
    theoretical_mean_interarrival_s: float
    seed: int


@dataclass(frozen=True, slots=True)
class HybridAlphaObservation:
    alpha: float
    selected_server_id: str | None
    selected_score_s: float | None
    candidate_scores: dict[str, float]
    workload_values_s: dict[str, float]
    data_label: str = "SYNTHETIC_WORKLOAD_NOT_SERVER_MEASUREMENTS"


def _nearest_rank_percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def evaluate_network_routing(
    *,
    scenario_name: str,
    network_model: Any,
    minimum_latency_strategy: Any,
    trials_per_user: int = 1_000,
    seed: int = 42,
) -> list[NetworkRoutingObservation]:
    """Compare Random and Nirmin's Minimum Latency using RTT only.

    The supplied ``minimum_latency_strategy`` is Nirmin's actual strategy
    instance. The server identifiers are read from NetworkModel.rtt_matrix.
    No server queue or processing behavior is simulated here.
    """
    if isinstance(trials_per_user, bool) or not isinstance(trials_per_user, int):
        raise ValueError("trials_per_user must be an integer")
    if trials_per_user <= 0:
        raise ValueError("trials_per_user must be > 0")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")

    rtt_matrix = getattr(network_model, "rtt_matrix", None)
    if not isinstance(rtt_matrix, dict) or not rtt_matrix:
        raise ValueError("network_model must expose a non-empty rtt_matrix")

    users = sorted(rtt_matrix)
    server_ids = sorted(rtt_matrix[users[0]])
    if not server_ids:
        raise ValueError("NetworkModel must contain at least one server")
    for user_id in users:
        if sorted(rtt_matrix[user_id]) != server_ids:
            raise ValueError("Every user must have RTT values for the same servers")

    rtt_lookup = network_model.get_rtt
    minimum_router = MinimumLatencyAdapter(minimum_latency_strategy, rtt_lookup)
    observations: list[NetworkRoutingObservation] = []

    for user_index, user_id in enumerate(users):
        minimum_request = Request(
            request_id=f"MIN-{scenario_name}-{user_id}",
            user_id=user_id,
            arrival_time_s=0.0,
            processing_units=1.0,
        )
        minimum_result = minimum_router.select_server(minimum_request, server_ids)
        minimum_server_id = minimum_result.selected_server_id
        if minimum_server_id is None:
            raise RuntimeError("Minimum Latency did not select a server")
        minimum_rtt = float(rtt_lookup(user_id, minimum_server_id))

        random_router = RandomRouter(seed=seed + user_index)
        random_rtts: list[float] = []
        for trial in range(trials_per_user):
            request = Request(
                request_id=f"RND-{scenario_name}-{user_id}-{trial:06d}",
                user_id=user_id,
                arrival_time_s=0.0,
                processing_units=1.0,
            )
            result = random_router.select_server(request, server_ids)
            if result.selected_server_id is None:
                raise RuntimeError("Random Router did not select an eligible server")
            random_rtts.append(float(rtt_lookup(user_id, result.selected_server_id)))

        random_average = sum(random_rtts) / len(random_rtts)
        random_median = (lambda xs: (xs[(len(xs) - 1) // 2] + xs[len(xs) // 2]) / 2)(
            sorted(random_rtts)
        )
        improvement_pct = (
            (random_average - minimum_rtt) / random_average * 100.0
            if random_average > 0
            else 0.0
        )
        observations.append(
            NetworkRoutingObservation(
                scenario=scenario_name,
                user_id=user_id,
                trials=trials_per_user,
                minimum_latency_server_id=minimum_server_id,
                minimum_latency_rtt_s=minimum_rtt,
                random_average_rtt_s=random_average,
                random_median_rtt_s=random_median,
                random_p95_rtt_s=_nearest_rank_percentile(random_rtts, 0.95),
                random_to_minimum_improvement_pct=improvement_pct,
            )
        )

    return observations


def summarize_poisson_trace(
    *,
    arrival_rate_per_s: float,
    request_count: int,
    user_ids: list[str],
    processing_units: float = 100.0,
    seed: int = 42,
) -> TrafficObservation:
    """Generate a Poisson trace and summarize arrivals, not server performance."""
    trace = generate_poisson_trace(
        number_of_requests=request_count,
        arrival_rate_per_s=arrival_rate_per_s,
        user_ids=user_ids,
        processing_units=processing_units,
        seed=seed,
    )
    arrival_times = [request.arrival_time_s for request in trace]
    if not arrival_times:
        start = end = span = mean_interval = observed_rate = None
    else:
        start = arrival_times[0]
        end = arrival_times[-1]
        span = end - start
        intervals = [right - left for left, right in zip(arrival_times, arrival_times[1:])]
        mean_interval = sum(intervals) / len(intervals) if intervals else None
        observed_rate = (len(intervals) / span) if span > 0 and intervals else None

    return TrafficObservation(
        arrival_rate_per_s=float(arrival_rate_per_s),
        request_count=len(trace),
        start_time_s=start,
        end_time_s=end,
        observed_span_s=span,
        mean_interarrival_s=mean_interval,
        observed_arrival_rate_per_s=observed_rate,
        theoretical_mean_interarrival_s=1.0 / arrival_rate_per_s,
        seed=seed,
    )


def evaluate_hybrid_alpha_sensitivity(
    *,
    network_model: Any,
    user_id: str,
    server_ids: list[str],
    synthetic_workload_seconds: dict[str, float],
    alphas: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0),
) -> list[HybridAlphaObservation]:
    """Show how alpha changes Hybrid decisions using labelled synthetic data.

    This is an algorithmic sensitivity test only. Workload values must never be
    presented as measurements from Sasha's server model.
    """
    if not server_ids:
        raise ValueError("server_ids must not be empty")
    missing = set(server_ids) - set(synthetic_workload_seconds)
    if missing:
        raise ValueError(f"Missing synthetic workload values for: {sorted(missing)}")
    for server_id in server_ids:
        value = synthetic_workload_seconds[server_id]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Synthetic workload for {server_id} must be numeric")
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"Synthetic workload for {server_id} must be finite and >= 0")

    request = Request(
        request_id="HYBRID-ALPHA-001",
        user_id=user_id,
        arrival_time_s=0.0,
        processing_units=100.0,
    )
    observations: list[HybridAlphaObservation] = []
    for alpha in alphas:
        router = HybridRouter(
            alpha=alpha,
            rtt_lookup=network_model.get_rtt,
            workload_estimator=lambda _request, server: synthetic_workload_seconds[server],
        )
        result = router.select_server(request, server_ids)
        selected_score = (
            result.candidate_scores[result.selected_server_id]
            if result.selected_server_id is not None
            else None
        )
        observations.append(
            HybridAlphaObservation(
                alpha=float(alpha),
                selected_server_id=result.selected_server_id,
                selected_score_s=selected_score,
                candidate_scores=dict(result.candidate_scores),
                workload_values_s={key: float(synthetic_workload_seconds[key]) for key in server_ids},
            )
        )
    return observations


def observation_to_dict(observation: Any) -> dict[str, Any]:
    """Convert one immutable observation dataclass to a CSV-ready dictionary."""
    return asdict(observation)
