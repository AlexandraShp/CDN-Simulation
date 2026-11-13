"""Build a deterministic sequence of requests from a predefined trace."""

from collections.abc import Iterable, Mapping

from minicdn.models import Request


# A trace row contains the four values required to construct one Request.
RequestSpec = Mapping[str, str | float]


def generate_fixed_trace(specifications: Iterable[RequestSpec]) -> list[Request]:
    """Convert predefined request specifications into ordered Request objects.

    Each specification must contain:
      - request_id: unique request identifier
      - user_id: identifier of the requesting user
      - arrival_time_s: arrival time, in seconds
      - processing_units: amount of server work required

    Rows must already be in non-decreasing arrival-time order. Requiring this
    makes mistakes in a manually prepared experiment trace visible instead of
    silently changing the supplied experiment.
    """
    requests: list[Request] = []
    seen_request_ids: set[str] = set()
    previous_arrival_time = -1.0

    for index, specification in enumerate(specifications):
        try:
            request = Request(
                request_id=specification["request_id"],
                user_id=specification["user_id"],
                arrival_time_s=specification["arrival_time_s"],
                processing_units=specification["processing_units"],
            )
        except KeyError as error:
            missing_field = error.args[0]
            raise ValueError(
                f"Trace row {index} is missing required field: {missing_field}"
            ) from error

        if request.request_id in seen_request_ids:
            raise ValueError(f"Duplicate request_id: {request.request_id}")

        if request.arrival_time_s < previous_arrival_time:
            raise ValueError(
                "Trace rows must be ordered by non-decreasing arrival_time_s; "
                f"row {index} arrives at {request.arrival_time_s}, before the "
                f"previous row at {previous_arrival_time}."
            )

        requests.append(request)
        seen_request_ids.add(request.request_id)
        previous_arrival_time = request.arrival_time_s

    return requests
