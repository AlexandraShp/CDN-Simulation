"""Adapter from Nirmin's MinimumLatencyStrategy to the shared result contract."""

from collections.abc import Iterable

from minicdn.models import Request, SelectionResult
from minicdn.strategies.contracts import (
    MinimumLatencyStrategyLike,
    RttLookup,
    get_server_id,
    validate_seconds,
)


class MinimumLatencyAdapter:
    """Wrap Nirmin's existing router without changing his implementation.

    Nirmin's current strategy accepts (user_id, eligible_servers) and returns
    a server ID. This adapter exposes the common (request, servers) interface
    and converts the return value into SelectionResult.
    """

    def __init__(
        self, strategy: MinimumLatencyStrategyLike, rtt_lookup: RttLookup
    ) -> None:
        self._strategy = strategy
        self._rtt_lookup = rtt_lookup

    def select_server(
        self, request: Request, eligible_servers: Iterable[object]
    ) -> SelectionResult:
        servers = tuple(eligible_servers)
        if not servers:
            return SelectionResult(
                selected_server_id=None,
                strategy_name="minimum_latency",
            )

        server_ids = [get_server_id(server) for server in servers]
        if len(server_ids) != len(set(server_ids)):
            raise ValueError("Eligible servers must have unique server IDs")

        selected_server_id = self._strategy.select_server(
            request.user_id, servers
        )
        if selected_server_id is None:
            raise RuntimeError(
                "Minimum Latency returned no server despite eligible servers being supplied"
            )
        if selected_server_id not in server_ids:
            raise RuntimeError(
                "Minimum Latency returned a server that was not in the eligible set"
            )

        # Keep per-candidate RTT values for experiment diagnostics.
        scores = {
            server_id: validate_seconds(
                self._rtt_lookup(request.user_id, server_id), "RTT", server_id
            )
            for server_id in server_ids
        }
        return SelectionResult(
            selected_server_id=selected_server_id,
            strategy_name="minimum_latency",
            candidate_scores=scores,
        )
