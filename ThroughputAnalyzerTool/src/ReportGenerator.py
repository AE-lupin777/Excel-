import json
from pathlib import Path

from PointMetric import PointMetric
from RangeMetric import RangeMetric
from FileMetric import FileMetric

import sys

test_dir = Path(sys.argv[1])

ROOT = Path(__file__).resolve().parent.parent

INPUT_DIR = ROOT / "input"

OUTPUT_DIR = ROOT / "output"

OUTPUT_DIR.mkdir(
    exist_ok=True
)


class ReportGenerator:

    def __init__(self, test_dir):

        self.test_dir = test_dir
        
        self.point_metric = PointMetric(
            test_dir
        )

        self.range_metric = RangeMetric(
            test_dir
        )
        
        self.file_metric = FileMetric(
            test_dir
        )

    def create_report(
        self
    ):

        event_report = (
            self.point_metric.event_report
        )

        report = {
            "TestID":
                test_dir.name,

            "Events":
                event_report.get(
                    "Events",
                    {}
                ),

            "PointMetrics": {},
            "RangeMetrics": {},
            "FileMetrics": []
        }

        events = (
            event_report.get(
                "Events",
                {}
            )
        )

        for event_id in sorted(
            events.keys()
        ):

            event_list = events.get(
                event_id,
                []
            )

            if not isinstance(
                event_list,
                list
            ):
                event_list = [
                    event_list
                ]

            for index, event in enumerate(
                event_list
            ):

                key = (
                    f"{event_id}"
                    f"_{index + 1}"
                )

                report[
                    "PointMetrics"
                ][key] = (
                    self.point_metric.analyze(
                        event_id,
                        event
                    )
                )

        event_names = set(
            events.keys()
        )

        range_definitions = [
            (
                "C_START",
                "C_END"
            ),
            (
                "C_START",
                "K_END"
            ),
            (
                "K_START",
                "K_END"
            )
        ]

        for (
            start_event,
            end_event
        ) in range_definitions:

            if (
                end_event
                not in event_names
            ):
                continue

            start_list = events.get(
                start_event,
                []
            )

            end_list = events.get(
                end_event,
                []
            )

            if not isinstance(
                start_list,
                list
            ):
                start_list = [
                    start_list
                ]

            if not isinstance(
                end_list,
                list
            ):
                end_list = [
                    end_list
                ]

            end_map = {
                item.get(
                    "fileId"
                ): item
                for item in end_list
            }

            for index, start_data in enumerate(
                start_list
            ):

                file_id = start_data.get(
                    "fileId"
                )

                end_data = end_map.get(
                    file_id
                )

                if end_data is None:

                    # print(
                    #     "NOT FOUND",
                    #     start_event,
                    #     end_event,
                    #     file_id
                    # )

                    # print(
                    #     "END IDS",
                    #     list(
                    #         end_map.keys()
                    #     )
                    # )

                    continue

                key = (
                    f"{start_event}"
                    f"_{index+1}"
                    f"~"
                    f"{end_event}"
                    f"_{index+1}"
                )

                report[
                    "RangeMetrics"
                ][key] = (
                    self.range_metric.analyze(
                        start_event,
                        end_event,
                        start_data,
                        end_data
                    )
                )

        report[
            "FileMetrics"
        ] = (
            self.file_metric.analyze()
        )

        return report

    def write_json(
        self,
        report
    ):

        output_file = (
            OUTPUT_DIR /
            "ResultReport.json"
        )

        with open(
            output_file,
            "w",
            encoding="utf-8-sig"
        ) as f:

            json.dump(
                report,
                f,
                indent=2,
                ensure_ascii=False
            )

        return output_file


def main():

    test_dir = Path(
        sys.argv[1]
    )

    generator = (
        ReportGenerator(
            test_dir
        )
    )

    report = (
        generator.create_report()
    )

    output_file = (
        generator.write_json(
            report
        )
    )

    print()
    print(
        f"Output : {output_file}"
    )
    print()


if __name__ == "__main__":
    main()