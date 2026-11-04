"""
Network delay experiment scenarios for the Mini CDN.

This module creates low, medium, and high network-delay
configurations using the same base RTT matrix.

All RTT values are stored in seconds internally.
"""

from src.network import NetworkModel


# Base RTT matrix for the low-delay scenario.
# Rows represent users, and columns represent CDN servers.
BASE_RTT_MATRIX = {
    "U1": {"A": 0.020, "B": 0.060, "C": 0.100},
    "U2": {"A": 0.080, "B": 0.025, "C": 0.050},
    "U3": {"A": 0.090, "B": 0.070, "C": 0.015},
}


# Each scenario scales every RTT by the same factor.
# This preserves the relative network topology.
SCENARIO_MULTIPLIERS = {
    "low": 1,
    "medium": 3,
    "high": 5,
}


def create_delay_scenario(scenario_name):
    """
    Create a NetworkModel for the requested delay scenario.

    Args:
        scenario_name: 'low', 'medium', or 'high'.

    Returns:
        A NetworkModel containing the scenario's RTT matrix.

    Raises:
        ValueError: If the scenario name is not supported.
    """

    # Normalize the input so names are case-insensitive.
    scenario_name = scenario_name.lower()

    if scenario_name not in SCENARIO_MULTIPLIERS:
        raise ValueError(
            f"Unknown delay scenario: {scenario_name}. "
            f"Choose from {list(SCENARIO_MULTIPLIERS.keys())}."
        )

    multiplier = SCENARIO_MULTIPLIERS[scenario_name]

    # Build a new matrix instead of modifying the shared base matrix.
    # This prevents one experiment from affecting another.
    scenario_matrix = {
        user_id: {
            server_id: rtt * multiplier
            for server_id, rtt in server_delays.items()
        }
        for user_id, server_delays in BASE_RTT_MATRIX.items()
    }

    return NetworkModel(scenario_matrix)


def get_scenario_rtt_matrix(scenario_name):
    """Return the RTT matrix for a scenario as a regular dictionary."""

    return create_delay_scenario(scenario_name).rtt_matrix
