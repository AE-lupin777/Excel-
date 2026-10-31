from datetime import (
    datetime,
    timezone,
    timedelta
)


class TimeAligner:

    JST = timezone(
        timedelta(hours=9)
    )

    def parse_event_time(
        self,
        timestamp
    ):

        return (
            datetime.strptime(
                timestamp,
                "%Y-%m-%d %H:%M:%S.%f"
            )
            .replace(
                tzinfo=self.JST
            )
        )

    def parse_resource_time(
        self,
        timestamp
    ):

        return (
            datetime.fromisoformat(
                timestamp
            )
        )

    def calc_diff_sec(
        self,
        event_time,
        resource_time
    ):

        return abs(
            (
                resource_time
                - event_time
            ).total_seconds()
        )

    def find_nearest_row(
        self,
        event_timestamp,
        rows
    ):

        event_dt = (
            self.parse_event_time(
                event_timestamp
            )
        )

        nearest_row = None
        nearest_diff = None

        for row in rows:

            try:

                sample_dt = (
                    self.parse_resource_time(
                        row[0]
                    )
                )

            except Exception:

                continue

            diff = self.calc_diff_sec(
                event_dt,
                sample_dt
            )

            if nearest_diff is None:

                nearest_diff = diff
                nearest_row = row

            elif diff < nearest_diff:

                nearest_diff = diff
                nearest_row = row

        return (
            nearest_row,
            nearest_diff
        )


if __name__ == "__main__":

    aligner = TimeAligner()

    event_time = (
        "2026-10-15 11:15:32.871"
    )

    sample_time = (
        "2026-10-15T02:15:32.806+00:00"
    )

    event_dt = (
        aligner.parse_event_time(
            event_time
        )
    )

    sample_dt = (
        aligner.parse_resource_time(
            sample_time
        )
    )

    diff = (
        aligner.calc_diff_sec(
            event_dt,
            sample_dt
        )
    )

    print()

    print(
        f"Event : {event_dt}"
    )

    print(
        f"Sample: {sample_dt}"
    )

    print(
        f"DiffSec: {diff}"
    )

    print()