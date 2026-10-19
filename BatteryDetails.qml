import QtQuick
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "Diagnostics.js" as Diagnostics

Column {
  id: root
  property var snapshot: ({})
  property var reading: ({})
  property real now: Date.now() / 1000
  property string error: ""
  property color foreground: Commons.Color.foreground
  property string fontFamily: Style.font.family
  property bool historyOpen: false
  property bool detailsOpen: false
  property bool active: true
  readonly property var battery: reading.battery || ({})
  readonly property bool fresh: !!snapshot.timestamp && reading.code !== "stale"
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

  Column {
    width: parent.width
    spacing: Style.spacing.labelGap
    // Stock two-column battery stats, followed by the extra sensor readings.
    Row {
      width: parent.width
      spacing: Style.space(20)
      Column {
        width: (parent.width - parent.spacing) / 2
        spacing: Style.spacing.labelGap
        InfoPair { label: "Battery size"; value: Diagnostics.metric(root.battery.fullWh, "Wh", 0) }
        InfoPair { label: "Charge cycles"; value: Diagnostics.known(root.battery.cycles) ? String(root.battery.cycles) : "—" }
      }
      Column {
        width: (parent.width - parent.spacing) / 2
        spacing: Style.spacing.labelGap
        InfoPair {
          label: root.reading.code === "limit" ? "Charge limit" : root.reading.code === "discharging" ? "Time left" : "Time to full"
          value: root.reading.code === "limit" ? root.battery.limitPercent + "%"
            : !root.fresh ? "Unavailable"
            : root.reading.code === "discharging" ? Diagnostics.duration(root.battery.timeToEmptyS)
            : ["charging", "slow"].indexOf(root.reading.code) !== -1 ? Diagnostics.duration(root.battery.timeToFullS) : "—"
        }
        InfoPair {
          label: root.reading.code === "discharging" ? "Discharging" : ["charging", "slow"].indexOf(root.reading.code) !== -1 ? "Charging" : "Power"
          value: Diagnostics.metric(root.fresh ? root.reading.powerW : null, "W", 1)
        }
      }
    }

    Row {
      width: parent.width
      spacing: Style.space(20)
      Column {
        width: (parent.width - parent.spacing) / 2
        InfoPair { label: "Current" + (root.battery.currentEstimated ? " ≈" : ""); value: Diagnostics.amps(root.fresh ? root.reading.currentA : null) }
      }
      Column {
        width: (parent.width - parent.spacing) / 2
        InfoPair { label: "Voltage"; value: Diagnostics.metric(root.fresh ? root.reading.voltageV : null, "V") }
      }
    }
    Detail {
      label: "External power"
      value: !root.fresh ? "Unavailable" : root.snapshot.acOnline === true ? "Connected" : root.snapshot.acOnline === false ? "Disconnected" : "Unknown"
    }
    Text {
      visible: root.reading.unstable === true
      width: parent.width
      text: "Power connection unstable"
      wrapMode: Text.WordWrap
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
    }
    Detail {
      visible: root.reading.code !== "limit" && (root.detailsOpen || Diagnostics.known(root.battery.limitPercent) && root.battery.limitPercent < 100)
      label: "Charge limit"
      value: !Diagnostics.known(root.battery.limitPercent) ? "Unavailable"
        : root.battery.limitPercent === 100 ? "100% · No reduced limit"
        : root.battery.limitPercent + "%"
    }
    Column {
      visible: root.detailsOpen
      width: parent.width
      spacing: Style.spacing.labelGap
      Detail { label: "State observed for"; value: root.fresh ? Diagnostics.duration(root.now - root.reading.since) : "Unavailable" }
      Detail { label: "Battery health"; value: Diagnostics.metric(root.battery.healthPercent, "%", 0) }
      Detail { label: "Design capacity"; value: Diagnostics.metric(root.battery.designWh, "Wh", 1) }
      Detail { label: "Temperature"; value: Diagnostics.metric(root.battery.temperatureC, "°C", 1) }
    }
  }

  Row {
    width: parent.width
    spacing: Style.space(8)
    Button {
      width: (root.width - parent.spacing) / 2
      text: root.detailsOpen ? "Hide details (d)" : "Details (d)"
      bordered: true
      foreground: root.foreground
      fontFamily: root.fontFamily
      fontSize: Style.font.bodySmall
      onClicked: root.detailsOpen = !root.detailsOpen
    }
    Button {
      width: (root.width - parent.spacing) / 2
      text: root.historyOpen ? "Hide history (g)" : "History (g)"
      bordered: true
      foreground: root.foreground
      fontFamily: root.fontFamily
      fontSize: Style.font.bodySmall
      onClicked: root.historyOpen = !root.historyOpen
    }
  }

  Loader {
    objectName: "power-history-loader"
    active: root.active && root.historyOpen
    visible: active
    width: parent.width
    height: item ? item.implicitHeight : 0
    sourceComponent: Component {
      HistoryView {
        snapshot: root.snapshot
        reading: root.reading
        battery: root.battery
        foreground: root.foreground
        fontFamily: root.fontFamily
      }
    }
  }

  Text {
    visible: root.detailsOpen || root.error !== "" || (root.battery.conflicts || []).length > 0
    width: parent.width
    text: (root.detailsOpen ? (root.battery.id || "Battery") + (root.battery.model ? " · " + root.battery.model : "")
      + "\n" + (root.battery.source || "Waiting for readings") + " · 5s sampling · up to 15s averages" : "")
      + (root.detailsOpen && root.battery.currentEstimated ? "\nCurrent estimated from power ÷ voltage." : "")
      + (root.battery.conflicts && root.battery.conflicts.length ? "\n" + root.battery.conflicts.join("\n") : "")
      + (root.error ? "\n" + root.error : "")
    wrapMode: Text.WordWrap
    textFormat: Text.PlainText
    color: root.foreground
    opacity: 0.55
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
  }

  component InfoPair: Row {
    property string label: ""
    property string value: ""

    width: parent.width
    spacing: Style.space(8)

    InfoLabel { text: label }
    Item { width: Math.max(0, parent.width - parent.children[0].implicitWidth - parent.children[2].implicitWidth - parent.spacing * 2); height: 1 }
    InfoValue { text: value }
  }

  component InfoLabel: Text {
    textFormat: Text.PlainText
    color: root.foreground
    opacity: 0.6
    font.family: root.fontFamily
    font.pixelSize: Style.font.bodySmall
  }

  component InfoValue: Text {
    textFormat: Text.PlainText
    color: root.foreground
    font.family: root.fontFamily
    font.pixelSize: Style.font.bodySmall
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
