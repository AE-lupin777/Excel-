ULAgent Status API Single Capture - Simple Version
==================================================

1. Overview
-----------
Double-click ULAgent_StatusCapture.bat to obtain one Status API snapshot.
The same PowerShell script works for Sender and Receiver.
The connection destination is configured only in ULAgent_StatusCapture.ini.

2. Files
--------
- ULAgent_StatusCapture.bat
- Capture-ULAgentStatus.ps1
- ULAgent_StatusCapture.ini
- README_ULAgent_StatusCapture.txt

3. Sender configuration
-----------------------
Target=Sender
BaseUrl=http://127.0.0.1:5080
RecordsPath=/api/transfers
Limit=500
OutputDirectory=Evidence

4. Receiver configuration
-------------------------
Target=Receiver
BaseUrl=http://127.0.0.1:5081
RecordsPath=/api/receives
Limit=500
OutputDirectory=Evidence

5. Execution
------------
1) Edit the INI for Sender or Receiver.
2) Place all files on the target Windows PC.
3) Double-click ULAgent_StatusCapture.bat.
4) Check the newly created folder under Evidence.

6. Output
---------
- all_results.json: execution information, health, status, and records
- records.json: record list only
- execution_info.csv: execution metadata
- status.csv: status count summary
- records.csv: Sender transfer records or Receiver receive records

7. Initial specification
------------------------
- One capture per execution
- GET requests only
- Maximum 500 records
- No automatic target detection
- No polling or long-time capture
- URL and record path are not embedded in the PowerShell script

8. Important note
-----------------
The Status API is localhost-only. Run the package on the same PC as the
Sender or Receiver service.
