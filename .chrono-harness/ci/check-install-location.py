"""Exercise the installer without downloading any tools."""
import contextlib
import hashlib
import io
from itertools import product
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


INSTALLER = Path(__file__).resolve().with_name("install.sh")


class InstallLocation(unittest.TestCase):
    def test_storage_stays_outside_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkout = root / "checkout"
            checkout.mkdir()
            outside = root / "external tools"
            outside.mkdir()
            stub = root / "mise"
            stub.write_text(
                '#!/bin/sh\n'
                'case "$1" in\n'
                ' install) printf "%s" "$MISE_DATA_DIR" > "$INSTALL_CALLS";;\n'
                ' which) printf "%s/%s\\n" "$MISE_DATA_DIR" "$2";;\n'
                ' *) exit 1;;\n'
                'esac\n'
            )
            stub.chmod(0o755)
            log = root / "calls"
            env = {"HOME": str(root), "PATH": f"{root}{os.pathsep}{os.defpath}",
                   "INSTALL_CALLS": str(log)}
            alias = root / "points-inside"
            alias.symlink_to(checkout, target_is_directory=True)
            inner = checkout / "tools"

            def install(**settings):
                return subprocess.run(["/bin/sh", INSTALLER], cwd=checkout,
                                      env={**env, **settings}, capture_output=True)

            for key in ("CHRONO_EXAMPLE_INSTALL_ROOT", "MISE_DATA_DIR", "XDG_DATA_HOME",
                        "MISE_INSTALLS_DIR", "MISE_INSTALL_STORE_DIR", "MISE_DOWNLOADS_DIR"):
                with self.subTest(variable=key):
                    result = install(**{key: str(alias / "tools")})
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertFalse(inner.exists())
                    self.assertFalse(log.exists())

            result = install(MISE_DATA_DIR=str(inner), CHRONO_EXAMPLE_INSTALL_ROOT=str(outside))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text(), str(outside))
            self.assertEqual((checkout / ".chrono-harness/bin/chrono-worktree").readlink(),
                             outside / "chrono-worktree")
            self.assertFalse(inner.exists())


    def test_missing_manager_selects_hosted_platform(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkout = root / "checkout"
            checkout.mkdir()
            commands = root / "commands"
            commands.mkdir()
            for name in ("python3", "dirname", "mktemp", "rm"):
                (commands / name).symlink_to(shutil.which(name))
            log = root / "calls"

            def stub(name, body):
                path = commands / name
                path.write_text("#!/bin/sh\n" + body)
                path.chmod(0o755)

            stub("uname", 'case "$1" in -s) printf "%s\\n" "$TEST_OS";; -m) printf "%s\\n" "$TEST_ARCH";; esac\n')
            stub("curl", 'printf "%s\\n" "$2" >> "$INSTALL_CALLS"; exit 6\n')
            env = {"HOME": str(root), "PATH": str(commands), "RUNNER_TEMP": str(root),
                   "INSTALL_CALLS": str(log)}

            def install(**settings):
                log.write_text("")
                return subprocess.run(["/bin/sh", INSTALLER], cwd=checkout,
                                      env={**env, **settings}, capture_output=True)

            result = install()
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b"Install mise", result.stderr)
            self.assertEqual(log.read_text(), "")
            for os_name, arch, asset in (("Darwin", "arm64", "macos-arm64"),
                                          ("Linux", "x86_64", "linux-x64")):
                result = install(GITHUB_ACTIONS="true", TEST_OS=os_name, TEST_ARCH=arch)
                self.assertEqual(result.returncode, 6, result.stderr)
                self.assertTrue(log.read_text().strip().endswith(f"/mise-v2026.11.12-{asset}"))
                self.assertFalse(list(root.glob("example-mise.*")))
            result = install(GITHUB_ACTIONS="true", TEST_OS="Linux", TEST_ARCH="arm64")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b"Unsupported runner platform", result.stderr)
            self.assertEqual(log.read_text(), "")

    def test_rust_scope_and_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkout = root / "checkout"
            bins = checkout / ".chrono-harness/bin"
            bins.mkdir(parents=True)
            outside = root / "tools"
            outside.mkdir()
            stub = root / "mise"
            stub.write_text(
                '#!/bin/sh\n'
                'if [ "$1" = install ]; then printf "%s\\n" "$2" >> "$INSTALL_CALLS"; fi\n'
                'if [ "$1" = which ]; then printf "%s/%s\\n" "$MISE_DATA_DIR" "$2"; fi\n'
            )
            stub.chmod(0o755)
            log = root / "calls"
            env = {"HOME": str(root), "PATH": f"{root}{os.pathsep}{os.defpath}",
                   "CHRONO_EXAMPLE_INSTALL_ROOT": str(outside), "INSTALL_CALLS": str(log)}
            link = bins / "chrono-distribution"
            link.mkdir()

            def install(**settings):
                log.write_text("")
                return subprocess.run(["/bin/sh", INSTALLER], cwd=checkout,
                                      env={**env, **settings}, capture_output=True)

            result = install(GITHUB_ACTIONS="true", GITHUB_JOB="detect")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b"already exists", result.stderr)
            self.assertEqual(list(link.iterdir()), [])
            self.assertEqual(log.read_text().splitlines(), ["http:chrono-distribution"])

            link.rmdir()
            result = install(GITHUB_ACTIONS="true", GITHUB_JOB="unit_example")
            self.assertEqual(result.returncode, 0, result.stderr)
            target = outside / link.name
            self.assertEqual(link.readlink(), target)
            inode = link.lstat().st_ino
            result = install(GITHUB_ACTIONS="true", GITHUB_JOB="unit_harness")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(link.lstat().st_ino, inode)
            self.assertEqual(log.read_text().splitlines(), ["rust", "http:chrono-distribution"])

            link.unlink()
            link.symlink_to(root / "old")
            result = install()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(link.readlink(), target)
            self.assertEqual(log.read_text().splitlines(), ["rust", "http:chrono-distribution"])

            link.unlink()
            link.write_text("existing file")
            result = install(GITHUB_ACTIONS="true", GITHUB_JOB="aggregate")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(link.read_text(), "existing file")
            self.assertEqual(log.read_text().splitlines(), ["http:chrono-distribution"])


class ContextArchive(unittest.TestCase):
    def test_archive_keeps_original_and_rejects_in_field_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "workflow-output"
            original = Path.cwd()
            base, candidate = "a" * 40, "b" * 64
            context = {"schema_version": 2, "operation": "validate.delta", "base": base,
                       "candidate": candidate, "dev_tip": base}
            archive = INSTALLER.with_name("archive-context.py")

            def archive_context(raw, stream):
                with patch.dict(os.environ, FULL_CONTEXT=raw, GITHUB_OUTPUT=str(output)):
                    with contextlib.redirect_stdout(stream):
                        runpy.run_path(str(archive))

            with patch.object(sys, "path", [str(archive.parent), *sys.path]):
                try:
                    os.chdir(root)
                    expected = runpy.run_path(str(archive.with_name(
                        "host_decisions.py")))["CONTEXT_EXPECTED"]
                    errors = {"S": "expected full check context", "O": "expected full check context",
                              "B": "invalid fixed base", "C": "invalid fixed candidate",
                              "T": "the development tip differs"}
                    invalid = (1, "other", base.upper(), "b" * 41, "other")
                    for flags, first_failure in zip(product((False, True), repeat=5), expected):
                        if first_failure == "+":
                            continue
                        supplied = {field: value if good else bad
                                    for (field, value), good, bad in
                                    zip(context.items(), flags, invalid)}
                        with self.subTest(supplied=supplied):
                            with self.assertRaisesRegex(ValueError, errors[first_failure]):
                                archive_context(json.dumps(supplied), io.StringIO())
                            self.assertFalse(Path("context.json").exists())
                            self.assertFalse(output.exists())
                    raw = json.dumps(context, indent=2) + "\n"
                    stream = io.StringIO()
                    archive_context(raw, stream)
                    self.assertEqual(Path("context.json").read_bytes(), raw.encode())
                    self.assertEqual(output.read_text(), f"name=full-round-{candidate}-{base}\n")
                    digest = hashlib.sha256(raw.encode()).hexdigest()
                    self.assertEqual(stream.getvalue(), f"Context SHA-256 {digest}\n")
                finally:
                    os.chdir(original)


if __name__ == "__main__":
    unittest.main()
