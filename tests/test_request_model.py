import pytest

from minicdn.models import Request


def test_request_stores_required_fields():
    request = Request("R001", "U1", 1.5, 100.0)

    assert request.request_id == "R001"
    assert request.user_id == "U1"
    assert request.arrival_time_s == 1.5
    assert request.processing_units == 100.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"request_id": "", "user_id": "U1", "arrival_time_s": 0.0, "processing_units": 10.0},
        {"request_id": "R1", "user_id": "", "arrival_time_s": 0.0, "processing_units": 10.0},
        {"request_id": "R1", "user_id": "U1", "arrival_time_s": -0.1, "processing_units": 10.0},
        {"request_id": "R1", "user_id": "U1", "arrival_time_s": 0.0, "processing_units": 0.0},
    ],
)
def test_request_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        Request(**kwargs)
