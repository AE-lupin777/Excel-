EVENTS = {
    # [B] Senderが送信対象ファイルを検出した時点
    "B_START": {
        "source": "SenderLog",
        "pattern": "Discovered"
    },
    # [C] Senderがファイル送信を開始した時点
    "C_START": {
        "display_name": "Sender Sending",
        "source": "SenderLog",
        "pattern": "Sending",
        "timestamp_source": "LogTimestamp"
    },
    # [C] SenderがReceiverから受信完了応答を受領した時点
    "C_END": {
        "source": "SenderLog",
        "pattern": "Receiver durably accepted"
    },
    # [G] Receiver が受信データの永続保存を完了した時点
    "G_START": {
        "display_name": "Receiver Durably Stored",
        "source": "ReceiverLog",
        "pattern": "Receiver durably stored"
    },
    # [K] ULsight DB登録待ち状態へ遷移した時点
    "K_START": {
        "source": "ReceiverLog",
        "pattern": "registration is pending"
    },
    # [G] Receiver 管理状態が受信完了状態になった時点
    "G_END": {
        "display_name": "Receive Complete",
        "source": "ReceiverRecords",
        "condition": {
            "receiveStatus": "RECEIVED"
        },
        "timestamp_column": "updatedAt"
    },
    # [K]
    # Receiver管理状態が
    # registrationStatus=REGISTERED
    # になった時点
    #
    # ※運用上は
    # ULsight DB登録完了として扱う
    "K_END": {
        "display_name": "Registration Complete",
        "source": "ReceiverRecords",
        "condition": {
            "registrationStatus": "REGISTERED"
        },
        "timestamp_column": "updatedAt"
    },
    # [F] Senderリソース情報取得
    "F": {
        "source": "SenderResource"
    },
    # [J] Receiverリソース情報取得
    "J": {
        "source": "ReceiverResource"
    },
    # [L] Linuxリソース情報取得
    "L": {
        "source": "LinuxResource"
    }
}