import json
import re

from pathlib import Path
import sys
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.styles import PatternFill
from openpyxl.styles import Border
from openpyxl.styles import Side
from openpyxl.styles import Alignment
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIR = ROOT / "output"


HEADER_FILL = PatternFill(
    "solid",
    fgColor="D9EAD3"
)

HEADER_FONT = Font(
    bold=True
)

HEADER_ALIGNMENT = Alignment(
    horizontal="center",
    vertical="center",
    wrap_text=True
)

THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin")
)


METRIC_DEFINITIONS = {
    "CpuTotal": "CPU使用率",
    "PrivateBytes": "プロセス使用メモリ",
    "DiskWrite": "ディスク書き込み量",
    "DiskRead": "ディスク読み込み量",
    "NetworkSend": "ネットワーク送信量",
    "NetworkReceive": "ネットワーク受信量",

    "FileId": "ファイルID",
    "FileType": "ファイル種別",
    "FileName": "ファイル名",

    "FileSizeBytes": "ファイルサイズ(Byte)",
    "FileSizeKB": "ファイルサイズ(KB)",

    "SendTime": "送信開始時刻",
    "ReceiveTime": "受信完了時刻",

    "DurationMs": "転送時間(ms)",

    "ThroughputBps": "スループット(Byte/秒)",
    "ThroughputKBps": "スループット(KB/秒)",
    "ThroughputMBps": "スループット(MB/秒)",

    "TransferFileCount": "転送ファイル数",
    "TransferSizeBytes": "転送サイズ(Byte)",
    "TransferSizeKB": "転送サイズ(KB)",
    "TransferSizeMB": "転送サイズ(MB)"
}

from datetime import (
    datetime,
    timezone,
    timedelta
)

JST = timezone(
    timedelta(hours=9)
)

def format_datetime_jst(
    value
):

    if not value:
        return ""

    try:

        dt = datetime.strptime(
            value,
            "%Y-%m-%d %H:%M:%S.%f %z"
        )

    except Exception:

        dt = datetime.fromisoformat(
            value
        )
    
    dt = dt.astimezone(
        JST
    )

    return dt.strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )[:-3]

def auto_fit(ws):

    for column in ws.columns:

        max_len = 0

        for cell in column:

            if cell.value is None:
                continue

            max_len = max(
                max_len,
                len(str(cell.value))
            )

        ws.column_dimensions[
            column[0].column_letter
        ].width = max_len + 5


def apply_header_style(ws, row):

    for cell in ws[row]:

        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.border = THIN_BORDER
        cell.alignment = HEADER_ALIGNMENT


def apply_borders(ws):

    for row in ws.iter_rows():

        for cell in row:

            cell.border = THIN_BORDER


def apply_number_format(ws):

    for row in ws.iter_rows():

        for cell in row:

            if isinstance(cell.value, int):

                cell.number_format = "#,##0"

            elif isinstance(cell.value, float):

                cell.number_format = "#,##0.000"


def finalize_sheet(ws):

    ws.freeze_panes = "A2"

    ws.row_dimensions[1].height = 35

    if ws.max_row > 2 and ws.max_column > 1:
        ws.auto_filter.ref = ws.dimensions

    apply_borders(ws)
    auto_fit(ws)


def flatten_dict(data, prefix=""):

    result = {}

    for key, value in data.items():

        new_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):

            result.update(
                flatten_dict(
                    value,
                    new_key
                )
            )

        else:

            result[new_key] = value

    return result


def get_metric_description(metric_name):

    if metric_name.endswith("_Min"):

        base = metric_name[:-4]

        return (
            f"{METRIC_DEFINITIONS.get(base, '(説明未登録)')} 最小値"
        )

    if metric_name.endswith("_Max"):

        base = metric_name[:-4]

        return (
            f"{METRIC_DEFINITIONS.get(base, '(説明未登録)')} 最大値"
        )

    if metric_name.endswith("_Avg"):

        base = metric_name[:-4]

        return (
            f"{METRIC_DEFINITIONS.get(base, '(説明未登録)')} 平均値"
        )

    return METRIC_DEFINITIONS.get(
        metric_name,
        "(説明未登録)"
    )

def build_header(column_name):

    metric = column_name

    if "." in column_name:
        metric = (
            column_name
            .split(".")[-1]
        )

    description = (
        get_metric_description(
            metric
        )
    )

    if description == "(説明未登録)":
        return column_name

    return (
        f"{column_name}\n"
        f"({description})"
    )

def get_column_description(column_name):

    if "." not in column_name:
        return ""

    metric = column_name.split(".")[-1]

    return get_metric_description(metric)

def create_summary_sheet(
    wb,
    report
):

    ws = wb.active

    ws.title = "Summary"

    file_metrics = report.get(
        "FileMetrics",
        []
    )

    event_count = sum(
        1
        for x in file_metrics
        if x.get("FileType") == "EVENT"
    )

    sampling_count = sum(
        1
        for x in file_metrics
        if x.get("FileType") == "SAMPLING"
    )

    process_count = sum(
        1
        for x in file_metrics
        if x.get("FileType") == "PROCESS"
    )

    total_size_mb = round(
        sum(
            x.get(
                "FileSizeBytes",
                0
            )
            for x in file_metrics
        ) / 1024 / 1024,
        2
    )

    total_size_kb = round(
        sum(
            x.get(
                "FileSizeBytes",
                0
            )
            for x in file_metrics
        ) / 1024,
        2
    )

    timestamps = []

    for events in report.get(
        "Events",
        {}
    ).values():

        if not isinstance(
            events,
            list
        ):
            events = [events]

        for event in events:

            timestamp = event.get(
                "timestamp"
            )

            if timestamp:
                timestamps.append(
                    timestamp
                )

    start_time = ""
    end_time = ""
    duration = ""

    if timestamps:

        start_time = min(
            timestamps
        )

        end_time = max(
            timestamps
        )

        start_dt = datetime.fromisoformat(
            start_time
            .strip()
            .replace(" +", "+")
            .replace(" -", "-")
        )

        end_dt = datetime.fromisoformat(
            end_time
            .strip()
            .replace(" +", "+")
            .replace(" -", "-")
        )

        duration = str(
            end_dt - start_dt
        )

        start_time = (
            format_datetime_jst(
                start_time
            )
        )

        end_time = (
            format_datetime_jst(
                end_time
            )
        )

    # if timestamps:

    #     start_time = min(
    #         timestamps
    #     )

    #     end_time = max(
    #         timestamps
    #     )

    #     start_dt = datetime.fromisoformat(
    #         start_time.replace(" ", "T", 1).replace(" +09:00", "+09:00")
    #     )

    #     end_dt = datetime.fromisoformat(
    #         end_time.replace(" ", "T", 1).replace(" +09:00", "+09:00")
    #     )

    #     start_time = (
    #         format_datetime_jst(
    #             start_time
    #         )
    #     )

    #     end_time = (
    #         format_datetime_jst(
    #             end_time
    #         )
    #     )

    ws.append(
        [
            "項目",
            "値"
        ]
    )

    apply_header_style(ws, 1)

    point_count = sum(
        1
        for x in report.get(
            "PointMetrics",
            {}
        ).values()
        if x.get("FileId")
    )

    rows = [
        [
            "対象ファイル数",
            len(file_metrics)
        ],
        [
            "EVENTファイル数",
            event_count
        ],
        [
            "SAMPLINGファイル数",
            sampling_count
        ],
        [
            "PROCESSファイル数",
            process_count
        ],
        [
            "PointMetrics件数",
            point_count
        ],
        [
            "試験開始時刻",
            start_time
        ],
        [
            "試験終了時刻",
            end_time
        ],
        [
            "試験時間",
            duration
        ],
        [
            "対象ファイル総容量(KB)",
            total_size_kb
            # round(
            #     sum(
            #         x.get(
            #             "FileSizeBytes",
            #             0
            #         )
            #         for x in file_metrics
            #     ),
            #     2
            # )
        ]
    ]

    for row in rows:
        ws.append(row)

    ws.freeze_panes = "A2"

    if ws.max_row > 1 and ws.max_column > 1:
        ws.auto_filter.ref = ws.dimensions

    apply_borders(ws)
    apply_number_format(ws)
    auto_fit(ws)
    ws.column_dimensions["A"].width = 30

def create_point_sheet(
    wb,
    report
):

    ws = wb.create_sheet(
        "PointMetrics"
    )

    records = []

    columns = set()

    file_map = {
        x.get("FileId"): x.get("FileName")
        for x in report.get(
            "FileMetrics",
            []
        )
    }

    reverse_file_map = {
        x.get("FileName"): x.get("FileId")
        for x in report.get(
            "FileMetrics",
            []
        )
    }

    target_file_ids = set(
        file_map.keys()
    )

    for _, data in report.get(
        "PointMetrics",
        {}
    ).items():

        row = flatten_dict(data)

        if row.get("Timestamp"):
            row["Timestamp"] = (
                format_datetime_jst(
                    row["Timestamp"]
                )
            )

        file_id = row.get("FileId")

        if not file_id:
            continue

        if (
            file_id
            and
            file_id not in target_file_ids
        ):
            continue

        row["FileName"] = (
            file_map.get(
                file_id,
                ""
            )
        )

        if (
            not row["FileName"]
            and
            row.get("EventId") == "B_START"
            and
            row.get("Evidence")
        ):
            match = re.search(
                r"Discovered\s+\w+\s+file\s+(.+)$",
                row.get(
                    "Evidence",
                    ""
                )
            )

            if match:
                file_name = (
                    match.group(1)
                )

                for x in report.get(
                    "FileMetrics",
                    []
                ):
                    if (
                        x.get("FileName")
                        == file_name
                    ):
                        row["FileName"] = (
                            file_name
                        )
                        row["FileId"] = (
                            x.get(
                                "FileId",
                                ""
                            )
                        )
                        break

        if (
            not row["FileName"]
            and
            row.get("Evidence")
        ):
                    
            evidence = row.get(
                "Evidence",
                ""
            )

            match = re.search(
                r"Discovered\s+\w+\s+file\s+(.+)$",
                evidence
            )

            if match:
                row["FileName"] = (
                    match.group(1)
                )

        if (
            not row.get("FileId")
            and
            row.get("FileName")
        ):
            row["FileId"] = (
                reverse_file_map.get(
                    row["FileName"],
                    ""
                )
            )

        if (
            row.get("EventId")
            == "B_START"
        ):
            print(row)

        records.append(row)

        columns.update(
            row.keys()
        )

    preferred_columns = [
        "FileName",
        "EventId",
        "Timestamp",
        "FileId",

        "Sender.CpuTotal",
        "Sender.PrivateBytes",
        "Sender.DiskRead",
        "Sender.DiskWrite",
        "Sender.NetworkReceive",
        "Sender.NetworkSend",

        "Receiver.CpuTotal",
        "Receiver.PrivateBytes",
        "Receiver.DiskRead",
        "Receiver.DiskWrite",
        "Receiver.NetworkReceive",
        "Receiver.NetworkSend",

        "Evidence"
    ]

    header_map = {
        "FileName": "ファイル名",
        "EventId": "イベント",
        "Timestamp": "日時",
        "FileId": "ファイルID",

        "Sender.CpuTotal":
            "Sender.CpuTotal(%)",

        "Sender.PrivateBytes":
            "Sender.PrivateBytes(MB)",

        "Sender.DiskRead":
            "Sender.DiskRead(KB/s)",

        "Sender.DiskWrite":
            "Sender.DiskWrite(KB/s)",

        "Sender.NetworkReceive":
            "Sender.NetworkReceive(KB/s)",

        "Sender.NetworkSend":
            "Sender.NetworkSend(KB/s)",

        "Receiver.CpuTotal":
            "Receiver.CpuTotal(%)",

        "Receiver.PrivateBytes":
            "Receiver.PrivateBytes(MB)",

        "Receiver.DiskRead":
            "Receiver.DiskRead(KB/s)",

        "Receiver.DiskWrite":
            "Receiver.DiskWrite(KB/s)",

        "Receiver.NetworkReceive":
            "Receiver.NetworkReceive(KB/s)",

        "Receiver.NetworkSend":
            "Receiver.NetworkSend(KB/s)",

        "Evidence":
            "エビデンス"
    }

    columns = (
        [
            c
            for c in preferred_columns
            if c in columns
        ]
        +
        sorted(
            columns
            - set(preferred_columns)
        )
    )

    ws.append(
        [
            header_map.get(
                col,
                build_header(col)
            )
            for col in columns
        ]
    )

    apply_header_style(ws, 1)

    event_order = {
        "B_START": 1,
        "C_START": 2,
        "C_END": 3,
        "G_START": 4,
        "K_START": 5,
        "G_END": 6,
        "K_END": 7
    }

    records = sorted(
        records,
        key=lambda r: (
            r.get(
                "FileName",
                ""
            ),
            event_order.get(
                r.get(
                    "EventId",
                    ""
                ),
                999
            )
        )
    )

    for record in records:

        ws.append(
            [
                record.get(col)
                for col in columns
            ]
        )

    for row in ws.iter_rows(
        min_row=2
    ):

        for cell in row:

            if isinstance(
                cell.value,
                (int, float)
            ):
                cell.number_format = "#,##0.000"

    finalize_sheet(ws)
    ws.column_dimensions["A"].width = 30   # FileName
    ws.column_dimensions["B"].width = 15   # EventId
    ws.column_dimensions["C"].width = 30   # Timestamp
    ws.column_dimensions["D"].width = 80   # FileId
    ws.column_dimensions["P"].width = 38
    ws.column_dimensions["Q"].width = 160

def create_range_sheet(
    wb,
    report
):

    ws = wb.create_sheet(
        "RangeMetrics"
    )

    records = []

    columns = {"RangeId"}

    file_map = {
        x.get("FileId"): x.get("FileName")
        for x in report.get(
            "FileMetrics",
            []
        )
    }

    reverse_file_map = {
        x.get("FileName"): x.get("FileId")
        for x in report.get(
            "FileMetrics",
            []
        )
    }

    range_name_map = {
        "C_START~C_END":
            "ファイル送信開始～受信完了",

        "C_START~K_END":
            "ファイル送信開始～DB登録完了",

        "K_START~K_END":
            "DB登録待ち～DB登録完了"
    }

    for range_id, data in report.get(
        "RangeMetrics",
        {}
    ).items():

        row = {
            "Key": range_id
        }

        row.update(
            flatten_dict(data)
        )

        row["RangeName"] = (
            range_name_map.get(
                row.get(
                    "RangeId",
                    ""
                ),
                ""
            )
        )

        if row.get("StartTime"):
            row["StartTime"] = (
                format_datetime_jst(
                    row["StartTime"]
                )
            )

        if row.get("EndTime"):
            row["EndTime"] = (
                format_datetime_jst(
                    row["EndTime"]
                )
            )

        file_id = row.get(
            "FileId"
        )

        row["FileName"] = (
            file_map.get(
                file_id,
                ""
            )
        )

        if (
            not row["FileName"]
            and
            row.get("Evidence")
        ):
            evidence = row.get(
                "Evidence",
                ""
            )

            match = re.search(
                r"Discovered\s+\w+\s+file\s+(.+)$",
                evidence
            )

            if match:
                row["FileName"] = (
                    match.group(1)
                )

        if (
            not row.get("FileId")
            and
            row.get("FileName")
        ):
            row["FileId"] = (
                reverse_file_map.get(
                    row["FileName"],
                    ""
                )
            )

        records.append(row)

        columns.update(
            row.keys()
        )

    range_order = {
        "C_START~C_END": 1,
        "C_START~K_END": 2,
        "K_START~K_END": 3
    }

    records.sort(
        key=lambda row: (
            row.get(
                "FileName",
                ""
            ),
            range_order.get(
                row.get(
                    "RangeId",
                    ""
                ),
                999
            )
        )
    )

    preferred_columns = [
        "FileName",
        "RangeName",
        "RangeId",
        "StartEvent",
        "EndEvent",
        "StartTime",
        "EndTime",
        "FileId",
        "DurationSec",
        "Evidence"
    ]

    columns = (
        [
            c
            for c in preferred_columns
            if c in columns
        ]
        +
        sorted(
            columns
            - set(preferred_columns)
        )
    )

    ws.append(
        [
            build_header(col)
            for col in columns
    ]
    )

    apply_header_style(ws, 1)

    for record in records:

        ws.append(
            [
                record.get(col)
                for col in columns
            ]
        )

    for row in ws.iter_rows(
        min_row=2
    ):

        for cell in row:

            column_name = columns[
                cell.column - 1
            ]

            if cell.value is None:
                continue

            if column_name.endswith(
                "Bytes"
            ):
                cell.number_format = "#,##0"

            elif column_name == (
                "ThroughputBps"
            ):
                cell.number_format = "#,##0.000"

            elif (
                "SizeKB" in column_name
                or "KBps" in column_name
            ):
                cell.number_format = "#,##0.000"

            elif (
                "SizeMB" in column_name
            ):
                cell.number_format = "#,##0.000"

            elif (
                "MBps" in column_name
            ):
                cell.number_format = "#,##0.000000"

            elif (
                column_name.endswith(
                    "DurationSec"
                )
                or "CpuTotal" in column_name
                or column_name.endswith("_Min")
                or column_name.endswith("_Max")
                or column_name.endswith("_Avg")
            ):
                cell.number_format = "#,##0.000"

    finalize_sheet(ws)
    ws.column_dimensions["B"].width = 35
    ws.column_dimensions["G"].width = 30
    ws.column_dimensions["C"].hidden = True
    ws.column_dimensions["D"].hidden = True
    ws.column_dimensions["E"].hidden = True

def create_metric_definition_sheet(
    wb,
    report
):

    ws = wb.create_sheet(
        "MetricDefinitions"
    )

    ws.append(
        [
            "MetricName",
            "Description"
        ]
    )

    apply_header_style(ws, 1)

    metric_names = set()

    for data in report.get(
        "PointMetrics",
        {}
    ).values():

        flat = flatten_dict(data)

        for key in flat.keys():

            if "." not in key:
                continue

            metric = key.split(".")[-1]

            metric_names.add(metric)

    for data in report.get(
        "RangeMetrics",
        {}
    ).values():

        flat = flatten_dict(data)

        for key in flat.keys():

            if "." not in key:
                continue

            metric = key.split(".")[-1]

            metric_names.add(metric)

    for data in report.get(
        "FileMetrics",
        []
    ):

        for key in data.keys():

            metric_names.add(
                key
            )

    for metric in sorted(metric_names):

        ws.append(
            [
                metric,
                get_metric_description(metric)
            ]
        )

    ws.freeze_panes = "A2"

    if ws.max_row > 1 and ws.max_column > 1:
        ws.auto_filter.ref = ws.dimensions

    apply_borders(ws)
    apply_number_format(ws)
    auto_fit(ws)
    ws.column_dimensions["B"].width = 50

def create_file_sheet(
    wb,
    report
):

    ws = wb.create_sheet(
        "FileMetrics"
    )

    records = report.get(
        "FileMetrics",
        []
    )

    if not records:
        finalize_sheet(ws)
        return

    columns = [
        "FileType",
        "FileName",
        "FileSizeBytes",
        "FileSizeKB",
        "SendTime",
        "ReceiveTime",
        "DurationMs",
        "ThroughputKBps",
        "ThroughputMBps"
    ]

    ws.append(
        [
            build_header(col)
            for col in columns
        ]
    )

    apply_header_style(ws, 1)

    for record in records:

        ws.append(
            [
                record.get(col)
                for col in columns
            ]
        )

    for row in ws.iter_rows(
        min_row=2
    ):

        for cell in row:

            column_name = columns[
                cell.column - 1
            ]

            if cell.value is None:
                continue

            if column_name.endswith(
                "Bytes"
            ):
                cell.number_format = "#,##0"

            elif (
                "SizeKB" in column_name
                or "KBps" in column_name
            ):
                cell.number_format = "#,##0.000"

            elif (
                "MBps" in column_name
            ):
                cell.number_format = "#,##0.000000"

            elif (
                "DurationMs" in column_name
            ):
                cell.number_format = "#,##0.000"

    finalize_sheet(ws)

def format_size(size):

    if size >= 1024 * 1024:
        return (
            f"{size / 1024 / 1024:.2f} MB"
        )

    if size >= 1024:
        return (
            f"{size / 1024:.2f} KB"
        )

    return (
        f"{size} Byte"
    )

def create_detail_sheet(
    wb,
    report
):

    ws = wb.create_sheet(
        "Detail"
    )

    headers = [
        "TestID",
        "ファイル名",
        "ファイルタイプ",
        "ファイルサイズ(KB)",
        "FileID",
        "Sender送信開始",
        "Receiver受信完了",
        "転送時間(ms)",
        "Throughput(KB/s)"
    ]

    ws.append(headers)

    apply_header_style(
        ws,
        1
    )

    test_id = report.get(
        "TestID"
    )

    records = sorted(
        report.get(
            "FileMetrics",
            []
        ),
        key=lambda x:
            x.get(
                "FileSizeBytes",
                0
            )
    )

    count = 1

    for record in records:
        ws.append(
            [
                test_id,

                record.get(
                    "FileName"
                ),

                record.get(
                    "FileType"
                ),

                round(
                    (
                        record.get(
                            "FileSizeBytes",
                            0
                        ) / 1024
                    ),
                    2
                ),

                record.get(
                    "FileId"
                ),

                format_datetime_jst(
                    record.get(
                        "SendTime"
                    )
                ),

                format_datetime_jst(
                    record.get(
                        "ReceiveTime"
                    )
                ),

                record.get(
                    "DurationMs"
                ),

                round(
                    (
                        (
                            record.get(
                                "ThroughputMBps"
                            ) or 0
                        ) * 1024
                    ),
                    3
                )
            ]            
        )
        count += 1

    for row in ws.iter_rows(
        min_row=2
    ): row[6].number_format = "#,##0.000"

    finalize_sheet(ws)
    # A TestID
    ws.column_dimensions["A"].width = 12

    # B ファイル名
    ws.column_dimensions["B"].width = 30

    # C ファイルタイプ
    ws.column_dimensions["C"].width = 15

    # D ファイルサイズ(KB)
    ws.column_dimensions["D"].width = 28

    # E FileID
    ws.column_dimensions["E"].hidden = True

    # F Sender送信開始
    ws.column_dimensions["F"].width = 28

    # G Receiver受信完了
    ws.column_dimensions["G"].width = 30

    # H 転送時間(ms)
    ws.column_dimensions["H"].width = 20

    # I Throughput(KB/s)
    ws.column_dimensions["I"].width = 25

def create_event_details_sheet(
    wb,
    report
):

    ws = wb.create_sheet(
        "EventDetails"
    )

    headers = [
        "ファイル名",
        "ファイルタイプ",
        "ファイルサイズ(KB)",
        "Event",
        "状態",
        "日時",
        "Status",
        "FileID",
        "Evidence"
    ]

    ws.append(
        headers
    )

    apply_header_style(
        ws,
        1
    )

    events = report.get(
        "Events",
        {}
    )

    file_metrics = {
        x.get(
            "FileId"
        ): x
        for x in report.get(
            "FileMetrics",
            []
        )
    }

    event_order = [
        "B_START",
        "C_START",
        "C_END",
        "G_START",
        "K_START",
        "G_END",
        "K_END"
    ]

    file_events = {}

    for event_id, event_list in events.items():

        if not isinstance(
            event_list,
            list
        ):
            event_list = [
                event_list
            ]

        for data in event_list:

            file_id = data.get(
                "fileId",
                ""
            )

            if (
                event_id == "B_START"
                and
                not file_id
            ):
                match = re.search(
                    r"Discovered\s+(\w+)\s+file\s+(.+)$",
                    data.get(
                        "evidence",
                        ""
                    )
                )

                if match:
                    file_name = (
                        match.group(2)
                    )

                    for x in report.get(
                        "FileMetrics",
                        []
                    ):

                        if (
                            x.get(
                                "FileName"
                            )
                            == file_name
                        ):

                            file_id = (
                                x.get(
                                    "FileId",
                                    ""
                                )
                            )

                            break

            if not file_id:
                continue

            if file_id not in file_events:
                file_events[file_id] = {}

            file_events[file_id][
                event_id
            ] = data

    sorted_file_items = sorted(
        file_events.items(),
        key=lambda x: (
            file_metrics.get(
                x[0],
                {}
            ).get(
                "FileName",
                ""
            )
        )
    )


    type_order = {
        "EVENT": 1,
        "SAMPLING": 2,
        "PROCESS": 3,
        "":99
    }

    sorted_file_items = sorted(
        file_events.items(),
        key=lambda x: (
            type_order.get(
                file_metrics.get(
                    x[0],
                    {}
                ).get(
                    "FileType",
                    ""
                ),
                99
            ),
            file_metrics.get(
                x[0],
                {}
            ).get(
                "FileName",
                ""
            )
        )
    )

    for file_id, event_map in sorted_file_items:
        for event_id in event_order:

            data = event_map.get(
                event_id
            )

            if data is None:
                continue

            file_name = ""
            file_type = ""

            file_id = data.get(
                "fileId",
                ""
            )

            metric = file_metrics.get(
                file_id
            )

            if metric:
                file_name = (
                    metric.get(
                        "FileName",
                        ""
                    )
                )

                file_type = (
                    metric.get(
                        "FileType",
                        ""
                    )
                )

            evidence = data.get(
                "evidence",
                ""
            )

            evidence = data.get(
                "evidence",
                ""
            )

            status = ""
            remarks = ""

            # Status設定
            if event_id == "B_START":

                status = (
                    "fileStatus=DISCOVERED"
                )

            elif event_id == "C_START":

                status = (
                    "transferStatus=SENDING"
                )

            elif event_id == "C_END":

                status = (
                    "transferStatus=ACCEPTED"
                )

            elif event_id == "G_START":

                status = (
                    "receiveStatus=STORED"
                )

            elif event_id == "G_END":

                status = (
                    "receiveStatus=RECEIVED"
                )

            elif event_id == "K_START":

                status = (
                    "registrationStatus=PENDING"
                )

            elif event_id == "K_END":

                status = (
                    "registrationStatus=REGISTERED"
                )

            # 備考欄
            if event_id == "B_START":

                remarks = (
                    "Senderが送信対象ファイルを検出"
                )

            elif event_id == "C_START":

                remarks = (
                    "Senderがファイル送信開始"
                )

            elif event_id == "C_END":

                remarks = (
                    "SenderがReceiver受信完了応答を受領"
                )

            elif event_id == "G_START":

                remarks = (
                    "Receiverがファイル保存完了"
                )

            elif event_id == "G_END":

                remarks = (
                    "receiveStatus=RECEIVED"
                )

            elif event_id == "K_START":

                remarks = (
                    "DB登録待ち状態"
                )

            elif event_id == "K_END":

                remarks = (
                    "DB登録完了"
                )

            # B_START情報抽出
            if event_id == "B_START":
                match = re.search(
                    r"Discovered\s+(\w+)\s+file\s+(.+)$",
                    evidence
                )

                if match:
                    file_type = match.group(
                        1
                    )
                    file_name = match.group(
                        2
                    )

            if (
                not file_id
                and
                event_id in [
                    "B_START",
                    "C_START",
                    "C_END"
                ]
            ):

                match = re.search(
                    r"([A-F0-9]{32,})",
                    evidence
                )

                if match:
                    file_id = match.group(
                        1
                    )

            if (
                event_id == "B_START"
                and
                not file_id
                and
                file_name
            ):

                for x in report.get(
                    "FileMetrics",
                    []
                ):

                    if (
                        x.get(
                            "FileName"
                        )
                        == file_name
                    ):

                        file_id = (
                            x.get(
                                "FileId",
                                ""
                            )
                        )

                        break

            metric = file_metrics.get(
                file_id
            )

            if not metric and file_name:
                for x in report.get(
                    "FileMetrics",
                    []
                ):

                    if (
                        x.get(
                            "FileName"
                        )
                        == file_name
                    ):
                        metric = x
                        break

            if metric:
                if not file_name:
                    file_name = (
                        metric.get(
                            "FileName",
                            ""
                        )
                    )

                if not file_type:
                    file_type = (
                        metric.get(
                            "FileType",
                            ""
                        )
                    )

                file_size = (
                    metric.get(
                        "FileSizeBytes",
                        0
                    )
                )

                file_size = round(
                    file_size / 1024,
                    2
                )

            else:

                file_size = ""

            ws.append(
                [
                    file_name,
                    file_type,
                    file_size,
                    event_id,
                    remarks,
                    format_datetime_jst(
                        data.get(
                            "timestamp"
                        )
                    ),
                    status,
                    file_id,
                    data.get(
                        "evidence",
                        ""
                    ),
                ]
            )
    
    finalize_sheet(
        ws
    )
    ws.column_dimensions["B"].width = 20
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["E"].width = 40
    ws.column_dimensions["F"].width = 30
    ws.column_dimensions["G"].width = 30
    ws.column_dimensions["H"].width = 80
    ws.column_dimensions["I"].width = 160

def main():
    test_dir = Path(
        sys.argv[1]
    )

    json_file = (
        OUTPUT_DIR /
        "ResultReport.json"
    )

    if not json_file.exists():

        raise Exception(
            "ResultReport.json が存在しません。"
        )

    with open(
        json_file,
        "r",
        encoding="utf-8-sig"
    ) as f:

        report = json.load(f)

    wb = Workbook()

    create_summary_sheet(
        wb,
        report
    )

    create_point_sheet(
        wb,
        report
    )

    create_range_sheet(
        wb,
        report
    )

    create_detail_sheet(
        wb,
        report
    )

    create_event_details_sheet(
        wb,
        report
    )

    create_metric_definition_sheet(
        wb,
        report
    )

    output_file = (
        OUTPUT_DIR /
        f"{test_dir.name}_ResultReport.xlsx"
    )

    try:

        wb.save(
            output_file
        )

    except PermissionError:

        print()
        print(
            "ERROR: ResultReport.xlsx が開かれています。"
        )
        print(
            "Excelを閉じて再実行してください。"
        )
        print()

        return

    print()
    print(
        f"Output : {output_file}"
    )
    print()


if __name__ == "__main__":
    main()