"""Reproduce and explain the previously observed failed campaign request.

Default settings reproduce the recorded case: Random routing, low network
multiplier, high traffic, seed 42, and 200 requests. Uses only the bundled
Nirmin and Sasha snapshots; no teammate repository paths are required.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from minicdn.integrations.nirmin import BASE_RTT_MATRIX, NetworkModel, MinimumLatencyStrategy
from minicdn.integrations.sasha import ServerWorkload, select_least_loaded
from minicdn.models import Request
from minicdn.simulation import SashaServerConfig, SashaServerRuntime, SimulationEngine
from minicdn.strategies import (
    HybridRouter,
    MinimumLatencyAdapter,
    RandomRouter,
    SashaLeastLoadedAdapter,
)
from minicdn.traffic import generate_poisson_trace

NETWORK_MULTIPLIERS = {"low": 1.0, "medium": 3.0, "high": 5.0}
TRAFFIC_RATES = {"low": 2.0, "medium": 12.0, "high": 24.0}
SERVER_CONFIGS = (("A", 20.0, 2), ("B", 40.0, 2), ("C", 30.0, 2))
PROCESSING_UNITS = 5.0


def run_diagnostic(
    *,
    network_scenario: str = "low",
    traffic_scenario: str = "high",
    strategy_name: str = "random",
    request_count: int = 200,
    seed: int = 42,
    alpha: float = 0.5,
) -> int:
    if network_scenario not in NETWORK_MULTIPLIERS:
        raise ValueError(f"Unknown network scenario: {network_scenario}")
    if traffic_scenario not in TRAFFIC_RATES:
        raise ValueError(f"Unknown traffic scenario: {traffic_scenario}")
    if strategy_name not in {"random", "minimum_latency", "least_loaded", "hybrid"}:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    if request_count < 1:
        raise ValueError("request_count must be >= 1")

    multiplier = NETWORK_MULTIPLIERS[network_scenario]
    matrix = {
        user_id: {server_id: rtt * multiplier for server_id, rtt in values.items()}
        for user_id, values in BASE_RTT_MATRIX.items()
    }
    network = NetworkModel(matrix)
    trace = generate_poisson_trace(
        number_of_requests=request_count,
        arrival_rate_per_s=TRAFFIC_RATES[traffic_scenario],
        user_ids=sorted(BASE_RTT_MATRIX),
        processing_units=PROCESSING_UNITS,
        seed=seed,
    )
    runtime = SashaServerRuntime(
        [SashaServerConfig(server_id, capacity, workers)
         for server_id, capacity, workers in SERVER_CONFIGS],
        ServerWorkload,
    )

    if strategy_name == "random":
        router = RandomRouter(seed=seed)
    elif strategy_name == "minimum_latency":
        router = MinimumLatencyAdapter(MinimumLatencyStrategy(network), network.get_rtt)
    elif strategy_name == "least_loaded":
        router = SashaLeastLoadedAdapter(select_least_loaded, runtime)
    else:
        router = HybridRouter(
            alpha=alpha,
            rtt_lookup=network.get_rtt,
            workload_estimator=runtime.estimate_completion_time,
        )

    result = SimulationEngine(network, runtime).run(trace, router)
    failures = [event for event in result.events if event.event_type == "REQUEST_FAILED"]
    unserved = [event for event in result.events if event.event_type == "REQUEST_UNSERVED"]

    print("Targeted campaign diagnostic")
    print(f"Network: {network_scenario} ({multiplier:g}x)")
    print(f"Traffic: {traffic_scenario} ({TRAFFIC_RATES[traffic_scenario]:g} req/s)")
    print(f"Strategy: {strategy_name} | requests: {request_count} | seed: {seed}")
    print(
        f"Completed: {result.summary.completed_requests} | "
        f"Failed: {result.summary.failed_requests} | "
        f"Unserved: {result.summary.unserved_requests}"
    )

    if failures:
        print("\nFailure event details:")
        for event in failures:
            print(json.dumps({
                "request_id": event.request_id,
                "time_s": event.time_s,
                "server_id": event.server_id,
                "details": event.details,
            }, sort_keys=True))
    else:
        print("\nNo failed request was reproduced in this targeted run.")

    if unserved:
        print("\nUnserved event details:")
        for event in unserved:
            print(json.dumps({
                "request_id": event.request_id,
                "time_s": event.time_s,
                "details": event.details,
            }, sort_keys=True))

    return len(failures)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", choices=NETWORK_MULTIPLIERS, default="low")
    parser.add_argument("--traffic", choices=TRAFFIC_RATES, default="high")
    parser.add_argument(
        "--strategy",
        choices=("random", "minimum_latency", "least_loaded", "hybrid"),
        default="random",
    )
    parser.add_argument("--request-count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--alpha", type=float, default=0.5)
    args = parser.parse_args()
    return 1 if run_diagnostic(
        network_scenario=args.network,
        traffic_scenario=args.traffic,
        strategy_name=args.strategy,
        request_count=args.request_count,
        seed=args.seed,
        alpha=args.alpha,
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
