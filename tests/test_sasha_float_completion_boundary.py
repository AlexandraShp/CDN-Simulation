"""Regression test for a one-ULP service-completion timing mismatch."""
from types import SimpleNamespace

from minicdn.integrations.sasha import ServerWorkload


def test_advance_to_accepts_simulation_deadline_within_float_tolerance():
    server = ServerWorkload(
        server_id="A",
        capacity_units_per_s=20.0,
        worker_count=1,
    )
    request = SimpleNamespace(request_id="R0010", processing_units=5.0)

    # This is the boundary observed in campaign seed 42. Sasha's worker
    # schedule finishes at .8385578802632309, while adding the estimated
    # remaining duration to SimPy's current time can produce .8385578802632307.
    scheduled_finish_s = 0.8385578802632309
    simulation_deadline_s = 0.8385578802632307
    started_at_s = 0.5885578802632309
    assert simulation_deadline_s < scheduled_finish_s

    server.assign(request, now_s=started_at_s)
    completed = server.advance_to(simulation_deadline_s)

    assert len(completed) == 1
    assert completed[0].request_id == "R0010"
    assert completed[0].finished_at_s == scheduled_finish_s
    assert server.busy_worker_count == 0
    assert server.queue_length == 0
