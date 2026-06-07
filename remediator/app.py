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

    # Sort alerts so the most important alert controls node-status.json.
    # Incident records will still be written for every alert.
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

    # Write incident files for every alert in the Alertmanager group.
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

    # Update node-status.json only once, based on the highest-priority alert.
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