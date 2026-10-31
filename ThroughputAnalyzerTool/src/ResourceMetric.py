# ResourceMetric.py

import csv
from pathlib import Path


def to_float(value):

    try:
        value = str(value).strip()

        if value == "":
            return 0.0

        return float(value)

    except Exception:
        return 0.0


def calc_avg(values):

    if not values:
        return 0.0

    return round(sum(values) / len(values), 3)


def calc_max(values):

    if not values:
        return 0.0

    return round(max(values), 3)


def find_column(
    headers,
    include_keywords,
    exclude_keywords=None
):

    if exclude_keywords is None:
        exclude_keywords = []

    for idx, col in enumerate(headers):

        col_lower = col.lower()

        if not all(
            keyword.lower() in col_lower
            for keyword in include_keywords
        ):
            continue

        if any(
            keyword.lower() in col_lower
            for keyword in exclude_keywords
        ):
            continue

        return idx

    return None

def collect_values(rows, column_index):

    if column_index is None:
        return []

    result = []

    for row in rows:

        if column_index >= len(row):
            continue

        result.append(
            to_float(row[column_index])
        )

    return result


def collect_network_sum(rows, headers, keyword):

    indexes = []

    for idx, col in enumerate(headers):

        col_lower = col.lower()

        if keyword in col_lower:
            indexes.append(idx)

    result = []

    for row in rows:

        total = 0.0

        for idx in indexes:

            if idx < len(row):
                total += to_float(row[idx])

        result.append(total)

    return result


def load_perfmon_csv(csv_file: Path):

    with open(
        csv_file,
        "r",
        encoding="utf-8-sig"
    ) as f:

        reader = csv.reader(f)

        rows = list(reader)

    headers = rows[0]
    data_rows = rows[1:]

    return headers, data_rows


def analyze_resource(csv_file: Path):

    headers, rows = load_perfmon_csv(
        csv_file
    )

    cpu_total_idx = find_column(
    headers,
    [
        "processor(_total)",
        "% processor time"
    ]
    )

    process_cpu_idx = find_column(
    headers,
    [
        "process(",
        "% processor time"
    ],
    [
        "idle"
    ]
    )

    memory_idx = find_column(
    headers,
    [
        "working set - private"
    ]
    )

    private_bytes_idx = find_column(
    headers,
    [
        "private bytes"
    ]
    )

    disk_read_idx = find_column(
        headers,
        [
            "physicaldisk(_total)",
            "disk read bytes/sec"
        ]
    )

    disk_write_idx = find_column(
    headers,
    [
        "physicaldisk(_total)",
        "disk write bytes/sec"
    ]
    )

    disk_queue_idx = find_column(
    headers,
    [
        "physicaldisk(_total)",
        "avg. disk queue length"
    ]
    )

    cpu_total = collect_values(
        rows,
        cpu_total_idx
    )

    process_cpu = collect_values(
        rows,
        process_cpu_idx
    )

    memory = collect_values(
        rows,
        memory_idx
    )

    private_bytes = collect_values(
        rows,
        private_bytes_idx
    )

    disk_read = collect_values(
        rows,
        disk_read_idx
    )

    disk_write = collect_values(
        rows,
        disk_write_idx
    )

    disk_queue = collect_values(
        rows,
        disk_queue_idx
    )

    network_send = collect_network_sum(
        rows,
        headers,
        r"bytes sent/sec"
    )

    network_recv = collect_network_sum(
        rows,
        headers,
        r"bytes received/sec"
    )

    return {

        "CpuTotalAvg":
            calc_avg(cpu_total),

        "CpuTotalMax":
            calc_max(cpu_total),

        "ProcessCpuAvg":
            calc_avg(process_cpu),

        "ProcessCpuMax":
            calc_max(process_cpu),

        "MemoryPrivateWorkingSetAvg":
            calc_avg(memory),

        "MemoryPrivateWorkingSetMax":
            calc_max(memory),

        "PrivateBytesAvg":
            calc_avg(private_bytes),

        "PrivateBytesMax":
            calc_max(private_bytes),

        "DiskReadBytesAvg":
            calc_avg(disk_read),

        "DiskReadBytesMax":
            calc_max(disk_read),

        "DiskWriteBytesAvg":
            calc_avg(disk_write),

        "DiskWriteBytesMax":
            calc_max(disk_write),

        "DiskQueueAvg":
            calc_avg(disk_queue),

        "DiskQueueMax":
            calc_max(disk_queue),

        "NetworkSendBytesAvg":
            calc_avg(network_send),

        "NetworkSendBytesMax":
            calc_max(network_send),

        "NetworkReceiveBytesAvg":
            calc_avg(network_recv),

        "NetworkReceiveBytesMax":
            calc_max(network_recv),
    }


def analyze_pair(
    sender_csv: Path,
    receiver_csv: Path
):

    return {

        "Sender":
            analyze_resource(
                sender_csv
            ),

        "Receiver":
            analyze_resource(
                receiver_csv
            )
    }
