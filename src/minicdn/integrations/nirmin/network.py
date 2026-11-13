
"""
Network delay model for the Mini CDN simulation.

This module stores the Round-Trip Time (RTT) between each user
and server and provides methods to retrieve network delays.
"""


class NetworkModel:
    """Represents network delays between users and CDN servers."""

    def __init__(self, rtt_matrix):
        # Store a copy so external changes do not silently modify our model.
        self.rtt_matrix = {
            user_id: dict(server_delays)
            for user_id, server_delays in rtt_matrix.items()
        }

        # Validate the RTT values before using them in the simulation.
        for user_id, server_delays in self.rtt_matrix.items():
            for server_id, rtt in server_delays.items():
                if not isinstance(rtt, (int, float)):
                    raise TypeError(
                        f"RTT for {user_id} -> {server_id} must be numeric."
                    )

                if rtt < 0:
                    raise ValueError(
                        f"RTT for {user_id} -> {server_id} cannot be negative."
                    )

    def get_rtt(self, user_id, server_id):
        """Return the round-trip time between a user and a server."""

        if user_id not in self.rtt_matrix:
            raise KeyError(f"Unknown user: {user_id}")

        if server_id not in self.rtt_matrix[user_id]:
            raise KeyError(
                f"No RTT defined for {user_id} -> {server_id}"
            )

        return self.rtt_matrix[user_id][server_id]

    def get_outbound_delay(self, user_id, server_id):
        """Return the user-to-server delay, assuming a symmetric path."""

        return self.get_rtt(user_id, server_id) / 2

    def get_return_delay(self, user_id, server_id):
        """Return the server-to-user delay, assuming a symmetric path."""

        return self.get_rtt(user_id, server_id) / 2

    def get_user_delays(self, user_id):
        """Return all server RTT values for a particular user."""

        if user_id not in self.rtt_matrix:
            raise KeyError(f"Unknown user: {user_id}")

        return dict(self.rtt_matrix[user_id])

    def update_rtt(self, user_id, server_id, new_rtt):
        """Update the RTT between an existing user and server."""

        if user_id not in self.rtt_matrix:
            raise KeyError(f"Unknown user: {user_id}")

        if server_id not in self.rtt_matrix[user_id]:
            raise KeyError(
                f"No RTT defined for {user_id} -> {server_id}"
            )

        if not isinstance(new_rtt, (int, float)):
            raise TypeError("RTT must be numeric.")

        if new_rtt < 0:
            raise ValueError("RTT cannot be negative.")

        self.rtt_matrix[user_id][server_id] = new_rtt
