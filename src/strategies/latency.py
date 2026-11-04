
"""
Minimum Latency routing strategy for the Mini CDN.

This strategy selects the eligible server with the lowest RTT
for the requesting user. It does not consider server workload.
"""


class MinimumLatencyStrategy:
    """Routes each request to the server with the lowest network RTT."""

    def __init__(self, network_model):
        # Reuse the shared network model instead of duplicating RTT data.
        self.network_model = network_model

    def select_server(self, user_id, eligible_servers):
        """
        Select the server with the smallest RTT.

        Args:
            user_id: ID of the user sending the request.
            eligible_servers: List of server objects or server IDs
                              that are currently available.

        Returns:
            The selected server ID, or None if no server is eligible.
        """

        # There is no possible destination if every server is unavailable.
        if not eligible_servers:
            return None

        # Extract server IDs so the strategy works with either server
        # objects or plain server ID strings.
        server_ids = [
            server.server_id if hasattr(server, "server_id") else server
            for server in eligible_servers
        ]

        # Find the server with the smallest RTT.
        # Sorting by server ID provides deterministic tie-breaking.
        selected_server_id = min(
            server_ids,
            key=lambda server_id: (
                self.network_model.get_rtt(user_id, server_id),
                server_id
            )
        )

        return selected_server_id
