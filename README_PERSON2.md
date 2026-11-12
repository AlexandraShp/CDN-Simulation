# Person 2: workload and Least Loaded routing

These modules are present on the existing `Sasha` branch. The workload scheduler and selector are independently usable; shared simulator integration remains pending.

## Responsibilities

- `src/workload.py`: multi-worker FIFO server scheduler, current worker state, committed backlog, pure incoming-request completion estimator, simulated time advancement.
- `src/strategies/load.py`: pure Least Loaded strategy with selection results and per-server candidate scores.

## Units and behavior

All times are in **seconds**. `capacity_units_per_s` is the processing rate **per worker**; each worker handles one request at a time. A request has `processing_units > 0` and `request_id`. Worker time per request equals `processing_units / capacity_units_per_s`.

`assign` commits the incoming request immediately, whether it starts on a free worker or enters the FIFO queue. `advance_to` handles completions, removes finished work and starts queued jobs when workers become available. Assigning at routing time reserves work immediately, so simultaneous routing decisions account for earlier assignments. Network transit delays remain the responsibility of the outer simulator. This model assumes the reservation uses queue order at selection time, not network arrival order: if your CDN models requests entering the FIFO queue only *after* network transit, the coordinator needs a separate in-transit reservation state or a scheduling policy adjustment.

`estimate_completion_time` **never mutates state**. It models existing worker completion times, all queued FIFO requests and the incoming request's own processing units. It returns the predicted duration until that request finishes *server processing* (not network round-trip time). It assumes no later requests jump ahead in the FIFO queue. It does not include network delay. Hybrid routing can combine its output with network RTT explicitly.

## Public API

```python
ServerWorkload(server_id: str, capacity_units_per_s: float, worker_count: int = 1)
ServerWorkload.assign(request: Any, now_s: float) -> None
ServerWorkload.advance_to(now_s: float) -> list[CompletionRecord]
ServerWorkload.estimate_completion_time(request: Any, now_s: float | None = None) -> float
select_least_loaded(request: Any, eligible_servers: Iterable[ServerWorkload], now_s: float | None = None) -> SelectionResult
```

`SelectionResult` currently has fields `selected_server_id: str | None`, `strategy_name: str`, `candidate_scores: Mapping[str, float]`. **Replace this local definition with the team's shared `SelectionResult`** when the actual constructor and field names are available. For no eligible servers, this package returns a result with `selected_server_id=None` (pending verification against the team's contract). Request objects from `src/models.py` can be passed directly if they expose `request_id` and `processing_units`.

### Example

```python
from src.workload import ServerWorkload
from src.strategies.load import select_least_loaded
from dataclasses import dataclass

@dataclass
class Request:
    request_id: str
    processing_units: float

servers = [ServerWorkload('beijing', 20.0, worker_count=2),
           ServerWorkload('shanghai', 40.0, worker_count=2)]
request = Request('r1', 5.0)
result = select_least_loaded(request, servers, now_s=0.0)
chosen = next(s for s in servers if s.server_id == result.selected_server_id)
chosen.assign(request, now_s=0.0)  # Only AFTER selecting
chosen.advance_to(now_s=1.0)
```

## Installation / testing

From repository root (Python 3.10+):

```powershell
python -m pip install pytest
python -m pytest tests/test_workload.py tests/test_load.py -v
python -m pytest -v
```

## Integration checklist

1. Verify the team's `Server`, `Request` and `SelectionResult` definitions; adapt the routing wrapper without changing scheduling logic.
2. Have the shared simulator call `assign` exactly once after routing. Do not independently duplicate queue or worker state in SimPy. Integrate completion events or call `advance_to(env.now)` before each state observation.
3. If simulating network transit before reaching a server, decide whether routing-time reservation order or server-arrival order determines FIFO; this package uses routing-time reservation order.
4. Keep the team's `src/strategies/` directory; inspect and coordinate before removing typo directory `src/stratagies/`.
5. Do not overwrite `src/models.py`, `src/network.py`, `src/simulation.py`, other strategies, `main.py`, or the existing README without reviewing team edits.

## Verified repository integration status (2026-11-12)

`src/models.py`, `src/network.py`, and `src/simulation.py` are empty. There is no shared Request, Server, routing contract, or SelectionResult to import. The original `src/stratagies/load.py` accepts only `servers`, calls `estimated_waiting_time()`, and returns a server ID; it is incompatible with this incoming-request-aware selector and remains untouched. `main.py` uses a SimPy Resource with fixed 0.05-second processing and does not call these modules.

The team must supply shared Request fields (`request_id`, `user_id`, `arrival_time_s`, `processing_units`), a server-to-ServerWorkload mapping, a shared SelectionResult contract, and simulator calls for reservation and time advancement. Only request_id and processing_units are consumed here; arrival_time_s does not automatically advance time. Pass now_s explicitly at routing time for a common comparison time across servers. Without it, each server uses its own last synchronized time.

The conceptual `estimate_completion_time(request, server)` interface is implemented as `server.estimate_completion_time(request, now_s=None)`; no module-level wrapper exists. Scores are durations from now_s, not absolute timestamps. Public state properties are busy_worker_count, queue_length, active_request_ids, queued_request_ids, and remaining_processing_units; completed contains CompletionRecord(request_id, finished_at_s).

Both requested pytest commands were attempted in this environment, but neither could start because python is not on PATH. No py or python3 launcher was found either. The previous 22-pass result is historical and is not a verified result for this revision. The new future-time regression cases also require execution in a Python environment.
