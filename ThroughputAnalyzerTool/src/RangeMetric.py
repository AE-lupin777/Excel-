import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from ResourceMetric import (
    load_perfmon_csv,
    to_float
)


ROOT = Path(__file__).resolve().parent.parent

INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"


class RangeMetric:

    def __init__(self, test_dir):
        
        self.test_dir = test_dir
        
        event_file = (
            OUTPUT_DIR /
            "EventReport.json"
        )

        with open(
            event_file,
            "r",
            encoding="utf-8-sig"
        ) as f:

            self.event_report = (
                json.load(f)
            )

    def normalize_datetime(
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

        dt = datetime.fromisoformat(
            value
        )

        if dt.tzinfo is None:

            jst = timezone(
                timedelta(hours=9)
            )

            return dt.replace(
                tzinfo=jst
            ).astimezone(
                timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    def find_test_dir(
            self
        ):

            return self.test_dir

    def find_resource_csvs(
        self
    ):

        # test_dir = (
        #     self.find_test_dir()
        # )

        test_dir = self.find_test_dir()

        csv_files = list(
            test_dir.rglob("*.csv")
        )

        sender_csv = None
        receiver_csv = None

        for csv_file in csv_files:

            name = (
                csv_file.name
                .lower()
            )

            if "sender" in name:
                sender_csv = csv_file

            elif "receiver" in name:
                receiver_csv = csv_file

        if sender_csv is None:
            raise Exception(
                "Sender Resource CSV が見つかりません。"
            )

        if receiver_csv is None:
            raise Exception(
                "Receiver Resource CSV が見つかりません。"
            )

        return (
            sender_csv,
            receiver_csv
        )

    def find_receiver_after_records_json(
        self
    ):

        test_dir = (
            self.find_test_dir()
        )

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

    def get_transfer_metrics(
        self,
        target_date
    ):

        records_json = (
            self.find_receiver_after_records_json()
        )

        with open(
            records_json,
            "r",
            encoding="utf-8-sig"
        ) as f:

            records = json.load(f)

        transfer_file_count = 0
        transfer_size_bytes = 0

        for record in records:

            file_name = (
                record.get(
                    "fileName",
                    ""
                )
            )

            if not file_name.startswith(
                f"{target_date}_"
            ):
                continue

            transfer_file_count += 1

            transfer_size_bytes += int(
                record.get(
                    "fileSize",
                    0
                )
            )

        return (
            transfer_file_count,
            transfer_size_bytes
        )

    def get_event_time(
            self,
            event_id
        ):

            event = (
                self.event_report[
                    "Events"
                ].get(
                    event_id
                )
            )

            if isinstance(
                event,
                list
            ):
                event = (
                    event[0]
                    if event
                    else None
                )

            if event is None:
                raise Exception(
                    f"{event_id} が存在しません。"
                )

            return self.normalize_datetime(
                event["timestamp"]
            )

    def get_events(
            self,
            event_id
        ):

            events = (
                self.event_report[
                    "Events"
                ].get(
                    event_id,
                    []
                )
            )

            if not isinstance(
                events,
                list
            ):
                events = [
                    events
                ]

            return events

    def extract_metrics_from_rows(
            self,
            headers,
            rows
        ):

            count = len(rows)

            if count == 0:
                return {}

            metrics = {}

            for index, header in enumerate(headers):

                values = []

                for row in rows:

                    if index >= len(row):
                        continue

                    try:
                        values.append(
                            to_float(
                                row[index]
                            )
                        )
                    except Exception:
                        pass

                if not values:
                    continue

                name = (
                    header.lower()
                )

                prefix = None

                if (
                    "processor(_total)"
                    in name
                    and
                    "% processor time"
                    in name
                ):
                    prefix = "CpuTotal"

                elif (
                    "private bytes"
                    in name
                ):
                    prefix = "PrivateBytes"

                    values = [
                        v / 1024 / 1024
                        for v in values
                    ]

                elif (
                    "disk read"
                    in name
                ):
                    prefix = "DiskRead"

                    values = [
                        v / 1024
                        for v in values
                    ]

                elif (
                    "disk write"
                    in name
                ):
                    prefix = "DiskWrite"

                    values = [
                        v / 1024
                        for v in values
                    ]

                elif (
                    "network send"
                    in name
                    or "bytes sent"
                    in name
                ):
                    prefix = "NetworkSend"

                    values = [
                        v / 1024
                        for v in values
                    ]

                elif (
                    "network receive"
                    in name
                    or "bytes received"
                    in name
                ):
                    prefix = "NetworkReceive"

                    values = [
                        v / 1024
                        for v in values
                    ]

                if prefix is None:
                    continue

                metrics[prefix + "_Min"] = min(values)

                metrics[prefix + "_Max"] = max(values)

                metrics[prefix + "_Avg"] = (
                    sum(values) / len(values)
                )

            return metrics

    def collect_range_rows(
        self,
        csv_file,
        start_dt,
        end_dt
    ):

        headers, rows = (
            load_perfmon_csv(
                csv_file,
            )
        )

        result_rows = []

        closest_row = None
        closest_diff = None

        for row in rows:

            try:

                row_dt = (
                    self.normalize_datetime(
                        row[0]
                    )
                )

            except Exception:
                continue

            if (
                start_dt
                <= row_dt
                <= end_dt
            ):
                result_rows.append(
                    row
                )

            diff = abs(
                (
                    row_dt
                    - start_dt
                ).total_seconds()
            )

            if (
                closest_diff is None
                or
                diff < closest_diff
            ):
                closest_diff = diff
                closest_row = row

        if (
            not result_rows
            and
            closest_row is not None
        ):
            result_rows.append(
                closest_row
            )

        return (
            headers,
            result_rows
        )

        # result_rows = []

        # for row in rows:

        #     try:

        #         row_dt = (
        #             self.normalize_datetime(
        #                 row[0]
        #             )
        #         )

        #     except Exception:
        #         continue

        #     if (
        #         start_dt
        #         <= row_dt
        #         <= end_dt
        #     ):
        #         result_rows.append(
        #             row
        #         )

        # return (
        #     headers,
        #     result_rows
        # )

    def analyze(
        self,
        start_event_id,
        end_event_id,
        start_event,
        end_event
    ):

        start_dt = (
            self.normalize_datetime(
                start_event["timestamp"]
            )
        )

        end_dt = (
            self.normalize_datetime(
                end_event["timestamp"]
            )
        )    

        (
            sender_csv,
            receiver_csv
        ) = (
            self.find_resource_csvs()
        )

        (
            sender_headers,
            sender_rows
        ) = (
            self.collect_range_rows(
                sender_csv,
                start_dt,
                end_dt
            )
        )

        # デバッグ用
        print(
            "SENDER",
            len(sender_rows)
        )

        (
            receiver_headers,
            receiver_rows
        ) = (
            self.collect_range_rows(
                receiver_csv,
                start_dt,
                end_dt
            )
        )

        # デバッグ用
        print(
            "RECEIVER",
            len(receiver_rows)
        )

        duration_sec = (
            end_dt
            - start_dt
        ).total_seconds()

        if duration_sec < 0:
            duration_sec = None

        return {
            "FileId":
                start_event.get(
                    "fileId",
                    ""
                ),

            "Evidence":
                start_event.get(
                    "evidence",
                    ""
                ),

            "StartEvent":
                start_event_id,

            "EndEvent":
                end_event_id,

            "StartTime":
                start_dt.isoformat(),

            "EndTime":
                end_dt.isoformat(),

            "DurationSec":
                duration_sec,

            "Sender":
                self.extract_metrics_from_rows(
                    sender_headers,
                    sender_rows
                ),

            "RangeId":
                (
                    f"{start_event_id}"
                    f"~"
                    f"{end_event_id}"
                ),

            "Receiver":
                self.extract_metrics_from_rows(
                    receiver_headers,
                    receiver_rows
                )
        }

def main():

    metric = RangeMetric()

    result = metric.analyze(
        "C_START",
        "C_END"
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()