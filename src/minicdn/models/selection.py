"""Shared result returned by a routing strategy."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SelectionResult:
    """Describe a routing decision without changing simulation state.

    `selected_server_id` is None when no eligible server was available.
    Candidate scores are measured in seconds for Hybrid.
    """

    selected_server_id: str | None
    strategy_name: str
    candidate_scores: dict[str, float] = field(default_factory=dict)

    @property
    def is_served(self) -> bool:
        """Whether the strategy selected a server."""
        return self.selected_server_id is not None
