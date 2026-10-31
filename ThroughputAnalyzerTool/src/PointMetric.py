import json
from pathlib import Path
from datetime import datetime, timezone
from datetime import timezone, timedelta

from tkinter import Tk
from tkinter import filedialog
from pathlib import Path

from ResourceMetric import (
    load_perfmon_csv,
    to_float
)


ROOT = Path(__file__).resolve().parent.parent

INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"


class PointMetric:

    def __init__(self, test_dir):

        self.test_dir = test_dir

        event_file = (
            OUTPUT_DIR /
            "EventReport.json"
        )

        with open(
            event_file,
            "r",
            encoding="utf-8"
        ) as f:

            self.event_report = (
                json.load(f)
            )

    def find_resource_csvs(
        self
    ):

        test_dir = self.test_dir
        
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

    def get_event(
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
                return (
                    event[0]
                    if event
                    else None
                )

            return event

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

    def normalize_datetime(
        self,
        value
    ):
        
        value = value.replace(
            " +09:00", "+09:00"
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

    def find_row_near_timestamp(
        self,
        csv_file,
        event_timestamp
    ):

        headers, rows = (
            load_perfmon_csv(
                csv_file
            )
        )

        if not rows:
            return (
                headers,
                None
            )

        event_dt = (
            self.normalize_datetime(
                event_timestamp
            )
        )

        nearest_row = None
        nearest_diff = None

        for row in rows:

            try:

                sample_dt = (
                    self.normalize_datetime(
                        row[0]
                    )
                )

            except Exception:
                continue

            diff = abs(
                (
                    sample_dt
                    - event_dt
                ).total_seconds()
            )

            if (
                nearest_diff
                is None
            ):

                nearest_diff = diff
                nearest_row = row

            elif (
                diff
                < nearest_diff
            ):

                nearest_diff = diff
                nearest_row = row

        if (
            nearest_diff is None
            or
            nearest_diff > 10
        ):
            return (
                headers,
                None
            )

        return (
            headers,
            nearest_row
        )

    def extract_metrics(
        self,
        headers,
        row
    ):

        if row is None:
            return {
                "CpuTotal": None,
                "PrivateBytes": None,
                "DiskRead": None,
                "DiskWrite": None,
                "NetworkSend": None,
                "NetworkReceive": None
            }

        result = {}

        for index, header in enumerate(headers):

            if index >= len(row):
                continue

            name = (
                header.lower()
            )

            value = (
                to_float(
                    row[index]
                )
            )

            if (

                "processor(_total)"
                in name
                and
                "% processor time"
                in name
            ):

                result[
                    "CpuTotal"
                ] = value

            elif (
                "private bytes"
                in name
            ):

                result[
                    "PrivateBytes"
                ] = (
                    value / 1024 / 1024
                )                

            elif (
                "disk read"
                in name
            ):
                result[
                    "DiskRead"
                ] = (
                    value / 1024
                )

            elif (
                "disk write"
                in name
            ):
                result[
                    "DiskWrite"
                ] = (
                    value / 1024
                )

            elif (
                "network send"
                in name
                or "bytes sent"
                in name
            ):

                result[
                    "NetworkSend"
                ] = (
                    result.get(
                        "NetworkSend",
                        0
                    )
                    + (value / 1024)
                )

            elif (
                "network receive"
                in name
                or "bytes received"
                in name
            ):

                result[
                    "NetworkReceive"
                ] = (
                    result.get(
                        "NetworkReceive",
                        0
                    )
                    + (value / 1024)
                )                

        return result

    def analyze(
            self,
            event_id,
            event
        ):

        if event is None:
            raise Exception(
                f"{event_id} が存在しません。"
            )

        (
            sender_csv,
            receiver_csv
        ) = (
            self.find_resource_csvs()
        )

        (
            sender_headers,
            sender_row
        ) = (
            self.find_row_near_timestamp(
                sender_csv,
                event["timestamp"],
            )
        )

        (
            receiver_headers,
            receiver_row
        ) = (
            self.find_row_near_timestamp(
                receiver_csv,
                event["timestamp"],
            )
        )

        return {
            "FileName":
                "",

            "EventId":
                event_id,

            "FileId":
                event.get(
                    "fileId",
                    ""
                ),

            "Evidence":
                event.get(
                    "evidence",
                    ""
                ),

            "Timestamp":
                event["timestamp"],

            "Sender":
                self.extract_metrics(
                    sender_headers,
                    sender_row
                ),

            "Receiver":
                self.extract_metrics(
                    receiver_headers,
                    receiver_row
                )
        }

def main():

    metric = PointMetric()

    result = metric.analyze(
        "C_START"
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