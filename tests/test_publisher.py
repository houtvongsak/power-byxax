"""Prove that privileged publishing operates on Git objects, not candidate code."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("publisher", Path(__file__).resolve().parents[1] / "bin/publish-sync.py")
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


class PublisherTests(unittest.TestCase):
    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-m', message)
        return self.git('rev-parse', 'HEAD')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-b', 'upstream')
        self.git('config', 'user.name', 'Publisher Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'Model.js').write_text('// upstream baseline\n')
        self.commit('Official baseline')
        self.git('switch', '-c', 'main')
        manifest = dict(id='io.github.houtvongsak.power-byxax', version='1.2.3', omarchy=dict(clonedFrom='omarchy.power'))
        (self.repo / 'manifest.json').write_text(json.dumps(manifest))
        (self.repo / 'bin').mkdir()
        (self.repo / 'bin/check').write_text('# trusted original validator\n')
        self.base = self.commit('Plugin base')
        remote = Path(self.temp.name) / 'remote.git'
        subprocess.check_call(['git', 'clone', '-q', '--bare', str(self.repo), str(remote)])
        self.git('remote', 'add', 'origin', str(remote))
        self.git('switch', 'upstream')
        (self.repo / 'Model.js').write_text("throw Error('Candidate code must not execute in publisher');\n")
        self.upstream = self.commit('Official update')
        self.git('switch', 'main')
        self.git('merge', '--no-edit', 'upstream')
        self.main = self.git('rev-parse', 'HEAD')
        self.bundle = Path(self.temp.name) / 'sync.bundle'

    def prepare(self):
        self.main = self.git('rev-parse', 'HEAD')
        self.git('bundle', 'create', str(self.bundle), 'main', 'upstream')
        self.git('reset', '--hard', self.base)

    def publish(self, **overrides):
        args = dict(bundle=self.bundle, base=self.base, main=self.main, upstream=self.upstream, tag='v4.0.5')
        args.update(overrides)
        before = Path.cwd()
        os.chdir(self.repo)
        try:
            return publisher.publish(**args)
        finally:
            os.chdir(before)

    def test_validated_tree_is_versioned_without_checkout_or_execution(self):
        self.prepare()
        result = self.publish()
        self.assertEqual(result['version'], '1.2.4')
        self.assertFalse(result['published'])
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual((self.repo / 'Model.js').read_text(), '// upstream baseline\n')
        released = json.loads(self.git('show', result['commit'] + ':manifest.json'))
        self.assertEqual(released['version'], '1.2.4')
        self.assertEqual(self.git('rev-parse', result['commit'] + '^'), self.main)

    def test_upstream_cannot_replace_automation_or_tests(self):
        (self.repo / 'bin/check').write_text('untrusted validator\n')
        self.commit('Replace trusted automation')
        self.prepare()
        with self.assertRaises(subprocess.CalledProcessError): self.publish()
        self.assertEqual(self.git('tag', '--list'), '')

    def test_bundle_commit_mismatch_is_rejected(self):
        self.prepare()
        with self.assertRaises(ValueError): self.publish(main=self.base)
        self.assertEqual(self.git('tag', '--list'), '')

    def test_manifest_symlink_is_rejected(self):
        manifest = self.repo / 'manifest.json'
        manifest.unlink()
        manifest.symlink_to('/tmp/outside-manifest.json')
        self.commit('Unsafe manifest type')
        self.prepare()
        with self.assertRaises(ValueError): self.publish()

    def test_remote_main_race_is_rejected(self):
        self.prepare()
        (self.repo / 'new-owner-change.txt').write_text('owner update\n')
        self.commit('Concurrent owner update')
        self.git('push', 'origin', 'main')
        self.git('reset', '--hard', self.base)
        with self.assertRaisesRegex(ValueError, 'Main changed'): self.publish()

    def test_unexpected_identity_is_rejected(self):
        (self.repo / 'manifest.json').write_text(json.dumps(dict(id='different.plugin', version='1.2.3')))
        self.commit('Unexpected plugin identity')
        self.prepare()
        with self.assertRaisesRegex(ValueError, 'identity'): self.publish()

    def test_inputs_are_validated_before_git_operations(self):
        self.prepare()
        with self.assertRaises(ValueError): self.publish(main='HEAD; echo bad')
        with self.assertRaises(ValueError): self.publish(tag='v4.0.5; echo bad')

    def test_publish_pushes_all_refs_without_running_candidate_code(self):
        self.prepare()
        with patch.object(publisher.subprocess, 'check_call') as github:
            result = self.publish(push=True)
        self.assertTrue(result['published'])
        self.assertEqual(self.git('ls-remote', 'origin', 'refs/heads/main').split()[0], result['commit'])
        self.assertEqual(self.git('ls-remote', 'origin', 'refs/heads/upstream').split()[0], self.upstream)
        self.assertIn('refs/tags/v1.2.4', self.git('ls-remote', 'origin', 'refs/tags/v1.2.4'))
        self.assertEqual(github.call_args.args[0][:4], ['gh', 'release', 'create', 'v1.2.4'])
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)


if __name__ == '__main__':
    unittest.main()
