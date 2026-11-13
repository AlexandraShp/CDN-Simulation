"""Generate a reproducible request trace with Poisson arrivals."""

import math
import random

from minicdn.models import Request


def generate_poisson_trace(
    number_of_requests: int,
    arrival_rate_per_s: float,
    user_ids: list[str],
    processing_units: float,
    seed: int,
    start_time_s: float = 0.0,
) -> list[Request]:
    """Generate requests whose inter-arrival times are exponentially distributed.

    Args:
        number_of_requests: Number of requests to generate (may be zero).
        arrival_rate_per_s: Average arrival rate, in requests per second.
        user_ids: Non-empty list of users from which request owners are sampled.
        processing_units: Fixed amount of work assigned to each request.
        seed: Seed used to make the generated trace reproducible.
        start_time_s: Arrival time of the first request, in seconds.

    The first request arrives at ``start_time_s``. Each later request arrives
    after an exponentially distributed interval with mean 1 / arrival_rate_per_s.
    Separate random generators keep arrival timing independent of user selection.
    """
    if not isinstance(number_of_requests, int) or isinstance(number_of_requests, bool):
        raise ValueError("number_of_requests must be an integer")
    if number_of_requests < 0:
        raise ValueError("number_of_requests must be >= 0")
    if not math.isfinite(arrival_rate_per_s) or arrival_rate_per_s <= 0:
        raise ValueError("arrival_rate_per_s must be a finite number > 0")
    if not user_ids or any(not user_id for user_id in user_ids):
        raise ValueError("user_ids must contain at least one non-empty user ID")
    if not math.isfinite(processing_units) or processing_units <= 0:
        raise ValueError("processing_units must be a finite number > 0")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    if not math.isfinite(start_time_s) or start_time_s < 0:
        raise ValueError("start_time_s must be a finite number >= 0")

    arrival_rng = random.Random(seed)
    user_rng = random.Random(seed + 1)

    requests: list[Request] = []
    current_arrival_time = start_time_s

    for index in range(number_of_requests):
        if index > 0:
            interarrival_time = arrival_rng.expovariate(arrival_rate_per_s)
            current_arrival_time += interarrival_time

        requests.append(
            Request(
                request_id=f"R{index + 1:04d}",
                user_id=user_rng.choice(user_ids),
                arrival_time_s=current_arrival_time,
                processing_units=processing_units,
            )
        )

    return requests
