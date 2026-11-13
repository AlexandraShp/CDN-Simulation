from minicdn.experiments.pre_server import (
    evaluate_hybrid_alpha_sensitivity,
    evaluate_network_routing,
    summarize_poisson_trace,
)


class FakeNetworkModel:
    def __init__(self):
        self.rtt_matrix = {
            "U1": {"A": 0.020, "B": 0.060, "C": 0.100},
            "U2": {"A": 0.080, "B": 0.025, "C": 0.050},
        }

    def get_rtt(self, user_id, server_id):
        return self.rtt_matrix[user_id][server_id]


class FakeMinimumLatencyStrategy:
    def __init__(self, network_model):
        self.network_model = network_model

    def select_server(self, user_id, eligible_servers):
        return min(
            eligible_servers,
            key=lambda server_id: (
                self.network_model.get_rtt(user_id, server_id),
                server_id,
            ),
        ) if eligible_servers else None


def test_network_routing_experiment_compares_random_with_minimum_latency():
    network = FakeNetworkModel()
    strategy = FakeMinimumLatencyStrategy(network)

    observations = evaluate_network_routing(
        scenario_name="test",
        network_model=network,
        minimum_latency_strategy=strategy,
        trials_per_user=200,
        seed=42,
    )

    assert len(observations) == 2
    for observation in observations:
        assert observation.minimum_latency_rtt_s <= observation.random_average_rtt_s
        assert observation.trials == 200
        assert 0 <= observation.random_to_minimum_improvement_pct <= 100


def test_poisson_traffic_summary_is_reproducible():
    kwargs = {
        "arrival_rate_per_s": 2.0,
        "request_count": 100,
        "user_ids": ["U1", "U2"],
        "seed": 17,
    }
    first = summarize_poisson_trace(**kwargs)
    second = summarize_poisson_trace(**kwargs)

    assert first == second
    assert first.request_count == 100
    assert first.theoretical_mean_interarrival_s == 0.5
    assert first.observed_span_s > 0
    assert first.mean_interarrival_s > 0
    assert first.observed_arrival_rate_per_s > 0


def test_hybrid_alpha_endpoints_choose_workload_and_latency_winners():
    network = FakeNetworkModel()
    observations = evaluate_hybrid_alpha_sensitivity(
        network_model=network,
        user_id="U1",
        server_ids=["A", "B", "C"],
        synthetic_workload_seconds={"A": 0.250, "B": 0.020, "C": 0.030},
        alphas=(0.0, 0.5, 1.0),
    )

    assert observations[0].selected_server_id == "B"
    assert observations[-1].selected_server_id == "A"
    assert all(
        item.data_label == "SYNTHETIC_WORKLOAD_NOT_SERVER_MEASUREMENTS"
        for item in observations
    )
