import QtQuick
import Quickshell
import "./plugin" as Battery

ShellRoot {
  Battery.Panel { id: power }
  Timer {
    interval: 1000
    repeat: true
    running: true
    property int attempts: 0
    property real firstTimestamp: 0
    onTriggered: {
      attempts++
      if (power.telemetry.timestamp && firstTimestamp === 0) firstTimestamp = power.telemetry.timestamp
      if (firstTimestamp && power.telemetry.timestamp > firstTimestamp) {
        if (!power.diagnosis.label || !Array.isArray(power.telemetry.history)) {
          console.error("POWER_SMOKE_FAILED: malformed telemetry")
          Qt.quit()
          return
        }
        console.log("POWER_SMOKE_OK", power.diagnosis.label,
          "battery=" + (power.diagnosis.battery ? power.diagnosis.battery.id : "none"),
          "current=" + power.diagnosis.currentA,
          "history=" + power.telemetry.history.length)
        Qt.quit()
      } else if (attempts >= 20) {
        console.error("POWER_SMOKE_FAILED: collector did not deliver two readings")
        Qt.quit()
      }
    }
  }
}
