# GPU Health Monitoring and Remediation Lab
[![CI](https://github.com/creationsoftre/gpu-health-monitoring-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/creationsoftre/gpu-health-monitoring-lab/actions/workflows/ci.yml)

# GPU Health Monitoring and Remediation Lab

## Overview

This project is a small-scale GPU infrastructure reliability lab built on a Windows 11 machine with WSL 2, Docker, and an NVIDIA RTX 3060 Ti.

The lab monitors GPU telemetry, stores metrics in Prometheus, visualizes the system in Grafana, routes alerts through Alertmanager, and uses a Python remediator service to record incidents and simulate node remediation.

## Project Goal

The goal of this project is to model a production-style GPU operations workflow:

```text
Observe → Detect → Alert → Route → Record → Remediate → Validate → Recover
```

This project simulates how an infrastructure team might identify, diagnose, and remediate unhealthy GPU assets in a larger AI infrastructure environment.

## Architecture

```text
RTX 3060 Ti
  ↓
GPU Exporter
  ↓
Prometheus
  ├── Stores GPU metrics
  ├── Evaluates alert rules
  ├── Scrapes remediator metrics
  └── Sends alerts to Alertmanager
        ↓
    Alertmanager
        ↓
    Remediator Webhook
        ├── Writes incident JSON files
        ├── Updates node-status.json
        └── Exposes remediation metrics
              ↓
          Prometheus
              ↓
          Grafana
```

## Technologies Used

* Windows 11
* WSL 2 Ubuntu
* Docker Desktop
* NVIDIA CUDA container support
* Python
* Flask
* Prometheus
* Grafana
* Alertmanager
* GitHub

## Main Components

### GPU Exporter

The GPU exporter collects GPU telemetry using `nvidia-smi` and exposes metrics at:

```text
http://localhost:9400/metrics
```

Example metrics:

```text
gpu_temperature_celsius
gpu_utilization_percent
gpu_memory_used_megabytes
gpu_memory_total_megabytes
gpu_power_draw_watts
gpu_exporter_up
```

### Prometheus

Prometheus scrapes metrics from the GPU exporter and remediator.

Prometheus UI:

```text
http://localhost:9090
```

Prometheus also evaluates alert rules for GPU and telemetry health.

### Grafana

Grafana visualizes GPU metrics and alert status.

Grafana UI:

```text
http://localhost:3000
```

Dashboard panels include:

* GPU temperature heatmap
* GPU utilization stat graph
* GPU memory usage gauge
* GPU power usage
* Warning alerts
* Critical alerts
* GPU exporter down alerts
* Node remediation status
* Incident counts

### Alertmanager

Alertmanager receives firing and resolved alerts from Prometheus.

Alertmanager UI:

```text
http://localhost:9093
```

### Remediator

The remediator is a Python Flask webhook service that receives alerts from Alertmanager.

It writes:

```text
incidents/
state/node-status.json
```

It also exposes metrics at:

```text
http://localhost:5001/metrics
```

Example remediator metrics:

```text
remediator_node_status
remediator_incidents_total
remediator_last_action_timestamp_seconds
```

## Remediation States

```text
0 = HEALTHY
1 = DEGRADED
2 = QUARANTINED
3 = VALIDATING
```

## Alert-to-Action Mapping

| Alert                      | Action                           | Status               |
| -------------------------- | -------------------------------- | -------------------- |
| GPUExporterDown            | MARK_TELEMETRY_DOWN              | DEGRADED             |
| GPUMetricsMissing          | QUARANTINE_NODE                  | QUARANTINED          |
| GPUHighTemperatureWarning  | MARK_DEGRADED                    | DEGRADED             |
| GPUHighTemperatureCritical | QUARANTINE_NODE                  | QUARANTINED          |
| GPUMemoryUsageHigh         | MARK_DEGRADED                    | DEGRADED             |
| GPUMemoryUsageCritical     | QUARANTINE_NODE                  | QUARANTINED          |
| Resolved alert             | VALIDATE_RECOVERY / RESTORE_NODE | VALIDATING → HEALTHY |

## Run the Project

From the project root:

```bash
docker compose up -d --build
```

Check containers:

```bash
docker compose ps
```

## Test GPU Workload

Run the CUDA sample:

```bash
docker run --rm -it --gpus all \
  nvcr.io/nvidia/k8s/cuda-sample:nbody \
  nbody -gpu -benchmark
```

## Test Alert and Remediation Flow

Stop the GPU exporter:

```bash
docker compose stop gpu-exporter
```

Wait 30–60 seconds.

Check node status:

```bash
cat state/node-status.json
```

Check incident logs:

```bash
ls -la incidents
```

Restart the exporter:

```bash
docker compose up -d gpu-exporter
```

The node status should eventually return to `HEALTHY`.

## Useful URLs

| Service              | URL                           |
| -------------------- | ----------------------------- |
| GPU Exporter Metrics | http://localhost:9400/metrics |
| Prometheus           | http://localhost:9090         |
| Prometheus Targets   | http://localhost:9090/targets |
| Prometheus Alerts    | http://localhost:9090/alerts  |
| Grafana              | http://localhost:3000         |
| Alertmanager         | http://localhost:9093         |
| Remediator Health    | http://localhost:5001/healthz |
| Remediator Status    | http://localhost:5001/status  |
| Remediator Metrics   | http://localhost:5001/metrics |

## What This Project Demonstrates

This project demonstrates:

* GPU telemetry collection
* Prometheus metric scraping
* Grafana dashboard visualization
* Alert rule creation
* Alertmanager routing
* Webhook-based remediation
* Incident logging
* Simulated GPU node quarantine
* Recovery validation
* Remediation metrics

## Portfolio Summary

Built a GPU health monitoring and remediation lab using Docker, Prometheus, Grafana, Alertmanager, and Python to monitor RTX 3060 Ti telemetry, detect degraded GPU conditions, route alerts, generate incident records, and simulate node quarantine, validation, and recovery workflows.

## Common Commands

| Command | Purpose |
|---|---|
| `make up` | Build and start the full stack |
| `make down` | Stop the stack |
| `make logs` | Follow logs for all services |
| `make ps` | Show container status |
| `make test-alert` | Stop the GPU exporter to trigger alerts |
| `make recover` | Restart the GPU exporter |
| `make status` | Show current node remediation status |
| `make incidents` | Show recent incident files |
| `make clean` | Stop stack and remove runtime data |
