from pathlib import Path

import pandas as pd

from dashboard.analytics import (
    alpha_metrics,
    apply_scenario_filters,
    best_alpha_by_scenario,
    load_campaign_data,
    strategy_metrics,
)


RESULTS = Path(__file__).resolve().parents[1] / "experiments" / "results" / "final_campaign"


def test_bundled_ten_repetition_campaign_is_complete_and_consistent():
    campaign = load_campaign_data(RESULTS)
    assert campaign.validation["strategy_rows"] == 360
    assert campaign.validation["alpha_rows"] == 450
    assert campaign.validation["repetition_count"] == 10
    assert campaign.validation["all_requests_completed"]
    assert campaign.validation["duplicate_strategy_keys"] == 0
    assert campaign.validation["duplicate_alpha_keys"] == 0
    assert campaign.validation["summary_consistent"]


def test_strategy_metrics_rank_hybrid_first_for_reference_campaign():
    campaign = load_campaign_data(RESULTS)
    summary = strategy_metrics(campaign.strategy_runs)
    assert summary.iloc[0]["strategy"] == "hybrid"
    assert summary.iloc[0]["average_response_ms"] < summary.iloc[1]["average_response_ms"]


def test_scenario_filters_reduce_data_without_mutating_source():
    campaign = load_campaign_data(RESULTS)
    original_count = len(campaign.strategy_runs)
    filtered = apply_scenario_filters(campaign.strategy_runs, "low", "high")
    assert len(filtered) == 40
    assert len(campaign.strategy_runs) == original_count
    assert set(filtered.network_scenario) == {"low"}
    assert set(filtered.traffic_scenario) == {"high"}


def test_alpha_metrics_and_best_alpha_by_scenario():
    campaign = load_campaign_data(RESULTS)
    metrics = alpha_metrics(campaign.hybrid_alpha_runs)
    assert list(metrics.alpha) == [0.0, 0.25, 0.5, 0.75, 1.0]
    best = best_alpha_by_scenario(campaign.hybrid_alpha_runs)
    assert len(best) == 9
    low_high = best[(best.network_scenario == "low") & (best.traffic_scenario == "high")]
    assert float(low_high.iloc[0].best_alpha) == 0.75


def test_reference_campaign_has_consistent_request_accounting():
    campaign = load_campaign_data(RESULTS)
    assert campaign.validation["request_accounting_consistent"]
    assert campaign.validation["all_requests_completed"]
