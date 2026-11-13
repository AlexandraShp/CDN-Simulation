"""Run a reproducible Mini CDN experiment campaign across all four strategies.

The same Poisson request trace is reused by every strategy within a scenario
and repetition. Each strategy receives fresh server instances with identical
configuration. Network scenarios use Nirmin's documented RTT multipliers
(1x, 3x, 5x); traffic scenarios vary the Poisson arrival rate.

Example (PowerShell, from the workspace root):

python experiments/run_experiment_campaign.py --request-count 300 --repeats 3

Inspected snapshots of Nirmin's and Sasha's components are bundled inside
``src/minicdn/integrations``. No separate branch folders are required.

All server capacities and processing units are explicit demonstration values
until the team approves the final experiment configuration. The CSV output
must therefore be labelled provisional until those settings are confirmed.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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


# These are copied from Nirmin's documented experiment configuration.
NETWORK_SCENARIOS: dict[str, float] = {
    "low": 1.0,
    "medium": 3.0,
    "high": 5.0,
}

# Arrival rates are requests per second; high traffic approaches busy-server
# conditions with the demonstration server capacities below.
TRAFFIC_SCENARIOS: dict[str, float] = {
    "low": 2.0,
    "medium": 12.0,
    "high": 24.0,
}

HYBRID_ALPHAS = (0.0, 0.25, 0.50, 0.75, 1.0)
DEFAULT_SEEDS = (42, 43, 44)

# Demonstration settings only. Replace with team-approved values before
# reporting final performance claims.
DEFAULT_SERVER_CONFIGS = (
    ("A", 20.0, 2),
    ("B", 40.0, 2),
    ("C", 30.0, 2),
)
DEFAULT_PROCESSING_UNITS = 5.0


@dataclass(frozen=True)
class RunRow:
    network_scenario: str
    network_multiplier: float
    traffic_scenario: str
    arrival_rate_per_s: float
    request_count: int
    repetition: int
    seed: int
    strategy: str
    alpha: float | None
    completed_requests: int
    unserved_requests: int
    failed_requests: int
    average_response_ms: float | None
    median_response_ms: float | None
    p95_response_ms: float | None
    average_queue_wait_ms: float | None
    average_network_ms: float | None
    throughput_requests_per_s: float | None
    average_server_utilization: float | None
    simulation_end_time_s: float
    failure_diagnostics: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "network_scenario": self.network_scenario,
            "network_multiplier": self.network_multiplier,
            "traffic_scenario": self.traffic_scenario,
            "arrival_rate_per_s": self.arrival_rate_per_s,
            "request_count": self.request_count,
            "repetition": self.repetition,
            "seed": self.seed,
            "strategy": self.strategy,
            "alpha": self.alpha,
            "completed_requests": self.completed_requests,
            "unserved_requests": self.unserved_requests,
            "failed_requests": self.failed_requests,
            "average_response_ms": self.average_response_ms,
            "median_response_ms": self.median_response_ms,
            "p95_response_ms": self.p95_response_ms,
            "average_queue_wait_ms": self.average_queue_wait_ms,
            "average_network_ms": self.average_network_ms,
            "throughput_requests_per_s": self.throughput_requests_per_s,
            "average_server_utilization": self.average_server_utilization,
            "simulation_end_time_s": self.simulation_end_time_s,
            "failure_diagnostics": self.failure_diagnostics,
        }


def make_network_matrix(multiplier: float) -> dict[str, dict[str, float]]:
    return {
        user_id: {
            server_id: rtt * multiplier
            for server_id, rtt in server_rtts.items()
        }
        for user_id, server_rtts in BASE_RTT_MATRIX.items()
    }


def _optional_ms(value: float | None) -> float | None:
    return None if value is None else float(value) * 1000.0


def run_one_strategy(
    *,
    strategy_name: str,
    alpha: float | None,
    trace: list[Request],
    seed: int,
    network_model: Any,
    server_workload_factory: type,
    least_loaded_selector: Callable[..., Any],
    network_model_strategy_class: type,
) -> RunRow:
    # New runtime + engine for every strategy guarantees a fresh server state.
    server_configs = [
        SashaServerConfig(server_id, capacity, workers)
        for server_id, capacity, workers in DEFAULT_SERVER_CONFIGS
    ]
    runtime = SashaServerRuntime(server_configs, server_workload_factory)
    engine = SimulationEngine(network_model, runtime)

    if strategy_name == "random":
        router = RandomRouter(seed=seed)
    elif strategy_name == "minimum_latency":
        nirmin_strategy = network_model_strategy_class(network_model)
        router = MinimumLatencyAdapter(nirmin_strategy, network_model.get_rtt)
    elif strategy_name == "least_loaded":
        router = SashaLeastLoadedAdapter(least_loaded_selector, runtime)
    elif strategy_name == "hybrid":
        if alpha is None:
            raise ValueError("Hybrid runs require an alpha value")
        router = HybridRouter(
            alpha=alpha,
            rtt_lookup=network_model.get_rtt,
            workload_estimator=runtime.estimate_completion_time,
        )
    else:
        raise ValueError(f"Unsupported strategy: {strategy_name}")

    result = engine.run(trace, router)
    summary = result.summary
    failure_events = [
        event for event in result.events if event.event_type == "REQUEST_FAILED"
    ]
    failure_diagnostics = " || ".join(
        (
            f"request={event.request_id}; time_s={event.time_s:.15g}; "
            f"server={event.server_id or ''}; "
            f"reason={event.details.get('reason', 'No reason recorded')}"
        )
        for event in failure_events
    )
    utilization_values = list(summary.utilization_by_server.values())
    average_utilization = (
        sum(utilization_values) / len(utilization_values)
        if utilization_values
        else None
    )
    return RunRow(
        network_scenario="",
        network_multiplier=1.0,
        traffic_scenario="",
        arrival_rate_per_s=0.0,
        request_count=len(trace),
        repetition=0,
        seed=seed,
        strategy=result.strategy_name,
        alpha=alpha,
        completed_requests=summary.completed_requests,
        unserved_requests=summary.unserved_requests,
        failed_requests=summary.failed_requests,
        average_response_ms=_optional_ms(summary.average_response_time_s),
        median_response_ms=_optional_ms(summary.median_response_time_s),
        p95_response_ms=_optional_ms(summary.p95_response_time_s),
        average_queue_wait_ms=_optional_ms(summary.average_queue_wait_s),
        average_network_ms=_optional_ms(summary.average_network_time_s),
        throughput_requests_per_s=summary.throughput_requests_per_s,
        average_server_utilization=average_utilization,
        simulation_end_time_s=result.simulation_end_time_s,
        failure_diagnostics=failure_diagnostics,
    )


def _write_rows(path: Path, rows: list[RunRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Refusing to write an empty experiment file: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].to_dict()))
        writer.writeheader()
        writer.writerows(row.to_dict() for row in rows)


def _mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _stdev(values: list[float]) -> float | None:
    return statistics.stdev(values) if len(values) >= 2 else (0.0 if values else None)


def aggregate_rows(rows: list[RunRow], *, hybrid_only: bool = False) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[RunRow]] = defaultdict(list)
    for row in rows:
        if hybrid_only:
            if row.strategy != "hybrid":
                continue
            key = (row.network_scenario, row.traffic_scenario, row.alpha)
        else:
            key = (row.network_scenario, row.traffic_scenario, row.strategy, row.alpha)
        groups[key].append(row)

    metrics = (
        "average_response_ms",
        "median_response_ms",
        "p95_response_ms",
        "average_queue_wait_ms",
        "average_network_ms",
        "throughput_requests_per_s",
        "average_server_utilization",
    )
    output: list[dict[str, Any]] = []
    for key, group in sorted(groups.items(), key=lambda item: tuple(str(v) for v in item[0])):
        network_scenario, traffic_scenario = key[0], key[1]
        row: dict[str, Any] = {
            "network_scenario": network_scenario,
            "traffic_scenario": traffic_scenario,
            "strategy": "hybrid" if hybrid_only else key[2],
            "alpha": key[2] if hybrid_only else key[3],
            "repetitions": len(group),
            "average_completed_requests": _mean([float(x.completed_requests) for x in group]),
            "average_failed_requests": _mean([float(x.failed_requests) for x in group]),
        }
        for metric in metrics:
            values = [float(getattr(item, metric)) for item in group if getattr(item, metric) is not None]
            row[f"mean_{metric}"] = _mean(values)
            row[f"stdev_{metric}"] = _stdev(values)
        output.append(row)
    return output


def _write_dict_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Refusing to write an empty summary file: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_campaign(
    *,
    request_count: int,
    repeats: int,
    base_seed: int,
    output_dir: Path,
    traffic_rates: dict[str, float] | None = None,
    network_scenarios: dict[str, float] | None = None,
) -> tuple[list[RunRow], list[RunRow]]:
    if request_count < 1 or repeats < 1:
        raise ValueError("request_count and repeats must both be positive")

    least_loaded_selector = select_least_loaded
    selected_rates = traffic_rates or TRAFFIC_SCENARIOS
    selected_network_scenarios = network_scenarios or NETWORK_SCENARIOS
    users = sorted(BASE_RTT_MATRIX)

    main_rows: list[RunRow] = []
    alpha_rows: list[RunRow] = []
    total_cases = len(selected_rates) * len(selected_network_scenarios) * repeats
    case_number = 0

    for network_name, multiplier in selected_network_scenarios.items():
        matrix = make_network_matrix(multiplier)
        network_model = NetworkModel(matrix)
        for traffic_name, arrival_rate in selected_rates.items():
            for repetition in range(1, repeats + 1):
                case_number += 1
                seed = base_seed + repetition - 1
                trace = generate_poisson_trace(
                    number_of_requests=request_count,
                    arrival_rate_per_s=arrival_rate,
                    user_ids=users,
                    processing_units=DEFAULT_PROCESSING_UNITS,
                    seed=seed,
                )
                print(
                    f"[{case_number}/{total_cases}] network={network_name}, "
                    f"traffic={traffic_name}, repeat={repetition}, seed={seed}"
                )

                baseline_specs = (
                    ("random", None),
                    ("minimum_latency", None),
                    ("least_loaded", None),
                    ("hybrid", 0.50),
                )
                baseline_hybrid: RunRow | None = None
                for strategy_name, alpha in baseline_specs:
                    row = run_one_strategy(
                        strategy_name=strategy_name,
                        alpha=alpha,
                        trace=trace,
                        seed=seed,
                        network_model=network_model,
                        server_workload_factory=ServerWorkload,
                        least_loaded_selector=least_loaded_selector,
                        network_model_strategy_class=MinimumLatencyStrategy,
                    )
                    row = RunRow(
                        **{
                            **row.__dict__,
                            "network_scenario": network_name,
                            "network_multiplier": multiplier,
                            "traffic_scenario": traffic_name,
                            "arrival_rate_per_s": arrival_rate,
                            "repetition": repetition,
                        }
                    )
                    main_rows.append(row)
                    if row.failed_requests:
                        print(
                            f"  WARNING: {row.failed_requests} failed request(s) "
                            f"under {row.strategy}: {row.failure_diagnostics}"
                        )
                    if strategy_name == "hybrid":
                        baseline_hybrid = row

                # Sweep the five alpha values. Reuse the baseline alpha=0.50
                # observation instead of executing that identical run twice.
                for alpha in HYBRID_ALPHAS:
                    if math.isclose(alpha, 0.50):
                        assert baseline_hybrid is not None
                        row = baseline_hybrid
                    else:
                        row = run_one_strategy(
                            strategy_name="hybrid",
                            alpha=alpha,
                            trace=trace,
                            seed=seed,
                            network_model=network_model,
                            server_workload_factory=ServerWorkload,
                            least_loaded_selector=least_loaded_selector,
                            network_model_strategy_class=MinimumLatencyStrategy,
                        )
                        row = RunRow(
                            **{
                                **row.__dict__,
                                "network_scenario": network_name,
                                "network_multiplier": multiplier,
                                "traffic_scenario": traffic_name,
                                "arrival_rate_per_s": arrival_rate,
                                "repetition": repetition,
                            }
                        )
                    alpha_rows.append(row)
                    if row.failed_requests:
                        print(
                            f"  WARNING: {row.failed_requests} failed request(s) "
                            f"under hybrid alpha={alpha}: {row.failure_diagnostics}"
                        )

    _write_rows(output_dir / "strategy_runs.csv", main_rows)
    _write_rows(output_dir / "hybrid_alpha_runs.csv", alpha_rows)
    _write_dict_rows(
        output_dir / "strategy_summary.csv",
        aggregate_rows(main_rows),
    )
    _write_dict_rows(
        output_dir / "hybrid_alpha_summary.csv",
        aggregate_rows(alpha_rows, hybrid_only=True),
    )
    return main_rows, alpha_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-count", type=int, default=200)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--base-seed", type=int, default=42)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("experiments/results/final_campaign")
    )
    args = parser.parse_args()

    try:
        main_rows, alpha_rows = run_campaign(
            request_count=args.request_count,
            repeats=args.repeats,
            base_seed=args.base_seed,
            output_dir=args.output_dir.resolve(),
        )
    except RuntimeError as error:
        parser.error(str(error))

    print("\nExperiment campaign completed.")
    print(f"Strategy observations: {len(main_rows)}")
    print(f"Hybrid alpha observations: {len(alpha_rows)}")
    failed_total = sum(row.failed_requests for row in main_rows)
    failed_total += sum(
        row.failed_requests for row in alpha_rows
        if row.alpha is None or not math.isclose(float(row.alpha), 0.50)
    )
    print(f"Failed requests recorded: {failed_total}")
    print(f"CSV outputs: {args.output_dir.resolve()}")
    print("IMPORTANT: server capacities and processing units are demonstration settings.")
    print("Confirm team-approved settings before using these as final project results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
