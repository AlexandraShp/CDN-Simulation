"""Strategy-independent simulation events, request outcomes and metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    time_s: float
    event_type: str
    request_id: str
    user_id: str
    server_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RequestResult:
    request_id: str
    user_id: str
    status: str
    strategy_name: str
    selected_server_id: str | None
    arrival_time_s: float
    server_arrival_time_s: float | None = None
    processing_start_time_s: float | None = None
    processing_completed_time_s: float | None = None
    response_completed_time_s: float | None = None
    outbound_delay_s: float = 0.0
    return_delay_s: float = 0.0
    network_time_s: float = 0.0
    queue_wait_s: float | None = None
    processing_time_s: float | None = None
    response_time_s: float | None = None
    candidate_scores: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SimulationSummary:
    total_requests: int
    completed_requests: int
    unserved_requests: int
    failed_requests: int
    average_response_time_s: float | None
    median_response_time_s: float | None
    p95_response_time_s: float | None
    average_queue_wait_s: float | None
    average_network_time_s: float | None
    throughput_requests_per_s: float | None
    utilization_by_server: dict[str, float]
    observation_window_s: float
    drain_period_included: bool = True


@dataclass(frozen=True, slots=True)
class SimulationResult:
    request_results: tuple[RequestResult, ...]
    events: tuple[SimulationEvent, ...]
    summary: SimulationSummary
    simulation_end_time_s: float
    strategy_name: str
