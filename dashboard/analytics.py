"""Data loading, validation and aggregation for the Mini CDN dashboard.

This module intentionally has no Streamlit dependency, so its data checks can
be tested independently from the user interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

STRATEGY_FILES = {
    "strategy_runs": "strategy_runs.csv",
    "strategy_summary": "strategy_summary.csv",
    "hybrid_alpha_runs": "hybrid_alpha_runs.csv",
    "hybrid_alpha_summary": "hybrid_alpha_summary.csv",
}

REQUIRED_STRATEGY_COLUMNS = {
    "network_scenario", "traffic_scenario", "repetition", "seed", "strategy",
    "request_count", "completed_requests", "unserved_requests", "failed_requests",
    "average_response_ms", "median_response_ms", "p95_response_ms",
    "average_queue_wait_ms", "average_network_ms", "throughput_requests_per_s",
    "average_server_utilization",
}
REQUIRED_ALPHA_COLUMNS = REQUIRED_STRATEGY_COLUMNS | {"alpha"}
STRATEGY_ORDER = ["random", "minimum_latency", "least_loaded", "hybrid"]
STRATEGY_LABELS = {
    "random": "Random",
    "minimum_latency": "Minimum Latency",
    "least_loaded": "Least Loaded",
    "hybrid": "Hybrid",
}
METRICS: dict[str, dict[str, str]] = {
    "average_response_ms": {"label": "Average response time", "unit": "ms", "direction": "lower"},
    "median_response_ms": {"label": "Median response time", "unit": "ms", "direction": "lower"},
    "p95_response_ms": {"label": "P95 response time", "unit": "ms", "direction": "lower"},
    "average_queue_wait_ms": {"label": "Average queue waiting time", "unit": "ms", "direction": "lower"},
    "average_network_ms": {"label": "Average network time", "unit": "ms", "direction": "lower"},
    "throughput_requests_per_s": {"label": "Throughput", "unit": "requests/s", "direction": "higher"},
    "average_server_utilization": {"label": "Average server utilization", "unit": "%", "direction": "context"},
}


@dataclass(frozen=True)
class CampaignData:
    strategy_runs: pd.DataFrame
    strategy_summary: pd.DataFrame
    hybrid_alpha_runs: pd.DataFrame
    hybrid_alpha_summary: pd.DataFrame
    validation: dict[str, Any]
    directory: Path


def _read_csv(path: Path, required: set[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required campaign file is missing: {path}")
    frame = pd.read_csv(path)
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {', '.join(sorted(missing))}")
    if frame.empty:
        raise ValueError(f"{path.name} contains no observations")
    return frame


def load_campaign_data(directory: str | Path) -> CampaignData:
    """Load all four campaign CSVs and validate their internal consistency."""
    folder = Path(directory).expanduser().resolve()
    strategy_runs = _read_csv(folder / STRATEGY_FILES["strategy_runs"], REQUIRED_STRATEGY_COLUMNS)
    strategy_summary = _read_csv(folder / STRATEGY_FILES["strategy_summary"], {
        "network_scenario", "traffic_scenario", "strategy", "repetitions",
        "mean_average_response_ms", "mean_p95_response_ms", "mean_average_queue_wait_ms",
    })
    hybrid_alpha_runs = _read_csv(folder / STRATEGY_FILES["hybrid_alpha_runs"], REQUIRED_ALPHA_COLUMNS)
    hybrid_alpha_summary = _read_csv(folder / STRATEGY_FILES["hybrid_alpha_summary"], {
        "network_scenario", "traffic_scenario", "alpha", "repetitions",
        "mean_average_response_ms", "mean_p95_response_ms", "mean_average_queue_wait_ms",
    })

    observed_strategies = set(strategy_runs["strategy"].dropna().astype(str))
    observed_alphas = sorted(float(value) for value in hybrid_alpha_runs["alpha"].dropna().unique())
    failures = int(strategy_runs["failed_requests"].fillna(0).sum())
    unserved = int(strategy_runs["unserved_requests"].fillna(0).sum())
    alpha_failures = int(hybrid_alpha_runs["failed_requests"].fillna(0).sum())
    alpha_unserved = int(hybrid_alpha_runs["unserved_requests"].fillna(0).sum())
    strategy_accounting = (
        strategy_runs["completed_requests"].fillna(0)
        + strategy_runs["unserved_requests"].fillna(0)
        + strategy_runs["failed_requests"].fillna(0)
        == strategy_runs["request_count"]
    )
    alpha_accounting = (
        hybrid_alpha_runs["completed_requests"].fillna(0)
        + hybrid_alpha_runs["unserved_requests"].fillna(0)
        + hybrid_alpha_runs["failed_requests"].fillna(0)
        == hybrid_alpha_runs["request_count"]
    )
    repetitions = sorted(int(value) for value in strategy_runs["repetition"].dropna().unique())
    network_scenarios = sorted(strategy_runs["network_scenario"].dropna().astype(str).unique())
    traffic_scenarios = sorted(strategy_runs["traffic_scenario"].dropna().astype(str).unique())

    duplicate_strategy_keys = int(strategy_runs.duplicated(
        ["network_scenario", "traffic_scenario", "repetition", "strategy"]
    ).sum())
    duplicate_alpha_keys = int(hybrid_alpha_runs.duplicated(
        ["network_scenario", "traffic_scenario", "repetition", "alpha"]
    ).sum())

    validation = {
        "strategy_rows": int(len(strategy_runs)),
        "alpha_rows": int(len(hybrid_alpha_runs)),
        "strategy_count": len(observed_strategies),
        "strategies": sorted(observed_strategies),
        "alpha_values": observed_alphas,
        "repetitions": repetitions,
        "repetition_count": len(repetitions),
        "network_scenarios": network_scenarios,
        "traffic_scenarios": traffic_scenarios,
        "failed_requests": failures,
        "unserved_requests": unserved,
        "alpha_failed_requests": alpha_failures,
        "alpha_unserved_requests": alpha_unserved,
        "duplicate_strategy_keys": duplicate_strategy_keys,
        "duplicate_alpha_keys": duplicate_alpha_keys,
        "request_accounting_consistent": bool(strategy_accounting.all() and alpha_accounting.all()),
        "all_requests_completed": bool(
            failures == 0 and unserved == 0 and alpha_failures == 0 and alpha_unserved == 0
            and strategy_accounting.all() and alpha_accounting.all()
        ),
        "complete_four_strategy_matrix": observed_strategies == set(STRATEGY_ORDER)
            and len(network_scenarios) == 3 and len(traffic_scenarios) == 3,
    }

    if not validation["all_requests_completed"]:
        validation["warnings"] = [
            "The campaign includes failed or unserved requests, or request accounting does not reconcile."
        ]
    else:
        validation["warnings"] = []
    if duplicate_strategy_keys or duplicate_alpha_keys:
        validation["warnings"].append("Duplicate run keys were detected.")
    if repetitions and len(repetitions) != 10:
        validation["warnings"].append(
            f"This dataset has {len(repetitions)} repetition(s), not the ten-repetition reference campaign."
        )

    # Check that precomputed summaries agree with the raw run observations.
    raw_strategy = strategy_runs.groupby(
        ["network_scenario", "traffic_scenario", "strategy"], as_index=False
    )["average_response_ms"].mean().rename(columns={"average_response_ms": "raw_mean_response"})
    joined_strategy = strategy_summary.merge(
        raw_strategy, on=["network_scenario", "traffic_scenario", "strategy"], how="outer", indicator=True
    )
    strategy_consistent = bool(
        (joined_strategy["_merge"] == "both").all()
        and ((joined_strategy["mean_average_response_ms"] - joined_strategy["raw_mean_response"]).abs() < 1e-6).all()
    )
    raw_alpha = hybrid_alpha_runs.groupby(
        ["network_scenario", "traffic_scenario", "alpha"], as_index=False
    )["average_response_ms"].mean().rename(columns={"average_response_ms": "raw_mean_response"})
    joined_alpha = hybrid_alpha_summary.merge(
        raw_alpha, on=["network_scenario", "traffic_scenario", "alpha"], how="outer", indicator=True
    )
    alpha_consistent = bool(
        (joined_alpha["_merge"] == "both").all()
        and ((joined_alpha["mean_average_response_ms"] - joined_alpha["raw_mean_response"]).abs() < 1e-6).all()
    )
    validation["summary_consistent"] = strategy_consistent and alpha_consistent
    if not validation["summary_consistent"]:
        validation["warnings"].append("At least one summary CSV does not match its raw run observations.")

    return CampaignData(
        strategy_runs=strategy_runs,
        strategy_summary=strategy_summary,
        hybrid_alpha_runs=hybrid_alpha_runs,
        hybrid_alpha_summary=hybrid_alpha_summary,
        validation=validation,
        directory=folder,
    )


def apply_scenario_filters(
    frame: pd.DataFrame,
    network_scenario: str = "All",
    traffic_scenario: str = "All",
) -> pd.DataFrame:
    filtered = frame.copy()
    if network_scenario != "All":
        filtered = filtered[filtered["network_scenario"] == network_scenario]
    if traffic_scenario != "All":
        filtered = filtered[filtered["traffic_scenario"] == traffic_scenario]
    return filtered


def strategy_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate run observations equally across the selected scenarios."""
    if frame.empty:
        return pd.DataFrame()
    metrics = [
        "average_response_ms", "median_response_ms", "p95_response_ms",
        "average_queue_wait_ms", "average_network_ms",
        "throughput_requests_per_s", "average_server_utilization",
    ]
    grouped = frame.groupby("strategy", as_index=False)[metrics].mean()
    grouped["response_stdev_ms"] = frame.groupby("strategy")["average_response_ms"].std().values
    grouped["strategy_label"] = grouped["strategy"].map(STRATEGY_LABELS).fillna(grouped["strategy"])
    return grouped.sort_values("average_response_ms", ascending=True).reset_index(drop=True)


def scenario_strategy_metrics(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    if metric not in frame.columns:
        raise ValueError(f"Unknown metric: {metric}")
    grouped = frame.groupby(
        ["network_scenario", "traffic_scenario", "strategy"], as_index=False
    )[metric].mean()
    grouped["strategy_label"] = grouped["strategy"].map(STRATEGY_LABELS).fillna(grouped["strategy"])
    grouped["scenario_label"] = (
        grouped["network_scenario"].str.title() + " network / "
        + grouped["traffic_scenario"].str.title() + " traffic"
    )
    return grouped


def alpha_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    return frame.groupby("alpha", as_index=False).agg(
        average_response_ms=("average_response_ms", "mean"),
        median_response_ms=("median_response_ms", "mean"),
        p95_response_ms=("p95_response_ms", "mean"),
        average_queue_wait_ms=("average_queue_wait_ms", "mean"),
        average_network_ms=("average_network_ms", "mean"),
        throughput_requests_per_s=("throughput_requests_per_s", "mean"),
        average_server_utilization=("average_server_utilization", "mean"),
        observations=("average_response_ms", "size"),
    ).sort_values("alpha")


def best_alpha_by_scenario(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.groupby(
        ["network_scenario", "traffic_scenario", "alpha"], as_index=False
    )["average_response_ms"].mean()
    if grouped.empty:
        return grouped
    idx = grouped.groupby(["network_scenario", "traffic_scenario"])["average_response_ms"].idxmin()
    best = grouped.loc[idx].sort_values(["network_scenario", "traffic_scenario"]).reset_index(drop=True)
    best = best.rename(columns={"alpha": "best_alpha", "average_response_ms": "best_average_response_ms"})
    return best


def improvement_percent(reference: float, candidate: float) -> float | None:
    """Positive values mean candidate is lower/faster than reference."""
    if reference == 0:
        return None
    return (reference - candidate) / reference * 100.0
