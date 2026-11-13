# Experiment results and interpretation

This folder contains preliminary experiments and the integrated ten-repetition
reference campaign. Keep their claims separate.

## Preliminary experiments

- `network_routing_comparison.csv`: network-only Random vs Minimum Latency.
- `poisson_traffic_characteristics.csv`: arrival trace statistics.
- `hybrid_alpha_sensitivity_synthetic.csv`: decision sensitivity using synthetic
  workload values, not Sasha's server measurements.

These preliminary files do not establish complete server-performance findings.

## Integrated reference campaign — `final_campaign/`

Contains the four uploaded ten-repetition campaign CSV files and `campaign_metadata.json`:

- `strategy_runs.csv`: four routing strategies at alpha 0.50 for Hybrid.
- `hybrid_alpha_runs.csv`: Hybrid at alpha 0, 0.25, 0.50, 0.75 and 1.00.
- `strategy_summary.csv`: means and sample standard deviations over repetitions.
- `hybrid_alpha_summary.csv`: means and sample standard deviations by alpha.

The reference set contains 360 strategy observations and 450 alpha observations,
with zero failed and zero unserved requests. Alpha=0.50 is the shared baseline
Hybrid observation in both exports; do not count it twice as an independent run.

## Measurement units and reporting cautions

- All `*_ms` columns are milliseconds.
- Throughput is completed requests per second.
- Utilization is a fraction between 0 and 1.
- P95 in the summary is the mean of run-level P95 statistics, not a pooled
  request-level percentile.
- The reference runner uses demonstration capacities and processing units.
  Confirm team-approved values before presenting the campaign as final project
  performance.
- Network scenarios multiply all RTTs by 1, 3 or 5, preserving the server
  ranking for each user.
- Findings apply to this simulation model, not a deployed production CDN.
