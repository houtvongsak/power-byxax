"""Exercise the production update script against disposable local Git repos."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "bin/sync-stock"


class SyncTests(unittest.TestCase):
    def git(self, path, *args):
        return subprocess.check_output(["git", "-C", str(path), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def init(self, path):
        path.mkdir()
        self.git(path, "init", "-b", "upstream")
        self.git(path, "config", "user.name", "Sync Test")
        self.git(path, "config", "user.email", "test@example.invalid")

    def commit(self, path, message):
        self.git(path, "add", "-A")
        self.git(path, "commit", "-m", message)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo, self.official = root / "plugin", root / "official"
        self.init(self.repo)
        self.init(self.official)
        self.source = self.official / "shell/plugins/panels/power"
        self.source.mkdir(parents=True)
        files = {"Panel.qml": "// stock title\n// stock body\n", "Model.js": "// stock model\n", "Obsolete.qml": "// optional component\n",
                 "manifest.json": json.dumps({"id": "omarchy.power"})}
        for name, content in files.items():
            (self.source / name).write_text(content)
            (self.repo / name).write_text(content)
        (self.repo / "LICENSE").write_text("Original license\n")
        (self.official / "LICENSE").write_text("Original license\n")
        self.commit(self.repo, "Stock plugin")
        self.commit(self.official, "Official source")
        self.git(self.repo, "switch", "-c", "main")
        (self.repo / "bin").mkdir()
        shutil.copy2(SCRIPT, self.repo / "bin/sync-stock")
        (self.repo / "Panel.qml").write_text("// custom title\n// stock body\n")
        self.commit(self.repo, "Custom plugin")
        self.before = self.git(self.repo, "rev-parse", "main")
        self.failure = root / "conflicts.txt"

    def run_sync(self, *args):
        return subprocess.run(["bash", "bin/sync-stock", str(self.official), "v4.0.5", *args],
                              cwd=self.repo, env=dict(os.environ, SYNC_FAILURE_FILE=str(self.failure)),
                              capture_output=True, text=True)

    def test_unchanged_source_does_not_release(self):
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "false")
        self.assertEqual(self.git(self.repo, "rev-parse", "main"), self.before)

    def test_nonconflicting_update_preserves_customizations_and_deletions(self):
        (self.source / "Obsolete.qml").unlink()
        (self.source / "Helper.js").write_text("// new upstream helper\n")
        self.commit(self.official, "Upstream change")
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "true")
        self.assertIn("custom title", (self.repo / "Panel.qml").read_text())
        self.assertFalse((self.repo / "Obsolete.qml").exists())
        self.assertTrue((self.repo / "Helper.js").exists())
        self.assertEqual(self.git(self.repo, "status", "--porcelain"), "")

    def test_conflict_leaves_main_unchanged_and_clean(self):
        (self.source / "Panel.qml").write_text("// changed upstream title\n// stock body\n")
        self.commit(self.official, "Conflicting change")
        result = self.run_sync()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.git(self.repo, "rev-parse", "main"), self.before)
        self.assertEqual(self.git(self.repo, "branch", "--show-current"), "main")
        self.assertEqual(self.git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(self.failure.read_text().strip(), "Panel.qml")

    def test_invalid_source_is_rejected_before_touching_branches(self):
        (self.source / "manifest.json").write_text('{"id":"different.plugin"}')
        result = self.run_sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git(self.repo, "rev-parse", "main"), self.before)
        self.assertEqual(self.git(self.repo, "branch", "--show-current"), "main")

    def test_push_publishes_upstream_but_never_main(self):
        remote = Path(self.temp.name) / "remote.git"
        subprocess.check_call(["git", "clone", "-q", "--bare", str(self.repo), str(remote)])
        self.git(self.repo, "remote", "add", "origin", str(remote))
        (self.source / "Model.js").write_text("// updated model\n")
        self.commit(self.official, "Upstream model change")
        result = self.run_sync("--push")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git(remote, "rev-parse", "main"), self.before)
        self.assertEqual(self.git(remote, "rev-parse", "upstream"), self.git(self.repo, "rev-parse", "upstream"))

    def test_fresh_checkout_can_track_remote_upstream(self):
        remote = Path(self.temp.name) / "remote.git"
        clone = Path(self.temp.name) / "fresh"
        subprocess.check_call(["git", "clone", "-q", "--bare", str(self.repo), str(remote)])
        subprocess.check_call(["git", "clone", "-q", str(remote), str(clone)])
        self.git(clone, "config", "user.name", "Sync Test")
        self.git(clone, "config", "user.email", "test@example.invalid")
        self.repo = clone
        self.assertEqual(self.git(clone, "branch", "--format=%(refname:short)"), "main")
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "false")


if __name__ == "__main__":
    unittest.main()
