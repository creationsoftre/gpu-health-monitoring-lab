from datetime import datetime, timezone
from pathlib import Path
import json
import time

from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST


app = Flask(__name__)

STATE_DIR = Path("/state")
INCIDENT_DIR = Path("/incidents")

STATE_DIR.mkdir(parents=True, exist_ok=True)
INCIDENT_DIR.mkdir(parents=True, exist_ok=True)

NODE_NAME = "windows11-rtx3060ti-lab"


# -----------------------------
# Prometheus metrics
# -----------------------------

incidents_total = Counter(
    "remediator_incidents_total",
    "Total number of incidents processed by the remediator",
    ["alertname", "severity", "status", "action"],
)

node_status_gauge = Gauge(
    "remediator_node_status",
    "Current simulated node status. 0 healthy, 1 degraded, 2 quarantined, 3 validating",
    ["node"],
)

last_action_timestamp = Gauge(
    "remediator_last_action_timestamp_seconds",
    "Unix timestamp of the last remediation action",
    ["node", "action"],
)


ALERT_PRIORITY = {
    "GPUHighTemperatureCritical": 100,
    "GPUMemoryUsageCritical": 90,
    "GPUMetricsMissing": 80,
    "GPUDegraded": 70,
    "GPUHighTemperatureWarning": 60,
    "GPUMemoryUsageHigh": 50,
    "GPUExporterDown": 40,
}


STATUS_VALUE = {
    "HEALTHY": 0,
    "DEGRADED": 1,
    "QUARANTINED": 2,
    "VALIDATING": 3,
}


# -----------------------------
# Helper functions
# -----------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def unix_now() -> float:
    return time.time()


def get_alert_name(alert: dict) -> str:
    return alert.get("labels", {}).get("alertname", "UnknownAlert")


def get_alert_severity(alert: dict) -> str:
    return alert.get("labels", {}).get("severity", "unknown")


def get_alert_summary(alert: dict) -> str:
    return alert.get("annotations", {}).get("summary", "")


def get_alert_priority(alert: dict) -> int:
    alertname = get_alert_name(alert)
    severity = get_alert_severity(alert)

    if alertname in ALERT_PRIORITY:
        return ALERT_PRIORITY[alertname]

    if severity == "critical":
        return 75

    if severity == "warning":
        return 45

    return 10


def decide_action(alertname: str, severity: str, alertmanager_status: str) -> tuple[str, str, str]:
    """
    Returns:
      node_status, action, reason
    """

    if alertmanager_status == "resolved":
        return (
            "VALIDATING",
            "VALIDATE_RECOVERY",
            f"Alert resolved: {alertname}. Node moved to validation state.",
        )

    if alertname == "GPUExporterDown":
        return (
            "DEGRADED",
            "MARK_TELEMETRY_DOWN",
            "Prometheus cannot scrape the GPU exporter.",
        )

    if alertname == "GPUMetricsMissing":
        return (
            "QUARANTINED",
            "QUARANTINE_NODE",
            "GPU metrics are missing.",
        )

    if alertname == "GPUHighTemperatureWarning":
        return (
            "DEGRADED",
            "MARK_DEGRADED",
            "GPU temperature is above warning threshold.",
        )

    if alertname == "GPUHighTemperatureCritical":
        return (
            "QUARANTINED",
            "QUARANTINE_NODE",
            "GPU temperature is above critical threshold.",
        )

    if alertname == "GPUMemoryUsageHigh":
        return (
            "DEGRADED",
            "MARK_DEGRADED",
            "GPU memory usage is above warning threshold.",
        )

    if alertname == "GPUMemoryUsageCritical":
        return (
            "QUARANTINED",
            "QUARANTINE_NODE",
            "GPU memory usage is above critical threshold.",
        )

    if alertname == "GPUDegraded":
        return (
            "QUARANTINED",
            "QUARANTINE_NODE",
            "GPU exporter reported degraded health status.",
        )

    if severity == "critical":
        return (
            "QUARANTINED",
            "QUARANTINE_NODE",
            f"Critical alert received: {alertname}.",
        )

    if severity == "warning":
        return (
            "DEGRADED",
            "MARK_DEGRADED",
            f"Warning alert received: {alertname}.",
        )

    return (
        "DEGRADED",
        "RECORD_UNKNOWN_ALERT",
        f"Unknown alert received: {alertname}.",
    )


def write_node_status(
    status: str,
    reason: str,
    last_alert: str,
    last_action: str,
    severity: str,
) -> dict:
    payload = {
        "node": NODE_NAME,
        "status": status,
        "reason": reason,
        "last_alert": last_alert,
        "last_action": last_action,
        "severity": severity,
        "updated_at": utc_now(),
        "note": (
            "This is simulated remediation. In a real Kubernetes GPU cluster, "
            "this action could cordon, taint, drain, or validate a GPU node."
        ),
    }

    (STATE_DIR / "node-status.json").write_text(json.dumps(payload, indent=2))

    node_status_gauge.labels(NODE_NAME).set(STATUS_VALUE.get(status, -1))
    last_action_timestamp.labels(NODE_NAME, last_action).set(unix_now())

    return payload


def mark_healthy_after_validation(last_alert: str, severity: str) -> dict:
    write_node_status(
        status="VALIDATING",
        reason=f"Alert resolved: {last_alert}. Validating recovery.",
        last_alert=last_alert,
        last_action="VALIDATE_RECOVERY",
        severity=severity,
    )

    time.sleep(2)

    healthy = write_node_status(
        status="HEALTHY",
        reason="Recovery validation completed successfully.",
        last_alert=last_alert,
        last_action="RESTORE_NODE",
        severity=severity,
    )

    return healthy


def write_incident_record(
    alertmanager_status: str,
    alert: dict,
    action: str,
    node_status: str,
    reason: str,
) -> str:
    alertname = get_alert_name(alert)
    severity = get_alert_severity(alert)

    incident = {
        "received_at": utc_now(),
        "node": NODE_NAME,
        "alertmanager_status": alertmanager_status,
        "alertname": alertname,
        "severity": severity,
        "action": action,
        "node_status": node_status,
        "reason": reason,
        "summary": get_alert_summary(alert),
        "labels": alert.get("labels", {}),
        "annotations": alert.get("annotations", {}),
        "startsAt": alert.get("startsAt"),
        "endsAt": alert.get("endsAt"),
    }

    filename = f"incident-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{alertname}.json"
    (INCIDENT_DIR / filename).write_text(json.dumps(incident, indent=2))

    incidents_total.labels(
        alertname=alertname,
        severity=severity,
        status=alertmanager_status,
        action=action,
    ).inc()

    print(json.dumps(incident), flush=True)

    return filename


# -----------------------------
# Routes
# -----------------------------

@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.get("/status")
def status():
    status_file = STATE_DIR / "node-status.json"

    if not status_file.exists():
        payload = write_node_status(
            status="HEALTHY",
            reason="Remediator initialized.",
            last_alert="None",
            last_action="INITIALIZE",
            severity="none",
        )
        return jsonify(payload)

    return app.response_class(
        status_file.read_text(),
        mimetype="application/json",
    )


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.post("/alerts")
def alerts():
    payload = request.get_json(force=True)

    alertmanager_status = payload.get("status", "unknown")
    alerts_list = payload.get("alerts", [])

    if not alerts_list:
        return jsonify(
            {
                "accepted": True,
                "alertmanager_status": alertmanager_status,
                "primary_alert": None,
                "incident_files": [],
                "node_status": None,
            }
        )

    alerts_list = sorted(
        alerts_list,
        key=get_alert_priority,
        reverse=True,
    )

    primary_alert = alerts_list[0]
    primary_alertname = get_alert_name(primary_alert)
    primary_severity = get_alert_severity(primary_alert)

    primary_node_status, primary_action, primary_reason = decide_action(
        alertname=primary_alertname,
        severity=primary_severity,
        alertmanager_status=alertmanager_status,
    )

    incident_files = []

    for alert in alerts_list:
        alertname = get_alert_name(alert)
        severity = get_alert_severity(alert)

        node_status, action, reason = decide_action(
            alertname=alertname,
            severity=severity,
            alertmanager_status=alertmanager_status,
        )

        if alertmanager_status == "resolved":
            node_status = "HEALTHY"
            action = "RESTORE_NODE"
            reason = "Alert resolved and recovery validation completed successfully."

        incident_file = write_incident_record(
            alertmanager_status=alertmanager_status,
            alert=alert,
            action=action,
            node_status=node_status,
            reason=reason,
        )

        incident_files.append(incident_file)

    if alertmanager_status == "resolved":
        final_status_payload = mark_healthy_after_validation(
            last_alert=primary_alertname,
            severity=primary_severity,
        )
    else:
        final_status_payload = write_node_status(
            status=primary_node_status,
            reason=primary_reason,
            last_alert=primary_alertname,
            last_action=primary_action,
            severity=primary_severity,
        )

    return jsonify(
        {
            "accepted": True,
            "alertmanager_status": alertmanager_status,
            "primary_alert": primary_alertname,
            "incident_files": incident_files,
            "node_status": final_status_payload,
        }
    )


if __name__ == "__main__":
    write_node_status(
        status="HEALTHY",
        reason="Remediator initialized.",
        last_alert="None",
        last_action="INITIALIZE",
        severity="none",
    )

    app.run(host="0.0.0.0", port=5001)