# Maintaining power-byxax

## Code boundaries

- `Panel.qml`, `Model.js`: stock Omarchy files. Keep panel changes focused on hooks.
- `bin/telemetry.py`: read-only, hardware-independent discovery, UPower fallback, bounded local history.
- `Diagnostics.js`: pure status rules, smoothing, durations, graph series. Test under Node.
- `PowerStore.qml`: shared collector lifecycle; one process for all bars/monitors in a shell.
- `BatteryDetails.qml`, `TrendGraph.qml`: added interface and graphs.

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

Clean merges run `bin/check` through `bin/release`, then publish a patch version.
Conflicts abort the local merge; test failures stop before publishing main.
Any failed sync opens a deduplicated GitHub issue. The pristine upstream branch
may already be pushed when a merge or validation fails, so check both branches.

To resolve an upstream conflict:

```sh
git pull --ff-only
git fetch origin
git merge origin/upstream
# Resolve the conflicts, then:
git add <resolved-files>
git commit
bin/check
bin/smoke
git push
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
state storage. It checks two successive live samples without opening its popup
or changing the installed bar. `bin/preview` renders `BatteryDetails.qml` in an
isolated window to a PNG; it does not capture desktop content.

For fake hardware, put plain-text sysfs-style attributes in a temporary directory:

```sh
python3 bin/telemetry.py --sysfs /tmp/fake-power-supply --no-upower
```

Use `--state-file /tmp/power-history.json --watch` to exercise recorded history.
The collector keeps at most 361 samples and 40 events, pruned to 30 minutes.
