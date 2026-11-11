
def select_least_loaded(servers):
    if not servers:
        raise ValueError("No servers available")

    selected = min(
        servers,
        key=lambda server: (
            server.estimated_waiting_time(),
            server.server_id
        )
    )

    return selected.server_id
