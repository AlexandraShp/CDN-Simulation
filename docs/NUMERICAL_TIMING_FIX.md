# Campaign failure diagnostic and floating-point boundary fix

## What was found

The campaign CSV records one failure in the run with:

- Network: low (1.0x RTT multiplier)
- Traffic: high (24 requests/second)
- Strategy: Random
- Repetition: 1, seed 42
- Request count: 200

Replaying the deterministic request trace against the bundled workload model isolated the issue to a floating-point completion boundary. For request `R0010`, Sasha's worker schedule stored a finish time of `0.8385578802632309` seconds, while adding the estimated remaining duration to the SimPy current time scheduled the process wake-up at `0.8385578802632307` seconds. The strict `finish_time <= now` comparison therefore missed the completion by approximately 0.2 femtoseconds, and the adapter reported that no completion record existed.

## Fix

The bundled Sasha snapshot now treats a worker completion as due when its scheduled finish is within `1e-12` seconds of the current simulation time. It retains the exact worker finish timestamp when starting the next FIFO job. This tolerance is substantially smaller than the simulation's reported precision and does not materially change request durations.

This is an integration correction to the vendored snapshot in Saif's workspace. Sasha's original GitHub branch is not modified; the same minimal change should be shared with Sasha for her source branch.

## Reproduce the former failing case

From the workspace root, after applying this patch:

```powershell
python experiments/diagnose_campaign_failure.py
```

Defaults reproduce the low-network/high-traffic Random run with 200 requests and seed 42. The script prints any `REQUEST_FAILED` event including its reason. A successful result should report zero failures.

## Future campaign diagnostics

The raw campaign CSVs now include a `failure_diagnostics` column. If a request fails in a later run, the row will retain its request ID, simulation time, server ID and exception message instead of only incrementing a failure count.
