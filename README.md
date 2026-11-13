# Mini CDN — Integrated Simulation and Dashboard

This is the complete, self-contained Mini CDN project workspace. It includes the
three developers' inspected components, the shared SimPy simulation engine,
all four routing strategies, reproducible experiment runners, the uploaded
ten-repetition campaign results, and an interactive Streamlit dashboard.

## What's included

- **Traffic:** Request model, fixed traces and Poisson arrivals.
- **Network:** Bundled snapshot of Nirmin's RTT model, delay scenarios and
  Minimum Latency strategy.
- **Server:** Bundled snapshot of Sasha's multi-worker workload model and
  Least Loaded selector.
- **Routing:** Random, Minimum Latency, Least Loaded and Hybrid.
- **Simulation:** SimPy orchestration, network transit, queue/processing adapter,
  response completion, event recording and performance metrics.
- **Experiments:** Network/traffic scenario campaign and Hybrid alpha sweep.
- **Results:** The ten-repetition campaign uploaded by the user, including all
  four CSV files and campaign metadata.
- **Dashboard:** Interactive overview, per-method analysis, comparison charts,
  alpha sensitivity, architecture diagram, CSV inspection/download and a page
  for launching new experiment campaigns.

Teammate components are included as local source snapshots. Their original
algorithms are retained, and the adapters connect them to the shared contracts.
See `docs/VENDORED_SOURCES.md` for attribution and synchronization guidance.

## 1. Install

Use Python 3.11 or newer for the dashboard. From the project root, run:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,dashboard]"
```

The core simulation supports Python 3.10+, while Streamlit's current documented
support includes Python 3.11–3.15. See the Streamlit installation guidance:
https://docs.streamlit.io/get-started/installation/command-line

## 2. Run tests

```powershell
python -m pytest -v
```

## 3. Run the integrated four-strategy demonstration

```powershell
python examples/run_integrated_demo.py --request-count 100 --arrival-rate 1.5 --seed 42
```

No separate teammate repository folders are required.

## 4. Launch the dashboard

```powershell
python -m streamlit run dashboard/app.py
```

Or double-click `RUN_DASHBOARD.bat` after installing dependencies.

Dashboard pages:

1. **Overview:** campaign health, KPI cards, strategy ranking, distributions and scorecard.
2. **Strategy analysis:** selectable Random, Minimum Latency, Least Loaded and Hybrid deep dives, with decision diagrams and per-scenario results.
3. **Strategy comparison:** interactive metric selection, grouped scenario charts and network-delay versus queue-wait analysis.
4. **Hybrid alpha lab:** alpha curves, scenario-specific sensitivity and best tested alpha by condition.
5. **Architecture:** end-to-end request lifecycle and developer responsibilities.
6. **Run experiments & data:** run new campaigns, inspect CSV files and download results.

See `dashboard/README.md` for dashboard details.

## 5. Run a new experiment campaign from the terminal

```powershell
python experiments/run_experiment_campaign.py --request-count 200 --repeats 10 --base-seed 42
```

The command writes four CSV files into `experiments/results/final_campaign/`.
To preserve the bundled reference campaign, use a new output folder:

```powershell
python experiments/run_experiment_campaign.py --request-count 200 --repeats 10 --base-seed 42 --output-dir experiments/results/my_campaign
```

Campaigns launched from the dashboard are automatically saved into a separate
timestamped directory under `experiments/results/dashboard_campaigns/`.

## 6. Bundled reference campaign

The dashboard initially loads `experiments/results/final_campaign/`, the
uploaded ten-repetition campaign:

- 360 four-strategy observations.
- 450 Hybrid alpha observations.
- 200 requests per trace and 10 repetitions.
- Zero failed requests and zero unserved requests.
- Network multipliers: 1×, 3× and 5×.
- Traffic rates: 2, 12 and 24 requests/second.
- Alpha values: 0, 0.25, 0.50, 0.75 and 1.

The alpha=0.50 observation is shared with the baseline Hybrid run in the main
strategy dataset; do not count it twice when combining the two CSV files.
See `reports/FINAL_EXPERIMENT_ANALYSIS.md` for the detailed summary.

## 7. Important experimental limitation

The reference campaign uses demonstration server settings: Server A=20,
Server B=40 and Server C=30 capacity units/second; two workers per server; and
five processing units per request. The campaign is technically validated, but
these values must be confirmed by the team before describing its results as
final project performance. P95 in the summary report is the mean of run-level
P95 values, not a pooled request-level percentile.

## Project documentation

- `docs/INTEGRATION_GUIDE.md` — local component adapters.
- `docs/SIMULATION_ENGINE_CONTRACT.md` — lifecycle and runtime contracts.
- `docs/VENDORED_SOURCES.md` — teammate snapshot attribution.
- `experiments/FINAL_EXPERIMENT_PLAN.md` — experiment design.
- `reports/FINAL_EXPERIMENT_ANALYSIS.md` — ten-repetition findings.
- `reports/DASHBOARD_CONTENTS.md` — dashboard pages and visualizations.
