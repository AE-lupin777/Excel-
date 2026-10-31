import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.styles import PatternFill
from openpyxl.styles import Border
from openpyxl.styles import Side


ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIR = ROOT / "output"

HEADER_FILL = PatternFill(
    "solid",
    fgColor="D9EAD3"
)

HEADER_FONT = Font(
    bold=True
)

THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin")
)


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


def write_dict_section(
    ws,
    title,
    data,
    start_row
):

    ws.cell(
        row=start_row,
        column=1,
        value=title
    )

    ws.cell(
        row=start_row,
        column=1
    ).font = Font(
        bold=True,
        size=12
    )

    row = start_row + 1

    ws.cell(
        row=row,
        column=1,
        value="Item"
    )

    ws.cell(
        row=row,
        column=2,
        value="Value"
    )

    for col in (1, 2):

        ws.cell(
            row=row,
            column=col
        ).fill = HEADER_FILL

        ws.cell(
            row=row,
            column=col
        ).font = HEADER_FONT

        ws.cell(
            row=row,
            column=col
        ).border = THIN_BORDER

    row += 1

    for key, value in data.items():

        if isinstance(
            value,
            dict
        ):

            for sub_key, sub_value in value.items():

                c1 = ws.cell(
                    row=row,
                    column=1,
                    value=f"{key}.{sub_key}"
                )

                c2 = ws.cell(
                    row=row,
                    column=2,
                    value=sub_value
                )

                c1.border = THIN_BORDER
                c2.border = THIN_BORDER

                row += 1

        else:

            c1 = ws.cell(
                row=row,
                column=1,
                value=key
            )

            c2 = ws.cell(
                row=row,
                column=2,
                value=value
            )

            c1.border = THIN_BORDER
            c2.border = THIN_BORDER

            row += 1

    return row + 2


def create_summary_sheet(
    wb,
    report
):

    ws = wb.active

    ws.title = "Summary"

    ws["A1"] = "Category"
    ws["B1"] = "Count"

    ws["A1"].fill = HEADER_FILL
    ws["B1"].fill = HEADER_FILL

    ws["A1"].font = HEADER_FONT
    ws["B1"].font = HEADER_FONT

    ws["A2"] = "PointMetrics"
    ws["B2"] = len(
        report["PointMetrics"]
    )

    ws["A3"] = "RangeMetrics"
    ws["B3"] = len(
        report["RangeMetrics"]
    )

    auto_fit(ws)


def create_point_sheet(
    wb,
    report
):

    ws = wb.create_sheet(
        "PointMetrics"
    )

    row = 1

    for (
        event_id,
        data
    ) in report[
        "PointMetrics"
    ].items():

        ws.cell(
            row=row,
            column=1,
            value=event_id
        )

        ws.cell(
            row=row,
            column=1
        ).font = Font(
            bold=True
        )

        row += 1

        row = write_dict_section(
            ws,
            "Metric",
            data,
            row
        )

    auto_fit(ws)


def create_range_sheet(
    wb,
    report
):

    ws = wb.create_sheet(
        "RangeMetrics"
    )

    row = 1

    for (
        range_id,
        data
    ) in report[
        "RangeMetrics"
    ].items():

        ws.cell(
            row=row,
            column=1,
            value=range_id
        )

        ws.cell(
            row=row,
            column=1
        ).font = Font(
            bold=True
        )

        row += 1

        row = write_dict_section(
            ws,
            "Metric",
            data,
            row
        )

    auto_fit(ws)


def main():

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
        encoding="utf-8"
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

    output_file = (
        OUTPUT_DIR /
        "ResultReport.xlsx"
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

    main()
if __name__ == "__main__":