"""Random eligible-server strategy using the shared routing result contract."""

import random
from collections.abc import Iterable

from minicdn.models import Request, SelectionResult
from minicdn.strategies.contracts import get_server_id


class RandomRouter:
    """Uniformly select an eligible server using a dedicated seeded RNG."""

    def __init__(self, seed: int) -> None:
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError("seed must be an integer")
        self._rng = random.Random(seed)

    def select_server(
        self, request: Request, eligible_servers: Iterable[object]
    ) -> SelectionResult:
        """Return a shared SelectionResult; an empty set means no selection."""
        del request  # Random routing does not use request attributes.
        servers = tuple(eligible_servers)
        if not servers:
            return SelectionResult(
                selected_server_id=None,
                strategy_name="random",
            )

        server_ids = [get_server_id(server) for server in servers]
        if len(server_ids) != len(set(server_ids)):
            raise ValueError("Eligible servers must have unique server IDs")

        selected = self._rng.choice(server_ids)
        return SelectionResult(
            selected_server_id=selected,
            strategy_name="random",
        )
