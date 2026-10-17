#!/usr/bin/env python3
"""Publish a validated upstream bundle without checking out or executing its code."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def git(*args, data=None, env=None):
    return subprocess.check_output(["git", *args], input=data, text=True, env=env).strip()


def publish(bundle, base, main, upstream, tag, push=False):
    for sha in (base, main, upstream):
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Invalid source commit")
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("Invalid official release tag")
    bundle = Path(bundle)
    if not bundle.is_file() or bundle.is_symlink() or bundle.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Invalid or oversized Git bundle")
    if git("rev-parse", "HEAD") != base or git("status", "--porcelain"):
        raise ValueError("Publisher must start from the clean, trusted base commit")
    remote_base = git("ls-remote", "origin", "refs/heads/main").split()[0]
    if remote_base != base:
        raise ValueError("Main changed during validation; rerun the workflow")
    git("bundle", "verify", str(bundle.resolve()))
    git("fetch", "--no-tags", "--no-recurse-submodules", str(bundle.resolve()),
        "refs/heads/main:refs/power-byxax/candidate",
        "refs/heads/upstream:refs/power-byxax/upstream")
    if git("rev-parse", "refs/power-byxax/candidate") != main or git("rev-parse", "refs/power-byxax/upstream") != upstream:
        raise ValueError("Bundle commits do not match validation outputs")
    git("merge-base", "--is-ancestor", base, main)
    git("merge-base", "--is-ancestor", upstream, main)
    old_upstream = git("ls-remote", "origin", "refs/heads/upstream").split()[0]
    git("merge-base", "--is-ancestor", old_upstream, upstream)
    # Runtime upstream updates cannot rewrite our tests, CI or publisher.
    git("diff", "--exit-code", base, main, "--", ".github", "bin", "tests")
    tree_entry = git("ls-tree", main, "--", "manifest.json").split()
    if len(tree_entry) < 4 or tree_entry[0] != "100644":
        raise ValueError("Manifest must be a regular tracked file")
    manifest = json.loads(git("show", main + ":manifest.json"))
    if manifest.get("id") != "io.github.houtvongsak.power-byxax" or manifest.get("omarchy", {}).get("clonedFrom") != "omarchy.power":
        raise ValueError("Upstream changed this plugin's identity")
    if not re.fullmatch(r"\d+\.\d+\.\d+", manifest.get("version", "")):
        raise ValueError("Invalid plugin version")
    major, minor, patch = map(int, manifest["version"].split("."))
    version = f"{major}.{minor}.{patch + 1}"
    manifest["version"] = version
    blob = git("hash-object", "-w", "--stdin", data=json.dumps(manifest, indent=2) + "\n")
    with tempfile.TemporaryDirectory(prefix="power-sync-index-") as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"))
        git("read-tree", main, env=env)
        git("update-index", "--add", "--cacheinfo", "100644," + blob + ",manifest.json", env=env)
        tree = git("write-tree", env=env)
    notes = f"Synced the official power plugin from Omarchy {tag}; automated checks passed."
    commit = git("commit-tree", tree, "-p", main, "-m", f"Release v{version}", "-m", notes)
    git("tag", "-a", "v" + version, commit, "-m", "v" + version, "-m", notes)
    if push:
        git("push", "--atomic", "origin", commit + ":refs/heads/main",
            upstream + ":refs/heads/upstream", "refs/tags/v" + version)
        with tempfile.TemporaryDirectory(prefix="power-sync-notes-") as tmp:
            body = Path(tmp) / "notes.txt"
            body.write_text(notes + "\n")
            subprocess.check_call(["gh", "release", "create", "v" + version, "--verify-tag",
                                   "--title", "v" + version, "--notes-file", str(body)])
    return {"version": version, "commit": commit, "published": push}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "base", "main", "upstream", "tag"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    print(json.dumps(publish(args.bundle, args.base, args.main, args.upstream, args.tag, args.publish)))
