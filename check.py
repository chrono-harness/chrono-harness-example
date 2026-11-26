import sys
from pathlib import Path

# This qualification checkout records the source bytes actually compiled by
# Python's ordinary import of the example. The application has no dependencies.
module_path = str(Path(__file__).resolve().with_name("message.py"))
compiled_source = []


def observe_compile(event, arguments):
    if event == "compile":
        source, filename = arguments
        if filename == module_path:
            compiled_source.append(source)


sys.addaudithook(observe_compile)
from message import greeting

assert __debug__ and len(compiled_source) == 1
assert greeting.__code__.co_filename == module_path
business_text = Path("message.txt").read_text(encoding="utf-8")
assert greeting(business_text) == "hello"
assert greeting("  hello  ") == "hello"
assert greeting("\t\n") == ""
assert greeting("  hello world\n") == "hello world"

print("compiled message.py", compiled_source[0].hex())
print("decoded message.txt", business_text.encode("utf-8").hex())
