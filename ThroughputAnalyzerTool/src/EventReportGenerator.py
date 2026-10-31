import json
from pathlib import Path

from EventExtractor import EventExtractor

import sys

ROOT = Path(__file__).resolve().parent.parent

INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"

OUTPUT_DIR.mkdir(
    exist_ok=True
)

def find_sender_log(
    test_dir: Path
):

    sender_dir = (
        test_dir /
        "sender"
    )

    logs = sorted(
        sender_dir.rglob(
            "ULAgent.Sender*.log"
        )
    )

    if not logs:
        raise Exception(
            "Sender Log が見つかりません。"
        )

    return logs[0]


def find_receiver_log(
    test_dir: Path
):

    receiver_dir = (
        test_dir /
        "receiver"
    )

    logs = sorted(
        receiver_dir.rglob(
            "ULAgent.Receiver*.log"
        )
    )

    if not logs:
        raise Exception(
            "Receiver Log が見つかりません。"
        )

    return logs[0]


def find_receiver_after_records_json(
    test_dir: Path
):

    receiver_dir = (
        test_dir /
        "receiver"
    )

    snapshots = sorted(
        [
            p
            for p
            in receiver_dir.iterdir()
            if (
                p.is_dir()
                and
                p.name.endswith(
                    "_Receiver"
                )
            )
        ],
        key=lambda x:
            x.name
    )

    if len(snapshots) < 2:
        raise Exception(
            "Receiver Snapshotが2つ以上必要です。"
        )

    after_snapshot = snapshots[-1]

    records_json = (
        after_snapshot /
        "records.json"
    )

    if not records_json.exists():
        raise Exception(
            "records.json が見つかりません。"
        )

    return records_json

def find_receiver_before_records_json(
    test_dir: Path
):

    receiver_dir = (
        test_dir /
        "receiver"
    )

    snapshots = sorted(
        [
            p
            for p
            in receiver_dir.iterdir()
            if (
                p.is_dir()
                and
                p.name.endswith(
                    "_Receiver"
                )
            )
        ],
        key=lambda x:
            x.name
    )

    if len(snapshots) < 2:
        raise Exception(
            "Receiver Snapshotが2つ以上必要です。"
        )

    before_snapshot = snapshots[0]

    records_json = (
        before_snapshot /
        "records.json"
    )

    if not records_json.exists():
        raise Exception(
            "records.json が見つかりません。"
        )

    return records_json

def generate_event_report(test_dir):

    test_dir = (
        test_dir
    )

    sender_log = (
        find_sender_log(
            test_dir
        )
    )

    receiver_log = (
        find_receiver_log(
            test_dir
        )
    )

    records_json = (
        find_receiver_after_records_json(
            test_dir
        )
    )

    receiver_before_records_json = (
        find_receiver_before_records_json(
            test_dir
        )
    )

    with open(
        records_json,
        "r",
        encoding="utf-8-sig"
    ) as f:

        records = json.load(f)

    with open(
        receiver_before_records_json,
        "r",
        encoding="utf-8-sig"
    ) as f:

        before_records = json.load(f)

    # target_file_ids = {
    #     record.get(
    #         "fileId"
    #     )
    #     for record in records
    # }

    before_file_ids = {
        record.get(
            "fileId"
        )
        for record in before_records
    }

    target_file_ids = {
        record.get(
            "fileId"
        )
        for record in records
        if record.get(
            "fileId"
        ) not in before_file_ids
    }

    receiver_before_records_json = (
        find_receiver_before_records_json(
            test_dir
        )
    )

    with open(
        receiver_before_records_json,
        "r",
        encoding="utf-8-sig"
    ) as f:

        before_records = json.load(f)

    before_file_ids = {
        record.get("fileId")
        for record in before_records
    }

    target_file_ids = {
        record.get("fileId")
        for record in records
        if record.get("fileId")
        not in before_file_ids
    }



    extractor = (
        EventExtractor()
    )

    events = (
        extractor.extract_all_events(
        sender_log_file=sender_log,
        receiver_log_file=receiver_log,
        records_json_file=records_json,
        target_file_ids=target_file_ids
        )
    )

    report = {
        "TestID":
            test_dir.name,
        "SenderLog":
            str(sender_log),
        "ReceiverLog":
            str(receiver_log),
        "RecordsJson":
            str(records_json),
        "EventCount":
            len(events),
        "Events":
            events
    }

    return report


def write_json(
    report
):

    output_file = (
        OUTPUT_DIR /
        "EventReport.json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            indent=2,
            ensure_ascii=False
        )

    return output_file


def print_report(
    report
):

    print()
    print(
        "===== EVENT REPORT ====="
    )
    print()

    for (
        event_id,
        event
    ) in sorted(
        report[
            "Events"
        ].items()
    ):

        print(
            f"{event_id:10} : "
            f"{event.get('timestamp')}"
        )

    print()
    print(
        f"Event Count : "
        f"{report['EventCount']}"
    )
    print()
    print(
        "========================"
    )
    print()


def main():
    test_dir = Path(
        sys.argv[1]
    )

    report = (
        generate_event_report(
            test_dir
        )
    )

    output_file = (
        write_json(
            report
        )
    )

    print(
        f"Output : {output_file}"
    )


if __name__ == "__main__":
    main()