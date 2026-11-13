# Bundled teammate source snapshots

This workspace includes snapshots of teammate-owned Python modules so the
integrated application is self-contained and can run without separate local
Git branches or extracted repository folders.

## Nirmin snapshot

Source branch/archive inspected: `CDN-Simulation-nirmin-latency`.

Original modules:
- `src/network.py` -> `src/minicdn/integrations/nirmin/network.py`
- `src/strategies/latency.py` -> `src/minicdn/integrations/nirmin/latency.py`
- `experiments/delay_scenarios.py` -> `src/minicdn/integrations/nirmin/delay_scenarios.py`

The implementations are retained. The delay scenario module's import was
changed to a package-relative import so it works inside this workspace.

## Sasha snapshot

Source branch/archive inspected: `CDN-Simulation-Sasha`.

Original modules:
- `src/workload.py` -> `src/minicdn/integrations/sasha/workload.py`
- `src/strategies/load.py` -> `src/minicdn/integrations/sasha/load.py`

The workload implementation is retained. The Least Loaded module's import was
changed from `from src.workload import ServerWorkload` to a package-relative
import (`from .workload import ServerWorkload`) so it can be imported safely
inside the integrated package. Its selection algorithm remains Sasha's.

## Ownership and updates

These are integration snapshots, not a claim that the original teammates'
branches have been modified. The teammates remain the owners of their source
modules. If a teammate changes the corresponding source branch, refresh the
matching snapshot here, review the diff, and run the complete test suite and
integrated demo again. Do not maintain two divergent implementations silently.

## Why snapshots are included

The adapters need concrete Python classes/functions at runtime. Previously,
the scripts dynamically imported them from separately extracted branch
folders, which made the workspace depend on those folders being present on
every developer's computer. Bundling the inspected source snapshots removes
that machine-specific path dependency while preserving clear module ownership.
