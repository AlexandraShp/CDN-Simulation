"""Tests for adapters around Sasha's real public workload API.

FakeWorkload below is a test fixture only. Production code injects Sasha's
actual ServerWorkload class from her branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from minicdn.models import Request, SelectionResult
from minicdn.simulation import SashaServerConfig, SashaServerRuntime, ServiceExecution
from minicdn.strategies import HybridRouter, SashaLeastLoadedAdapter


@dataclass(frozen=True)
class _Completion:
    request_id: str
    finished_at_s: float


class FakeWorkload:
    """Minimal test double for Sasha's ServerWorkload public interface."""

    def __init__(self, server_id, capacity_units_per_s, worker_count=1):
        self.server_id = server_id
        self.capacity_units_per_s = float(capacity_units_per_s)
        self.worker_count = worker_count
        self.current_time_s = 0.0
        self._available_at = [0.0] * worker_count
        self._jobs = []
        self.completed = []

    def advance_to(self, now_s):
        if now_s < self.current_time_s:
            raise ValueError("time moved backwards")
        self.current_time_s = float(now_s)
        newly_completed = []
        remaining = []
        for request_id, finish_at in self._jobs:
            if finish_at <= now_s:
                record = _Completion(request_id, finish_at)
                self.completed.append(record)
                newly_completed.append(record)
            else:
                remaining.append((request_id, finish_at))
        self._jobs = remaining
        return newly_completed

    def estimate_completion_time(self, request, now_s=None):
        now = self.current_time_s if now_s is None else float(now_s)
        availability = sorted(max(now, worker_end) for worker_end in self._available_at)
        # Existing reservations have already been represented in worker-end
        # values; place the new request on the earliest available worker.
        start = availability[0]
        return start + request.processing_units / self.capacity_units_per_s - now

    def assign(self, request, now_s):
        self.advance_to(now_s)
        worker_index = min(
            range(self.worker_count), key=lambda index: self._available_at[index]
        )
        start = max(now_s, self._available_at[worker_index])
        finish = start + request.processing_units / self.capacity_units_per_s
        self._available_at[worker_index] = finish
        self._jobs.append((request.request_id, finish))


class ManualEnvironment:
    """Tiny generator driver for testing the runtime without installing SimPy."""

    def __init__(self):
        self.now = 0.0

    def process(self, generator):
        return generator

    @staticmethod
    def timeout(delay):
        return SimpleNamespace(delay=float(delay))


def _finish_manual_process(process, env, target_time):
    delay = next(process)
    assert delay.delay == pytest.approx(target_time - env.now)
    env.now = target_time
    with pytest.raises(StopIteration) as stopped:
        next(process)
    return stopped.value.value


def _runtime():
    return SashaServerRuntime(
        [SashaServerConfig("A", 10.0, worker_count=1)],
        server_workload_factory=FakeWorkload,
    )


def test_runtime_creates_fresh_servers_at_each_run():
    runtime = _runtime()
    env1 = ManualEnvironment()
    runtime.start_run(env1)
    first_server = runtime.get_server("A")
    first_server.assign(Request("R1", "U1", 0.0, 10.0), now_s=0.0)

    env2 = ManualEnvironment()
    runtime.start_run(env2)
    second_server = runtime.get_server("A")

    assert second_server is not first_server
    assert second_server._available_at == [0.0]
    assert second_server.completed == []
    assert second_server.estimate_completion_time(
        Request("R2", "U1", 0.0, 5.0), now_s=0.0
    ) == pytest.approx(0.5)


def test_hybrid_uses_sasha_read_only_estimator():
    runtime = SashaServerRuntime(
        [
            SashaServerConfig("A", 10.0, worker_count=1),
            SashaServerConfig("B", 5.0, worker_count=1),
        ],
        server_workload_factory=FakeWorkload,
    )
    env = ManualEnvironment()
    runtime.start_run(env)
    servers = runtime.eligible_servers()
    request = Request("R1", "U1", 0.0, 10.0)

    router = HybridRouter(
        alpha=0.0,
        rtt_lookup=lambda _user, _server: 0.1,
        workload_estimator=runtime.estimate_completion_time,
    )
    before = [
        (server.current_time_s, tuple(server._jobs), tuple(server.completed))
        for server in servers
    ]
    result = router.select_server(request, servers)
    after = [
        (server.current_time_s, tuple(server._jobs), tuple(server.completed))
        for server in servers
    ]

    assert before == after
    assert result.selected_server_id == "A"
    assert result.candidate_scores["A"] == pytest.approx(1.0)
    assert result.candidate_scores["B"] == pytest.approx(2.0)
    assert all(server.current_time_s == 0.0 for server in servers)
    assert all(len(server.completed) == 0 for server in servers)


def test_least_loaded_adapter_calls_sashas_selector_and_converts_result():
    runtime = SashaServerRuntime(
        [SashaServerConfig("A", 10.0), SashaServerConfig("B", 20.0)],
        server_workload_factory=FakeWorkload,
    )
    runtime.start_run(ManualEnvironment())
    servers = runtime.eligible_servers()
    calls = []

    def sasha_selector(request, eligible_servers, now_s=None):
        calls.append(now_s)
        scores = {
            server.server_id: server.estimate_completion_time(request, now_s=now_s)
            for server in eligible_servers
        }
        chosen = min(scores, key=lambda server_id: (scores[server_id], server_id))
        return SimpleNamespace(
            selected_server_id=chosen,
            strategy_name="least_loaded",
            candidate_scores=scores,
        )

    adapter = SashaLeastLoadedAdapter(sasha_selector, runtime)
    result = adapter.select_server(Request("R1", "U1", 0.0, 10.0), servers)

    assert calls == [0.0]
    assert isinstance(result, SelectionResult)
    assert result.selected_server_id == "B"
    assert result.strategy_name == "least_loaded"


def test_sasha_runtime_uses_fifo_model_and_returns_service_execution():
    runtime = _runtime()
    env = ManualEnvironment()
    runtime.start_run(env)
    request1 = Request("R1", "U1", 0.0, 10.0)
    request2 = Request("R2", "U1", 0.0, 5.0)

    process1 = runtime.submit(env, request1, "A")
    delay1 = next(process1)  # commits R1 to Sasha workload model
    process2 = runtime.submit(env, request2, "A")
    delay2 = next(process2)  # commits R2 behind R1 in FIFO order

    assert delay1.delay == pytest.approx(1.0)
    assert delay2.delay == pytest.approx(1.5)

    env.now = 1.0
    with pytest.raises(StopIteration) as first_stopped:
        next(process1)
    first_result = first_stopped.value.value
    assert first_result == ServiceExecution(queue_wait_s=0.0, processing_time_s=1.0)

    env.now = 1.5
    with pytest.raises(StopIteration) as second_stopped:
        next(process2)
    second_result = second_stopped.value.value
    assert second_result == ServiceExecution(queue_wait_s=1.0, processing_time_s=0.5)


def test_runtime_rejects_unknown_server_id():
    runtime = _runtime()
    runtime.start_run(ManualEnvironment())
    with pytest.raises(KeyError, match="Unknown Sasha server ID"):
        runtime.get_server("missing")


def test_server_config_validation():
    with pytest.raises(ValueError):
        SashaServerConfig("", 10.0, 1)
    with pytest.raises(ValueError):
        SashaServerConfig("A", 0.0, 1)
    with pytest.raises(ValueError):
        SashaServerConfig("A", 10.0, 0)
