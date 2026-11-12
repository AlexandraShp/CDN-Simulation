from dataclasses import dataclass
import pytest
from src.workload import ServerWorkload


@dataclass(frozen=True)
class Request:
    request_id: str
    user_id: str = 'user'
    arrival_time_s: float = 0.0
    processing_units: float = 1.0


def req(identifier, units=1.0):
    return Request(identifier, processing_units=units)


def test_idle_server_incoming_work():
    server = ServerWorkload('s1', 10.0)
    assert server.estimate_completion_time(req('a', 2)) == pytest.approx(0.2)
    assert server.queue_length == 0
    assert server.busy_worker_count == 0


def test_one_worker_busy_prediction_and_completion():
    server = ServerWorkload('s1', 10.0)
    server.assign(req('a', 10), 0)
    server.advance_to(0.4)
    assert server.remaining_processing_units == pytest.approx(6)
    assert server.estimate_completion_time(req('b', 2)) == pytest.approx(0.8)
    assert server.active_request_ids == ('a',)
    assert [x.request_id for x in server.advance_to(1)] == ['a']


def test_parallel_workers_and_fifo_queued_requests():
    server = ServerWorkload('s', 10, worker_count=2)
    server.assign(req('a', 10), 0)
    server.assign(req('b', 20), 0)
    server.assign(req('c', 10), 0)
    server.assign(req('d', 30), 0)
    assert server.queue_length == 2
    assert server.queued_request_ids == ('c', 'd')
    # c starts on worker 0 at t=1; d starts on worker 0 at t=2.
    assert server.estimate_completion_time(req('e', 10)) == pytest.approx(3)
    server.advance_to(1)
    assert server.active_request_ids == ('c', 'b')
    assert server.queued_request_ids == ('d',)
    server.advance_to(2)
    assert server.active_request_ids == ('d',)
    assert server.queue_length == 0
    server.advance_to(5)
    assert server.busy_worker_count == 0
    assert {x.request_id for x in server.completed} == {'a','b','c','d'}


def test_predict_does_not_mutate_state():
    server = ServerWorkload('s', 10, worker_count=2)
    server.assign(req('a', 10), 0)
    server.assign(req('b', 20), 0)
    server.assign(req('c', 10), 0)
    before = (server.current_time_s, server.queue_length, server.active_request_ids,
              server.queued_request_ids, server.remaining_processing_units,
              tuple(server.completed))
    assert server.estimate_completion_time(req('new', 5), now_s=0.5) == pytest.approx(2.0)
    after = (server.current_time_s, server.queue_length, server.active_request_ids,
             server.queued_request_ids, server.remaining_processing_units,
             tuple(server.completed))
    assert after == before


def test_different_capacity_and_request_size():
    fast = ServerWorkload('fast', 100, worker_count=2)
    slow = ServerWorkload('slow', 10)
    assert fast.estimate_completion_time(req('r', 50)) == pytest.approx(.5)
    assert slow.estimate_completion_time(req('r', 50)) == pytest.approx(5)


@pytest.mark.parametrize('capacity',[0,-1,float('nan'),float('inf')])
def test_invalid_capacity(capacity):
    with pytest.raises(ValueError):
        ServerWorkload('s',capacity)


@pytest.mark.parametrize('units',[0,-1,float('nan'),float('inf')])
def test_invalid_processing_units(units):
    with pytest.raises(ValueError):
        ServerWorkload('s',10).estimate_completion_time(req('r', units))


def test_invalid_worker_count_and_duplicate_ids():
    with pytest.raises(ValueError):
        ServerWorkload('s',10,worker_count=0)
    server = ServerWorkload('s',10)
    server.assign(req('r',1),0)
    with pytest.raises(ValueError):
        server.assign(req('r',1),0)


def test_time_cannot_move_backwards():
    server = ServerWorkload('s',10)
    server.advance_to(2)
    with pytest.raises(ValueError):
        server.advance_to(1)


def test_reservation_counted_immediately():
    server = ServerWorkload('s',10)
    assert server.estimate_completion_time(req('r2',1)) == pytest.approx(.1)
    server.assign(req('r1',10),0)
    assert server.estimate_completion_time(req('r2',1)) == pytest.approx(1.1)

@pytest.mark.parametrize('now', [0.5, 1, 2, 3, 10])
def test_future_prediction_matches_advanced_state(now):
    from copy import deepcopy
    server = ServerWorkload('s', 10, worker_count=2)
    for identifier, units in [('a', 10), ('b', 20), ('c', 15), ('d', 30)]:
        server.assign(req(identifier, units), 0)
    before = deepcopy(server.__dict__)
    predicted = server.estimate_completion_time(req('incoming', 5), now)
    assert server.__dict__ == before
    advanced = deepcopy(server)
    advanced.advance_to(now)
    assert predicted == pytest.approx(advanced.estimate_completion_time(req('incoming', 5)))
