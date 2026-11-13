"""Adapter for Sasha's Least Loaded selector and shared SelectionResult."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from minicdn.models import Request, SelectionResult
from minicdn.strategies.contracts import get_server_id, validate_seconds


class SashaLeastLoadedAdapter:
    """Wrap Sasha's ``select_least_loaded`` function without copying its logic.

    The actual selector function is injected from Sasha's branch. Its local
    SelectionResult is converted into the team's shared SelectionResult.
    """

    def __init__(self, selector: Callable[..., Any], server_runtime: Any) -> None:
        if not callable(selector):
            raise TypeError("selector must be Sasha's callable select_least_loaded function")
        if not hasattr(type(server_runtime), "current_time_s"):
            raise TypeError("server_runtime must expose a current_time_s property")
        self._selector = selector
        self._runtime = server_runtime

    def select_server(
        self, request: Request, eligible_servers: Iterable[object]
    ) -> SelectionResult:
        servers = tuple(eligible_servers)
        if not servers:
            return SelectionResult(None, "least_loaded")

        server_ids = [get_server_id(server) for server in servers]
        if len(server_ids) != len(set(server_ids)):
            raise ValueError("Eligible servers must have unique server IDs")

        # Sasha's selector expects this exact now_s keyword and returns its own
        # temporary SelectionResult. Only its output is adapted here.
        result = self._selector(
            request,
            servers,
            now_s=float(self._runtime.current_time_s),
        )
        selected_id = getattr(result, "selected_server_id", None)
        raw_scores = getattr(result, "candidate_scores", {})
        if not isinstance(raw_scores, Mapping):
            raise TypeError("Sasha selector candidate_scores must be a mapping")
        scores = {
            str(server_id): validate_seconds(score, "Sasha workload score", str(server_id))
            for server_id, score in raw_scores.items()
        }
        unknown_scores = set(scores) - set(server_ids)
        if unknown_scores:
            raise ValueError(
                f"Sasha selector returned scores for unknown servers: {sorted(unknown_scores)}"
            )
        if selected_id is None:
            if servers:
                raise RuntimeError("Sasha Least Loaded returned no selection despite eligible servers")
            return SelectionResult(None, "least_loaded", scores)
        if selected_id not in server_ids:
            raise RuntimeError(
                f"Sasha Least Loaded selected {selected_id!r}, outside the eligible server set"
            )
        return SelectionResult(
            selected_server_id=selected_id,
            strategy_name="least_loaded",
            candidate_scores=scores,
        )
