import QtQuick
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "Diagnostics.js" as Diagnostics

Column {
  id: root
  property var snapshot: ({})
  property var reading: ({})
  property var battery: ({})
  property color foreground: Commons.Color.foreground
  property string fontFamily: Style.font.family
  readonly property var recentEvents: (reading.events || []).slice(0, 8)
  readonly property string singleBatteryId: (snapshot.batteries || []).length === 1 ? snapshot.batteries[0].id : ""
  spacing: Style.space(10)

  Column {
    width: parent.width
    spacing: Style.spacing.labelGap
    TrendGraph {
      width: parent.width
      title: "Battery current"
      unit: "A"
      zeroAxis: true
      foreground: root.foreground
      points: Diagnostics.series(root.snapshot.history, root.battery.id, "currentA")
    }
    Text {
      width: parent.width
      text: "+ Charging · − Discharging · Gaps: unknown"
      wrapMode: Text.WordWrap
      textFormat: Text.PlainText
      color: root.foreground
      opacity: 0.6
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
    }
  }

  Column {
    width: parent.width
    spacing: Style.spacing.labelGap
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
        text: "−30m"
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
      textFormat: Text.PlainText
      color: root.foreground
      opacity: 0.6
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
    }
  }

  Column {
    width: parent.width
    spacing: Style.spacing.controlGap
    PanelSectionHeader { text: "RECENT EVENTS"; foreground: root.foreground; fontFamily: root.fontFamily }
    Text {
      visible: !root.recentEvents.length
      width: parent.width
      text: "No recent changes."
      color: root.foreground
      opacity: 0.6
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
    }
    FontMetrics {
      id: eventFont
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
    }
    Column {
      visible: root.recentEvents.length > 0
      width: parent.width
      spacing: Style.spacing.labelGap
      Repeater {
        model: root.recentEvents
        Item {
          required property var modelData
          width: parent.width
          implicitHeight: Math.max(eventTime.implicitHeight, eventText.implicitHeight)
          Text {
            id: eventTime
            width: Math.ceil(eventFont.advanceWidth("00:00:00"))
            text: Qt.formatDateTime(new Date(modelData.timestamp * 1000), "HH:mm:ss")
            color: root.foreground
            opacity: 0.6
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
          }
          Text {
            id: eventText
            anchors.left: eventTime.right
            anchors.leftMargin: Style.spacing.controlGap
            anchors.right: parent.right
            text: Diagnostics.eventLabel(modelData, root.singleBatteryId)
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
          }
        }
      }
    }
  }
}
