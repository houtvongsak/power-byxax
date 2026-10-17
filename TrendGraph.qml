import QtQuick
import qs.Commons
import "Diagnostics.js" as Diagnostics

Item {
  id: root
  property var points: []
  property color foreground: Color.foreground
  property string title: ""
  property string unit: ""
  property bool zeroAxis: false
  readonly property var values: points.filter(function(p) { return Diagnostics.known(p.value) })
  readonly property real minimum: values.length ? Math.min.apply(null, values.map(function(p) { return p.value }).concat(zeroAxis ? [0] : [])) : 0
  readonly property real maximum: values.length ? Math.max.apply(null, values.map(function(p) { return p.value }).concat(zeroAxis ? [0] : [])) : 1
  readonly property real spread: Math.max(maximum - minimum, unit === "V" ? 0.1 : 0.05)
  readonly property real low: minimum - spread * 0.1
  readonly property real high: maximum + spread * 0.1
  implicitHeight: Style.space(100)
  onPointsChanged: plot.requestPaint()
  onForegroundChanged: plot.requestPaint()

  Text {
    id: heading
    text: root.title
    color: root.foreground
    font.family: Style.font.family
    font.pixelSize: Style.font.bodySmall
  }
  Text {
    anchors.right: parent.right
    text: root.values.length ? (root.unit === "A" ? Diagnostics.amps(root.maximum) : root.maximum.toFixed(2) + " " + root.unit) : "Unavailable"
    color: root.foreground
    opacity: 0.6
    font.family: Style.font.family
    font.pixelSize: Style.font.caption
  }
  Rectangle {
    anchors.top: heading.bottom
    anchors.topMargin: Style.space(6)
    anchors.bottom: parent.bottom
    width: parent.width
    color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.04)
    radius: Style.cornerRadius
    Canvas {
      id: plot
      anchors.fill: parent
      anchors.margins: Style.space(5)
      onWidthChanged: requestPaint()
      onHeightChanged: requestPaint()
      onPaint: {
        var ctx = getContext("2d")
        ctx.clearRect(0, 0, width, height)
        if (!root.points.length || !root.values.length) return
        var end = root.points[root.points.length - 1].timestamp
        var start = end - 1800
        var span = root.high - root.low
        function y(v) { return height - (v - root.low) / span * height }
        ctx.strokeStyle = Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.15)
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(0, root.zeroAxis ? y(0) : height / 2)
        ctx.lineTo(width, root.zeroAxis ? y(0) : height / 2)
        ctx.stroke()
        ctx.strokeStyle = root.foreground
        ctx.fillStyle = root.foreground
        ctx.lineWidth = 1.8
        ctx.beginPath()
        var previous = null
        for (var i = 0; i < root.points.length; i++) {
          var p = root.points[i]
          if (!Diagnostics.known(p.value)) { previous = null; continue }
          var x = (p.timestamp - start) / 1800 * width
          if (!previous || p.timestamp - previous.timestamp > 15) ctx.moveTo(x, y(p.value))
          else ctx.lineTo(x, y(p.value))
          previous = p
        }
        ctx.stroke()
        var last = root.values[root.values.length - 1]
        ctx.beginPath()
        ctx.arc((last.timestamp - start) / 1800 * width, y(last.value), 2.5, 0, Math.PI * 2)
        ctx.fill()
      }
    }
    Text {
      anchors.centerIn: parent
      visible: root.values.length < 2
      text: root.values.length ? "Collecting history…" : "Sensor unavailable"
      color: root.foreground
      opacity: 0.6
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
    }
    Text {
      anchors.left: parent.left
      anchors.bottom: parent.bottom
      anchors.margins: Style.space(5)
      text: root.values.length ? (root.unit === "A" ? Diagnostics.amps(root.minimum) : root.minimum.toFixed(2) + " " + root.unit) : ""
      color: root.foreground
      opacity: 0.5
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
    }
  }
}
