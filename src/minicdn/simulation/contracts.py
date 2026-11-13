"""Stable interfaces between the shared engine and teammate-owned modules.

The server implementation is intentionally an injected dependency. This file
contains contracts and result data only; it does not implement server queues,
workers, processing, or workload estimation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from minicdn.models import Request


@dataclass(frozen=True, slots=True)
class ServiceExecution:
    """Timing information returned when a server finishes one request.

    The server backend owns the actual FIFO queue and worker scheduling. Its
    SimPy event should succeed with this value when the request has completed.
    Durations are measured from the request's arrival at the server.
    """

    queue_wait_s: float
    processing_time_s: float


class NetworkDelayProvider(Protocol):
    """Network API required by the simulation engine."""

    def get_outbound_delay(self, user_id: str, server_id: str) -> float:
        ...

    def get_return_delay(self, user_id: str, server_id: str) -> float:
        ...


class RoutingStrategy(Protocol):
    """Common routing interface used by the shared simulation engine."""

    def select_server(self, request: Request, eligible_servers: Any) -> Any:
        ...


class ServerRuntime(Protocol):
    """Adapter boundary for Sasha's server/worker implementation.

    `start_run(env)` is an optional lifecycle hook. If present, the engine calls
    it once at the beginning of every strategy run so the runtime can reset its
    state and bind itself to that run's SimPy environment.

    `eligible_servers` must return the server objects currently available for
    new requests. Each object must expose a string `server_id` attribute.

    `submit` must enqueue the request in the server's real FIFO/worker model
    and return a SimPy event that succeeds with ServiceExecution after the
    request has finished processing. It must not bypass the server model.
    """

    def all_servers(self) -> Any:
        ...

    def eligible_servers(self) -> Any:
        ...

    def worker_count(self, server_id: str) -> int:
        ...

    def submit(self, env: Any, request: Request, server_id: str) -> Any:
        ...
