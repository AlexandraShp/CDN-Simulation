# Dashboard contents

The dashboard is the interactive presentation layer for the integrated simulation.

## Overview

Campaign validation, request counts, failures, response-time ranking, run-to-run
variability and a strategy scorecard.

## Strategy analysis

Selectable method deep dives for Random, Minimum Latency, Least Loaded and Hybrid.
Each method has a decision diagram, explanation, strengths, trade-offs, responsibility
owner, metric cards, scenario comparisons and run-level observations.

## Strategy comparison

Interactive selection of response, median, P95, queue wait, network time, throughput
or utilization; grouped comparisons across network/traffic scenarios; and a scatter
plot showing the network-time versus queue-wait trade-off.

## Hybrid alpha lab

Formula explanation, overall alpha response and queue curves, scenario-specific
alpha curves, and best tested alpha by network/traffic condition.

## Architecture

A lifecycle diagram from request generation through routing, network transit, server
queueing, processing, return path and metrics, plus component ownership information.

## Run experiments and data

Launches the project's existing campaign runner with request count, repetitions and
seed controls. Each new campaign is saved to its own timestamped directory. The page
also supports inspecting and downloading the result CSVs.
