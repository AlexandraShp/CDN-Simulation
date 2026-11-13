from dashboard.charts import request_lifecycle_diagram, strategy_diagram


def test_each_strategy_has_a_three_stage_decision_diagram():
    for strategy in ("random", "minimum_latency", "least_loaded", "hybrid"):
        figure = strategy_diagram(strategy)
        assert len(figure.layout.shapes) == 3
        assert len(figure.layout.annotations) >= 5


def test_request_lifecycle_diagram_has_six_stages():
    figure = request_lifecycle_diagram()
    assert len(figure.layout.shapes) == 6
    assert len(figure.layout.annotations) >= 12
