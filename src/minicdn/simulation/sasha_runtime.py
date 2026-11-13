"""Adapter for Sasha's deterministic ServerWorkload model.

This module adapts Sasha's existing workload implementation to the shared
SimPy ServerRuntime contract. It does not implement worker scheduling or FIFO
queue behavior itself; all of that remains inside the injected
``ServerWorkload`` class.

Queue policy: requests are committed to Sasha's FIFO model when they arrive at
the selected server, after outbound network transit. This follows the shared
CDN request lifecycle. Workload estimates are made at the routing decision
point and, as documented in the project contract, do not include requests
that are still travelling through the network.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from minicdn.simulation.contracts import ServiceExecution
from minicdn.strategies.contracts import get_server_id, validate_seconds


@dataclass(frozen=True, slots=True)
class SashaServerConfig:
    """Configuration used to create a fresh Sasha server for each run."""

    server_id: str
    capacity_units_per_s: float
    worker_count: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.server_id, str) or not self.server_id:
            raise ValueError("server_id must be a non-empty string")
        if (
            isinstance(self.capacity_units_per_s, bool)
            or not isinstance(self.capacity_units_per_s, (int, float))
            or not math.isfinite(self.capacity_units_per_s)
            or self.capacity_units_per_s <= 0
        ):
            raise ValueError("capacity_units_per_s must be finite and > 0")
        if (
            isinstance(self.worker_count, bool)
            or not isinstance(self.worker_count, int)
            or self.worker_count < 1
        ):
            raise ValueError("worker_count must be a positive integer")


class SashaServerRuntime:
    """Expose Sasha's ServerWorkload objects to the shared SimPy engine.

    Args:
        server_configs: Immutable server settings. New Sasha workload objects
            are created from these settings at the beginning of every run, so
            comparing strategies starts from identical empty server states.
        server_workload_factory: Sasha's actual ``ServerWorkload`` class (or a
            compatible factory) injected by the integration script.
        eligibility_filter: Optional predicate for server availability. When
            omitted, every configured server is eligible.

    The factory is injected so the runtime remains decoupled from the concrete
    server implementation. The self-contained workspace supplies the inspected
    Sasha snapshot from ``minicdn.integrations.sasha`` by default in its runners.
    """

    def __init__(
        self,
        server_configs: Iterable[SashaServerConfig],
        server_workload_factory: Callable[..., Any],
        eligibility_filter: Callable[[Any], bool] | None = None,
    ) -> None:
        configs = tuple(server_configs)
        if not configs:
            raise ValueError("At least one server configuration is required")
        ids = [config.server_id for config in configs]
        if len(ids) != len(set(ids)):
            raise ValueError("Server configurations contain duplicate server IDs")
        if not callable(server_workload_factory):
            raise TypeError("server_workload_factory must be callable")
        if eligibility_filter is not None and not callable(eligibility_filter):
            raise TypeError("eligibility_filter must be callable")

        self._configs = configs
        self._factory = server_workload_factory
        self._eligibility_filter = eligibility_filter
        self._servers: dict[str, Any] = {}
        self._env: Any | None = None
        self._current_time_s = 0.0

    @property
    def current_time_s(self) -> float:
        """Current SimPy time after the most recent runtime synchronization."""
        if self._env is None:
            raise RuntimeError("Server runtime has not been bound to a simulation run")
        return float(self._env.now)

    def start_run(self, env: Any) -> None:
        """Create clean Sasha server instances for a new strategy comparison."""
        self._env = env
        self._current_time_s = float(env.now)
        self._servers = {}
        for config in self._configs:
            server = self._factory(
                server_id=config.server_id,
                capacity_units_per_s=config.capacity_units_per_s,
                worker_count=config.worker_count,
            )
            self._validate_server(server, config)
            self._servers[config.server_id] = server

    def all_servers(self) -> tuple[Any, ...]:
        self._require_started()
        return tuple(self._servers.values())

    def eligible_servers(self) -> tuple[Any, ...]:
        """Synchronize Sasha's state to env.now and return available servers."""
        self._require_started()
        now_s = float(self._env.now)
        self._advance_all_to(now_s)
        servers = tuple(self._servers.values())
        if self._eligibility_filter is not None:
            servers = tuple(server for server in servers if self._eligibility_filter(server))
        return servers

    def worker_count(self, server_id: str) -> int:
        server = self._get_server(server_id)
        count = getattr(server, "worker_count", None)
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError(f"Sasha server {server_id} has an invalid worker_count")
        return count

    def get_server(self, server_id: str) -> Any:
        """Return the current run's Sasha workload object for an ID."""
        return self._get_server(server_id)

    def estimate_completion_time(self, request: Any, server: Any) -> float:
        """Read-only workload callback suitable for HybridRouter."""
        self._require_started()
        server_id = get_server_id(server)
        current_server = self._get_server(server_id)
        if current_server is not server:
            raise ValueError("Workload estimator received a server from another runtime/run")
        now_s = float(self._env.now)
        server_time_s = getattr(server, "current_time_s", None)
        if not isinstance(server_time_s, (int, float)) or not math.isclose(
            float(server_time_s), now_s, rel_tol=1e-9, abs_tol=1e-9
        ):
            raise RuntimeError(
                "Server state is not synchronized with SimPy time; call "
                "eligible_servers() before making a workload-aware routing decision"
            )
        # The estimate itself is read-only. eligible_servers() performs the
        # separate state synchronization before a router inspects candidates.
        estimate = server.estimate_completion_time(request, now_s=now_s)
        return validate_seconds(estimate, "Sasha workload estimate", server_id)

    def submit(self, env: Any, request: Any, server_id: str) -> Any:
        """Return a SimPy process backed by Sasha's real FIFO/worker scheduler."""
        self._require_started()
        if env is not self._env:
            raise ValueError("submit received an environment different from the active run")
        server = self._get_server(server_id)
        return env.process(self._serve(env, request, server))

    def _serve(self, env: Any, request: Any, server: Any):
        """Commit at server arrival, then wait until Sasha records completion."""
        server_id = get_server_id(server)
        started_at_s = float(env.now)
        self._advance_server_to(server, started_at_s)

        # Estimate before assign: Sasha's estimator models the incoming request
        # in addition to existing work, so calling it after assign would count
        # the same request twice.
        completion_duration_s = validate_seconds(
            server.estimate_completion_time(request, now_s=started_at_s),
            "Sasha workload estimate",
            server_id,
        )
        processing_time_s = validate_seconds(
            float(request.processing_units) / float(server.capacity_units_per_s),
            "Sasha processing time",
            server_id,
        )
        if processing_time_s <= 0:
            raise ValueError("Sasha processing time must be > 0")
        if completion_duration_s + 1e-9 < processing_time_s:
            raise RuntimeError(
                "Sasha completion estimate is shorter than the incoming request's own processing time"
            )
        queue_wait_s = max(0.0, completion_duration_s - processing_time_s)

        # This is the only state-changing operation. Sasha remains the owner of
        # assignment, FIFO ordering, worker schedules and completion records.
        server.assign(request, now_s=started_at_s)
        yield env.timeout(completion_duration_s)

        finished_at_s = float(env.now)
        server.advance_to(finished_at_s)
        completion = next(
            (
                record
                for record in reversed(server.completed)
                if record.request_id == str(request.request_id)
            ),
            None,
        )
        if completion is None:
            raise RuntimeError(
                f"Sasha workload model did not record completion for request {request.request_id}"
            )
        if not math.isclose(
            float(completion.finished_at_s),
            finished_at_s,
            rel_tol=1e-9,
            abs_tol=1e-7,
        ):
            raise RuntimeError(
                "Sasha completion record does not match the SimPy service event time"
            )
        return ServiceExecution(
            queue_wait_s=queue_wait_s,
            processing_time_s=processing_time_s,
        )

    def _advance_all_to(self, now_s: float) -> None:
        for server in self._servers.values():
            self._advance_server_to(server, now_s)
        self._current_time_s = now_s

    @staticmethod
    def _advance_server_to(server: Any, now_s: float) -> None:
        advance = getattr(server, "advance_to", None)
        if not callable(advance):
            raise TypeError("Sasha server must expose advance_to(now_s)")
        advance(now_s)

    def _get_server(self, server_id: str) -> Any:
        self._require_started()
        try:
            return self._servers[server_id]
        except KeyError as error:
            raise KeyError(f"Unknown Sasha server ID: {server_id}") from error

    def _require_started(self) -> None:
        if self._env is None or not self._servers:
            raise RuntimeError("Call start_run(env) before using SashaServerRuntime")

    @staticmethod
    def _validate_server(server: Any, config: SashaServerConfig) -> None:
        if get_server_id(server) != config.server_id:
            raise ValueError("ServerWorkload factory returned an unexpected server ID")
        if getattr(server, "capacity_units_per_s", None) != config.capacity_units_per_s:
            raise ValueError("ServerWorkload factory returned an unexpected processing capacity")
        if getattr(server, "worker_count", None) != config.worker_count:
            raise ValueError("ServerWorkload factory returned an unexpected worker count")
        for method_name in ("assign", "advance_to", "estimate_completion_time"):
            if not callable(getattr(server, method_name, None)):
                raise TypeError(f"Sasha server must expose {method_name}()")
        if not isinstance(getattr(server, "completed", None), list):
            raise TypeError("Sasha server must expose a completed list of completion records")
