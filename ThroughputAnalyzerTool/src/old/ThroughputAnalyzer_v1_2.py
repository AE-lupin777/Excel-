import json
import csv
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent

INPUT_DIR = ROOT / "Input"
OUTPUT_DIR = ROOT / "Output"

OUTPUT_DIR.mkdir(exist_ok=True)


def load_json(path: Path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def find_snapshot_dirs(base_dir: Path, suffix: str):

    dirs = sorted(
        [
            p for p in base_dir.iterdir()
            if p.is_dir() and p.name.endswith(suffix)
        ],
        key=lambda p: p.name
    )

    if len(dirs) < 2:
        raise Exception(
            f"{base_dir} に {suffix} フォルダが2個以上必要です。"
        )

    return dirs[0], dirs[-1]


def sender_stat(folder: Path):

    data = load_json(folder / "all_results.json")
    status = data["status"]

    return {
        "sent": int(status.get("sent", 0)),
        "failed": int(status.get("failed", 0)),
        "skipped": int(status.get("skipped", 0)),
    }


def receiver_stat(folder: Path):

    data = load_json(folder / "all_results.json")
    status = data["status"]

    return {
        "received": int(status.get("received", 0)),
        "registered": int(status.get("registered", 0)),
        "registrationFailed": int(
            status.get("registrationFailed", 0)
        )
    }


def find_receiver_dir(test_dir: Path):

    receiver = test_dir / "receiver"

    if receiver.exists():
        return receiver

    receiver = test_dir / "receiver"

    if receiver.exists():
        return receiver

    raise Exception(
        "receiver/receiver フォルダが見つかりません。"
    )


def load_records_by_fileid(csv_file: Path):

    records = {}

    with open(
        csv_file,
        "r",
        encoding="utf-8-sig"
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            file_id = row.get("fileId")

            if file_id:
                records[file_id] = row

    return records


def get_delta_records(
    receiver_before_dir: Path,
    receiver_after_dir: Path
):

    before_file = receiver_before_dir / "records.csv"
    after_file = receiver_after_dir / "records.csv"

    before_records = load_records_by_fileid(
        before_file
    )

    after_records = load_records_by_fileid(
        after_file
    )

    delta_file_ids = (
        set(after_records.keys())
        - set(before_records.keys())
    )

    delta_records = {}

    for file_id in delta_file_ids:
        delta_records[file_id] = after_records[file_id]

    return delta_records


def calc_file_type_stats(delta_records):

    result = {
        "EventCount": 0,
        "ProcessCount": 0,
        "SamplingCount": 0,
        "EventBytes": 0,
        "ProcessBytes": 0,
        "SamplingBytes": 0,
        "TotalBytes": 0,
    }

    for row in delta_records.values():

        log_type = (
            row.get("logType", "")
            .strip()
            .upper()
        )

        try:
            size = int(
                row.get("fileSize", 0)
            )
        except:
            size = 0

        result["TotalBytes"] += size

        if log_type == "EVENT":

            result["EventCount"] += 1
            result["EventBytes"] += size

        elif log_type == "PROCESS":

            result["ProcessCount"] += 1
            result["ProcessBytes"] += size

        elif log_type == "SAMPLING":

            result["SamplingCount"] += 1
            result["SamplingBytes"] += size

    return result


def parse_log_time(line: str):

    m = re.match(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})",
        line
    )

    if not m:
        return None

    try:
        return datetime.strptime(
            m.group(1),
            "%Y-%m-%d %H:%M:%S.%f"
        )
    except:
        return None


def calc_throughput_duration(
    sender_dir: Path,
    delta_records
):

    target_ids = set(
        x.upper()
        for x in delta_records.keys()
    )

    if not target_ids:
        return 0.0

    first_sending = None
    last_accepted = None

    log_files = list(
        sender_dir.glob("ULAgent.Sender*.log")
    )

    for log_file in log_files:

        with open(
            log_file,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            for line in f:

                upper_line = line.upper()

                matched = False

                for file_id in target_ids:

                    if file_id in upper_line:
                        matched = True
                        break

                if not matched:
                    continue

                ts = parse_log_time(line)

                if ts is None:
                    continue

                if "SENDING" in upper_line:

                    if (
                        first_sending is None
                        or ts < first_sending
                    ):
                        first_sending = ts

                elif (
                    "RECEIVER DURABLY ACCEPTED"
                    in upper_line
                ):

                    if (
                        last_accepted is None
                        or ts > last_accepted
                    ):
                        last_accepted = ts

    if (
        first_sending is None
        or last_accepted is None
    ):
        return 0.0

    return round(
        (
            last_accepted
            - first_sending
        ).total_seconds(),
        3
    )


def write_csv(report):

    out = OUTPUT_DIR / "ThroughputReport.csv"

    with open(
        out,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=report.keys()
        )

        writer.writeheader()
        writer.writerow(report)


def write_json(report):

    out = OUTPUT_DIR / "ThroughputReport.json"

    with open(
        out,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=2
        )


def analyze(test_dir: Path):

    sender_dir = test_dir / "sender"
    receiver_dir = find_receiver_dir(test_dir)

    sender_before, sender_after = \
        find_snapshot_dirs(
            sender_dir,
            "_Sender"
        )

    receiver_before, receiver_after = \
        find_snapshot_dirs(
            receiver_dir,
            "_Receiver"
        )

    sb = sender_stat(sender_before)
    sa = sender_stat(sender_after)

    rb = receiver_stat(receiver_before)
    ra = receiver_stat(receiver_after)

    sent_count = (
        sa["sent"]
        - sb["sent"]
    )

    received_count = (
        ra["received"]
        - rb["received"]
    )

    registered_count = (
        ra["registered"]
        - rb["registered"]
    )

    delta_records = get_delta_records(
        receiver_before,
        receiver_after
    )

    stats = calc_file_type_stats(
        delta_records
    )

    total_bytes = stats["TotalBytes"]

    total_mb = round(
        total_bytes / 1024 / 1024,
        6
    )

    duration_sec = calc_throughput_duration(
        sender_dir,
        delta_records
    )

    if duration_sec > 0:
        files_per_sec = round(
            received_count / duration_sec,
            3
        )

        mb_per_sec = round(
            total_mb / duration_sec,
            3
        )
    else:
        files_per_sec = 0.0
        mb_per_sec = 0.0

    report = {

        "TestID": test_dir.name,

        "SentCount": sent_count,
        "ReceivedCount": received_count,
        "RegisteredCount": registered_count,

        "TotalBytes": total_bytes,
        "TotalMB": total_mb,

        "DurationSec": duration_sec,
        "FilesPerSec": files_per_sec,
        "MBPerSec": mb_per_sec,

        "EventCount":
            stats["EventCount"],

        "ProcessCount":
            stats["ProcessCount"],

        "SamplingCount":
            stats["SamplingCount"],

        "EventBytes":
            stats["EventBytes"],

        "ProcessBytes":
            stats["ProcessBytes"],

        "SamplingBytes":
            stats["SamplingBytes"],
    }

    write_csv(report)
    write_json(report)

    print("===== RESULT =====")

    for k, v in report.items():
        print(
            f"{k:20}: {v}"
        )

    print("==================")


def main():

    tests = [
        p for p in INPUT_DIR.iterdir()
        if p.is_dir()
    ]

    if not tests:
        raise Exception(
            "Input配下にTestIDフォルダがありません。"
        )

    analyze(tests[0])


if __name__ == "__main__":
    main()