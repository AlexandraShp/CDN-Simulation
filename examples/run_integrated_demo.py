"""Run all four routing strategies using the integrated local components.

The inspected snapshots of Nirmin's and Sasha's modules are included under
``src/minicdn/integrations``. No separate teammate repository folders are
required to run this demonstration.

Example (PowerShell, from the workspace root):

    python examples/run_integrated_demo.py --request-count 100 --arrival-rate 1.5

Server capacities and request workload are demonstration settings. Confirm
team-approved settings before treating output as final experimental evidence.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

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


def _write_results(results, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "strategy",
        "total_requests",
        "completed_requests",
        "unserved_requests",
        "failed_requests",
        "average_response_ms",
        "median_response_ms",
        "p95_response_ms",
        "average_queue_wait_ms",
        "average_network_ms",
        "throughput_requests_per_s",
        "utilization_by_server",
        "simulation_end_time_s",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for result in results:
            summary = result.summary
            to_ms = lambda value: None if value is None else value * 1000.0
            writer.writerow(
                {
                    "strategy": result.strategy_name,
                    "total_requests": summary.total_requests,
                    "completed_requests": summary.completed_requests,
                    "unserved_requests": summary.unserved_requests,
                    "failed_requests": summary.failed_requests,
                    "average_response_ms": to_ms(summary.average_response_time_s),
                    "median_response_ms": to_ms(summary.median_response_time_s),
                    "p95_response_ms": to_ms(summary.p95_response_time_s),
                    "average_queue_wait_ms": to_ms(summary.average_queue_wait_s),
                    "average_network_ms": to_ms(summary.average_network_time_s),
                    "throughput_requests_per_s": summary.throughput_requests_per_s,
                    "utilization_by_server": repr(summary.utilization_by_server),
                    "simulation_end_time_s": result.simulation_end_time_s,
                }
            )


def run_demo(
    *,
    request_count: int = 100,
    arrival_rate: float = 1.5,
    seed: int = 42,
    output: Path = Path("experiments/results/integrated_demo_comparison.csv"),
) -> Path:
    if request_count < 1:
        raise ValueError("request_count must be >= 1")
    if arrival_rate <= 0:
        raise ValueError("arrival_rate must be > 0")

    network_model = NetworkModel(BASE_RTT_MATRIX)
    server_configs = [
        # Demonstration capacities, not yet final team-approved values.
        SashaServerConfig("A", capacity_units_per_s=20.0, worker_count=2),
        SashaServerConfig("B", capacity_units_per_s=40.0, worker_count=2),
        SashaServerConfig("C", capacity_units_per_s=30.0, worker_count=2),
    ]
    trace: list[Request] = generate_poisson_trace(
        number_of_requests=request_count,
        arrival_rate_per_s=arrival_rate,
        user_ids=sorted(BASE_RTT_MATRIX),
        processing_units=5.0,
        seed=seed,
    )

    # Each strategy receives fresh servers and the same input trace.
    results = []
    for strategy_name in ("random", "minimum_latency", "least_loaded", "hybrid"):
        runtime = SashaServerRuntime(server_configs, ServerWorkload)
        if strategy_name == "random":
            router = RandomRouter(seed=seed)
        elif strategy_name == "minimum_latency":
            router = MinimumLatencyAdapter(
                MinimumLatencyStrategy(network_model), network_model.get_rtt
            )
        elif strategy_name == "least_loaded":
            router = SashaLeastLoadedAdapter(select_least_loaded, runtime)
        else:
            router = HybridRouter(
                alpha=0.5,
                rtt_lookup=network_model.get_rtt,
                workload_estimator=runtime.estimate_completion_time,
            )
        results.append(SimulationEngine(network_model, runtime).run(trace, router))

    output_path = output.resolve()
    _write_results(results, output_path)
    print("Integrated Mini CDN demonstration completed.")
    print(f"Requests: {len(trace)} | Arrival rate: {arrival_rate} req/s | Seed: {seed}")
    print(f"CSV results: {output_path}")
    for result in results:
        summary = result.summary
        average_ms = (
            "n/a"
            if summary.average_response_time_s is None
            else f"{summary.average_response_time_s * 1000:.3f} ms"
        )
        print(
            f"{result.strategy_name:16s} completed={summary.completed_requests:4d} "
            f"failed={summary.failed_requests:3d} avg_response={average_ms}"
        )
    print("NOTE: Results use demonstration server capacities and processing units.")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-count", type=int, default=100)
    parser.add_argument("--arrival-rate", type=float, default=1.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/results/integrated_demo_comparison.csv"),
    )
    args = parser.parse_args()
    if args.request_count < 1 or args.arrival_rate <= 0:
        parser.error("request-count and arrival-rate must be positive")
    run_demo(
        request_count=args.request_count,
        arrival_rate=args.arrival_rate,
        seed=args.seed,
        output=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
