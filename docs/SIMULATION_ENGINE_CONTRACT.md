# Shared simulation engine: integration contract

The engine in `src/minicdn/simulation/engine.py` owns the common request
lifecycle. It uses SimPy and is independent of the dashboard.

## Lifecycle

1. Wait until `Request.arrival_time_s` and record `REQUEST_GENERATED`.
2. Ask the injected router to choose from the currently eligible servers.
3. Record `SERVER_SELECTED`, or `REQUEST_UNSERVED` if there is no selection.
4. Apply the network model's outbound delay.
5. Submit the request to the server runtime. The server runtime owns its real
   FIFO queue, workers and processing logic.
6. Record the server arrival, queue entry (when applicable), processing start
   and processing completion timestamps.
7. Apply the network model's return delay and record `RESPONSE_COMPLETED`.
8. Return request outcomes, a timestamped event log and aggregate metrics.

## Server runtime adapter

The engine deliberately does not implement a server/workload model.
`SashaServerRuntime` now adapts Sasha's existing workload objects and exposes
these operations to the engine:

```python
all_servers() -> Iterable[ServerLike]
eligible_servers() -> Iterable[ServerLike]
worker_count(server_id: str) -> int
submit(env, request, server_id: str) -> SimPy Event[ServiceExecution]
start_run(env) -> None  # optional lifecycle hook, used by SashaServerRuntime
```

Each server object must have a non-empty string `server_id`.
`all_servers` returns the complete configured inventory (including currently
unavailable servers) so utilization output can include every server.
`eligible_servers` returns only servers currently selectable for new requests.
`submit` must enqueue the request in Sasha's actual FIFO/worker implementation
and return a SimPy event that succeeds when processing completes. The event's
value must be `ServiceExecution(queue_wait_s, processing_time_s)`.

`ServiceExecution` is a result contract, not a queue implementation. The
engine uses it to record accurate timestamps and metrics. The workload estimator remains Sasha-owned. `HybridRouter` calls the runtime's
read-only `estimate_completion_time` callback, and
`SashaLeastLoadedAdapter` delegates to Sasha's actual `select_least_loaded`
function.

## Units and accounting

All internal time values are seconds. The engine uses the network model's
outbound and return delay methods separately. For Nirmin's initial symmetric
model these are RTT/2 each, so total network time is exactly one RTT.

Response time is measured from request generation to response completion and
therefore includes outbound network delay, queue wait, processing, and return
network delay.

The observation window starts at simulation time zero and ends when the last
request has completed its response or been marked unserved/failed. It includes
the post-arrival drain period. Throughput is completed requests divided by this
full window. Utilization is total processing time divided by
(worker_count × the same observation window).

P95 uses the nearest-rank definition. Average, median and P95 response times
are `None` when no requests complete; they are not reported as zero.

## Running

Install the project dependencies first:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -v
```

The server runtime must be reset between strategy comparisons. Reuse the same
request trace, network configuration and initial server state for every
strategy to keep experiments fair.


## Sasha workload adapter (implemented)

`minicdn.simulation.SashaServerRuntime` adapts Sasha's existing
`ServerWorkload` without copying its worker, FIFO or estimator logic. Construct
it with `SashaServerConfig` values and inject Sasha's `ServerWorkload` class as
`server_workload_factory`. The engine calls the optional `start_run(env)` hook
before obtaining `all_servers()`. This creates fresh server workload instances
for every strategy run so every comparison begins from identical empty state.

The runtime calls `advance_to(env.now)` before workload-aware routing decisions.
`HybridRouter` uses `runtime.estimate_completion_time` as its workload callback.
`SashaLeastLoadedAdapter` wraps Sasha's actual `select_least_loaded` function
and converts its local result into the shared `SelectionResult`.

**Queue timing decision:** following the shared request lifecycle, the adapter
commits a request to Sasha's workload model when the request reaches the
selected server, after outbound network transit. Queue order is therefore
server-arrival order. The workload estimate is evaluated at the routing
decision time and includes work already committed to server workers/queues; it
does not include requests still in network transit, matching the documented
known limitation in the project contract. Do not describe this as transit-aware
reservation. If the team later chooses routing-time reservation instead, the
engine contract and FIFO policy must be changed together.

The adapter uses Sasha's `estimate_completion_time` before `assign`, because
that estimator models the candidate request in addition to existing work.
After the estimate is captured, `assign` is called exactly once at server
arrival. The adapter waits for the predicted completion time, invokes
`advance_to`, verifies Sasha recorded the completion, and returns
`ServiceExecution(queue_wait_s, processing_time_s)` to the engine.

## Run an integrated demonstration

With SimPy installed, run this from the workspace root:

```powershell
python examples/run_integrated_demo.py --request-count 100 --arrival-rate 1.5
```

The example uses local snapshots of Nirmin's network/latency modules and
Sasha's server/workload modules under `src/minicdn/integrations`. Separate
branch folders are not required. Its server capacity settings and request size
are demonstration parameters, not final team-approved experiment settings.
