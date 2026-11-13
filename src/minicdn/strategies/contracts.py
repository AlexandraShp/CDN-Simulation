"""Shared routing contracts and helpers.

These definitions keep Saif's strategies compatible with teammate modules
without importing or reimplementing their network/server internals.
"""

import math
from collections.abc import Callable, Iterable
from typing import Protocol, TypeVar

from minicdn.models import Request


class ServerLike(Protocol):
    """Minimum server interface required by workload-aware strategies."""

    server_id: str


ServerT = TypeVar("ServerT", bound=ServerLike)
RttLookup = Callable[[str, str], float]
WorkloadEstimator = Callable[[Request, ServerT], float]


class MinimumLatencyStrategyLike(Protocol):
    """Interface exposed by Nirmin's current MinimumLatencyStrategy."""

    def select_server(
        self, user_id: str, eligible_servers: Iterable[object]
    ) -> str | None:
        ...


def get_server_id(server: ServerLike | str) -> str:
    """Return a string ID from either a server ID or a server object."""
    server_id = server if isinstance(server, str) else getattr(server, "server_id", None)
    if not isinstance(server_id, str) or not server_id:
        raise ValueError("Every eligible server must have a non-empty string server_id")
    return server_id


def validate_seconds(value: float, metric_name: str, server_id: str) -> float:
    """Validate a non-negative, finite time value and return it as float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{metric_name} for server {server_id} must be numeric seconds")
    if not math.isfinite(value) or value < 0:
        raise ValueError(
            f"{metric_name} for server {server_id} must be finite and >= 0 seconds"
        )
    return float(value)
