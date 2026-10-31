# PerformanceCounter監視ツール

## 1. 概要

本ツールは Windows Performance Counter を利用して性能情報を収集し、BLG および CSV ファイルとして保存するツールです。

収集処理には常駐型の CollectorHost 方式を採用しています。

CollectorHost は初期化時に起動され、複数回の試験で再利用されます。これにより、2回目以降の収集開始時間を短縮できます。 【1-3e626b】【2-7b784e】

### 主な機能

- Performance Counter収集
- BLGファイル出力
- CSVファイル出力
- Start／Stop制御
- CollectorHost再利用
- Sender／Receiver対応
- 収集結果検証

---

## 2. フォルダ構成

```text
PersistentHost_ReadyCandidate/
├─ Initialize-PerformanceCollection.cmd
├─ README.md
├─ config/
│  ├─ counters.txt
│  ├─ counters.effective.txt
│  └─ role.conf
├─ scripts/
│  ├─ CollectorHost.ps1
│  ├─ Convert-PerformanceLog.ps1
│  ├─ HostCommon.ps1
│  ├─ PerformanceCollection.cmd
│  ├─ Setup-PerformanceCollection.ps1
│  ├─ Start-CollectorHost.ps1
│  ├─ Start-PerformanceCollection.ps1
│  ├─ Stop-CollectorHost.ps1
│  └─ Stop-PerformanceCollection.ps1
├─ logs/
└─ output/
```

### フォルダ説明

| フォルダ | 用途 |
|----------|------|
| config | 設定ファイル |
| scripts | 実行スクリプト |
| logs | ログ・状態ファイル |
| output | BLG・CSV出力 |

【1-3e626b】

---

## 3. 事前準備

### PowerShell

Windows PowerShell 管理者権限 を使用してください。CollectorHost は Windows PowerShell で動作します。 【1-3e626b】【2-7b784e】

### 管理者権限

初期設定時は管理者権限の PowerShell を推奨します。

### 配置

ツール一式を対象PCへ配置してください。

### 注意事項

過去に実行した別PCの状態ファイルをコピーしないでください。

以下のフォルダは実行環境ごとに生成されるため、別PCへ持ち込まないでください。

```text
logs
output
```

【1-3e626b】

---

## 4. 初期化

試験開始前に必ず実行してください。

### Sender側

```cmd
.\Initialize-PerformanceCollection.cmd sender
```

### Receiver側

```cmd
.\Initialize-PerformanceCollection.cmd receiver
```

初期化では以下を実施します。

- Role設定
- Performance Counter確認
- counters.effective.txt生成
- CollectorHost起動

【1-3e626b】

### 正常終了例

```text
Result : Ready
```

初期化完了後は CollectorHost が待機状態になります。 【1-3e626b】【2-7b784e】

---

## 5. 収集開始

収集を開始します。

```cmd
.\scripts\PerformanceCollection.cmd start TEST_001
```

TEST_001 の部分には試験名を指定してください。

例

```cmd
.\scripts\PerformanceCollection.cmd start FASTTEST
```

### 正常終了例

```text
Result            : Started
LifecycleStatus   : Running
```

Started が表示された時点で、Collector Pipeline が最初のサンプル取得に到達しています。 【3-a54f25】

---

## 6. 収集停止

収集を停止します。

```cmd
.\scripts\PerformanceCollection.cmd stop
```

### 正常終了例

```text
Result            : Stopped
LifecycleStatus   : CompletedValidated
```

CompletedValidated が表示された場合、以下が完了しています。

- 収集停止
- BLG検証
- CSV生成
- 出力整合性確認

【4-ab035c】

---

## 7. CollectorHost終了

すべての試験終了後に実行します。

```cmd
.\scripts\PerformanceCollection.cmd shutdown
```

### 正常終了例

```text
Result : Stopped
```

shutdown は試験ごとではなく、すべての試験終了後に一度だけ実行してください。 【1-3e626b】【5-2e92bd】

---

## 8. 推奨運用手順

```text
Initialize
    ↓
Start
    ↓
試験実施
    ↓
Stop

（必要回数繰り返す）

    ↓
shutdown
```

CollectorHost は Start／Stop のたびに再起動せず、試験期間中は再利用されます。 【1-3e626b】【2-7b784e】

---

## 9. 出力ファイル

### output

収集結果が保存されます。

```text
*.blg
*.csv
```

### logs

ログお*び状態ファイルが保存されます。

```text
*.log
col*ector-host.json
collector-run**.final.json
``*

*1-3e626b】【3-a54f25】【4-ab035c】*
*--

## 10. 出力確認項目

Stop*完*後は以下を確認してください。

###*BLG

```text**.blg
```

が生成されていること。

### CSV*
```text
*.csv
```

*生成されていること。

*## Stop結果

```text*LifecycleStatus : CompletedValidat*d
```

となっていること。

【4-ab035c】*
---

*# 11. トラ*ルシューティング

### Startできない

確認ファイル

`*`text
logs\collector-host.json
*ogs\*ollector-host.ready
```

*ollectorHost が Ready 状態であることを確認してく*さい。 *2-7b784e】

### Stopできない

確認ファイル

`*`text
logs\collection-state.json
l*gs\collector-run-*.final.json
*``

*集状態が残っていないか確認してください。 *4-ab035c】

### 初*化でエラーになる

初期化ログを保存してください。

特に*Export-Counter 関連エラーが発生する*合があります。 *1-3e626b】

---

## 12. 制約事項

以下は*評価または保証対象外です。

* 長*間収集
- スリープ復帰
- ロ*オフ
- CollectorHost強制終了後の復旧
-*書*かけBLGの復旧
* 高*荷環境での長時間連*運用

【1-3e626b】

---

## 13. 注意事項

* logs*フォルダおよび output フォルダの内容*別PCへコピーしないでください。
-*試験中は CollectorHost*を手動終了しないでください。
-*shutdown*実行*にすべての収集が停止していることを確認してください。
-*既存正式版との置き換えは*途評価*承認後に実施してください。

*1-3e626b】【2-7b784e】
````*