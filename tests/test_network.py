import pytest

from src.network import NetworkModel


@pytest.fixture
def network():
    # Create a small network for testing.
    rtt_matrix = {
        "U1": {"A": 0.020, "B": 0.060, "C": 0.100},
        "U2": {"A": 0.080, "B": 0.025, "C": 0.050},
        "U3": {"A": 0.090, "B": 0.070, "C": 0.015},
    }

    return NetworkModel(rtt_matrix)


def test_get_rtt(network):
    assert network.get_rtt("U1", "A") == 0.020


def test_outbound_and_return_delay(network):
    assert network.get_outbound_delay("U1", "A") == 0.010
    assert network.get_return_delay("U1", "A") == 0.010


def test_get_user_delays(network):
    assert network.get_user_delays("U2") == {
        "A": 0.080,
        "B": 0.025,
        "C": 0.050,
    }


def test_update_rtt(network):
    network.update_rtt("U1", "A", 0.030)
    assert network.get_rtt("U1", "A") == 0.030


def test_unknown_user(network):
    with pytest.raises(KeyError):
        network.get_rtt("U4", "A")


def test_unknown_server(network):
    with pytest.raises(KeyError):
        network.get_rtt("U1", "D")


def test_negative_rtt():
    with pytest.raises(ValueError):
        NetworkModel({"U1": {"A": -0.020}})


def test_non_numeric_rtt():
    with pytest.raises(TypeError):
        NetworkModel({"U1": {"A": "fast"}})
