# Mini CDN experiments

All teammate components needed by the experiment runners are included as
inspected snapshots under `src/minicdn/integrations`. You do not need to clone
or extract Nirmin's or Sasha's branches on the same computer to run these
scripts.

## Preliminary network, traffic and Hybrid sensitivity experiments

```powershell
python experiments/run_pre_server_experiments.py
```

Outputs are written to `experiments/results/`:

- `network_routing_comparison.csv`: Random vs Minimum Latency using RTT only.
- `poisson_traffic_characteristics.csv`: statistical characteristics of generated arrivals.
- `hybrid_alpha_sensitivity_synthetic.csv`: Hybrid routing decisions using explicitly synthetic workload values.

These preliminary experiments do **not** measure end-to-end response time,
queue waiting time, server throughput or utilization.

## Integrated four-strategy demonstration

```powershell
python examples/run_integrated_demo.py --request-count 100 --arrival-rate 1.5
```

This runs all four strategies against the same request trace and writes
`experiments/results/integrated_demo_comparison.csv`.

## Repeated integrated experiment campaign

```powershell
python experiments/run_experiment_campaign.py --request-count 200 --repeats 3
```

The campaign compares Random, Minimum Latency, Least Loaded and Hybrid over
low/medium/high network-delay multipliers and low/medium/high Poisson arrival
rates. Each strategy receives the same trace within each repetition and starts
with fresh server objects. Hybrid is also run at alpha values 0, 0.25, 0.50,
0.75 and 1.00.

The campaign currently uses demonstration server capacities and processing
units. Confirm team-approved values before treating these as final findings.

## Metrics

- Average response time (ms)
- Median response time (ms)
- P95 response time (ms)
- Average queue waiting time (ms)
- Average network time (ms)
- Throughput (completed requests/s)
- Average server utilization (fraction from 0 to 1)
- Completed, unserved and failed request counts

Summary CSVs contain means and sample standard deviations across repetitions.
The results describe this simulation and its assumptions; they are not
measurements from a deployed production CDN.
