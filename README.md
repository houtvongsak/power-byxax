# power-byxax

An Omarchy power panel based on the official `omarchy.power` plugin.

This repository currently contains the stock panel with its own plugin identity.
Clearer charging states, live current and voltage readings, and recent power
history are planned; they are not implemented yet.

## Source

- Official repository: [basecamp/omarchy](https://github.com/basecamp/omarchy)
- Baseline release: **v4.0.4**
- Source commit: `c668141e9c42b13c80c9ca4ea108e11708c5e8a5`
- Plugin directory: [`shell/plugins/panels/power`](https://github.com/basecamp/omarchy/tree/c668141e9c42b13c80c9ca4ea108e11708c5e8a5/shell/plugins/panels/power)
- Plugin ID: `io.github.houtvongsak.power-byxax`

The `upstream` branch preserves the original plugin files and Omarchy license.
The `main` branch contains this plugin's changes. Automatic upstream syncing
has not been configured yet.

`Panel.qml` and `Model.js` currently match the official source byte for byte.
The manifest identifies this as a clone of `omarchy.power`, keeping the original
IPC targets used by Omarchy.

## License

MIT; see [LICENSE](LICENSE). Original Omarchy code by David Heinemeier Hansson.
