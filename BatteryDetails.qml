import QtQuick
import qs.Commons
import qs.Ui
import "Diagnostics.js" as Diagnostics

Column {
  id: root
  property var snapshot: ({})
  property var reading: ({})
  property real now: Date.now() / 1000
  property string error: ""
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family
  property bool historyOpen: false
  readonly property var battery: reading.battery || ({})
  signal batteryPicked(string batteryId)
  spacing: Style.space(10)

  Flow {
    visible: (root.snapshot.batteries || []).length > 1
    width: parent.width
    spacing: Style.space(6)
    Repeater {
      model: root.snapshot.batteries || []
      Button {
        required property var modelData
        text: modelData.id + (Diagnostics.known(modelData.percentage) ? " · " + Math.round(modelData.percentage) + "%" : "")
        active: root.battery.id === modelData.id
        bordered: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        fontSize: Style.font.bodySmall
        onClicked: root.batteryPicked(modelData.id)
      }
    }
  }

  Text {
    width: parent.width
    text: root.reading.reason || "Waiting for readings…"
    wrapMode: Text.WordWrap
    textFormat: Text.PlainText
    color: root.foreground
    opacity: 0.75
    font.family: root.fontFamily
    font.pixelSize: Style.font.bodySmall
  }
  Text {
    visible: root.reading.unstable === true
    width: parent.width
    text: "Power connection unstable · several connect/disconnect events were detected in two minutes. The cause is unknown."
    wrapMode: Text.WordWrap
    color: root.foreground
    font.family: root.fontFamily
    font.pixelSize: Style.font.bodySmall
  }

  Row {
    width: parent.width
    spacing: Style.space(8)
    Repeater {
      model: [
        { label: "CURRENT" + (root.battery.currentEstimated ? " ≈" : ""), value: Diagnostics.amps(root.reading.currentA) },
        { label: "VOLTAGE", value: Diagnostics.metric(root.reading.voltageV, "V") },
        { label: "POWER", value: Diagnostics.metric(root.reading.powerW, "W", 1) }
      ]
      Column {
        required property var modelData
        width: (root.width - Style.space(16)) / 3
        spacing: Style.space(3)
        Text {
          text: modelData.label
          color: root.foreground
          opacity: 0.6
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          font.letterSpacing: 1
        }
        Text {
          width: parent.width
          text: modelData.value
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          font.bold: true
          color: root.foreground
          elide: Text.ElideRight
        }
      }
    }
  }

  Detail { label: "External power"; value: root.snapshot.acOnline === true ? "Connected" : root.snapshot.acOnline === false ? "Disconnected" : "Unknown" }
  Detail { label: "State observed for"; value: root.reading.code === "stale" ? "Unavailable" : Diagnostics.duration(root.now - root.reading.since) }
  Detail {
    label: "Charge limit"
    value: !Diagnostics.known(root.battery.limitPercent) ? "Unavailable"
      : root.battery.limitPercent === 100 ? "100% · No reduced limit"
      : root.battery.limitPercent + "%"
  }
  Detail {
    label: root.reading.code === "discharging" ? "Time left · estimate" : "Time to full · estimate"
    value: root.reading.code === "discharging" ? Diagnostics.duration(root.battery.timeToEmptyS)
      : ["charging", "slow"].indexOf(root.reading.code) !== -1 ? Diagnostics.duration(root.battery.timeToFullS) : "Unavailable"
  }
  Detail { label: "Battery health"; value: Diagnostics.metric(root.battery.healthPercent, "%", 0) }
  Detail { label: "Battery size"; value: Diagnostics.metric(root.battery.fullWh, "Wh", 1) }
  Detail { label: "Design capacity"; value: Diagnostics.metric(root.battery.designWh, "Wh", 1) }
  Detail { label: "Cycles · reported"; value: Diagnostics.known(root.battery.cycles) ? String(root.battery.cycles) : "Unavailable" }
  Detail { label: "Temperature"; value: Diagnostics.metric(root.battery.temperatureC, "°C", 1) }

  Button {
    width: parent.width
    text: root.historyOpen ? "Hide history (h)" : "Show history · last 30 minutes (h)"
    bordered: true
    foreground: root.foreground
    fontFamily: root.fontFamily
    fontSize: Style.font.bodySmall
    onClicked: root.historyOpen = !root.historyOpen
  }

  Column {
    visible: root.historyOpen
    width: parent.width
    spacing: Style.space(10)
    TrendGraph {
      width: parent.width
      title: "Battery current · charging ↑ / draining ↓"
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

  Text {
    width: parent.width
    text: (root.battery.id || "Battery") + (root.battery.model ? " · " + root.battery.model : "")
      + "\n" + (root.battery.source || "Waiting for readings") + " · 5s sampling · up to 15s averages"
      + (root.battery.currentEstimated ? "\nCurrent estimated from power ÷ voltage." : "")
      + (root.battery.conflicts && root.battery.conflicts.length ? "\n" + root.battery.conflicts.join("\n") : "")
      + (root.error ? "\n" + root.error : "")
    wrapMode: Text.WordWrap
    textFormat: Text.PlainText
    color: root.foreground
    opacity: 0.55
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
  }

  component Detail: Item {
    property string label: ""
    property string value: ""
    width: root.width
    implicitHeight: Math.max(detailLabel.implicitHeight, detailValue.implicitHeight)
    Text {
      id: detailLabel
      width: parent.width * 0.47
      text: parent.label
      wrapMode: Text.WordWrap
      color: root.foreground
      opacity: 0.6
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
    }
    Text {
      id: detailValue
      anchors.right: parent.right
      width: parent.width * 0.51
      text: parent.value
      horizontalAlignment: Text.AlignRight
      wrapMode: Text.WordWrap
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
    }
  }
}
