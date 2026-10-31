# ThroughputAnalyzerTool
# Version : v1.0 Status : Completed

## 概要

ThroughputAnalyzerTool は ULAgent の試験結果フォルダを解析し、試験前後の差分から転送結果を集計するツールです。

現在の v1.0 では以下を算出します。

- SentCount
- ReceivedCount
- RegisteredCount
- TotalBytes
- TotalMB

出力結果は CSV および JSON として保存されます。

---

## 動作環境

- Python 3.13 以降推奨
- Windows 11

---

## フォルダ構成

```text
ThroughputAnalyzerTool
│
├─ Input
│   └─ sample01
│       ├─ sender
│       │   ├─ ULAgent.Sender-20261015.log
│       │   ├─ 20261015_111259_UJW230932_Sender
│       │   └─ 20261015_111651_UJW230932_Sender
│       │
│       ├─ receiver
│       │   ├─ ULAgent.Receiver-20261015.log
│       │   ├─ 20261015_021353_UJSVR026_Receiver
│       │   └─ 20261015_021757_UJSVR026_Receiver
│       │
│       └─ ULAgentディレクトリ
│
├─ Output
├─ src
│   └─ ThroughputAnalyzer.py
├─ requirements.txt
├─ run.bat
└─ README.md
```

---

## 入力

Input 配下に TestID フォルダを配置します。

例:

```text
Input
└─ sample01
```

現在の v1.0 では Input 配下の最初の TestID フォルダを解析対象とします。

---

## 試験前後判定

### Sender

フォルダ名末尾が `_Sender` のフォルダを時刻順に並べます。

- 最古のフォルダ → 試験前
- 最新のフォルダ → 試験後

### Receiver

フォルダ名末尾が `_Receiver` のフォルダを時刻順に並べます。

- 最古のフォルダ → 試験前
- 最新のフォルダ → 試験後

---

## 算出ロジック

### SentCount

```text
Sender試験後.sent
-
Sender試験前.sent
```

### ReceivedCount

```text
Receiver試験後.received
-
Receiver試験前.received
```

### RegisteredCount

```text
Receiver試験後.registered
-
Receiver試験前.registered
```

### TotalBytes

Receiver試験後の records.csv の fileSize 列合計値。

### TotalMB

```text
TotalBytes ÷ 1024 ÷ 1024
```

---

## 出力

### CSV

```text
Output\ThroughputReport.csv
```

### JSON

```text
Output\ThroughputReport.json
```

---

## 出力項目

```text
TestID
SentCount
ReceivedCount
RegisteredCount
TotalBytes
TotalMB
```

---

## 実行方法

仮想環境有効化

```powershell
.\.venv\Scripts\Activate.ps1
```

実行

```powershell
python .\src\ThroughputAnalyzer.py
```

または

```powershell
.\run.bat
```

---

## 実行例

```text
===== RESULT =====

TestID              : sample01
SentCount           : 3
ReceivedCount       : 3
RegisteredCount     : 2
TotalBytes          : 161060
TotalMB             : 0.153599

==================
```

---

## 制約

- Sender試験前後フォルダが2個以上存在すること
- Receiver試験前後フォルダが2個以上存在すること
- all_results.json が存在すること
- records.csv が存在すること
- フォルダ名の時刻順で試験前後を判定すること

---

## 今後の拡張予定

### v1.1

- DurationSec
- FilesPerSec
- MBPerSec

### v1.2

- GUI対応
- グラフ表示

### v1.3

- 複数試験比較
- CSV一括集計

### v2.0

- PerformanceCounter連携
- CPU使用率集計
- メモリ使用率集計
- Network使用率集計

## Version

### v1.0

Completed

Functions

- SentCount
- ReceivedCount
- RegisteredCount
- TotalBytes
- TotalMB
