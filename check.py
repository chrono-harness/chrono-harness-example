from pathlib import Path
from runpy import run_path

# Load the checked-out source even when Python has cached this module.
greeting = run_path(str(Path(__file__).with_name("message.py")))["greeting"]

assert greeting(Path("message.txt").read_text()) == "hello"
assert greeting("  hello  ") == "hello"
assert greeting("\t\n") == ""
assert greeting("  hello world\n") == "hello world"
