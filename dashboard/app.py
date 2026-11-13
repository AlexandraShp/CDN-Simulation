"""Interactive Mini CDN dashboard for campaign analysis and new runs."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.analytics import (
    METRICS,
    STRATEGY_LABELS,
    STRATEGY_ORDER,
    alpha_metrics,
    apply_scenario_filters,
    best_alpha_by_scenario,
    improvement_percent,
    load_campaign_data,
    scenario_strategy_metrics,
    strategy_metrics,
)
from dashboard.charts import request_lifecycle_diagram, strategy_diagram


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = PROJECT_ROOT / "experiments" / "results" / "final_campaign"
CAMPAIGN_SCRIPT = PROJECT_ROOT / "experiments" / "run_experiment_campaign.py"

METHODS = {
    "random": {
        "title": "Random Routing",
        "short": "Reproducible baseline that selects uniformly from eligible servers.",
        "principle": "The router chooses one eligible server using a dedicated seeded random generator. It does not inspect RTT or workload.",
        "strength": "Simple, low decision overhead and useful as a baseline for evaluating more informed policies.",
        "tradeoff": "It can send a request to a distant or busy server because all eligible servers have equal selection probability.",
        "decision": "Uniform random choice from the eligible-server set.",
        "responsibility": "Saif — baseline routing implementation",
    },
    "minimum_latency": {
        "title": "Minimum Latency",
        "short": "Selects the eligible server with the lowest user-to-server RTT.",
        "principle": "The strategy asks Nirmin's network model for each eligible server's RTT and selects the lowest value.",
        "strength": "Minimizes the network component of response time and is especially useful when servers have very different network distances.",
        "tradeoff": "It ignores server workload. A nearby server can become congested while a slightly more distant server is idle.",
        "decision": "argmin over RTT(user, server).",
        "responsibility": "Nirmin — network model and Minimum Latency",
    },
    "least_loaded": {
        "title": "Least Loaded",
        "short": "Selects the server with the shortest predicted completion time for the incoming request.",
        "principle": "The strategy reuses Sasha's workload estimator, which accounts for active workers, queued work, request size and server capacity.",
        "strength": "Reduces queueing and avoids assigning work to servers with long predicted completion times.",
        "tradeoff": "It does not directly optimize network distance, so a low-workload server may be farther from the user.",
        "decision": "argmin over Sasha's predicted request completion duration.",
        "responsibility": "Sasha — server workload model and Least Loaded",
    },
    "hybrid": {
        "title": "Hybrid Routing",
        "short": "Balances network RTT and predicted server completion time using alpha.",
        "principle": "The router combines Nirmin's RTT lookup and Sasha's workload estimator using a weighted score.",
        "strength": "Balances network distance against server congestion and can avoid the weaknesses of optimizing either metric alone.",
        "tradeoff": "Performance depends on the alpha weight and on the scale/meaning of the RTT and workload values. Alpha should be selected using controlled experiments.",
        "decision": "Score(server) = α × RTT + (1 − α) × predicted workload completion time.",
        "responsibility": "Saif — Hybrid routing and alpha experiments",
    },
}

st.set_page_config(
    page_title="Mini CDN Control Center",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.35rem; padding-bottom: 2.2rem;}
      .hero {padding: 1.2rem 1.4rem; border-radius: 14px;
             background: linear-gradient(115deg, rgba(38,92,145,.16), rgba(38,145,130,.10));
             border: 1px solid rgba(110,140,170,.25); margin-bottom: 1rem;}
      .hero h1 {margin: 0 0 .3rem 0; font-size: 2rem;}
      .hero p {margin: 0; color: #64748b;}
      .small-muted {color: #718096; font-size: .86rem;}
      div[data-testid="stMetric"] {background: rgba(120,140,160,.07); border: 1px solid rgba(120,140,160,.16);
        padding: .75rem .9rem; border-radius: 12px;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _mtime_stamp(folder: Path) -> float:
    files = [folder / name for name in (
        "strategy_runs.csv", "strategy_summary.csv", "hybrid_alpha_runs.csv", "hybrid_alpha_summary.csv"
    )]
    return max((file.stat().st_mtime for file in files if file.exists()), default=0.0)


@st.cache_data(show_spinner=False)
def _load_data(folder_string: str, stamp: float):
    del stamp
    return load_campaign_data(folder_string)


def _ms(value: float | int | None) -> str:
    return "—" if value is None or pd.isna(value) else f"{float(value):,.2f} ms"


def _pct(value: float | int | None) -> str:
    return "—" if value is None or pd.isna(value) else f"{float(value) * 100:.1f}%"


def _filtered(frame: pd.DataFrame, network: str, traffic: str) -> pd.DataFrame:
    return apply_scenario_filters(frame, network, traffic)


def _metric_frame(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    return scenario_strategy_metrics(frame, metric)


def _metric_value(row: pd.Series, metric: str) -> str:
    value = row.get(metric)
    if pd.isna(value):
        return "—"
    if metric == "average_server_utilization":
        return f"{float(value) * 100:.1f}%"
    if metric == "throughput_requests_per_s":
        return f"{float(value):.2f} req/s"
    return _ms(float(value))


def _summary_for(frame: pd.DataFrame) -> pd.DataFrame:
    data = strategy_metrics(frame)
    if not data.empty:
        data["average_server_utilization_pct"] = data["average_server_utilization"] * 100.0
    return data


def _display_scenario_table(frame: pd.DataFrame) -> None:
    rows = _metric_frame(frame, "average_response_ms")
    if rows.empty:
        st.info("No observations match the current filters.")
        return
    pivot = rows.pivot_table(
        index="scenario_label", columns="strategy_label", values="average_response_ms", aggfunc="mean"
    ).reindex(columns=[STRATEGY_LABELS[key] for key in STRATEGY_ORDER if STRATEGY_LABELS[key] in rows.strategy_label.unique()])
    st.dataframe(pivot.style.format("{:.1f} ms"), use_container_width=True)


def _render_overview(data) -> None:
    st.markdown("## Project overview")
    runs = data.strategy_runs
    summary = _summary_for(runs)
    total_requests = int(runs["request_count"].sum())
    completed = int(runs["completed_requests"].sum())
    failures = int(runs["failed_requests"].sum() + runs["unserved_requests"].sum())
    best = summary.iloc[0] if not summary.empty else None

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Strategy observations", f"{len(runs):,}")
    c2.metric("Requests processed", f"{total_requests:,}")
    c3.metric("Completed requests", f"{completed:,}")
    c4.metric("Failures / unserved", f"{failures:,}")
    c5.metric("Repetitions", str(data.validation["repetition_count"]))

    if best is not None:
        st.success(
            f"Best average response in the current dataset: {best['strategy_label']} "
            f"({best['average_response_ms']:.2f} ms). This describes the bundled demonstration configuration."
        )

    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Average response time by strategy")
        fig = px.bar(
            summary, x="strategy_label", y="average_response_ms", color="strategy_label",
            labels={"strategy_label": "Routing strategy", "average_response_ms": "Average response (ms)"},
            hover_data={"median_response_ms": ":.2f", "p95_response_ms": ":.2f", "average_queue_wait_ms": ":.2f"},
        )
        fig.update_layout(showlegend=False, height=390, yaxis_title="Milliseconds", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Response-time distribution across repetitions")
        fig = px.box(
            runs, x="strategy", y="average_response_ms", color="strategy",
            category_orders={"strategy": STRATEGY_ORDER},
            labels={"strategy": "Routing strategy", "average_response_ms": "Run average (ms)"},
            points="outliers",
        )
        fig.update_layout(showlegend=False, height=390, xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Performance scorecard")
    scorecard = summary[[
        "strategy_label", "average_response_ms", "median_response_ms", "p95_response_ms",
        "average_queue_wait_ms", "average_network_ms", "throughput_requests_per_s",
        "average_server_utilization_pct",
    ]].rename(columns={
        "strategy_label": "Strategy",
        "average_response_ms": "Average response (ms)",
        "median_response_ms": "Median response (ms)",
        "p95_response_ms": "Mean run-level P95 (ms)",
        "average_queue_wait_ms": "Queue wait (ms)",
        "average_network_ms": "Network time (ms)",
        "throughput_requests_per_s": "Throughput (req/s)",
        "average_server_utilization_pct": "Average utilization (%)",
    })
    st.dataframe(scorecard.style.format({
        "Average response (ms)": "{:.2f}", "Median response (ms)": "{:.2f}",
        "Mean run-level P95 (ms)": "{:.2f}", "Queue wait (ms)": "{:.2f}",
        "Network time (ms)": "{:.2f}", "Throughput (req/s)": "{:.2f}",
        "Average utilization (%)": "{:.1f}",
    }), use_container_width=True, hide_index=True)

    st.subheader("What the results suggest")
    if len(summary) >= 2:
        random_value = float(summary.loc[summary.strategy == "random", "average_response_ms"].iloc[0])
        winner = summary.iloc[0]
        improvement = improvement_percent(random_value, float(winner.average_response_ms))
        st.markdown(
            f"- **{winner.strategy_label}** has the lowest overall mean response time in this dataset.\n"
            f"- It is {improvement:.1f}% lower than Random across the same bundled experiment matrix.\n"
            f"- Compare network time and queue waiting time separately: a strategy can improve one component while worsening the other."
        )


def _render_methods(data, network: str, traffic: str) -> None:
    st.markdown("## Strategy deep dive")
    st.caption("Select a method to inspect its decision logic, strengths, trade-offs and measured results.")
    selected_label = st.radio(
        "Routing method", [STRATEGY_LABELS[key] for key in STRATEGY_ORDER], horizontal=True,
        label_visibility="collapsed",
    )
    selected = next(key for key, label in STRATEGY_LABELS.items() if label == selected_label)
    info = METHODS[selected]
    frame = _filtered(data.strategy_runs, network, traffic)
    own = frame[frame.strategy == selected].copy()
    all_summary = _summary_for(frame)
    own_summary = all_summary[all_summary.strategy == selected]

    st.subheader(info["title"])
    st.write(info["short"])
    st.plotly_chart(strategy_diagram(selected), use_container_width=True, config={"displayModeBar": False})

    a, b = st.columns(2)
    with a:
        st.markdown("**How it works**")
        st.write(info["principle"])
        st.markdown("**Decision rule**")
        st.code(info["decision"], language="text")
    with b:
        st.markdown("**Strength**")
        st.write(info["strength"])
        st.markdown("**Trade-off**")
        st.write(info["tradeoff"])
    st.caption(info["responsibility"])

    if own.empty:
        st.info("No observations match the current filters.")
        return
    row = own_summary.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Average response", _ms(row.average_response_ms))
    c2.metric("Mean run-level P95", _ms(row.p95_response_ms))
    c3.metric("Queue waiting", _ms(row.average_queue_wait_ms))
    c4.metric("Network time", _ms(row.average_network_ms))

    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.subheader("Response time by scenario")
        scenario = own.groupby(["network_scenario", "traffic_scenario"], as_index=False).agg(
            response=("average_response_ms", "mean"),
            variation=("average_response_ms", "std"),
        )
        scenario["scenario"] = scenario.network_scenario.str.title() + " / " + scenario.traffic_scenario.str.title()
        fig = px.bar(scenario, x="scenario", y="response", error_y="variation",
                     labels={"scenario": "Network / traffic", "response": "Average response (ms)"})
        fig.update_layout(height=360, xaxis_title="", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with chart_right:
        st.subheader("Run-to-run variability")
        fig = px.box(own, x="network_scenario", y="average_response_ms", color="traffic_scenario",
                     category_orders={"network_scenario": ["low", "medium", "high"],
                                      "traffic_scenario": ["low", "medium", "high"]},
                     labels={"network_scenario": "Network delay", "traffic_scenario": "Traffic", "average_response_ms": "Response (ms)"})
        fig.update_layout(height=360)
        st.plotly_chart(fig, use_container_width=True)

    metric_choice = st.selectbox(
        "Inspect another metric", list(METRICS),
        format_func=lambda key: f"{METRICS[key]['label']} ({METRICS[key]['unit']})",
        key=f"method_metric_{selected}",
    )
    metric_data = own.groupby(["network_scenario", "traffic_scenario"], as_index=False)[metric_choice].mean()
    metric_data["scenario"] = metric_data.network_scenario.str.title() + " / " + metric_data.traffic_scenario.str.title()
    if metric_choice == "average_server_utilization":
        metric_data[metric_choice] *= 100.0
    fig = px.bar(metric_data, x="scenario", y=metric_choice,
                 labels={"scenario": "Network / traffic", metric_choice: METRICS[metric_choice]["label"] + (" (%)" if metric_choice == "average_server_utilization" else f" ({METRICS[metric_choice]['unit']})")})
    fig.update_layout(height=330, xaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Show run-level observations"):
        st.dataframe(own.sort_values(["network_scenario", "traffic_scenario", "repetition"]),
                     use_container_width=True, hide_index=True)


def _render_comparison(data, network: str, traffic: str) -> None:
    st.markdown("## Strategy comparison")
    frame = _filtered(data.strategy_runs, network, traffic)
    metric = st.selectbox(
        "Metric to compare", list(METRICS), index=0,
        format_func=lambda key: f"{METRICS[key]['label']} ({METRICS[key]['unit']})",
    )
    chart_data = _metric_frame(frame, metric)
    if chart_data.empty:
        st.info("No data is available for these filters.")
        return
    if metric == "average_server_utilization":
        chart_data[metric] *= 100.0
    label = METRICS[metric]["label"]
    unit = "%" if metric == "average_server_utilization" else METRICS[metric]["unit"]

    left, right = st.columns([1.15, 1])
    with left:
        st.subheader(f"{label} by strategy")
        fig = px.bar(chart_data, x="strategy_label", y=metric, color="strategy_label",
                     labels={"strategy_label": "Strategy", metric: f"{label} ({unit})"},
                     category_orders={"strategy_label": [STRATEGY_LABELS[x] for x in STRATEGY_ORDER]})
        fig.update_layout(showlegend=False, height=390, xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Scenario-by-scenario comparison")
        fig = px.bar(chart_data, x="scenario_label", y=metric, color="strategy_label", barmode="group",
                     labels={"scenario_label": "Network / traffic scenario", metric: f"{label} ({unit})", "strategy_label": "Strategy"})
        fig.update_layout(height=390, xaxis_title="", legend_title="Strategy")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Network delay versus queue waiting time")
    scatter_data = frame.copy()
    scatter_data["strategy_label"] = scatter_data.strategy.map(STRATEGY_LABELS)
    fig = px.scatter(scatter_data, x="average_network_ms", y="average_queue_wait_ms", color="strategy_label",
                     symbol="traffic_scenario", hover_data=["network_scenario", "traffic_scenario", "repetition", "average_response_ms"],
                     labels={"average_network_ms": "Network time (ms)", "average_queue_wait_ms": "Queue wait (ms)", "strategy_label": "Strategy"})
    fig.update_layout(height=430)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Each point is one simulation run. This plot makes the network-delay / queue-wait trade-off visible.")
    with st.expander("Scenario result table"):
        st.dataframe(chart_data.sort_values(["network_scenario", "traffic_scenario", metric]),
                     use_container_width=True, hide_index=True)


def _render_alpha(data, network: str, traffic: str) -> None:
    st.markdown("## Hybrid alpha laboratory")
    st.latex(r"\mathrm{Score}(s)=\alpha\,\mathrm{RTT}_s+(1-\alpha)\,\mathrm{Workload}_s")
    st.write("Alpha controls the scoring balance: 0 is workload-only, 1 is RTT-only. Both inputs are represented in seconds in the current model.")
    frame = _filtered(data.hybrid_alpha_runs, network, traffic)
    if frame.empty:
        st.info("No alpha observations match the current filters.")
        return
    alpha_summary = alpha_metrics(frame)
    best = alpha_summary.loc[alpha_summary.average_response_ms.idxmin()]
    st.success(f"Best alpha for the selected filters: **{best.alpha:.2f}** — {best.average_response_ms:.2f} ms average response.")

    left, right = st.columns(2)
    with left:
        fig = px.line(alpha_summary, x="alpha", y="average_response_ms", markers=True,
                      labels={"alpha": "Alpha", "average_response_ms": "Average response (ms)"},
                      title="Response time versus alpha")
        fig.update_layout(height=370)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        fig = px.line(alpha_summary, x="alpha", y="average_queue_wait_ms", markers=True,
                      labels={"alpha": "Alpha", "average_queue_wait_ms": "Average queue wait (ms)"},
                      title="Queue waiting time versus alpha")
        fig.update_layout(height=370)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Alpha sensitivity by scenario")
    scenario_alpha = frame.groupby(["network_scenario", "traffic_scenario", "alpha"], as_index=False)["average_response_ms"].mean()
    scenario_alpha["scenario"] = scenario_alpha.network_scenario.str.title() + " network / " + scenario_alpha.traffic_scenario.str.title() + " traffic"
    fig = px.line(scenario_alpha, x="alpha", y="average_response_ms", color="scenario", markers=True,
                  labels={"alpha": "Alpha", "average_response_ms": "Average response (ms)", "scenario": "Scenario"})
    fig.update_layout(height=440)
    st.plotly_chart(fig, use_container_width=True)

    best_by_scenario = best_alpha_by_scenario(frame)
    st.subheader("Best alpha for each network / traffic combination")
    st.dataframe(best_by_scenario.style.format({"best_alpha": "{:.2f}", "best_average_response_ms": "{:.2f} ms"}),
                 use_container_width=True, hide_index=True)
    st.caption("The best alpha is selected by minimum mean response time among the tested values. It is not a universal optimum beyond this configuration.")

    st.subheader("All tested alpha values")
    st.dataframe(alpha_summary, use_container_width=True, hide_index=True)


def _render_architecture() -> None:
    st.markdown("## System architecture")
    st.write("One request moves through request generation, routing, network delivery, server queueing and processing, return travel, and metrics collection.")
    from dashboard.charts import request_lifecycle_diagram
    st.plotly_chart(request_lifecycle_diagram(), use_container_width=True, config={"displayModeBar": False})
    st.subheader("Responsibilities")
    responsibilities = pd.DataFrame([
        ["Nirmin", "NetworkModel, RTT matrix, Minimum Latency", "RTT and outbound/return network delays"],
        ["Sasha", "ServerWorkload, FIFO queue, workers, Least Loaded", "Processing capacity, completion prediction and service"],
        ["Saif", "Request generation, Random, Hybrid, experiments", "Traffic traces, routing composition and alpha studies"],
        ["Shared engine", "SimPy orchestration and metrics", "Request lifecycle, event recording and performance summaries"],
    ], columns=["Owner", "Components", "Responsibility"])
    st.dataframe(responsibilities, use_container_width=True, hide_index=True)
    st.subheader("How each router decides")
    for strategy in STRATEGY_ORDER:
        with st.expander(METHODS[strategy]["title"]):
            st.plotly_chart(strategy_diagram(strategy), use_container_width=True, config={"displayModeBar": False})
            st.write(METHODS[strategy]["principle"])


def _run_campaign_ui() -> None:
    st.markdown("## Run a new experiment campaign")
    st.write("The dashboard launches the same integrated campaign runner used from the terminal. Every strategy receives the same generated trace for a given scenario and repetition, with fresh server state for each strategy.")
    st.warning(
        "The current campaign uses demonstration server settings: A=20, B=40, C=30 capacity units/s; "
        "two workers per server; five processing units per request. Confirm team-approved parameters before treating results as final."
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        request_count = st.number_input("Requests per trace", min_value=50, max_value=5000, value=200, step=50)
    with c2:
        repeats = st.number_input("Repetitions", min_value=1, max_value=20, value=10, step=1)
    with c3:
        base_seed = st.number_input("Base random seed", min_value=0, max_value=2_000_000_000, value=42, step=1)

    st.caption("Full matrix: 3 network scenarios × 3 traffic scenarios × selected repetitions. The alpha sweep tests 0, 0.25, 0.5, 0.75 and 1.")
    if st.button("▶ Run experiment campaign", type="primary", use_container_width=True):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = PROJECT_ROOT / "experiments" / "results" / "dashboard_campaigns" / timestamp
        command = [
            sys.executable, "-u", str(CAMPAIGN_SCRIPT),
            "--request-count", str(int(request_count)),
            "--repeats", str(int(repeats)),
            "--base-seed", str(int(base_seed)),
            "--output-dir", str(output_dir),
        ]
        env = os.environ.copy()
        source_path = str(PROJECT_ROOT / "src")
        env["PYTHONPATH"] = source_path + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONUNBUFFERED"] = "1"
        log_placeholder = st.empty()
        lines: list[str] = []
        process = None
        try:
            with st.status("Running the integrated Mini CDN campaign…", expanded=True) as status:
                st.code(" ".join(command), language="powershell")
                process = subprocess.Popen(
                    command, cwd=PROJECT_ROOT, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                )
                assert process.stdout is not None
                for line in iter(process.stdout.readline, ""):
                    lines.append(line.rstrip())
                    log_placeholder.code("\n".join(lines[-24:]), language="text")
                return_code = process.wait()
                if return_code == 0:
                    status.update(label="Experiment campaign completed", state="complete", expanded=False)
                    st.session_state["active_results_dir"] = str(output_dir)
                    st.success(f"Results saved to `{output_dir.relative_to(PROJECT_ROOT)}`. The dashboard will load this campaign.")
                else:
                    status.update(label="Experiment campaign failed", state="error", expanded=True)
                    st.error(f"Campaign exited with code {return_code}. Review the terminal output above.")
        except OSError as error:
            st.error(f"Could not start the experiment process: {error}")
        if lines:
            st.session_state["last_campaign_log"] = "\n".join(lines)
        if process is not None and process.returncode == 0:
            st.rerun()

    st.divider()
    left, right = st.columns(2)
    with left:
        st.markdown("**Load the bundled ten-repetition campaign**")
        if st.button("Use bundled reference results", use_container_width=True):
            st.session_state["active_results_dir"] = str(DEFAULT_RESULTS)
            st.rerun()
    with right:
        active = Path(st.session_state.get("active_results_dir", str(DEFAULT_RESULTS)))
        st.markdown("**Current results source**")
        st.code(str(active.relative_to(PROJECT_ROOT) if active.is_relative_to(PROJECT_ROOT) else active), language="text")


def _render_data(data) -> None:
    st.markdown("## Campaign data and validation")
    v = data.validation
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Strategy rows", f"{v['strategy_rows']:,}")
    c2.metric("Alpha rows", f"{v['alpha_rows']:,}")
    c3.metric("Duplicate strategy keys", str(v["duplicate_strategy_keys"]))
    c4.metric("Duplicate alpha keys", str(v["duplicate_alpha_keys"]))
    if v["all_requests_completed"]:
        st.success("All requests in both result datasets completed: zero failures and zero unserved requests.")
    else:
        st.error("The loaded campaign contains failed or unserved requests. Review raw CSV data before interpreting performance.")
    for warning in v["warnings"]:
        st.warning(warning)
    st.write(f"**Results directory:** `{data.directory}`")

    files = {
        "Strategy runs": data.directory / "strategy_runs.csv",
        "Strategy summary": data.directory / "strategy_summary.csv",
        "Hybrid alpha runs": data.directory / "hybrid_alpha_runs.csv",
        "Hybrid alpha summary": data.directory / "hybrid_alpha_summary.csv",
    }
    selected_file = st.selectbox("Inspect result file", list(files))
    path = files[selected_file]
    frame = pd.read_csv(path)
    st.dataframe(frame, use_container_width=True, hide_index=True)
    st.download_button(
        f"Download {path.name}", data=path.read_bytes(), file_name=path.name,
        mime="text/csv", use_container_width=True,
    )


def main() -> None:
    st.markdown(
        "<div class='hero'><h1>🌐 Mini CDN Control Center</h1>"
        "<p>Interactive simulation analysis · routing strategies · traffic experiments · Hybrid alpha</p></div>",
        unsafe_allow_html=True,
    )
    active_directory = Path(st.session_state.get("active_results_dir", str(DEFAULT_RESULTS)))
    if not active_directory.exists():
        active_directory = DEFAULT_RESULTS
    try:
        data = _load_data(str(active_directory), _mtime_stamp(active_directory))
    except Exception as error:
        st.error(f"Could not load campaign data: {error}")
        st.info("Run a campaign from the Run experiments page or restore the bundled final_campaign CSV files.")
        st.stop()

    with st.sidebar:
        st.markdown("# Mini CDN")
        st.caption("Simulation and analytics dashboard")
        page = st.radio(
            "Navigate", ["Overview", "Strategy analysis", "Strategy comparison", "Hybrid alpha lab", "Architecture", "Run experiments & data"],
        )
        st.divider()
        st.markdown("### Scenario filters")
        network_options = ["All"] + sorted(data.strategy_runs.network_scenario.unique().tolist())
        traffic_options = ["All"] + sorted(data.strategy_runs.traffic_scenario.unique().tolist())
        network = st.selectbox("Network delay", network_options)
        traffic = st.selectbox("Traffic intensity", traffic_options)
        st.divider()
        st.caption("Bundled reference campaign")
        st.write(f"{data.validation['repetition_count']} repetitions · {data.validation['strategy_rows']} strategy observations")
        st.caption("Demonstration configuration — confirm team-approved capacities and processing units before final reporting.")

    if page == "Overview":
        _render_overview(data)
    elif page == "Strategy analysis":
        _render_methods(data, network, traffic)
    elif page == "Strategy comparison":
        _render_comparison(data, network, traffic)
    elif page == "Hybrid alpha lab":
        _render_alpha(data, network, traffic)
    elif page == "Architecture":
        _render_architecture()
    else:
        _run_campaign_ui()
        _render_data(data)

    st.divider()
    st.caption(
        "Methodology: run-level observations are averaged across the selected scenarios. "
        "P95 is the mean of each run's P95, not a pooled request-level percentile. "
        "The current dataset uses demonstration server capacities and processing units."
    )


if __name__ == "__main__":
    main()
