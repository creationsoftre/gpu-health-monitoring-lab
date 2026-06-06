import csv
import io
import math
import subprocess
import time

from prometheus_client import Gauge, start_http_server


PORT = 9400
COLLECTION_INTERVAL_SECONDS = 5

# Prometheus metric names should include units where appropriate.
gpu_temperature = Gauge(
    "gpu_temperature_celsius",
    "Current GPU temperature in Celsius",
    ["gpu_name", "gpu_uuid"],
)

gpu_utilization = Gauge(
    "gpu_utilization_percent",
    "Current GPU utilization percentage",
    ["gpu_name", "gpu_uuid"],
)

gpu_memory_used = Gauge(
    "gpu_memory_used_megabytes",
    "Current GPU memory usage in megabytes",
    ["gpu_name", "gpu_uuid"],
)

gpu_memory_total = Gauge(
    "gpu_memory_total_megabytes",
    "Total GPU memory in megabytes",
    ["gpu_name", "gpu_uuid"],
)

gpu_power_draw = Gauge(
    "gpu_power_draw_watts",
    "Current GPU power draw in watts",
    ["gpu_name", "gpu_uuid"],
)

gpu_exporter_up = Gauge(
    "gpu_exporter_up",
    "Whether the exporter successfully collected GPU metrics",
)


def parse_number(value: str) -> float:
    # Convert an nvidia-smi value into a number Prometheus can store.
    cleaned = value.strip()

    if cleaned in {"", "N/A", "[Not Supported]"}:
        return math.nan

    return float(cleaned)


def collect_gpu_metrics() -> None:
    fields = [
        "name",
        "uuid",
        "temperature.gpu",
        "utilization.gpu",
        "memory.used",
        "memory.total",
        "power.draw",
    ]

    command = [
        "nvidia-smi",
        f"--query-gpu={','.join(fields)}",
        "--format=csv,noheader,nounits",
    ]

    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )

    rows = csv.reader(io.StringIO(result.stdout))

    for row in rows:
        if len(row) != len(fields):
            continue

        gpu_name = row[0].strip()
        gpu_uuid = row[1].strip()
        labels = (gpu_name, gpu_uuid)

        gpu_temperature.labels(*labels).set(parse_number(row[2]))
        gpu_utilization.labels(*labels).set(parse_number(row[3]))
        gpu_memory_used.labels(*labels).set(parse_number(row[4]))
        gpu_memory_total.labels(*labels).set(parse_number(row[5]))
        gpu_power_draw.labels(*labels).set(parse_number(row[6]))

    gpu_exporter_up.set(1)


def main() -> None:
    start_http_server(PORT)
    print(f"GPU exporter listening on port {PORT}", flush=True)

    while True:
        try:
            collect_gpu_metrics()
        except Exception as error:
            gpu_exporter_up.set(0)
            print(f"GPU metric collection failed: {error}", flush=True)

        time.sleep(COLLECTION_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()