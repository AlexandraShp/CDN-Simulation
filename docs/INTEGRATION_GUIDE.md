# Integration guide: Saif's routing modules

This guide documents the adapters and self-contained teammate source snapshots
inspected on 2026-11-12. The workspace includes those snapshots under
`minicdn.integrations`, so running the project does not require separate local
clones or extracted branch folders. Original ownership and update guidance are
documented in `VENDORED_SOURCES.md`.

## Common router interface

All strategies exposed to the simulation engine should follow this call shape:

```python
result = router.select_server(request, eligible_servers)
```

Each router returns `minicdn.models.SelectionResult`:

- `selected_server_id`: selected string ID, or `None` if no server is eligible.
- `strategy_name`: stable strategy identifier.
- `candidate_scores`: per-server scores in seconds where meaningful. Random routing leaves this empty.

## Nirmin's Minimum Latency integration

Nirmin's current code exposes:

```python
network_model = NetworkModel(rtt_matrix)
latency_strategy = MinimumLatencyStrategy(network_model)
selected_id = latency_strategy.select_server(user_id, eligible_servers)
rtt_s = network_model.get_rtt(user_id, server_id)
```

The adapter wraps that existing implementation without changing Nirmin's branch:

```python
from minicdn.strategies.minimum_latency_adapter import MinimumLatencyAdapter

minimum_latency = MinimumLatencyAdapter(
    strategy=latency_strategy,
    rtt_lookup=network_model.get_rtt,
)
result = minimum_latency.select_server(request, eligible_servers)
```

The adapter verifies that Nirmin's result is one of the eligible servers and
adds per-candidate RTT values to `SelectionResult` for experiment diagnostics.

## Hybrid integration with Sasha's estimator

Hybrid receives the actual Sasha workload estimator through the bound runtime
callback. The adapter does not reimplement workload calculations:

```python
hybrid = HybridRouter(
    alpha=0.5,
    rtt_lookup=network_model.get_rtt,
    workload_estimator=sasha_workload_estimator,
)
result = hybrid.select_server(request, eligible_servers)
```

The estimator interface expected by this workspace is:

```python
estimate_completion_time(request, server) -> float  # seconds
```

It must be a read-only prediction: evaluating a candidate must not enqueue the
request, reserve a worker, or mutate server state. It should predict the
time from the routing decision until the incoming request completes.

## Random routing

```python
random_router = RandomRouter(seed=42)
result = random_router.select_server(request, eligible_servers)
```

## Important integration decisions

1. Server IDs are strings throughout the routing boundary.
2. RTT and predicted completion duration are both seconds before they are
   combined by Hybrid.
3. Routers only select; the simulation engine performs network travel,
   queueing, processing, and completion.
4. The bundled Nirmin and Sasha modules are snapshots of their inspected
   branch implementations. The adapters do not reimplement their algorithms.
5. Refresh the snapshots and re-run integration tests when teammates update
   their source branches; see `VENDORED_SOURCES.md`.

## Shared simulation engine (new)

`minicdn.simulation.SimulationEngine` orchestrates a full request lifecycle.
It uses Nirmin's `get_outbound_delay` and `get_return_delay` methods and the
common router interface. It intentionally delegates all worker/queue/processing
behaviour to the injected `ServerRuntime` interface. See
`SIMULATION_ENGINE_CONTRACT.md` for the exact methods and `ServiceExecution`
return value provided by `SashaServerRuntime`.

The engine records request lifecycle events and computes response time,
queue wait, network time, throughput and server utilization. The observation
window includes the final drain period; throughput and utilization use this
same window.


## Sasha integration (now adapted)

Sasha's uploaded implementation exposes:

```python
from src.workload import ServerWorkload
from src.strategies.load import select_least_loaded

server = ServerWorkload(
    server_id="A", capacity_units_per_s=20.0, worker_count=2
)
server.estimate_completion_time(request, now_s=simulation_time_s)
server.assign(request, now_s=server_arrival_time_s)
server.advance_to(simulation_time_s)

selection = select_least_loaded(
    request, eligible_servers, now_s=simulation_time_s
)
```

The integration modules are:

- `minicdn.simulation.SashaServerRuntime`: resets the real Sasha server
  workload objects between strategy runs and adapts their queue/worker API to
  the engine's SimPy `submit` event.
- `minicdn.strategies.SashaLeastLoadedAdapter`: calls Sasha's actual selector
  and converts its result into the shared `SelectionResult`.
- `runtime.estimate_completion_time`: callback to inject into `HybridRouter`.

Example construction:

```python
runtime = SashaServerRuntime(
    [
        SashaServerConfig("A", capacity_units_per_s=20.0, worker_count=2),
        SashaServerConfig("B", capacity_units_per_s=40.0, worker_count=2),
    ],
    server_workload_factory=ServerWorkload,
)
least_loaded = SashaLeastLoadedAdapter(select_least_loaded, runtime)
hybrid = HybridRouter(
    alpha=0.5,
    rtt_lookup=network_model.get_rtt,
    workload_estimator=runtime.estimate_completion_time,
)
```

`SimulationEngine.run()` detects the optional `start_run(env)` method and calls
it before retrieving servers. That makes a new clean set of Sasha server
objects for every strategy run. `eligible_servers()` advances the workload
objects to the current SimPy time before routing. Requests are assigned to the
Sasha FIFO model only after outbound travel, when they arrive at the server.

This follows the shared project lifecycle. Sasha's estimator does not include
requests currently travelling through the network; this limitation is
explicitly retained rather than hidden.
