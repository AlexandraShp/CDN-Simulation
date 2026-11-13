# Mini CDN — Ten-Repetition Experiment Analysis

## Dataset validation

The bundled reference campaign contains:

- 360 strategy observations: 4 strategies × 9 network/traffic combinations × 10 repetitions.
- 450 Hybrid alpha observations: 5 alpha values × 9 combinations × 10 repetitions.
- 200 requests per generated trace.
- 10 repetitions with seeds 42–51.
- Zero failed and zero unserved requests in both result datasets.
- No duplicate run keys; the strategy summary and alpha summary match their raw CSV data.

The alpha=0.50 observation is the same baseline Hybrid run also recorded in the four-strategy file. Do not count it as a separate independent run when combining the two CSV datasets.

## Overall average response time

Equal-weighted mean of the 90 run-level observations per strategy:

| Strategy | Average response (ms) | Median response (ms) | Mean run-level P95 (ms) | Queue wait (ms) | Network time (ms) | Throughput (req/s) |
|---|---:|---:|---:|---:|---:|---:|
| Random | 415.200 | 356.614 | 752.041 | 63.140 | 171.622 | 11.837 |
| Minimum Latency | 297.538 | 239.572 | 556.802 | 57.242 | 59.505 | 12.024 |
| Least Loaded | 324.040 | 323.296 | 473.722 | 27.347 | 160.494 | 12.406 |
| Hybrid (α=0.50) | 253.681 | 236.857 | 348.680 | 18.226 | 79.745 | 12.543 |

Hybrid's mean response time is 38.9% lower than Random, 14.7% lower than Minimum Latency, and 21.7% lower than Least Loaded in this experiment configuration.

## Hybrid alpha sweep

| Alpha | Average response (ms) | Queue wait (ms) | Mean run-level P95 (ms) |
|---:|---:|---:|---:|
| 0.00 | 324.040 | 27.347 | 473.722 |
| 0.25 | 273.520 | 21.111 | 402.587 |
| 0.50 | 253.681 | 18.226 | 348.680 |
| 0.75 | 261.648 | 28.064 | 392.784 |
| 1.00 | 297.538 | 57.242 | 556.802 |

Alpha=0.50 gives the lowest overall mean response time across the nine scenarios. Alpha=0.75 is best in the low-network/high-traffic scenario; alpha=0.50 is best in the other eight scenarios.

## Interpretation

- Minimum Latency has the lowest mean network time, but not the lowest end-to-end response time.
- Least Loaded reduces queue time compared with Random and Minimum Latency.
- Hybrid achieves the lowest mean response, queue wait and mean run-level P95 in this dataset.
- The results illustrate the trade-off between network delay and server workload rather than proving a universally optimal alpha or routing strategy.

## Important limitations

The campaign uses demonstration configuration values: server capacities A=20, B=40 and C=30 capacity units/second; two workers per server; and five processing units per request. Traffic rates are 2, 12 and 24 requests/second. Network RTT matrices are scaled by 1×, 3× and 5×. These settings must be confirmed by the team before reporting the results as final project performance.

The mean P95 in the table is the arithmetic mean of each run's P95, not a P95 computed from all pooled request-level samples. Repetitions are ten per scenario, which is stronger than the earlier three-repetition pilot but does not remove all uncertainty.
