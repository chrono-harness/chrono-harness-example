"""Small independent example program."""

from pathlib import Path
from runpy import run_path


decisions = run_path(str(Path(__file__).with_name(".chrono-harness") / "ci/host_decisions.py"))


def greeting(text):
    return text.strip(decisions["TRIM_CHARS"])

if __name__ == "__main__":
    print(greeting(Path("message.txt").read_text()))
