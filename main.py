import sys

from pathlib import Path
import json
import re

from generators import (
    generate_event,
    generate_sampling,
    generate_process
)

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QGroupBox,
    QFormLayout,
    QMessageBox,
    QInputDialog,
    QDialog
)


ROOT_DIR = Path(__file__).resolve().parent.parent
SCENARIO_DIR = ROOT_DIR / "scenarios"
APP_SETTINGS_FILE = ROOT_DIR / "config" / "app_settings.json"

DEFAULT_SAMPLING = {
    "data01": 100.25,
    "data02": 100.50,
    "data03": 100.75
}

INVALID_SCENARIO_NAME = re.compile(r'[<>:"/\\|?*]')

class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.app_settings = self.read_app_settings()
        self.current_sampling = dict(DEFAULT_SAMPLING)
        self.saved_scenario_snapshot = None
        self.active_scenario_name = None
        self.scenario_change_in_progress = False

        self.setWindowTitle(
            "ULAgent Test Data Designer"
        )

        self.resize(800, 600)

        widget = QWidget()

        self.setCentralWidget(widget)

        layout = QVBoxLayout(widget)

        #
        # シナリオ選択
        #
        layout.addWidget(
            QLabel("テストシナリオ")
        )

        self.scenario_combo = QComboBox()

        layout.addWidget(
            self.scenario_combo
        )

        scenario_button_layout = QHBoxLayout()

        self.new_scenario_button = QPushButton(
            "シナリオ 新規作成"
        )

        self.new_scenario_button.clicked.connect(
            self.new_scenario
        )

        scenario_button_layout.addWidget(
            self.new_scenario_button
        )

        self.save_as_button = QPushButton(
            "現在のシナリオに名前を付けて保存"
        )

        self.save_as_button.clicked.connect(
            self.save_scenario_as
        )

        scenario_button_layout.addWidget(
            self.save_as_button
        )

        self.delete_scenario_button = QPushButton(
            "現在のシナリオを削除"
        )

        self.delete_scenario_button.clicked.connect(
            self.delete_scenario
        )

        scenario_button_layout.addWidget(
            self.delete_scenario_button
        )

        layout.addLayout(
            scenario_button_layout
        )

        self.load_scenarios()

        #
        # 接続先
        #
        connection_group = QGroupBox(
            "接続先"
        )

        connection_layout = QFormLayout()

        self.connection_combo = QComboBox()

        self.connection_combo.addItems(
            [
                "PMC",
                "TMC",
                "CTC"
            ]
        )

        connection_layout.addRow(
            "Connection",
            self.connection_combo
        )

        connection_group.setLayout(
            connection_layout
        )

        layout.addWidget(
            connection_group
        )

        #
        # Chamber
        #
        chamber_group = QGroupBox(
            "Chamber"
        )

        chamber_layout = QFormLayout()

        self.chamber_combo = QComboBox()

        self.chamber_combo.addItems(
            [
                "Chamber-A",
                "Chamber-B",
                "Chamber-C"
            ]
        )

        chamber_layout.addRow(
            "Chamber",
            self.chamber_combo
        )

        chamber_group.setLayout(
            chamber_layout
        )

        layout.addWidget(
            chamber_group
        )

        #
        # EVENT
        #
        event_group = QGroupBox(
            "EVENT"
        )

        event_layout = QFormLayout()

        self.severity_combo = QComboBox()

        self.severity_combo.addItems(
            [
                "Info",
                "Warn",
                "Error"
            ]
        )

        self.message_edit = QLineEdit()

        self.message_edit.setText(
            "Test Start"
        )

        event_layout.addRow(
            "Severity",
            self.severity_combo
        )

        event_layout.addRow(
            "Message",
            self.message_edit
        )

        event_group.setLayout(
            event_layout
        )

        layout.addWidget(
            event_group
        )

        #
        # PROCESS
        #
        process_group = QGroupBox(
            "PROCESS"
        )

        process_layout = QFormLayout()

        self.lot_id_edit = QLineEdit()

        self.lot_id_edit.setText(
            "LOT-001"
        )

        self.recipe_edit = QLineEdit()

        self.recipe_edit.setText(
            "TEST_RECIPE_01"
        )

        self.wafer_id_edit = QLineEdit()

        self.wafer_id_edit.setText(
            "WF-001"
        )

        process_layout.addRow(
            "LotID",
            self.lot_id_edit
        )

        process_layout.addRow(
            "Recipe",
            self.recipe_edit
        )

        process_layout.addRow(
            "WaferID",
            self.wafer_id_edit
        )

        process_group.setLayout(
            process_layout
        )

        layout.addWidget(
            process_group
        )

        #
        # シナリオを上書き保存 ボタン
        #
        self.save_button = QPushButton(
            "シナリオを上書き保存"
        )

        self.save_button.clicked.connect(
            self.save_scenario
        )

        layout.addWidget(
            self.save_button
        )

        #
        # テストファイルを生成 ボタン
        #
        self.generate_button = QPushButton(
            "テストファイルを生成"
        )

        self.generate_button.clicked.connect(
            self.generate
        )

        layout.addWidget(
            self.generate_button
        )

        #
        # シナリオロード設定
        #
        self.scenario_combo.currentTextChanged.connect(
            self.on_scenario_changed
        )

        self.restore_last_scenario()

    @staticmethod
    def write_json(file_path, data):

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        temporary_file = file_path.with_suffix(
            file_path.suffix + ".tmp"
        )

        with open(
                temporary_file,
                "w",
                encoding="utf-8") as f:

            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False
            )

        temporary_file.replace(
            file_path
        )

    def create_confirmation_dialog(
            self,
            title,
            message,
            buttons,
            default_button):

        dialog = QMessageBox(
            QMessageBox.Icon.Question,
            title,
            message,
            buttons,
            self
        )

        dialog.setDefaultButton(
            default_button
        )

        button_labels = {
            QMessageBox.StandardButton.Save:
                "保存",
            QMessageBox.StandardButton.Discard:
                "保存しない",
            QMessageBox.StandardButton.Cancel:
                "キャンセル",
            QMessageBox.StandardButton.Yes:
                "はい",
            QMessageBox.StandardButton.No:
                "いいえ"
        }

        for standard_button, label in button_labels.items():

            button = dialog.button(
                standard_button
            )

            if button is not None:
                button.setText(label)

        return dialog

    def ask_confirmation(
            self,
            title,
            message,
            buttons,
            default_button):

        dialog = self.create_confirmation_dialog(
            title,
            message,
            buttons,
            default_button
        )

        return QMessageBox.StandardButton(
            dialog.exec()
        )

    def read_app_settings(self):

        if not APP_SETTINGS_FILE.exists():
            return {}

        try:

            with open(
                    APP_SETTINGS_FILE,
                    "r",
                    encoding="utf-8") as f:

                settings = json.load(f)

            if isinstance(settings, dict):
                return settings

        except (
                OSError,
                json.JSONDecodeError):

            pass

        return {}

    def save_app_settings(self):

        settings = {
            "schema_version": 1,
            "last_scenario":
                self.scenario_combo.currentText()
        }

        self.write_json(
            APP_SETTINGS_FILE,
            settings
        )

        self.app_settings = settings

    def restore_last_scenario(self):

        if self.scenario_combo.count() == 0:
            return

        scenario_name = self.app_settings.get(
            "last_scenario",
            "Normal"
        )

        index = self.scenario_combo.findText(
            scenario_name
        )

        if index < 0:
            index = 0

        self.scenario_change_in_progress = True

        try:
            self.scenario_combo.setCurrentIndex(
                index
            )

        finally:
            self.scenario_change_in_progress = False

        self.load_scenario()

    def select_scenario_without_signal(self, scenario_name):

        index = self.scenario_combo.findText(
            scenario_name
        )

        if index < 0:
            return False

        self.scenario_change_in_progress = True

        try:
            self.scenario_combo.setCurrentIndex(
                index
            )

        finally:
            self.scenario_change_in_progress = False

        return True

    def on_scenario_changed(self, scenario_name):

        if self.scenario_change_in_progress:
            return

        if not scenario_name:
            return

        previous_scenario = self.active_scenario_name

        if previous_scenario is None:
            self.load_scenario(scenario_name)
            return

        if scenario_name == previous_scenario:
            return

        if self.has_unsaved_scenario_changes():

            answer = self.ask_confirmation(
                "未保存の変更",
                (
                    f"{previous_scenario} の設定が変更されています。\n"
                    f"保存して {scenario_name} に切り替えますか？"
                ),
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )

            if answer == QMessageBox.StandardButton.Cancel:

                self.select_scenario_without_signal(
                    previous_scenario
                )

                return

            if answer == QMessageBox.StandardButton.Save:

                if not self.save_scenario_to_name(
                        previous_scenario,
                        select_saved_scenario=False,
                        show_message=False):

                    self.select_scenario_without_signal(
                        previous_scenario
                    )

                    return

        if not self.load_scenario(scenario_name):

            self.select_scenario_without_signal(
                previous_scenario
            )

    # def load_scenarios(self):

    #     if not SCENARIO_DIR.exists():
    #         return

    #     for file in sorted(
    #             SCENARIO_DIR.glob("*.json"),
    #             key=lambda path: path.stem.lower()):

    #         self.scenario_combo.addItem(
    #             file.stem
    #         )

    def load_scenarios(self):

        self.scenario_combo.clear()

        if not SCENARIO_DIR.exists():
            return

        for file in sorted(
                SCENARIO_DIR.glob("*.json"),
                key=lambda path: path.stem.lower()):

            self.scenario_combo.addItem(
                file.stem
            )

    def generate(self):

        event_data = {

            "source":
                self.connection_combo.currentText(),

            "severity":
                self.severity_combo.currentText(),

            "message":
                self.message_edit.text()
        }

        event_file = generate_event(
            **event_data
        )

        sampling_file = generate_sampling(
            self.current_sampling
        )

        process_data = {

            "lot_id":
                self.lot_id_edit.text(),

            "recipe":
                self.recipe_edit.text(),

            "wafer_id":
                self.wafer_id_edit.text()
        }

        process_file = generate_process(
            process_data
        )

        # QMessageBox.information(

        #     self,

        #     "完了",

        #     f"""EVENT生成完了

        #     {event_file}

        #     SAMPLING生成完了

        #     {sampling_file}

        #     PROCESS生成完了

        #     {process_file}
        #     """
        # )

        QMessageBox.information(
            self,
            "完了",
            (
                f"EVENT生成完*\n\n"
                f"{event_file}\n\n"
                f"SAMPLI*G生成完了\n\n"
                f"{sampling_file}\n\n"
                f"PROCESS生成完了\n\n"
                f"{process_file}"
            )
        )

    def save_scenario(self):

        scenario_name = self.scenario_combo.currentText()

        if not scenario_name:

            QMessageBox.warning(
                self,
                "エラー",
                "シナリオ名がありません"
            )

            return

        self.save_scenario_to_name(
            scenario_name
        )

    def get_current_scenario(self):

        return {

            "schema_version": 1,

            "connection":
                self.connection_combo.currentText(),

            "chamber":
                self.chamber_combo.currentText(),

            "event": {

                "source":
                    self.connection_combo.currentText(),

                "severity":
                    self.severity_combo.currentText(),

                "message":
                    self.message_edit.text()
            },

            "sampling":
                dict(self.current_sampling),

            "process": {

                "lot_id":
                    self.lot_id_edit.text(),

                "recipe":
                    self.recipe_edit.text(),

                "wafer_id":
                    self.wafer_id_edit.text()
            }
        }

    def save_scenario_to_name(
            self,
            scenario_name,
            select_saved_scenario=True,
            show_message=True):

        scenario_file = (
            SCENARIO_DIR
            / f"{scenario_name}.json"
        )

        try:

            self.write_json(
                scenario_file,
                self.get_current_scenario()
            )

        except OSError as error:

            QMessageBox.warning(
                self,
                "保存エラー",
                f"シナリオを保存できませんでした。\n\n{error}"
            )

            return False

        index = self.scenario_combo.findText(
            scenario_name
        )

        if index < 0:

            self.scenario_combo.addItem(
                scenario_name
            )

            index = self.scenario_combo.findText(
                scenario_name
            )

        if select_saved_scenario:

            self.select_scenario_without_signal(
                scenario_name
            )

            self.active_scenario_name = scenario_name

        self.saved_scenario_snapshot = (
            self.get_current_scenario()
        )

        if select_saved_scenario:
            self.save_app_settings()

        if show_message:

            QMessageBox.information(

                self,

                "保存完了",

                f"{scenario_name}.json を保存しました"
            )

        return True

    def validate_scenario_name(self, scenario_name):

        if not scenario_name:
            return "シナリオ名を入力してください"

        if scenario_name in {".", ".."}:
            return "このシナリオ名は使用できません"

        if INVALID_SCENARIO_NAME.search(
                scenario_name):

            return (
                "シナリオ名に使用できない文字が含まれています。\n"
                "使用できない文字: < > : \" / \\ | ? *"
            )

        return None

    def create_scenario_name_dialog(self, title):

        dialog = QInputDialog(
            self
        )

        dialog.setWindowTitle(
            title
        )

        dialog.setLabelText(
            "シナリオ名"
        )

        dialog.setOkButtonText(
            "決定"
        )

        dialog.setCancelButtonText(
            "キャンセル"
        )

        return dialog

    def ask_scenario_name(self, title):

        dialog = self.create_scenario_name_dialog(
            title
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        scenario_name = dialog.textValue().strip()

        error_message = self.validate_scenario_name(
            scenario_name
        )

        if error_message:

            QMessageBox.warning(
                self,
                "入力エラー",
                error_message
            )

            return None

        return scenario_name

    def find_scenario_file(self, scenario_name):

        if not SCENARIO_DIR.exists():
            return None

        for file in SCENARIO_DIR.glob("*.json"):

            if file.stem.casefold() == scenario_name.casefold():
                return file

        return None

    def reset_scenario_fields(self):

        self.connection_combo.setCurrentText(
            "PMC"
        )

        self.chamber_combo.setCurrentText(
            "Chamber-A"
        )

        self.severity_combo.setCurrentText(
            "Info"
        )

        self.message_edit.setText(
            "Test Start"
        )

        self.lot_id_edit.setText(
            "LOT-001"
        )

        self.recipe_edit.setText(
            "TEST_RECIPE_01"
        )

        self.wafer_id_edit.setText(
            "WF-001"
        )

        self.current_sampling = dict(
            DEFAULT_SAMPLING
        )

    def new_scenario(self):

        if self.has_unsaved_scenario_changes():

            current_scenario = self.active_scenario_name

            answer = self.ask_confirmation(
                "未保存の変更",
                (
                    f"{current_scenario} の設定が変更されています。\n"
                    "保存して新しいシナリオを作成しますか？"
                ),
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )

            if answer == QMessageBox.StandardButton.Cancel:
                return

            if answer == QMessageBox.StandardButton.Save:

                if not current_scenario:

                    QMessageBox.warning(
                        self,
                        "保存エラー",
                        "保存先のシナリオがありません"
                    )

                    return

                if not self.save_scenario_to_name(
                        current_scenario,
                        select_saved_scenario=False,
                        show_message=False):

                    return

        scenario_name = self.ask_scenario_name(
            "新規シナリオ"
        )

        if scenario_name is None:
            return

        if self.find_scenario_file(scenario_name):

            QMessageBox.warning(
                self,
                "保存エラー",
                "同じ名前のシナリオが存在します"
            )

            return

        self.reset_scenario_fields()

        self.save_scenario_to_name(
            scenario_name
        )

    def save_scenario_as(self):

        scenario_name = self.ask_scenario_name(
            "名前を付けて保存"
        )

        if scenario_name is None:
            return

        existing_file = self.find_scenario_file(
            scenario_name
        )

        if existing_file:

            answer = self.ask_confirmation(
                "上書き確認",
                f"{existing_file.name} は既に存在します。上書きしますか？",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if answer != QMessageBox.StandardButton.Yes:
                return

            scenario_name = existing_file.stem

        self.save_scenario_to_name(
            scenario_name
        )

    def delete_scenario(self):

        scenario_name = self.scenario_combo.currentText()

        if not scenario_name:
            return

        scenario_file = self.find_scenario_file(
            scenario_name
        )

        if scenario_file is None:

            QMessageBox.warning(
                self,
                "削除エラー",
                "シナリオファイルが見つかりません"
            )

            return

        answer = self.ask_confirmation(
            "削除確認",
            f"{scenario_file.name} を削除しますか？",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            scenario_file.unlink()

        except OSError as error:

            QMessageBox.warning(
                self,
                "削除エラー",
                f"シナリオを削除できませんでした。\n\n{error}"
            )

            return

        index = self.scenario_combo.currentIndex()

        self.scenario_change_in_progress = True

        try:
            self.scenario_combo.removeItem(
                index
            )

        finally:
            self.scenario_change_in_progress = False

        self.active_scenario_name = None
        self.saved_scenario_snapshot = None

        if self.scenario_combo.count() > 0:
            self.load_scenario()

        self.save_app_settings()

        QMessageBox.information(
            self,
            "削除完了",
            f"{scenario_file.name} を削除しました"
        )

    def load_scenario(self, scenario_name=None):

        if scenario_name is None:
            scenario_name = self.scenario_combo.currentText()

        if not scenario_name:
            return False

        scenario_file = self.find_scenario_file(
            scenario_name
        )

        if scenario_file is None:
            return False

        try:

            with open(
                    scenario_file,
                    "r",
                    encoding="utf-8") as f:

                scenario = json.load(f)

            event = scenario["event"]
            sampling = scenario["sampling"]
            process = scenario["process"]

            if not all(
                    isinstance(section, dict)
                    for section in (
                        event,
                        sampling,
                        process
                    )):

                raise TypeError(
                    "event, sampling and process must be objects"
                )

            self.current_sampling = {
                "data01": sampling["data01"],
                "data02": sampling["data02"],
                "data03": sampling["data03"]
            }

            connection = scenario.get(
                "connection",
                event.get("source", "PMC")
            )

            chamber = scenario.get(
                "chamber",
                "Chamber-A"
            )

            severity = event["severity"]
            message = event["message"]
            lot_id = process["lot_id"]
            recipe = process["recipe"]
            wafer_id = process["wafer_id"]

        except (
                OSError,
                json.JSONDecodeError,
                KeyError,
                TypeError) as error:

            QMessageBox.warning(
                self,
                "読込エラー",
                f"{scenario_file.name} を読み込めませんでした。\n\n{error}"
            )

            return False
        connection_index = self.connection_combo.findText(
            connection
        )

        if connection_index >= 0:
            self.connection_combo.setCurrentIndex(
                connection_index
            )
        chamber_index = self.chamber_combo.findText(
            chamber
        )

        if chamber_index >= 0:
            self.chamber_combo.setCurrentIndex(
                chamber_index
            )

        #
        # EVENT
        #
        index = self.severity_combo.findText(
            severity
        )

        if index >= 0:
            self.severity_combo.setCurrentIndex(
                index
            )

        self.message_edit.setText(
            message
        )

        #
        # PROCESS
        #
        self.lot_id_edit.setText(
            lot_id
        )

        self.recipe_edit.setText(
            recipe
        )

        self.wafer_id_edit.setText(
            wafer_id
        )

        self.saved_scenario_snapshot = (
            self.get_current_scenario()
        )

        self.active_scenario_name = scenario_name

        return True

    def has_unsaved_scenario_changes(self):

        if self.saved_scenario_snapshot is None:
            return False

        return (
            self.get_current_scenario()
            != self.saved_scenario_snapshot
        )

    def closeEvent(self, event):

        if self.has_unsaved_scenario_changes():

            answer = self.ask_confirmation(
                "未保存の変更",
                (
                    "シナリオ設定が変更されています。\n"
                    "保存して終了しますか？"
                ),
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )

            if answer == QMessageBox.StandardButton.Cancel:

                event.ignore()
                return

            if answer == QMessageBox.StandardButton.Save:

                scenario_name = (
                    self.scenario_combo.currentText()
                )

                if not scenario_name:

                    QMessageBox.warning(
                        self,
                        "保存エラー",
                        "保存先のシナリオがありません"
                    )

                    event.ignore()
                    return

                if not self.save_scenario_to_name(
                        scenario_name):

                    event.ignore()
                    return

        try:
            self.save_app_settings()

        except OSError as error:

            QMessageBox.warning(
                self,
                "設定保存エラー",
                f"アプリ設定を保存できませんでした。\n\n{error}"
            )

        super().closeEvent(event)


def main():

    app = QApplication(sys.argv)

    window = MainWindow()

    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
