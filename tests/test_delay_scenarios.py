"""
Tests for the network delay experiment scenarios.

These tests verify that RTT values scale correctly
without changing the underlying network topology.
"""

import pytest

from experiments.delay_scenarios import (
    create_delay_scenario,
    get_scenario_rtt_matrix,
)


def test_low_delay_scenario():
    # The low scenario should preserve the original RTT values.
    network = create_delay_scenario("low")

    assert network.get_rtt("U1", "A") == 0.020


def test_medium_delay_scenario():
    # Medium delay multiplies every base RTT by three.
    network = create_delay_scenario("medium")

    assert network.get_rtt("U1", "A") == 0.060


def test_high_delay_scenario():
    # High delay multiplies every base RTT by five.
    network = create_delay_scenario("high")

    assert network.get_rtt("U1", "A") == 0.100


def test_scenario_preserves_server_ranking():
    # U1 should still prefer A in every scenario.
    for scenario in ["low", "medium", "high"]:
        network = create_delay_scenario(scenario)

        delays = network.get_user_delays("U1")

        closest_server = min(delays, key=delays.get)

        assert closest_server == "A"


def test_scenario_names_are_case_insensitive():
    # Scenario names should work regardless of capitalization.
    network = create_delay_scenario("MEDIUM")

    assert network.get_rtt("U1", "A") == 0.060


def test_unknown_scenario_raises_error():
    # Unsupported scenarios should not silently create a network.
    with pytest.raises(ValueError):
        create_delay_scenario("extreme")


def test_scenario_matrices_are_independent():
    # Updating one scenario must not modify the base matrix or another.
    low = create_delay_scenario("low")
    high = create_delay_scenario("high")

    low.update_rtt("U1", "A", 0.500)

    assert high.get_rtt("U1", "A") == 0.100



def test_get_scenario_rtt_matrix():
    # The helper should return the expected matrix.
    matrix = get_scenario_rtt_matrix("medium")

    # Use approximate comparison to handle floating-point precision.
    assert matrix["U2"]["B"] == pytest.approx(0.075)

