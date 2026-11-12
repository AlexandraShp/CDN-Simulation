"""Pure Least Loaded server selection using incoming-request completion estimates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from src.workload import ServerWorkload


@dataclass(frozen=True)
class SelectionResult:
    """Temporary standalone result; replace with project's shared result type.

    Names and field types are documented for easy integration. No selection is
    represented with ``selected_server_id=None`` and an empty score mapping.
    """
    selected_server_id: str | None
    strategy_name: str
    candidate_scores: Mapping[str, float]


def select_least_loaded(
    request: Any,
    eligible_servers: Iterable[ServerWorkload],
    now_s: float | None = None,
) -> SelectionResult:
    """Select the server with the shortest estimated processing completion.

    This function NEVER enqueues, advances, or mutates a ServerWorkload. The
    outer simulator must call chosen_server.assign(request, now_s) explicitly.
    """
    servers = list(eligible_servers)
    if not servers:
        return SelectionResult(None, "least_loaded", {})
    ids = [s.server_id for s in servers]
    if len(ids) != len(set(ids)):
        raise ValueError("eligible servers contain duplicate server IDs")
    scores = {
        server.server_id: server.estimate_completion_time(request, now_s=now_s)
        for server in servers
    }
    selected_id = min(scores, key=lambda sid: (scores[sid], sid))
    return SelectionResult(selected_id, "least_loaded", scores)
