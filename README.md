# power-byxax

A clearer replacement for Omarchy's power widget: charging states, live current,
voltage and watts, plus 30 minutes of local history. Keeps the original power-profile
controls and theme styling.

<img src="preview.png" width="520" alt="Power panel preview using simulated battery readings">

## Install

Requires **Omarchy 4.0.4 or a compatible later version**, and **Python 3**.
No build steps or extra Python libraries.

```sh
omarchy plugin add https://github.com/houtvongsak/power-byxax.git --enable --yes
```

Automatically replaces the built-in power widget and detects battery sensors.
Missing readings show **Unavailable**. Hardware support depends on your laptop's
Linux drivers.

## Use

- **Left-click** opens the panel; **right-click** toggles the bar percentage.
- **d** toggles battery details; **g** toggles history. Both collapse when you close the popup.
- Select a battery when your laptop has multiple packs.

Readings update every 5 seconds. History stays on your device and records while
the popup is closed.

## Update

```sh
omarchy plugin update io.github.houtvongsak.power-byxax
omarchy restart shell
```

## Uninstall

```sh
omarchy plugin remove io.github.houtvongsak.power-byxax
```

Restores the built-in power widget.

Development, troubleshooting and automatic upstream updates: [MAINTAINING.md](MAINTAINING.md).

MIT licensed. Based on [Omarchy's power plugin](https://github.com/basecamp/omarchy/tree/v4.0.4/shell/plugins/panels/power)
by David Heinemeier Hansson; see [LICENSE](LICENSE).
