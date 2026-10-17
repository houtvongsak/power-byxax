import QtQuick
import Quickshell
import "./plugin" as Battery

ShellRoot {
  Battery.Panel { id: power }
  Battery.BatteryDetails {
    id: details
    width: 348
    active: false
    historyOpen: true
    snapshot: power.telemetry
    reading: power.diagnosis
  }
  Timer {
    interval: 1000
    repeat: true
    running: true
    property int attempts: 0
    property real firstTimestamp: 0
    property int phase: 0
    function fail(reason) { console.error("POWER_SMOKE_FAILED:", reason); Qt.quit() }
    onTriggered: {
      attempts++
      if (power.telemetry.timestamp && firstTimestamp === 0) firstTimestamp = power.telemetry.timestamp
      if (firstTimestamp && power.telemetry.timestamp > firstTimestamp) {
        if (!power.diagnosis.label || !Array.isArray(power.telemetry.history)) {
          fail("malformed telemetry")
          return
        }
        var loader = details.children.find(function(child) { return child.objectName === "power-history-loader" })
        if (!loader) { fail("history loader missing"); return }
        if (phase === 0) {
          if (loader.item) { fail("closed history instantiated graphs"); return }
          details.active = true
          phase = 1
          return
        }
        if (phase === 1) {
          if (!loader.item) { fail("opened history did not instantiate graphs"); return }
          details.active = false
          phase = 2
          return
        }
        if (loader.item) { fail("closed history retained graph objects"); return }
        console.log("POWER_SMOKE_OK", power.diagnosis.label,
          "battery=" + (power.diagnosis.battery ? power.diagnosis.battery.id : "none"),
          "current=" + power.diagnosis.currentA,
          "history=" + power.telemetry.history.length, "lazy_graphs=verified")
        Qt.quit()
      } else if (attempts >= 20) {
        console.error("POWER_SMOKE_FAILED: collector did not deliver two readings")
        Qt.quit()
      }
    }
  }
}
