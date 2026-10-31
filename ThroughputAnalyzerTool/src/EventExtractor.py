from EventDefinitions import EVENTS
import json
import re


class EventExtractor:

    def __init__(self):
        self.events = EVENTS

    def get_event(self, event_id):
        return self.events.get(event_id)

    def get_all_events(self):
        return self.events

    def get_sender_event_ids(self):
        result = []
        for event_id, event in self.events.items():
            if event.get("source") == "SenderLog":
                result.append(event_id)
        return result

    def get_receiver_event_ids(self):
        result = []
        for event_id, event in self.events.items():
            if event.get("source") == "ReceiverLog":
                result.append(event_id)
        return result

    def get_records_event_ids(self):
        result = []
        for event_id, event in self.events.items():
            if event.get("source") == "ReceiverRecords":
                result.append(event_id)
        return result

    def parse_timestamp(self, line):

        m = re.match(
            r"(\d{4}-\d{2}-\d{2} "
            r"\d{2}:\d{2}:\d{2}\.\d{3} "
            r"[+-]\d{2}:\d{2})",
            line
        )

        if not m:
            return None

        return m.group(1)

    def is_start_event(self, event_id):
        return event_id.endswith("_START")

    def is_end_event(self, event_id):
        return event_id.endswith("_END")

    def extract_sender_log_events(
        self,
        sender_log_file,
        target_file_ids
    ):
        result = {}

        sender_events = {
            event_id: self.events[event_id]
            for event_id in self.get_sender_event_ids()
        }

        with open(
            sender_log_file,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            for line in f:

                for (
                    event_id,
                    event
                ) in sender_events.items():

                    pattern = event.get(
                        "pattern"
                    )

                    if pattern not in line:
                        continue

                    timestamp = (
                        self.parse_timestamp(
                            line
                        )
                    )

                    file_id = None

                    match = re.search(
                        r"([A-F0-9]{32,})",
                        line
                    )

                    if match:
                        file_id = match.group(1)

                    if (
                        file_id
                        and
                        file_id not in target_file_ids
                    ):
                        continue

                    if event_id not in result:
                        result[event_id] = []

                    result[event_id].append({
                        "timestamp":
                            timestamp,
                        "source":
                            "SenderLog",
                        "fileId":
                            file_id,
                        "evidence":
                            line.strip()
                    })

        return result

    def extract_receiver_log_events(
        self,
        receiver_log_file,
        target_file_ids
    ):
        result = {}

        receiver_events = {
            event_id: self.events[event_id]
            for event_id in self.get_receiver_event_ids()
        }

        with open(
            receiver_log_file,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            for line in f:

                for (
                    event_id,
                    event
                ) in receiver_events.items():

                    pattern = event.get(
                        "pattern"
                    )

                    if pattern not in line:
                        continue

                    timestamp = (
                        self.parse_timestamp(
                            line
                        )
                    )

                    file_id = None

                    match = re.search(
                        r"stored ([A-F0-9]+)",
                        line
                    )

                    if match:
                        file_id = match.group(1)

                    if (
                        file_id
                        and
                        file_id not in target_file_ids
                    ):
                        continue

                    if event_id not in result:
                        result[event_id] = []

                    result[event_id].append({
                        "timestamp":
                            timestamp,
                        "source":
                            "ReceiverLog",
                        "fileId":
                            file_id,
                        "evidence":
                            line.strip()
                    })

        return result

    def extract_records_events(
        self,
        records_json_file,
        receiver_log_file,
        target_file_ids
    ):
        result = {}

        with open(
            records_json_file,
            "r",
            encoding="utf-8-sig"
        ) as f:

            records = json.load(f)

        record_events = {
            event_id: self.events[event_id]
            for event_id in self.get_records_event_ids()
        }

        for (
            event_id,
            event
        ) in record_events.items():

            condition = event.get(
                "condition"
            )

            if condition is None:
                continue

            key = next(
                iter(
                    condition.keys()
                )
            )

            value = (
                condition[key]
            )

            matched = []

            for record in records:

                if (
                    record.get(key)
                    == value
                ):
                    matched.append(
                        record
                    )

            if event_id in [
                "G_END",
                "K_END"
            ]:

                receiver_events = (
                    self.extract_receiver_log_events(
                        receiver_log_file,
                        target_file_ids
                    )
                )

                start_event_id = {
                    "G_END": "G_START",
                    "K_END": "K_START"
                }[event_id]

                start_events = (
                    receiver_events.get(
                        start_event_id,
                        []
                    )
                )

                target_file_ids_from_event = {
                    event.get("fileId")
                    for event in start_events
                    if event.get("fileId")
                }

                matched = [
                    r
                    for r in matched
                    if r.get(
                        "fileId"
                    )
                    in target_file_ids_from_event
                ]

            if not matched:
                continue

            if event_id not in result:
                result[event_id] = []

            for target in matched:

                result[event_id].append({
                    "timestamp":
                        target.get(
                            "updatedAt"
                        ),
                    "source":
                        "ReceiverRecords",
                    "fileId":
                        target.get(
                            "fileId"
                        ),
                    "evidence":
                        (
                            f"{key}"
                            f"="
                            f"{value}"
                        )
                })

        return result

    def extract_all_events(
        self,
        sender_log_file,
        receiver_log_file,
        records_json_file,
        target_file_ids        
    ):
        result = {}

        result.update(
            self.extract_sender_log_events(
                sender_log_file,
                target_file_ids
            )
        )

        result.update(
            self.extract_receiver_log_events(
                receiver_log_file,
                target_file_ids
            )
        )

        result.update(
            self.extract_records_events(
                records_json_file,
                receiver_log_file,
                target_file_ids                
            )
        )
        
        return result


if __name__ == "__main__":

    extractor = EventExtractor()

    print()
    print(
        "=== Sender Events ==="
    )
    print(
        extractor.get_sender_event_ids()
    )

    print()
    print(
        "=== Receiver Events ==="
    )
    print(
        extractor.get_receiver_event_ids()
    )

    print()
    print(
        "=== Records Events ==="
    )
    print(
        extractor.get_records_event_ids()
    )

    print()