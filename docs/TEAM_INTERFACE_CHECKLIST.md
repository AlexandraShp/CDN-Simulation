# Team interface checklist — current integration status

This checklist records what has been verified from the branches inspected on
2026-11-12 and the adapters in this workspace. Revisit it if a teammate changes
an API or the team updates Technical Contract v1.0.

## Verified in the inspected branches / local adapters

- [x] Request fields used by the workspace: `request_id`, `user_id`, `arrival_time_s`, `processing_units`
- [x] Shared strategy call: `select_server(request, eligible_servers)`
- [x] Shared `SelectionResult`: `selected_server_id`, `strategy_name`, `candidate_scores`
- [x] String server IDs
- [x] Nirmin RTT lookup: `NetworkModel.get_rtt(user_id, server_id)`, seconds
- [x] Nirmin outbound and return delay methods: each returns RTT / 2
- [x] Sasha workload estimator: `ServerWorkload.estimate_completion_time(request, now_s=...)`, seconds
- [x] Sasha assignment and state progression: `assign(request, now_s)` and `advance_to(now_s)`
- [x] Sasha Least Loaded function: `select_least_loaded(request, eligible_servers, now_s=...)`
- [x] Simulation observation window includes the post-arrival drain period
- [x] New server workload instances are created for each strategy run by `SashaServerRuntime.start_run(env)`

## Team decisions still to confirm before final reporting

- [ ] Final shared Git repository layout and pull-request ownership
- [ ] Agreed production server IDs, worker counts and processing capacities
- [ ] Processing-unit generation policy (fixed value, range or distribution)
- [ ] Final request arrival rates, simulation duration and repetition count
- [ ] Whether requests in network transit should influence workload-aware routing
- [ ] Final dashboard owner and presentation/demo responsibilities

## Explicit current simulation policy

Requests are committed to Sasha's FIFO workload model when they arrive at the
selected server, after outbound network travel. Queue order is therefore
server-arrival order. At routing time, workload estimates include work already
committed to server workers and queues but do not include requests still in
network transit. This known limitation follows the current technical contract;
changing it requires a deliberate policy and engine update.

Do not duplicate the network model, server model, workload estimator, or shared
simulation engine in Saif's modules.
