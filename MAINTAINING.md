# Maintaining power-byxax

## Code boundaries

- `Panel.qml`, `Model.js`: stock Omarchy files. Keep panel changes focused on hooks.
- `bin/telemetry.py`: read-only, hardware-independent discovery, UPower fallback, bounded local history.
- `Diagnostics.js`: pure status rules, smoothing, durations, graph series. Test under Node.
- `PowerStore.qml`: shared collector lifecycle; one process for all bars/monitors in a shell.
- `BatteryDetails.qml`, `HistoryView.qml`, `TrendGraph.qml`: compact interface, optional details, and lazily loaded graphs.

No collector code writes charge thresholds, changes power profiles, or attempts
battery recovery. The stock power-profile controls remain deliberate user actions.

## Upstream tracking

`upstream` contains the official power plugin directory and root Omarchy license.
Its commit message records the release tag and exact source commit. The initial
baseline is v4.0.4, `c668141e9c42b13c80c9ca4ea108e11708c5e8a5`.

`.github/workflows/sync-omarchy.yml` checks the latest stable GitHub release every
Monday, and supports **Run workflow**. It uses the same tested `bin/sync-stock`
script available locally. That script validates the source, mirrors upstream
including deletions, and merges into main. It never pushes main itself.

Clean merges run `bin/check` in a job with read-only repository permissions.
Validated main/upstream commits are transferred as an immutable workflow artifact.
A separate job starts from the trusted workflow commit and runs
`bin/publish-sync.py`. It checks the bundle's exact commits, ancestry, current
remote main, plugin identity, and manifest file type. It refuses changes to
`.github`, `bin`, or `tests`, and never checks out or executes candidate code.
The publisher versions the validated tree using an alternate Git index, then
atomically pushes main, upstream, and the release tag. Only this job can publish;
a third job has issue-writing permission solely for failure reports.

Conflicts or test failures leave both remote branches unchanged and open a GitHub
issue linking the run. The unchanged-source path creates no release. A concurrent
owner update stops publishing and requires a new workflow run. If GitHub release
creation fails after an atomic push, inspect the refs and retry only that operation.

To resolve an upstream conflict:

```sh
git pull --ff-only
git fetch origin
# Fetch the official tag shown in the failed run, then mirror it locally:
git clone --depth 1 --branch <official-tag> https://github.com/basecamp/omarchy.git /tmp/omarchy-source
bin/sync-stock /tmp/omarchy-source <official-tag>
# For a conflict, rerun `git merge upstream`, resolve it, then:
git add <resolved-files>
git commit
bin/check
bin/smoke
git push --atomic origin main upstream
```

If an upstream release moves the power plugin or removes required entry files,
the sync stops for manual adaptation. Passing checks cover the simulated
scenarios and QML syntax; they do not establish runtime compatibility on every
laptop or with every future shell API. Test runtime/UI after substantial changes.

## Release

Commit changes on main, then run:

```sh
bin/release patch "Fixed X"
bin/release minor "Added Y"
```

The script runs checks before changing the version, creates the release commit
and annotated tag, atomically pushes both refs, and creates a GitHub release.
GitHub authentication and permission to push are required. If creating the
GitHub release fails after the push, inspect remote refs and retry only the
missing release operation; do not blindly bump again.

The upstream workflow uses a shared concurrency group to serialize its releases.
It does not change repository notification/watch settings.

## Local testing

`bin/check` exercises paused/slow/normal charging, missing sensors, stale and
conflicting readings, multiple packs, UPower threshold metadata, persistence,
connection events, and Git merge/conflict behavior. It parses all QML files when
`qmlformat` is installed, and uses Omarchy's manifest validator when available.
CI requires QML parsing.

`bin/smoke` starts a separate Quickshell config with the real panel and temporary
state storage. It checks two successive live samples and verifies graph objects
are created only while open, without opening its popup
or changing the installed bar. `bin/preview` renders `BatteryDetails.qml` in an
isolated window to a PNG; it does not capture desktop content.

For fake hardware, put plain-text sysfs-style attributes in a temporary directory:

```sh
python3 bin/telemetry.py --sysfs /tmp/fake-power-supply --no-upower
```

Use `--state-file /tmp/power-history.json --watch` to exercise recorded history.
The collector keeps at most 361 samples and 40 events, pruned to 30 minutes.
History omits repeated metadata and is held in memory, with durable file
checkpoints once a minute, immediately on events, and at normal shutdown.
An abrupt crash can lose the last minute. File permissions remain 0600.
A temporary storage failure preserves in-memory history and keeps the error
visible; saving is retried. Invalid encoding, malformed/deep JSON, and nonfinite
historical metrics are handled without a restart loop.

## Performance audit

A matched 65-second run on the development laptop used a prefilled 361-sample
history and discarded stdout. CPU includes child processes; disk writes come
from `/proc/<pid>/io` on the user's disk-backed cache directory.

| Collector | v1.0.0 | Audited version |
|---|---:|---:|
| CPU, one-core average | 0.86% | 0.14% |
| Resident memory | 20.4 MiB | 19.4 MiB |
| Disk writes during the run | 3.43 MB | 0.15 MB |
| Persisted history size | 252 KB | 69 KB |

These are short-run measurements on one laptop, not universal hardware results.
The original stock widget uses the shared shell/UPower service and has no
persistent Python collector. The added collector's roughly 20 MB resident cost
is the remaining tradeoff for background history and sensor interpretation.
No third-party Python or Node runtime packages were added.

The audit also removed unused stock battery/system polling, dormant rotating
phrases/animations, and unused statistics components. The popup uses the stock
380-unit width; advanced details are collapsed and graphs are unloaded when the
popup closes. Keyboard profile navigation scrolls the controls into view.

Installed updates must be followed by `omarchy restart shell` on shells that
retain QML/IPC caches. An isolated smoke test always uses a fresh engine and does
not establish that a running desktop has reloaded updated code. Verify a new
collector PID and the installed IPC methods after restarting.
