import QtQuick
import qs.Commons
import qs.Ui
import "Diagnostics.js" as Diagnostics

Column {
  id: root
  property var snapshot: ({})
  property var reading: ({})
  property var battery: ({})
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family
  spacing: Style.space(10)
    TrendGraph {
      width: parent.width
      title: "Battery current"
      unit: "A"
      zeroAxis: true
      foreground: root.foreground
      points: Diagnostics.series(root.snapshot.history, root.battery.id, "currentA")
    }
    TrendGraph {
      width: parent.width
      title: "Battery voltage"
      unit: "V"
      foreground: root.foreground
      points: Diagnostics.series(root.snapshot.history, root.battery.id, "voltageV")
    }
    Text {
      width: parent.width
      text: "Positive current: charging. Negative: draining. Unknown flow directions leave gaps."
      wrapMode: Text.WordWrap
      color: root.foreground
      opacity: 0.6
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
    }
    Item {
      width: parent.width
      implicitHeight: timeStart.implicitHeight
      Text {
        id: timeStart
        text: "30 minutes ago"
        color: root.foreground
        opacity: 0.6
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
      Text {
        anchors.right: parent.right
        text: "Now"
        color: root.foreground
        opacity: 0.6
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
    }
    Text {
      width: parent.width
      text: Diagnostics.voltageTrend(root.snapshot.history, root.battery.id)
      wrapMode: Text.WordWrap
      color: root.foreground
      opacity: 0.6
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
    }
    PanelSectionHeader { text: "RECENT EVENTS"; foreground: root.foreground; fontFamily: root.fontFamily }
    Text {
      visible: !(root.reading.events || []).length
      width: parent.width
      text: "No connection or battery-state changes recorded yet."
      wrapMode: Text.WordWrap
      color: root.foreground
      opacity: 0.6
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
    }
    Repeater {
      model: (root.reading.events || []).slice(0, 8)
      Text {
        required property var modelData
        width: root.width
        text: Qt.formatDateTime(new Date(modelData.timestamp * 1000), "HH:mm:ss") + "  " + modelData.label
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
      }
    }
}
