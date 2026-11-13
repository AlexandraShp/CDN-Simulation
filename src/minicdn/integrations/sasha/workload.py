"""Deterministic FIFO, multi-worker workload model for a simulated CDN.

All times are seconds. ``capacity_units_per_s`` is the service rate *per worker*.
One request uses ``processing_units / capacity_units_per_s`` seconds on one worker.

The model is deliberately independent of SimPy. A SimPy integration should call
``advance_to(env.now)`` before reading or changing committed state, and ``assign``
when a routing decision reserves processing work. Each call to ``estimate_completion_time``
uses a virtual copy of the worker schedules, and never changes the real state.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import heapq
import math
from typing import Any, Deque


# SimPy and floating-point arithmetic can differ by a few ULPs when the
# duration returned by estimate_completion_time is added back to the current
# time. Treat a completion within 1 picosecond as due, while preserving the
# exact scheduled finish timestamp for the next queued job.
_COMPLETION_TIME_TOLERANCE_S = 1e-12


def _positive_finite(value: float, label: str) -> float:
    try:
        numeric = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{label} must be a finite positive number") from exc
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{label} must be a finite positive number")
    return numeric


def _time(value: float) -> float:
    try:
        numeric = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("now_s must be finite and nonnegative") from exc
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError("now_s must be finite and nonnegative")
    return numeric


def _request_units(request: Any) -> float:
    return _positive_finite(getattr(request, "processing_units", None), "processing_units")


def _request_id(request: Any) -> str:
    value = getattr(request, "request_id", None)
    if value is None or not isinstance(value, (str, int)):
        raise ValueError("request.request_id must be a string or integer")
    return str(value)


@dataclass(frozen=True)
class ProcessingJob:
    request_id: str
    processing_units: float


@dataclass(frozen=True)
class WorkerJob:
    request_id: str
    processing_units: float
    started_at_s: float
    finishes_at_s: float


@dataclass(frozen=True)
class CompletionRecord:
    request_id: str
    finished_at_s: float


class ServerWorkload:
    """A work-conserving server with identical parallel workers and FIFO backlog.

    Requests are reserved at ``assign`` time. Busy workers process one request
    each, while extra requests enter a FIFO queue. ``advance_to`` executes
    completions and starts pending requests at the correct simulated times.

    A routing decision at ``now_s`` can use ``estimate_completion_time`` for
    end-to-end *processing completion duration* excluding network transit.
    """

    def __init__(
        self,
        server_id: str,
        capacity_units_per_s: float,
        worker_count: int = 1,
    ) -> None:
        if not isinstance(server_id, str) or not server_id:
            raise ValueError("server_id must be a nonempty string")
        if isinstance(worker_count, bool) or not isinstance(worker_count, int) or worker_count < 1:
            raise ValueError("worker_count must be a positive integer")
        self.server_id = server_id
        self.capacity_units_per_s = _positive_finite(capacity_units_per_s, "capacity_units_per_s")
        self.worker_count = worker_count
        self.current_time_s = 0.0
        self._workers: list[WorkerJob | None] = [None] * worker_count
        self._queue: Deque[ProcessingJob] = deque()
        self._outstanding_ids: set[str] = set()
        self.completed: list[CompletionRecord] = []

    @property
    def busy_worker_count(self) -> int:
        return sum(job is not None for job in self._workers)

    @property
    def queue_length(self) -> int:
        return len(self._queue)

    @property
    def active_request_ids(self) -> tuple[str, ...]:
        return tuple(job.request_id for job in self._workers if job is not None)

    @property
    def queued_request_ids(self) -> tuple[str, ...]:
        return tuple(job.request_id for job in self._queue)

    @property
    def remaining_processing_units(self) -> float:
        busy = sum(
            max(0.0, (job.finishes_at_s - self.current_time_s) * self.capacity_units_per_s)
            for job in self._workers if job is not None
        )
        return busy + sum(job.processing_units for job in self._queue)

    def _start(self, worker_index: int, job: ProcessingJob, when_s: float) -> None:
        self._workers[worker_index] = WorkerJob(
            request_id=job.request_id,
            processing_units=job.processing_units,
            started_at_s=when_s,
            finishes_at_s=when_s + job.processing_units / self.capacity_units_per_s,
        )

    def advance_to(self, now_s: float) -> list[CompletionRecord]:
        """Process scheduled completions up to now_s; return newly completed jobs."""
        now_s = _time(now_s)
        if now_s < self.current_time_s:
            raise ValueError("simulation time cannot move backwards")
        finished: list[CompletionRecord] = []
        while True:
            events = [
                (job.finishes_at_s, index)
                for index, job in enumerate(self._workers)
                if job is not None
                and (
                    job.finishes_at_s <= now_s
                    or math.isclose(
                        job.finishes_at_s,
                        now_s,
                        rel_tol=0.0,
                        abs_tol=_COMPLETION_TIME_TOLERANCE_S,
                    )
                )
            ]
            if not events:
                break
            finish_at, index = min(events)
            old = self._workers[index]
            assert old is not None
            self._workers[index] = None
            self._outstanding_ids.remove(old.request_id)
            record = CompletionRecord(old.request_id, finish_at)
            self.completed.append(record)
            finished.append(record)
            if self._queue:
                self._start(index, self._queue.popleft(), finish_at)
        self.current_time_s = now_s
        return finished

    def assign(self, request: Any, now_s: float) -> None:
        """Commit a request to this server (including its work in future estimates).

        This is a *reservation* at routing time. Network transit is modeled by
        the outer simulator; this module handles processing work only.
        """
        now_s = _time(now_s)
        if now_s < self.current_time_s:
            raise ValueError("simulation time cannot move backwards")
        units = _request_units(request)
        rid = _request_id(request)
        self.advance_to(now_s)
        if rid in self._outstanding_ids:
            raise ValueError(f"duplicate outstanding request_id: {rid}")
        job = ProcessingJob(rid, units)
        self._outstanding_ids.add(rid)
        for index, worker in enumerate(self._workers):
            if worker is None:
                self._start(index, job, now_s)
                break
        else:
            self._queue.append(job)

    def estimate_completion_time(self, request: Any, now_s: float | None = None) -> float:
        """Predict duration from now_s until request processing completes.

        Simulates FIFO placement onto identical workers without changing state.
        Must be called with the simulation's current time; if omitted uses the
        last synchronized time. Future-now queries are supported without mutation.
        """
        units = _request_units(request)
        now = self.current_time_s if now_s is None else _time(now_s)
        if now < self.current_time_s:
            raise ValueError("cannot estimate in the past")
        # Model queue progression until `now` on local copies. It is important
        # not to pretend queued work starts at `now` when workers actually freed
        # earlier; doing so would overestimate in future-snapshot queries.
        worker_end = [job.finishes_at_s if job is not None else self.current_time_s
                      for job in self._workers]
        pending = deque(self._queue)
        if pending:
            # The real state is work-conserving: all workers were busy when a
            # queue existed. Advance the copied work schedule to `now`.
            while pending and min(worker_end) <= now:
                worker_index = min(range(self.worker_count), key=lambda i: (worker_end[i], i))
                start = worker_end[worker_index]
                waiting = pending.popleft()
                worker_end[worker_index] = start + waiting.processing_units / self.capacity_units_per_s
        availability = [max(now, end) for end in worker_end]
        heapq.heapify(availability)
        for waiting in pending:
            started = heapq.heappop(availability)
            finishes = started + waiting.processing_units / self.capacity_units_per_s
            heapq.heappush(availability, finishes)
        started = heapq.heappop(availability)
        return started + units / self.capacity_units_per_s - now
