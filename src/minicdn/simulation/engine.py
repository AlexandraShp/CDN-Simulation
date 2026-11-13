"""Shared SimPy orchestration for the Mini CDN request lifecycle.

The engine owns arrival scheduling, routing orchestration, network travel,
event recording and metrics. The injected ServerRuntime owns actual FIFO
queueing, workers and processing; this module does not reimplement Sasha's job.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from minicdn.models import Request, SelectionResult
from minicdn.simulation.contracts import (
    NetworkDelayProvider,
    RoutingStrategy,
    ServerRuntime,
    ServiceExecution,
)
from minicdn.simulation.metrics import build_summary
from minicdn.simulation.results import (
    RequestResult,
    SimulationEvent,
    SimulationResult,
)
from minicdn.strategies.contracts import get_server_id, validate_seconds


class SimulationEngine:
    """Run requests through routing, network, server execution and response.

    The observation window begins at t=0 and ends when the final request has
    completed its return trip or has been marked unserved/failed. Thus throughput
    and utilization use a window that includes the post-arrival drain period.
    """

    def __init__(
        self,
        network_model: NetworkDelayProvider,
        server_runtime: ServerRuntime,
    ) -> None:
        self._network_model = network_model
        self._server_runtime = server_runtime

    def run(
        self,
        requests: Iterable[Request],
        strategy: RoutingStrategy,
    ) -> SimulationResult:
        """Execute one strategy over one request trace using SimPy.

        A fresh SimPy environment is created for every call. If the injected
        runtime exposes ``start_run(env)``, it is called before reading servers;
        SashaServerRuntime uses this hook to create clean workload objects for
        fair strategy comparisons.
        """
        try:
            import simpy
        except ImportError as error:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "SimPy is required to run the simulation. Install project "
                "dependencies with: python -m pip install -r requirements.txt"
            ) from error

        trace = tuple(requests)
        self._validate_trace(trace)

        env = simpy.Environment()
        # Some runtimes (including the Sasha adapter) need a fresh set of
        # server objects for each strategy so comparisons start from the same
        # empty workload state. The hook is optional for simpler test runtimes.
        start_run = getattr(self._server_runtime, "start_run", None)
        if callable(start_run):
            start_run(env)

        outcomes: list[RequestResult] = []
        events: list[SimulationEvent] = []
        all_servers = tuple(self._server_runtime.all_servers())
        all_server_ids = [get_server_id(server) for server in all_servers]
        if len(all_server_ids) != len(set(all_server_ids)):
            raise ValueError("ServerRuntime returned duplicate server IDs")
        worker_counts: dict[str, int] = {}
        for server_id in all_server_ids:
            worker_count = self._server_runtime.worker_count(server_id)
            if isinstance(worker_count, bool) or not isinstance(worker_count, int) or worker_count <= 0:
                raise ValueError(f"Server {server_id} must have a positive integer worker_count")
            worker_counts[server_id] = worker_count
        strategy_names: set[str] = set()

        for request in trace:
            env.process(
                self._execute_request(
                    env=env,
                    request=request,
                    strategy=strategy,
                    outcomes=outcomes,
                    events=events,
                    worker_counts=worker_counts,
                    strategy_names=strategy_names,
                )
            )

        env.run()
        simulation_end_time_s = float(env.now)

        # A run cannot mix strategy names; this also catches a malformed router.
        strategy_name = next(iter(strategy_names), getattr(strategy, "name", strategy.__class__.__name__))
        if len(strategy_names) > 1:
            raise RuntimeError(f"One simulation returned multiple strategy names: {strategy_names}")

        outcomes.sort(key=lambda item: (item.arrival_time_s, item.request_id))
        event_priority = {
            "REQUEST_GENERATED": 0,
            "SERVER_SELECTED": 1,
            "REQUEST_UNSERVED": 2,
            "REQUEST_FAILED": 3,
            "REQUEST_ARRIVED_AT_SERVER": 4,
            "QUEUE_ENTERED": 5,
            "PROCESSING_STARTED": 6,
            "PROCESSING_COMPLETED": 7,
            "RESPONSE_COMPLETED": 8,
        }
        events.sort(
            key=lambda item: (
                item.time_s,
                event_priority.get(item.event_type, 99),
                item.request_id,
            )
        )

        summary = build_summary(outcomes, worker_counts, simulation_end_time_s)
        return SimulationResult(
            request_results=tuple(outcomes),
            events=tuple(events),
            summary=summary,
            simulation_end_time_s=simulation_end_time_s,
            strategy_name=strategy_name,
        )

    def _execute_request(
        self,
        *,
        env: Any,
        request: Request,
        strategy: RoutingStrategy,
        outcomes: list[RequestResult],
        events: list[SimulationEvent],
        worker_counts: dict[str, int],
        strategy_names: set[str],
    ):
        # Wait until the request's absolute arrival time.
        if request.arrival_time_s > env.now:
            yield env.timeout(request.arrival_time_s - env.now)

        self._record(
            events, env.now, "REQUEST_GENERATED", request, details={
                "processing_units": request.processing_units
            }
        )

        eligible_servers = tuple(self._server_runtime.eligible_servers())
        eligible_ids = [get_server_id(server) for server in eligible_servers]
        if len(eligible_ids) != len(set(eligible_ids)):
            raise ValueError("ServerRuntime returned duplicate eligible server IDs")

        selection = strategy.select_server(request, eligible_servers)
        if not isinstance(selection, SelectionResult):
            raise TypeError("Every routing strategy must return SelectionResult")
        strategy_names.add(selection.strategy_name)

        selected_id = selection.selected_server_id
        candidate_scores = dict(selection.candidate_scores)
        if selected_id is None:
            if eligible_ids:
                # The router may legitimately decline a request, but this must
                # be explicit in the event log and result.
                self._record(
                    events, env.now, "REQUEST_UNSERVED", request,
                    details={"reason": "router returned no selection"},
                )
            else:
                self._record(
                    events, env.now, "REQUEST_UNSERVED", request,
                    details={"reason": "no eligible servers"},
                )
            outcomes.append(
                RequestResult(
                    request_id=request.request_id,
                    user_id=request.user_id,
                    status="unserved",
                    strategy_name=selection.strategy_name,
                    selected_server_id=None,
                    arrival_time_s=request.arrival_time_s,
                    candidate_scores=candidate_scores,
                )
            )
            return

        if selected_id not in eligible_ids:
            raise RuntimeError(
                f"Router selected {selected_id!r}, which is not in the eligible server set"
            )

        unknown_eligible_ids = set(eligible_ids) - set(worker_counts)
        if unknown_eligible_ids:
            raise ValueError(
                "Eligible servers were not included by ServerRuntime.all_servers(): "
                f"{sorted(unknown_eligible_ids)}"
            )

        self._record(
            events,
            env.now,
            "SERVER_SELECTED",
            request,
            server_id=selected_id,
            details={
                "strategy": selection.strategy_name,
                "candidate_scores": candidate_scores,
            },
        )

        outbound_delay_s = validate_seconds(
            self._network_model.get_outbound_delay(request.user_id, selected_id),
            "outbound network delay",
            selected_id,
        )
        return_delay_s = validate_seconds(
            self._network_model.get_return_delay(request.user_id, selected_id),
            "return network delay",
            selected_id,
        )

        if outbound_delay_s:
            yield env.timeout(outbound_delay_s)
        server_arrival_time_s = float(env.now)
        self._record(
            events, server_arrival_time_s, "REQUEST_ARRIVED_AT_SERVER", request,
            server_id=selected_id,
        )

        service_event = self._server_runtime.submit(env, request, selected_id)
        try:
            service_execution = yield service_event
        except Exception as error:
            self._record(
                events, env.now, "REQUEST_FAILED", request, server_id=selected_id,
                details={"reason": str(error)},
            )
            outcomes.append(
                RequestResult(
                    request_id=request.request_id,
                    user_id=request.user_id,
                    status="failed",
                    strategy_name=selection.strategy_name,
                    selected_server_id=selected_id,
                    arrival_time_s=request.arrival_time_s,
                    server_arrival_time_s=server_arrival_time_s,
                    outbound_delay_s=outbound_delay_s,
                    network_time_s=outbound_delay_s,
                    candidate_scores=candidate_scores,
                )
            )
            return
        if not isinstance(service_execution, ServiceExecution):
            raise TypeError(
                "ServerRuntime.submit must complete with a ServiceExecution value"
            )

        queue_wait_s = validate_seconds(
            service_execution.queue_wait_s, "queue wait", selected_id
        )
        processing_time_s = validate_seconds(
            service_execution.processing_time_s, "processing time", selected_id
        )
        if processing_time_s <= 0:
            raise ValueError("processing_time_s must be > 0 for a completed request")

        processing_start_time_s = server_arrival_time_s + queue_wait_s
        processing_completed_time_s = float(env.now)
        expected_completion_time_s = processing_start_time_s + processing_time_s
        if not math.isclose(
            processing_completed_time_s,
            expected_completion_time_s,
            rel_tol=1e-9,
            abs_tol=1e-7,
        ):
            raise RuntimeError(
                "ServerRuntime timing does not match SimPy completion time: "
                f"expected {expected_completion_time_s}, got {processing_completed_time_s}"
            )

        if queue_wait_s > 0:
            self._record(
                events,
                server_arrival_time_s,
                "QUEUE_ENTERED",
                request,
                server_id=selected_id,
                details={"queue_wait_s": queue_wait_s},
            )
        self._record(
            events,
            processing_start_time_s,
            "PROCESSING_STARTED",
            request,
            server_id=selected_id,
            details={"queue_wait_s": queue_wait_s},
        )
        self._record(
            events,
            processing_completed_time_s,
            "PROCESSING_COMPLETED",
            request,
            server_id=selected_id,
            details={"processing_time_s": processing_time_s},
        )

        if return_delay_s:
            yield env.timeout(return_delay_s)
        response_completed_time_s = float(env.now)

        network_time_s = outbound_delay_s + return_delay_s
        response_time_s = response_completed_time_s - request.arrival_time_s
        self._record(
            events,
            response_completed_time_s,
            "RESPONSE_COMPLETED",
            request,
            server_id=selected_id,
            details={
                "response_time_s": response_time_s,
                "network_time_s": network_time_s,
                "queue_wait_s": queue_wait_s,
                "processing_time_s": processing_time_s,
            },
        )

        outcomes.append(
            RequestResult(
                request_id=request.request_id,
                user_id=request.user_id,
                status="completed",
                strategy_name=selection.strategy_name,
                selected_server_id=selected_id,
                arrival_time_s=request.arrival_time_s,
                server_arrival_time_s=server_arrival_time_s,
                processing_start_time_s=processing_start_time_s,
                processing_completed_time_s=processing_completed_time_s,
                response_completed_time_s=response_completed_time_s,
                outbound_delay_s=outbound_delay_s,
                return_delay_s=return_delay_s,
                network_time_s=network_time_s,
                queue_wait_s=queue_wait_s,
                processing_time_s=processing_time_s,
                response_time_s=response_time_s,
                candidate_scores=candidate_scores,
            )
        )

    @staticmethod
    def _record(
        events: list[SimulationEvent],
        time_s: float,
        event_type: str,
        request: Request,
        *,
        server_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        events.append(
            SimulationEvent(
                time_s=float(time_s),
                event_type=event_type,
                request_id=request.request_id,
                user_id=request.user_id,
                server_id=server_id,
                details=details or {},
            )
        )

    @staticmethod
    def _validate_trace(requests: tuple[Request, ...]) -> None:
        seen_ids: set[str] = set()
        for request in requests:
            if not isinstance(request, Request):
                raise TypeError("Simulation trace must contain Request objects")
            if request.request_id in seen_ids:
                raise ValueError(f"Duplicate request_id in simulation trace: {request.request_id}")
            if not math.isfinite(request.arrival_time_s) or request.arrival_time_s < 0:
                raise ValueError(
                    f"Invalid arrival_time_s for request {request.request_id}"
                )
            seen_ids.add(request.request_id)
