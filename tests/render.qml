import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import "./plugin" as Battery
import "./plugin/Diagnostics.js" as Diagnostics

// Isolated artifact renderer: never screenshots the user's desktop.
ShellRoot {
  id: root
  property var fixture: ({})
  readonly property var reading: Diagnostics.view(fixture, "", fixture.timestamp || 0)
  FileView {
    path: Quickshell.env("POWER_PREVIEW_FIXTURE")
    onLoaded: root.fixture = JSON.parse(text())
  }
  FloatingWindow {
    visible: true
    implicitWidth: 520
    implicitHeight: contents.implicitHeight + 64
    color: Color.popups.background
    Rectangle {
      id: capture
      width: parent.width
      height: contents.implicitHeight + 64
      color: Color.background
      Column {
        id: contents
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 32
        spacing: 16
        Text {
          width: parent.width
          text: "Battery" + (root.reading.battery ? " · " + Math.round(root.reading.battery.percentage) + "%" : "")
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.title
          font.bold: true
        }
        Text {
          width: parent.width
          text: root.reading.label
          wrapMode: Text.WordWrap
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          font.bold: true
        }
        Battery.BatteryDetails {
          width: parent.width
          snapshot: root.fixture
          reading: root.reading
          now: root.fixture.timestamp || 0
          historyOpen: Quickshell.env("POWER_PREVIEW_HISTORY") === "1"
        }
        Text {
          text: Quickshell.env("POWER_PREVIEW_CAPTION") || "SIMULATED READINGS · LAYOUT PREVIEW"
          color: Color.foreground
          opacity: 0.4
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }
      }
    }
    Timer {
      interval: 1500
      running: true
      onTriggered: capture.grabToImage(function(result) {
        if (result.saveToFile(Quickshell.env("POWER_PREVIEW_OUTPUT"))) console.log("POWER_RENDER_OK")
        else console.error("POWER_RENDER_FAILED")
        Qt.quit()
      })
    }
  }
}
