"""Release gates run against local remotes and a fake GitHub executable."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "bin/release"


class ReleaseTests(unittest.TestCase):
    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo = root / "plugin"
        self.repo.mkdir()
        (self.repo / "bin").mkdir()
        shutil.copy2(SCRIPT, self.repo / "bin/release")
        (self.repo / "bin/check").write_text("#!/usr/bin/env bash\nexit 0\n")
        (self.repo / "bin/check").chmod(0o755)
        (self.repo / "manifest.json").write_text('{"version":"1.2.3"}\n')
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Release Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("add", "-A")
        self.git("commit", "-m", "Initial version")
        self.before = self.git("rev-parse", "HEAD")
        self.remote = root / "remote.git"
        subprocess.check_call(["git", "clone", "-q", "--bare", str(self.repo), str(self.remote)])
        self.git("remote", "add", "origin", str(self.remote))
        fakebin = root / "fakebin"
        fakebin.mkdir()
        gh = fakebin / "gh"
        gh.write_text("""#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
notes = pathlib.Path(args[args.index('--notes-file')+1]).read_text()
pathlib.Path(os.environ['RELEASE_TEST_LOG']).write_text(json.dumps({'args':args,'notes':notes}))
""")
        gh.chmod(0o755)
        self.log = root / "gh-call.json"
        self.env = dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ["PATH"], RELEASE_TEST_LOG=str(self.log))

    def run_release(self, part="patch", notes="First line\nSecond line"):
        return subprocess.run(["bash", "bin/release", part, notes], cwd=self.repo,
                              env=self.env, capture_output=True, text=True)

    def test_failed_checks_do_not_change_version_push_or_publish(self):
        (self.repo / "bin/check").write_text("#!/usr/bin/env bash\nexit 1\n")
        self.git("add", "bin/check")
        self.git("commit", "-m", "Fail validation")
        before = self.git("rev-parse", "HEAD")
        result = self.run_release()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), before)
        self.assertEqual(json.loads((self.repo / "manifest.json").read_text())["version"], "1.2.3")
        self.assertEqual(self.git("tag", "--list"), "")
        self.assertFalse(self.log.exists())

    def test_success_pushes_version_and_tag_and_preserves_release_notes(self):
        result = self.run_release()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.repo / "manifest.json").read_text())["version"], "1.2.4")
        remote = subprocess.check_output(["git", "--git-dir", str(self.remote), "rev-parse", "main"], text=True).strip()
        self.assertEqual(remote, self.git("rev-parse", "HEAD"))
        self.assertEqual(self.git("tag", "--list"), "v1.2.4")
        log = json.loads(self.log.read_text())
        self.assertEqual(log["args"][:3], ["release", "create", "v1.2.4"])
        self.assertEqual(log["notes"], "First line\nSecond line\n")

    def test_dirty_tree_is_rejected_before_version_change(self):
        (self.repo / "unfinished.txt").write_text("unfinished work")
        result = self.run_release()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.before)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
