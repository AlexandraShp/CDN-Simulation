# Final Mini CDN Experiment Campaign

## Campaign design

For every network scenario, traffic scenario and repetition, the campaign
creates one Poisson request trace and reuses that exact trace for each routing
strategy. Every strategy run gets freshly constructed Sasha server instances
with identical configuration, so one strategy cannot inherit another
strategy's queue state.

The main comparison runs:

- Random
- Minimum Latency
- Least Loaded
- Hybrid (alpha = 0.50)

A separate Hybrid sensitivity sweep runs alpha = 0, 0.25, 0.50, 0.75 and 1.00.
The alpha = 0.50 run is reused from the main comparison.

## Scenarios

### Network delay

These multipliers match Nirmin's `experiments/delay_scenarios.py`:

| Scenario | RTT multiplier |
|---|---:|
| Low | 1x |
| Medium | 3x |
| High | 5x |

The multiplier applies to every user/server RTT. It changes the magnitude of
network delays but preserves the ranking of servers for each user. Therefore,
these tests investigate delay sensitivity, not changing network topology.

### Traffic intensity

| Scenario | Poisson arrival rate |
|---|---:|
| Low | 2 requests/s |
| Medium | 12 requests/s |
| High | 24 requests/s |

Defaults are 200 requests per trace, 3 repetitions, and seeds 42, 43 and 44.

## Demonstration server settings

The first campaign uses the settings from the integrated demonstration:

| Server | Capacity (processing units/s per worker) | Workers |
|---|---:|---:|
| A | 20 | 2 |
| B | 40 | 2 |
| C | 30 | 2 |

Each request requires 5 processing units. These are demonstration assumptions,
not confirmed final team settings. Confirm them before presenting final results.

## Metrics

- Average response time (ms)
- Median response time (ms)
- P95 response time (ms)
- Average queue waiting time (ms)
- Average network time (ms)
- Throughput (completed requests/s)
- Average server utilization (fraction from 0 to 1)
- Completed, unserved and failed request counts

The summary CSVs contain means and sample standard deviations across repeats.

## Run command

From the Saif workspace root, after installing the project and SimPy dependency:

```powershell
python experiments/run_experiment_campaign.py --request-count 200 --repeats 3
```

Use `--output-dir` to choose a different output folder.

## Output files

- `strategy_runs.csv`
- `hybrid_alpha_runs.csv`
- `strategy_summary.csv`
- `hybrid_alpha_summary.csv`

These results describe the simulation and the configured assumptions. They
are not measurements from a deployed production CDN.
