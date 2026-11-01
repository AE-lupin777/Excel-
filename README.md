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
