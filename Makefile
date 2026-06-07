.PHONY: up down restart build logs ps status incidents test-alert recover clean prometheus-reload alertmanager-reload remediator-rebuild

up:
	docker compose up -d --build

down:
	docker compose down

restart:
	docker compose down
	docker compose up -d

build:
	docker compose build

logs:
	docker compose logs -f

ps:
	docker compose ps

status:
	@cat state/node-status.json || echo "No node status file found yet."

incidents:
	@ls -lt incidents | head -n 10

test-alert:
	docker compose stop gpu-exporter
	@echo "GPU exporter stopped. Wait 30-60 seconds, then check Prometheus, Alertmanager, Grafana, and state/node-status.json."

recover:
	docker compose up -d gpu-exporter
	@echo "GPU exporter restarted. Wait 30-60 seconds for alerts to resolve."

clean:
	docker compose down -v
	rm -f incidents/*.json
	rm -f state/*.json

prometheus-reload:
	docker compose up -d --force-recreate prometheus

alertmanager-reload:
	docker compose up -d --force-recreate alertmanager

remediator-rebuild:
	docker compose build --no-cache remediator
	docker compose up -d remediator

simulate-failure:
	touch state/simulate_failure
	@echo "Simulation enabled. GPU exporter will report degraded GPU health."

clear-simulation:
	rm -f state/simulate_failure
	@echo "Simulation cleared. GPU exporter will return to real GPU telemetry."

simulation-status:
	@if [ -f state/simulate_failure ]; then echo "Simulation is ON"; else echo "Simulation is OFF"; fi