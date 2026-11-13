"""Integration tests use a test-only SimPy server adapter.

This fake backend exists only to verify engine orchestration. It is not a
production server/workload implementation and does not replace Sasha's work.
"""

import pytest

simpy = pytest.importorskip("simpy")

from minicdn.models import Request, SelectionResult
from minicdn.simulation import ServiceExecution, SimulationEngine


class FakeNetwork:
    def __init__(self, rtt_by_pair):
        self.rtt_by_pair = rtt_by_pair

    def get_outbound_delay(self, user_id, server_id):
        return self.rtt_by_pair[(user_id, server_id)] / 2

    def get_return_delay(self, user_id, server_id):
        return self.rtt_by_pair[(user_id, server_id)] / 2


class FakeServer:
    def __init__(self, server_id, worker_count=1, processing_rate=1.0):
        self.server_id = server_id
        self.worker_count = worker_count
        self.processing_rate = processing_rate


class FakeServerRuntime:
    """Test fixture only: minimal SimPy resource to exercise the engine port."""

    def __init__(self, servers):
        self.servers = tuple(servers)
        self.resources = {}

    def all_servers(self):
        return self.servers

    def eligible_servers(self):
        return self.servers

    def worker_count(self, server_id):
        server = next(item for item in self.servers if item.server_id == server_id)
        return server.worker_count

    def submit(self, env, request, server_id):
        server = next(item for item in self.servers if item.server_id == server_id)
        if server_id not in self.resources:
            self.resources[server_id] = simpy.Resource(
                env, capacity=server.worker_count
            )
        resource = self.resources[server_id]
        return env.process(self._serve(env, resource, request, server))

    @staticmethod
    def _serve(env, resource, request, server):
        arrived_at_server = env.now
        with resource.request() as worker_request:
            yield worker_request
            processing_started = env.now
            processing_time_s = request.processing_units / server.processing_rate
            yield env.timeout(processing_time_s)
        return ServiceExecution(
            queue_wait_s=processing_started - arrived_at_server,
            processing_time_s=processing_time_s,
        )


class ChooseFirstRouter:
    def select_server(self, request, eligible_servers):
        del request
        servers = tuple(eligible_servers)
        if not servers:
            return SelectionResult(None, "choose_first")
        return SelectionResult(servers[0].server_id, "choose_first")


class NeverSelectRouter:
    def select_server(self, request, eligible_servers):
        del request, eligible_servers
        return SelectionResult(None, "never_select")


def test_engine_runs_request_through_network_server_and_response():
    server = FakeServer("S1", worker_count=1, processing_rate=2.0)
    runtime = FakeServerRuntime([server])
    network = FakeNetwork({("U1", "S1"): 0.2})
    engine = SimulationEngine(network, runtime)

    result = engine.run(
        [Request("R1", "U1", 0.0, 4.0)],
        ChooseFirstRouter(),
    )

    outcome = result.request_results[0]
    assert outcome.status == "completed"
    assert outcome.selected_server_id == "S1"
    assert outcome.outbound_delay_s == pytest.approx(0.1)
    assert outcome.return_delay_s == pytest.approx(0.1)
    assert outcome.processing_time_s == pytest.approx(2.0)
    assert outcome.queue_wait_s == pytest.approx(0.0)
    assert outcome.response_time_s == pytest.approx(2.2)
    assert result.summary.average_network_time_s == pytest.approx(0.2)
    assert result.summary.utilization_by_server["S1"] == pytest.approx(2.0 / 2.2)

    event_types = [event.event_type for event in result.events]
    assert event_types == [
        "REQUEST_GENERATED",
        "SERVER_SELECTED",
        "REQUEST_ARRIVED_AT_SERVER",
        "PROCESSING_STARTED",
        "PROCESSING_COMPLETED",
        "RESPONSE_COMPLETED",
    ]


def test_engine_accounts_for_fifo_queue_wait_from_server_backend():
    server = FakeServer("S1", worker_count=1, processing_rate=1.0)
    runtime = FakeServerRuntime([server])
    network = FakeNetwork({("U1", "S1"): 0.0})
    engine = SimulationEngine(network, runtime)
    requests = [
        Request("R1", "U1", 0.0, 2.0),
        Request("R2", "U1", 0.0, 1.0),
    ]

    result = engine.run(requests, ChooseFirstRouter())
    outcomes = {item.request_id: item for item in result.request_results}

    assert outcomes["R1"].queue_wait_s == pytest.approx(0.0)
    assert outcomes["R2"].queue_wait_s == pytest.approx(2.0)
    assert outcomes["R2"].response_time_s == pytest.approx(3.0)
    assert any(event.event_type == "QUEUE_ENTERED" for event in result.events)


def test_engine_marks_request_unserved_when_no_server_is_eligible():
    runtime = FakeServerRuntime([])
    network = FakeNetwork({})
    engine = SimulationEngine(network, runtime)

    result = engine.run(
        [Request("R1", "U1", 1.0, 10.0)],
        NeverSelectRouter(),
    )

    assert result.request_results[0].status == "unserved"
    assert result.summary.unserved_requests == 1
    assert result.summary.completed_requests == 0
    assert result.summary.average_response_time_s is None
    assert any(event.event_type == "REQUEST_UNSERVED" for event in result.events)


def test_engine_rejects_duplicate_request_ids():
    engine = SimulationEngine(FakeNetwork({}), FakeServerRuntime([]))
    requests = [
        Request("R1", "U1", 0.0, 1.0),
        Request("R1", "U2", 1.0, 1.0),
    ]

    with pytest.raises(ValueError, match="Duplicate request_id"):
        engine.run(requests, NeverSelectRouter())
