"""Reusable Plotly diagrams for the Mini CDN Streamlit dashboard."""

from __future__ import annotations

import plotly.graph_objects as go

METHOD_STEPS = {
    "random": ["Eligible\nservers", "Seeded random\nselection", "Selected\nserver"],
    "minimum_latency": ["User + eligible\nservers", "Nirmin RTT\nlookup", "Server with\nminimum RTT"],
    "least_loaded": ["Request + eligible\nservers", "Sasha completion\ntime estimator", "Server with\nminimum estimate"],
    "hybrid": ["RTT + workload\nestimates", "Weighted score\nα·RTT + (1−α)·W", "Server with\nminimum score"],
}


def _flow_figure(labels: list[str], title: str) -> go.Figure:
    fig = go.Figure()
    x_positions = [0.02, 0.385, 0.75]
    width = 0.23
    for index, (label, x) in enumerate(zip(labels, x_positions)):
        fig.add_shape(
            type="rect", x0=x, y0=0.34, x1=x + width, y1=0.69,
            line={"width": 1.5, "color": "#5276A7"},
            fillcolor="#EAF1FA" if index != 1 else "#DDECEB",
            layer="below",
        )
        fig.add_annotation(
            x=x + width / 2, y=0.515, text=label.replace("\n", "<br>"),
            showarrow=False, font={"size": 13, "color": "#172B4D"},
            align="center",
        )
        if index < 2:
            fig.add_annotation(
                x=x + width + 0.065, y=0.515, text="→", showarrow=False,
                font={"size": 24, "color": "#718096"},
            )
    fig.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left"},
        height=230, margin={"l": 8, "r": 8, "t": 48, "b": 12},
        xaxis={"visible": False, "range": [0, 1]},
        yaxis={"visible": False, "range": [0, 1]},
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def strategy_diagram(strategy: str) -> go.Figure:
    labels = METHOD_STEPS.get(strategy, METHOD_STEPS["random"])
    return _flow_figure(labels, "How this routing strategy makes its decision")


def request_lifecycle_diagram() -> go.Figure:
    labels = [
        "Request\ngenerator", "Routing\nstrategy", "Outbound\nnetwork", "Server FIFO\nqueue", "Worker\nprocessing", "Return path +\nmetrics",
    ]
    fig = go.Figure()
    xs = [0.02, 0.19, 0.36, 0.53, 0.70, 0.86]
    width = 0.125
    for index, (label, x) in enumerate(zip(labels, xs)):
        fig.add_shape(
            type="rect", x0=x, y0=0.40, x1=x + width, y1=0.68,
            line={"width": 1.2, "color": "#5276A7"},
            fillcolor="#EAF1FA" if index not in (3, 4) else "#DDECEB",
        )
        fig.add_annotation(
            x=x + width / 2, y=0.54, text=label.replace("\n", "<br>"),
            showarrow=False, font={"size": 10, "color": "#172B4D"}, align="center",
        )
        if index < len(xs) - 1:
            fig.add_annotation(
                x=x + width + 0.035, y=0.54, text="→", showarrow=False,
                font={"size": 18, "color": "#718096"},
            )
    fig.add_annotation(
        x=0.5, y=0.18,
        text="The engine records each stage and computes response, queue, network, throughput and utilization metrics.",
        showarrow=False, font={"size": 11, "color": "#52637A"}, align="center",
    )
    fig.update_layout(
        title={"text": "End-to-end request lifecycle", "x": 0.02, "xanchor": "left"},
        height=260, margin={"l": 5, "r": 5, "t": 48, "b": 10},
        xaxis={"visible": False, "range": [0, 1]},
        yaxis={"visible": False, "range": [0, 1]},
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
