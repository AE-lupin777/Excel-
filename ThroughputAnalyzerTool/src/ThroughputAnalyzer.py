from pathlib import Path
import subprocess
import sys

from tkinter import Tk
from tkinter import filedialog

def select_test_dir():

    root = Tk()
    root.withdraw()

    selected = filedialog.askdirectory(
        title="解析対象フォルダを選択"
    )

    root.destroy()

    if not selected:
        raise Exception(
            "フォルダが選択されませんでした。"
        )

    return Path(selected)

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"


def run_step(script_name, test_dir):

    script_path = (
        SRC_DIR / script_name
    )

    print()
    print(
        f"===== {script_name} START ====="
    )

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            str(test_dir)
        ]
    )

    if result.returncode != 0:

        raise Exception(
            f"{script_name} "
            f"failed."
        )

    print(
        f"===== {script_name} END ====="
    )
    print()


def main():

    print()
    print(
        "===================================="
    )
    print(
        " ThroughputAnalyzer START"
    )
    print(
        "===================================="
    )

    test_dir = select_test_dir()

    steps = [
        "EventReportGenerator.py",
        "ReportGenerator.py",
        "ExcelWriter.py"
    ]

    for step in steps:
        run_step(
            step,
            test_dir
        )

    print(
        "===================================="
    )
    print(
        " ThroughputAnalyzer COMPLETE"
    )
    print(
        "===================================="
    )
    print()

    print(
        f"Output : "
        f"{ROOT / 'output'}"
    )


if __name__ == "__main__":
    main()