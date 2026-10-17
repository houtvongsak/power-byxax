import QtQuick
import Quickshell
import qs.Commons
import qs.Ui
import "./plugin" as Battery

// Render the real popup layout with fixture telemetry, without a desktop capture.
ShellRoot {
  Battery.Panel { id: power }
  FloatingWindow {
    visible: true
    implicitWidth: Number(Quickshell.env("POWER_PREVIEW_WIDTH")) || Style.space(380)
    implicitHeight: capture.height
    color: Color.popups.background
    Rectangle {
      id: capture
      width: parent.width
      height: card.height
      color: Color.popups.background
      BorderSurface {
        id: card
        width: parent.width
        height: contentHost.height + contentTopInset + contentBottomInset
        color: Color.popups.background
        borderSpec: Border.surfaceSpec("popups", "border", Color.popups.border, Math.max(1, Style.space(2)))
        padding: Style.spacing.popupPadding
        radius: Style.cornerRadius
        Item {
          id: contentHost
          x: card.contentLeftInset
          y: card.contentTopInset
          width: card.width - card.contentLeftInset - card.contentRightInset
          height: power.previewContent.implicitHeight
        }
      }
      Component.onCompleted: {
        power.previewContent.parent = contentHost
        power.previewDetails.active = true
        power.previewDetails.historyOpen = Quickshell.env("POWER_PREVIEW_HISTORY") === "1"
        power.previewDetails.detailsOpen = Quickshell.env("POWER_PREVIEW_DETAILS") === "1"
        power.profiles = ["power-saver", "balanced", "performance"]
        power.activeProfile = "balanced"
        power.phraseIndex = 1
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
