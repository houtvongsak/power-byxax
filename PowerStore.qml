pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// One collector shared by every bar/monitor in this shell process.
Item {
  id: root
  property var snapshot: ({})
  property real now: Date.now() / 1000
  property string error: ""
  readonly property string script: decodeURIComponent(String(Qt.resolvedUrl("bin/telemetry.py")).replace(/^file:\/\//, ""))
  readonly property string stateFile: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state") + "/power-byxax/history.json"

  Process {
    id: collector
    command: ["python3", "-u", root.script, "--watch", "--state-file", root.stateFile]
    running: true
    stdout: SplitParser {
      onRead: function(line) {
        try {
          var next = JSON.parse(line)
          if (!Array.isArray(next.batteries) || typeof next.timestamp !== "number") return
          root.snapshot = next
          root.now = Date.now() / 1000
          root.error = next.storageError ? "History could not be saved: " + next.storageError : ""
        } catch (e) { root.error = "Could not read battery telemetry." }
      }
    }
    stderr: SplitParser { onRead: function(line) { root.error = String(line).substring(0, 200) } }
    onExited: restartTimer.restart()
  }
  Timer {
    id: restartTimer
    interval: 5000
    onTriggered: collector.running = true
  }
  Timer {
    interval: 5000
    repeat: true
    running: true
    onTriggered: root.now = Date.now() / 1000
  }
}
