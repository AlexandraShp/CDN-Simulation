"""Run network, traffic-generation and synthetic-Hybrid experiments.

Example (PowerShell, from the workspace root)::

    python experiments/run_pre_server_experiments.py

The inspected snapshot of Nirmin's network components is bundled locally.
No external branch folders are required. These preliminary experiments do not
claim real server workload or end-to-end CDN performance.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

# Make the local src-layout package importable when this file is run directly.
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SRC = WORKSPACE_ROOT / "src"
if str(LOCAL_SRC) not in sys.path:
    sys.path.insert(0, str(LOCAL_SRC))

from minicdn.integrations.nirmin import NetworkModel, MinimumLatencyStrategy, create_delay_scenario  # noqa: E402
from minicdn.experiments.pre_server import (  # noqa: E402
    evaluate_hybrid_alpha_sensitivity,
    evaluate_network_routing,
    summarize_poisson_trace,
)


SYNTHETIC_WORKLOAD_SECONDS = {
    # Demonstration values only. These are not taken from Sasha's server model.
    "A": 0.250,
    "B": 0.020,
    "C": 0.030,
}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Cannot write an empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(args: argparse.Namespace) -> Path:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    network_rows: list[dict[str, Any]] = []
    low_delay_model = None
    for scenario_name in ("low", "medium", "high"):
        network_model = create_delay_scenario(scenario_name)
        if not isinstance(network_model, NetworkModel):
            raise TypeError("Nirmin's scenario factory did not return NetworkModel")
        if scenario_name == "low":
            low_delay_model = network_model
        minimum_strategy = MinimumLatencyStrategy(network_model)
        observations = evaluate_network_routing(
            scenario_name=scenario_name,
            network_model=network_model,
            minimum_latency_strategy=minimum_strategy,
            trials_per_user=args.trials_per_user,
            seed=args.seed,
        )
        network_rows.extend(asdict(item) for item in observations)

    if low_delay_model is None:
        raise RuntimeError("Could not create Nirmin's low-delay scenario")

    users = sorted(low_delay_model.rtt_matrix)
    server_ids = sorted(low_delay_model.rtt_matrix[users[0]])

    traffic_rows = []
    for rate in args.arrival_rates:
        observation = summarize_poisson_trace(
            arrival_rate_per_s=rate,
            request_count=args.requests,
            user_ids=users,
            processing_units=args.processing_units,
            seed=args.seed,
        )
        traffic_rows.append(asdict(observation))

    # The shipped example values are intentionally limited to Nirmin's A/B/C
    # topology. They are clearly labelled synthetic, not Sasha measurements.
    if set(server_ids) != set(SYNTHETIC_WORKLOAD_SECONDS):
        raise ValueError(
            "The illustrative Hybrid alpha example expects server IDs A, B, C. "
            f"Nirmin's current topology supplied {server_ids}. Update "
            "SYNTHETIC_WORKLOAD_SECONDS in this script only if the topology changes."
        )
    hybrid_observations = evaluate_hybrid_alpha_sensitivity(
        network_model=low_delay_model,
        user_id=users[0],
        server_ids=server_ids,
        synthetic_workload_seconds=SYNTHETIC_WORKLOAD_SECONDS,
    )
    hybrid_rows = []
    for observation in hybrid_observations:
        row = asdict(observation)
        row["candidate_scores"] = json.dumps(row["candidate_scores"], sort_keys=True)
        row["workload_values_s"] = json.dumps(row["workload_values_s"], sort_keys=True)
        hybrid_rows.append(row)

    write_csv(output_dir / "network_routing_comparison.csv", network_rows)
    write_csv(output_dir / "poisson_traffic_characteristics.csv", traffic_rows)
    write_csv(output_dir / "hybrid_alpha_sensitivity_synthetic.csv", hybrid_rows)

    notes = """# Pre-server experiment notes

These outputs are intentionally limited to experiments that do not require
Sasha's server runtime.

- `network_routing_comparison.csv`: Random vs Nirmin's Minimum Latency using
  RTT only, with Nirmin's low/medium/high delay scenarios.
- `poisson_traffic_characteristics.csv`: arrival-trace characteristics for
  several configured Poisson arrival rates. These are traffic statistics,
  not server performance results.
- `hybrid_alpha_sensitivity_synthetic.csv`: validates Hybrid's alpha decision
  behavior using illustrative workload values. The values are synthetic and
  are NOT measurements from Sasha's server model.

Do NOT use these files as final claims about response time, queue waiting time,
throughput, server utilization, or the overall performance winner. Those require
integration with Sasha's actual multi-worker FIFO server runtime and a complete
end-to-end simulation.
"""
    (output_dir / "README.md").write_text(notes, encoding="utf-8")
    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=int, default=1_000)
    parser.add_argument("--trials-per-user", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--processing-units", type=float, default=100.0)
    parser.add_argument(
        "--arrival-rates",
        type=float,
        nargs="+",
        default=[0.5, 1.0, 2.0, 5.0],
        help="Poisson request rates to summarize, in requests per second",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=WORKSPACE_ROOT / "experiments" / "results",
    )
    args = parser.parse_args()
    if args.requests < 1:
        parser.error("--requests must be >= 1")
    if args.trials_per_user < 1:
        parser.error("--trials-per-user must be >= 1")
    if args.processing_units <= 0:
        parser.error("--processing-units must be > 0")
    if any(rate <= 0 for rate in args.arrival_rates):
        parser.error("all --arrival-rates values must be > 0")
    return args


if __name__ == "__main__":
    output = run(parse_args())
    print(f"Pre-server experiments completed. Results saved to: {output}")
