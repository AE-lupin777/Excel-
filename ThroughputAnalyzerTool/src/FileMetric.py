import json
import re

from pathlib import Path
from datetime import datetime


ROOT = Path(__file__).resolve().parent.parent

INPUT_DIR = ROOT / "input"


class FileMetric:
    def __init__(
        self,
        test_dir
    ):
        self.test_dir = test_dir

    def find_test_dir(
        self
    ):

        tests = [
            p
            for p
            in INPUT_DIR.iterdir()
            if p.is_dir()
        ]

        if not tests:
            raise Exception(
                "input配下にTestIDフォルダがありません。"
            )

        return tests[0]

    def find_sender_log(
        self,
        test_dir
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

    def find_sender_after_records_json(
            self,
            test_dir
        ):

            sender_dir = (
                test_dir /
                "sender"
            )

            snapshots = sorted(
                [
                    p
                    for p
                    in sender_dir.iterdir()
                    if (
                        p.is_dir()
                        and
                        p.name.endswith(
                            "_Sender"
                        )
                    )
                ],
                key=lambda x: x.name
            )

            if len(snapshots) < 2:
                raise Exception(
                    "Sender Snapshotが2つ以上必要です。"
                )

            records_json = (
                snapshots[-1]
                / "records.json"
            )

            return records_json

    def find_sender_before_records_json(
            self,
            test_dir
        ):

            sender_dir = (
                test_dir /
                "sender"
            )

            snapshots = sorted(
                [
                    p
                    for p
                    in sender_dir.iterdir()
                    if (
                        p.is_dir()
                        and
                        p.name.endswith(
                            "_Sender"
                        )
                    )
                ],
                key=lambda x: x.name
            )

            if len(snapshots) < 2:
                raise Exception(
                    "Sender Snapshotが2つ以上必要です。"
                )

            records_json = (
                snapshots[-2]
                / "records.json"
            )

            return records_json

    def find_receiver_log(
        self,
        test_dir
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
        self,
        test_dir
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
            key=lambda x: x.name
        )

        if len(snapshots) < 2:
            raise Exception(
                "Receiver Snapshotが2つ以上必要です。"
            )

        records_json = (
            snapshots[-1]
            / "records.json"
        )

        return records_json

    def find_receiver_before_records_json(
            self,
            test_dir
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
                key=lambda x: x.name
            )

            if len(snapshots) < 2:
                raise Exception(
                    "Receiver Snapshotが2つ以上必要です。"
                )

            records_json = (
                snapshots[-2]
                / "records.json"
            )

            return records_json

    

    def parse_sender_times(
        self,
        sender_log
    ):

        result = {}

        pattern = re.compile(
            r"^(.*?) \[INF\] Sending ([A-F0-9]+)"
        )

        with open(
            sender_log,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            for line in f:

                match = pattern.search(
                    line
                )

                if not match:
                    continue

                timestamp = (
                    match.group(1)
                    .strip()
                )

                file_id = (
                    match.group(2)
                    .strip()
                )

                result[file_id] = (
                    timestamp
                )

        return result

    def parse_receiver_times(
        self,
        receiver_log
    ):

        result = {}

        pattern = re.compile(
            r"^(.*?) \[INF\] Receiver durably stored ([A-F0-9]+)"
        )

        with open(
            receiver_log,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            for line in f:

                match = pattern.search(
                    line
                )

                if not match:
                    continue

                timestamp = (
                    match.group(1)
                    .strip()
                )

                file_id = (
                    match.group(2)
                    .strip()
                )

                result[file_id] = (
                    timestamp
                )

        return result

    def to_datetime(
        self,
        value
    ):

        value = value.replace(
            " +09:00",
            "+09:00"
        )

        value = value.replace(
            " +00:00",
            "+00:00"
        )

        return datetime.fromisoformat(
            value
        )

    def get_file_type(
        self,
        file_name
    ):

        name = file_name.lower()

        if name.endswith(
            ".csv"
        ):
            return "SAMPLING"

        if name.endswith(
            ".evt"
        ):
            return "EVENT"

        if name.endswith(
            ".log"
        ):
            return "PROCESS"

        return "UNKNOWN"

    def analyze(
        self
    ):

        test_dir = (
            self.test_dir
        )

        sender_log = (
            self.find_sender_log(
                test_dir
            )
        )

        receiver_log = (
            self.find_receiver_log(
                test_dir
            )
        )

        before_records_json = (
            self.find_receiver_before_records_json(
                test_dir
            )
        )

        after_records_json = (
            self.find_receiver_after_records_json(
                test_dir
            )
        )

        records_json = (
            self.find_receiver_after_records_json(
                test_dir
            )
        )

        sender_times = (
            self.parse_sender_times(
                sender_log
            )
        )

        receiver_times = (
            self.parse_receiver_times(
                receiver_log
            )
        )

        with open(
            before_records_json,
            "r",
            encoding="utf-8-sig"
        ) as f:

            before_records = json.load(f)

        before_ids = {
            r.get(
                "fileId"
            )
            for r in before_records
        }

        with open(
            records_json,
            "r",
            encoding="utf-8-sig"
        ) as f:

            records = json.load(f)

        target_file_ids = set()

        for record in records:

            file_id = record.get(
                "fileId"
            )

            if file_id not in before_ids:

                target_file_ids.add(
                    file_id
                )

        result = []

        for record in records:

            file_name = (
                record.get(
                    "fileName",
                    ""
                )
            )

            file_id = record.get(
                "fileId"
            )

            if (
                file_id
                not in target_file_ids
            ):
                continue

            send_time = (
                sender_times.get(
                    file_id
                )
            )

            if file_id in before_ids:

                print(
                    "SKIP",
                    file_id
                )

                continue

            send_time = (
                sender_times.get(
                    file_id
                )
            )

            receive_time = (
                receiver_times.get(
                    file_id
                )
            )

            if receive_time is None:
                continue

            duration_ms = None
            throughput_kbps = None
            throughput_mbps = None

            if (
                send_time
                and
                receive_time
            ):

                start_dt = (
                    self.to_datetime(
                        send_time
                    )
                )

                end_dt = (
                    self.to_datetime(
                        receive_time
                    )
                )

                duration_ms = (
                    end_dt
                    - start_dt
                ).total_seconds() * 1000

                if duration_ms > 0:

                    throughput_kbps = (
                        (
                            record.get(
                                "fileSize",
                                0
                            )
                            / 1024
                        )
                        /
                        (
                            duration_ms
                            / 1000
                        )
                    )

                    throughput_mbps = (
                        throughput_kbps
                        / 1024
                    )

            result.append(
                {
                    "FileId":
                        file_id,
                    "FileName":
                        file_name,
                    "FileType":
                        self.get_file_type(
                            file_name
                        ),
                    "FileSizeBytes":
                        record.get(
                            "fileSize",
                            0
                        ),
                    "FileSizeKB":
                        (
                            record.get(
                                "fileSize",
                                0
                            )
                            / 1024
                        ),
                    "SendTime":
                        send_time,
                    "ReceiveTime":
                        receive_time,
                    "DurationMs":
                        duration_ms,
                    "ThroughputKBps":
                        throughput_kbps,
                    "ThroughputMBps":
                        throughput_mbps
                }
            )

        return result


def main():

    metric = FileMetric()

    result = metric.analyze()

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()