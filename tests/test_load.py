from dataclasses import dataclass
import pytest
from src.strategies.load import select_least_loaded
from src.workload import ServerWorkload

@dataclass(frozen=True)
class Request:
    request_id: str
    processing_units: float


def test_selects_lowest_incoming_completion():
    a = ServerWorkload('a',10)
    b = ServerWorkload('b',20)
    a.assign(Request('existing',10),0)
    result = select_least_loaded(Request('incoming',5),[a,b],0)
    assert result.selected_server_id == 'b'
    assert result.strategy_name == 'least_loaded'
    assert result.candidate_scores == pytest.approx({'a':1.5,'b':.25})
    assert a.queue_length == b.queue_length == 0


def test_different_request_sizes_can_change_selection():
    # A: small backlog, slow service; B: larger backlog, faster service.
    a = ServerWorkload('a',10)
    b = ServerWorkload('b',100)
    b.assign(Request('existing',40),0)
    assert select_least_loaded(Request('small',1),[a,b]).selected_server_id == 'a'
    assert select_least_loaded(Request('large',10),[a,b]).selected_server_id == 'b'


def test_ties_are_resolved_by_string_id():
    a = ServerWorkload('a',10)
    b = ServerWorkload('b',10)
    result = select_least_loaded(Request('incoming',1),[b,a])
    assert result.selected_server_id == 'a'


def test_empty_eligible_returns_no_selection():
    result = select_least_loaded(Request('incoming',1),[])
    assert result.selected_server_id is None
    assert result.candidate_scores == {}


def test_router_does_not_modify_workers_or_queue():
    a = ServerWorkload('a',10)
    a.assign(Request('x',10),0)
    before = (a.current_time_s, a.active_request_ids, a.queued_request_ids)
    select_least_loaded(Request('y',5),[a],.5)
    assert before == (a.current_time_s, a.active_request_ids, a.queued_request_ids)


def test_reject_duplicate_server_ids():
    with pytest.raises(ValueError):
        select_least_loaded(Request('r',1),[ServerWorkload('a',10),ServerWorkload('a',20)])
