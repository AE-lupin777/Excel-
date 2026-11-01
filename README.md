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
