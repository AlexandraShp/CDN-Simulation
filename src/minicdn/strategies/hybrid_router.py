"""Hybrid routing: combine network RTT and predicted server workload."""

import math
from collections.abc import Iterable
from typing import Generic

from minicdn.models import Request, SelectionResult
from minicdn.strategies.contracts import (
    RttLookup,
    ServerT,
    WorkloadEstimator,
    get_server_id,
    validate_seconds,
)


class HybridRouter(Generic[ServerT]):
    """Select the eligible server with the lowest alpha-weighted score.

    Dependencies are injected at construction time:
      rtt_lookup(user_id, server_id) -> RTT in seconds
      workload_estimator(request, server) -> predicted completion offset in seconds

    The estimator is supplied by the server/workload component (Sasha); this
    class deliberately does not implement or mutate server workload.
    """

    def __init__(
        self,
        alpha: float,
        rtt_lookup: RttLookup,
        workload_estimator: WorkloadEstimator[ServerT],
    ) -> None:
        if isinstance(alpha, bool) or not isinstance(alpha, (int, float)):
            raise ValueError("alpha must be a number between 0 and 1")
        if not math.isfinite(alpha) or not 0 <= alpha <= 1:
            raise ValueError("alpha must be between 0 and 1 inclusive")
        if not callable(rtt_lookup):
            raise TypeError("rtt_lookup must be callable")
        if not callable(workload_estimator):
            raise TypeError("workload_estimator must be callable")

        self.alpha = float(alpha)
        self._rtt_lookup = rtt_lookup
        self._workload_estimator = workload_estimator

    def select_server(
        self, request: Request, eligible_servers: Iterable[ServerT]
    ) -> SelectionResult:
        """Return the lowest-score server, without changing simulation state."""
        servers = tuple(eligible_servers)
        if not servers:
            return SelectionResult(
                selected_server_id=None,
                strategy_name="hybrid",
            )

        scores: dict[str, float] = {}
        for server in servers:
            server_id = get_server_id(server)
            if server_id in scores:
                raise ValueError(f"Duplicate eligible server_id: {server_id}")

            # Do not call a component whose weight is exactly zero.
            if self.alpha == 1.0:
                rtt_s = validate_seconds(
                    self._rtt_lookup(request.user_id, server_id), "RTT", server_id
                )
                scores[server_id] = rtt_s
            elif self.alpha == 0.0:
                workload_s = validate_seconds(
                    self._workload_estimator(request, server), "workload", server_id
                )
                scores[server_id] = workload_s
            else:
                rtt_s = validate_seconds(
                    self._rtt_lookup(request.user_id, server_id), "RTT", server_id
                )
                workload_s = validate_seconds(
                    self._workload_estimator(request, server), "workload", server_id
                )
                scores[server_id] = (
                    self.alpha * rtt_s + (1.0 - self.alpha) * workload_s
                )

        selected_server_id = min(
            scores, key=lambda server_id: (scores[server_id], server_id)
        )
        return SelectionResult(
            selected_server_id=selected_server_id,
            strategy_name="hybrid",
            candidate_scores=scores,
        )
