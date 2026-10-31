ULAgent Resource Timeline Viewer v0.1 (prototype)

Run:
  py -m pip install PySide6
  py ResourceTimelineViewer.py

Current implementation:
- Select an Evidence directory and recursively discover Status Capture JSON/CSV and ULAgent Sender/Receiver log files.
- Correlate file records by fileId/fileName.
- Display file list, common-time-axis event markers, details and event/log table.
- Recognize restart/stop/error/receive-related log events conservatively.
- A remains Not Observed; it is never substituted with another event.
- AI analysis prompt is generated locally and copied to the clipboard. No AI API connection is implemented.
- Resource CSV import is deliberately conservative until the confirmed CSV schema is provided; numeric columns with a recognizable timestamp column are imported.

Important:
This prototype never modifies source Evidence files.
