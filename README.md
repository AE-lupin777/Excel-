# PerformanceCounter監視ツール（常駐CollectorHost方式・評価候補）

## 1. 位置付け

Windows PowerShell 5.1で常駐するCollectorHostを初期化時に起動し、試験ごとに再利用する改善版です。`Get-Counter` の実収集パイプラインが最初のサンプルを出力した時点をReady条件とし、BLG・CSV出力、TestId管理、Start／Stopを行います。

**現時点では評価候補です。既存の正式版を置き換えないでください。** Sender側の基本動作は実機確認済みですが、Receiver側は未確認です。

## 2. 配布フォルダ構成

```text
PersistentHost_ReadyCandidate/
├─ Initialize-PerformanceCollection.cmd
├─ README.md
├─ config/
│  └─ counters.txt
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
├─ logs/      （実行ログ・状態ファイルの出力先）
└─ output/    （BLG・CSVの出力先）
```

`config/role.conf` は初期化時にSender／Receiverの指定を書き込みます。`config/counters.effective.txt` はSetupで実行PCの取得可能なカウンターを判定して生成・更新します。`logs` と `output` の過去の実行結果や状態ファイルは、別PCへコピーしないでください。

開発用の `Test-*.ps1`、`Setup-PerformanceCollection_BOMTest.ps1`、`Setup-PerformanceCollection_Diagnostic.ps1` は上記の通常運用用構成には含めません。`PerformanceCollection.cmd test` はテストスクリプトを別途配置した開発環境向けで、通常配布版では使用しません。

## 3. 初期化と操作

PowerShellで本フォルダへ移動したうえで実行します。実機での操作は許可された検証環境で行ってください。

**Sender側の初期化**

```powershell
.\Initialize-PerformanceCollection.cmd sender
```

**Receiver側の初期化**

```powershell
.\Initialize-PerformanceCollection.cmd receiver
```

初期化CMDはRoleを設定し、Setupを実行します。Setupは実行環境・カウンターを確認し、`counters.effective.txt` を更新してCollectorHostを起動します。**初期化時に自動収集テストは実行しません。**

**収集開始・停止・Host終了**

```powershell
.\scripts\PerformanceCollection.cmd start TEST_001
# 必要な時間だけ収集する
.\scripts\PerformanceCollection.cmd stop
# 別の試験を行う場合は start／stop を繰り返す
.\scripts\PerformanceCollection.cmd shutdown
```

`shutdown` は各試験のたびではなく、すべての試験終了時に実行します。`start` がStartedを返したら実際の最初のカウンターサンプルに到達しています。`stop` 後にBLG・CSV、サンプル数、カウンター数、CSV行・列数を確認してください。

## 4. 状態管理・安全性

- HostはPIDだけでなくHostId、プロセス起動時刻、実行ファイルパスで照合します。
- Readyファイル欠落や状態不整合時に、同一Hostの重複起動を防ぐ仕組みがあります。
- RunIdをBLG・CSV・ログ・要求／完了状態に使用します。
- JSON状態更新には一時ファイルと置換を使用します。
- Start失敗時は停止要求を送り、完了確認後にActive状態を整理します。
- 正常完了は `CompletedValidated`、Start失敗後の整理完了は `StartFailedCleaned` として扱います。
- 異常時は状態・BLG・ログなどの証跡を残し、Stop／shutdownは識別が一致しないプロセスを強制終了しません。

## 5. 確認済み結果（2026-10-11）

**客PC・Sender側**：Setup成功、`ConfiguredCount=14`、`EffectiveCount=16`、`SkippedCount=0`。同一CollectorHostで3回連続Start／Stop成功、各回BLG・CSV生成成功、shutdown成功。

| 試験 | Start内部計測 |
|---|---:|
| 1回目 | 7.449秒 |
| 2回目 | 1.827秒 |
| 3回目 | 1.786秒 |

初回は遅く、Host再利用時の2・3回目は約1.8秒でした。現行版と厳密に同じ方法での速度比較は未完了です。**Receiver側の実機動作は未確認です。**

## 6. 既知の問題・制約

- `Setup-PerformanceCollection.ps1` で、`Export-Counter` が見つからないエラーが断続的に発生した実績があります。原因は未特定です。初期化でエラーが出た場合は、収集開始せず結果を記録してください。
- プロセスが存在しないPCでは、そのプロセス用カウンターがスキップされます。`SkippedCount` は対象PCのRole・プロセス稼働状況を踏まえて判断してください。
- 長時間収集、スリープ、ログオフ、Host強制終了時の書きかけBLG復旧、Receiver側の実環境については未検証です。書きかけBLGの復旧は保証しません。
- 正式採用・既存ツールへの置換は別途判断してください。
