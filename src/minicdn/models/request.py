"""Request data model, following the team's proposed Technical Contract v1.0."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Request:
    """One client request entering the CDN simulation.

    All time values are in seconds. `processing_units` describes the amount
    of work the selected server must perform; it is not a duration by itself.
    """

    request_id: str
    user_id: str
    arrival_time_s: float
    processing_units: float

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id must not be empty")
        if not self.user_id:
            raise ValueError("user_id must not be empty")
        if self.arrival_time_s < 0:
            raise ValueError("arrival_time_s must be >= 0")
        if self.processing_units <= 0:
            raise ValueError("processing_units must be > 0")
