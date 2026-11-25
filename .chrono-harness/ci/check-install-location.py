"""Exercise the installer without downloading any tools."""
import json
import os
import resource
from pathlib import Path
import subprocess
import tempfile
import unittest


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


if __name__ == "__main__":
    soft_limit, _ = resource.getrlimit(resource.RLIMIT_FSIZE)
    # Darwin and Linux represent infinity differently.
    file_size_limit = None if soft_limit == resource.RLIM_INFINITY else soft_limit
    print(json.dumps({"rlimit_fsize_bytes": file_size_limit}), flush=True)
    unittest.main()
