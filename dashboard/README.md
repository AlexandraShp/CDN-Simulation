# Mini CDN Streamlit Dashboard

The dashboard is part of the integrated Mini CDN workspace. It reads the campaign CSVs produced by `experiments/run_experiment_campaign.py` and can launch new campaigns using that same runner.

## Install

From the project root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,dashboard]"
```

If the project is already installed in the virtual environment, install only the dashboard packages:

```powershell
python -m pip install "streamlit>=1.40,<2" "pandas>=2.2,<4" "plotly>=5.20,<7"
```

## Start the dashboard

From the project root:

```powershell
python -m streamlit run dashboard/app.py
```

Or double-click `RUN_DASHBOARD.bat` after dependencies are installed.

## Pages

- **Overview:** campaign health, KPI cards, strategy ranking and result scorecard.
- **Strategy analysis:** selectable Random, Minimum Latency, Least Loaded and Hybrid pages with decision diagrams, explanations, trade-offs and per-scenario metrics.
- **Strategy comparison:** interactive metric selection, grouped scenario charts and network-time versus queue-wait scatter plot.
- **Hybrid alpha lab:** alpha response curves, queue-wait curves, scenario-specific alpha curves and best-alpha table.
- **Architecture:** end-to-end request lifecycle diagram and component ownership.
- **Run experiments & data:** launches the integrated campaign runner and inspects/downloads the CSV files.

## Data source

The default data source is `experiments/results/final_campaign/`. It contains the uploaded ten-repetition campaign. New dashboard-launched campaigns are stored separately under `experiments/results/dashboard_campaigns/<timestamp>/`, so the reference results are not overwritten.

## Interpretation note

The bundled campaign uses demonstration server capacities (A=20, B=40, C=30 capacity units/s; two workers per server) and five processing units per request. These values must be confirmed by the team before the results are described as final project performance. The dashboard labels them as demonstration settings.

P95 displayed in aggregated comparisons is the mean of each run's P95. It is not a P95 calculated by pooling all request-level samples.
