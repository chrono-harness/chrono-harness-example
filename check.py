from pathlib import Path
from runpy import run_path

# Load the current source even when Python has cached this module.
root = Path(__file__).parent
greeting = run_path(str(root / "message.py"))["greeting"]
cases = run_path(str(root / ".chrono-harness/ci/host_decisions.py"))["BUSINESS_CASES"]

assert greeting(Path("message.txt").read_text()) == "hello"
for text, expected in cases:
    assert greeting(text) == expected, (text, expected)
