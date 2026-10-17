// Pure interpretation of recorded evidence. Never infer a hardware fault or
// pre-charge/thermal protection from voltage/current alone.
function known(value) {
  return typeof value === "number" && isFinite(value)
}

function batteryIn(sample, id) {
  var batteries = sample && sample.batteries || []
  for (var i = 0; i < batteries.length; i++) if (batteries[i].id === id) return batteries[i]
  return null
}

function recent(history, sample, battery) {
  var out = []
  var previous = sample.timestamp
  for (var i = history.length - 1; i >= 0; i--) {
    var point = history[i]
    if (point.timestamp > sample.timestamp) continue
    if (sample.timestamp - point.timestamp > 15 || previous - point.timestamp > 12) break
    var b = batteryIn(point, battery.id)
    if (!b || point.acOnline !== sample.acOnline || b.status !== battery.status) break
    out.unshift({ timestamp: point.timestamp, battery: b })
    previous = point.timestamp
  }
  if (!out.length) out.push({ timestamp: sample.timestamp, battery: battery })
  return out
}

function average(points, field) {
  var sum = 0, count = 0
  for (var i = 0; i < points.length; i++) {
    var v = points[i].battery[field]
    if (known(v)) { sum += v; count++ }
  }
  return count ? sum / count : null
}

function flow(battery) {
  // A small positive reading is still a reading. Do not repeat upstream's
  // mistake of treating <=0.2 W as evidence of a charge limit.
  if (known(battery.currentA)) return battery.currentA > 0
  if (known(battery.powerW)) return battery.powerW > 0
  return null
}

function classify(sample, battery, history) {
  if (!battery) return { code: "missing", label: "No battery detected", reason: "No system battery readings are available." }
  var points = recent(history || [], sample, battery)
  var settled = points.length >= 3 && points[points.length - 1].timestamp - points[0].timestamp >= 10
  var rate = average(points, "powerW"), current = average(points, "currentA")
  var active = flow(battery)
  var online = sample.acOnline
  var status = battery.status
  var result = function(code, label, reason) {
    return { code: code, label: label, reason: reason, currentA: current, powerW: rate,
      voltageV: average(points, "voltageV"), settled: settled }
  }
  if (known(battery.currentA) && known(battery.powerW)
      && ((battery.currentA === 0 && battery.powerW > 0.2) || (battery.powerW === 0 && battery.currentA > 0.02)))
    return result("conflict", "Readings disagree", "Battery current and power readings disagree. Waiting for consistent measurements.")
  if (status === "Discharging" || status === "Empty") {
    return result("discharging", online === true ? "Battery draining on AC" : "On battery",
      online === true ? "External power is detected, but the battery reports discharge. The cause is unknown."
      : online === false ? "External power is not detected. Current is leaving the battery."
      : "The battery reports discharge; external power detection is unavailable.")
  }
  if (status === "Charging" && online === false)
    return result("conflict", "Readings disagree", "The battery reports charging, but external power is not detected. Waiting for consistent readings.")
  if (status === "Charging") {
    if (active === false) {
      var allIdle = points.every(function(p) { return flow(p.battery) === false })
      return result(settled && allIdle ? "idle" : "checking", settled && allIdle ? "No measurable charging" : "Checking charging",
        "The battery reports charging, but little or no current is measured. The reason is unknown.")
    }
    var allSlow = points.every(function(p) {
      return flow(p.battery) === true && (known(p.battery.currentA) ? p.battery.currentA <= 0.15 : known(p.battery.powerW) && p.battery.powerW <= 2)
    })
    if (settled && allSlow)
      return result("slow", "Charging slowly", "A small charging current has persisted for at least 10 seconds. This does not identify the cause.")
    return result("charging", "Charging", active === null
      ? "Charging is reported by the battery; current and power measurements are unavailable."
      : "The battery reports charging and measurable power flow.")
  }
  if (online === false)
    return result("offline", "External power disconnected", "External power is not detected. The battery's flow state is " + String(status || "unknown").toLowerCase() + ".")
  if (online === null || online === undefined)
    return result("unknown", "Power source unknown", "External power detection is unavailable. Battery status: " + String(status || "Unknown") + ".")
  if (active === true)
    return result("conflict", "Readings disagree", "Current is measured while the battery reports " + String(status || "Unknown").toLowerCase() + ". Flow direction and cause are unknown.")
  if (status === "Full" && known(battery.percentage) && battery.percentage >= 99)
    return result("full", "Fully charged", "The battery reports full and external power is detected.")
  if ((status === "Not charging" || status === "Full") && known(battery.limitPercent)
      && battery.limitPercent < 100 && known(battery.percentage)
      && battery.percentage >= battery.limitPercent - 1 && active === false)
    return result("limit", "Charge limit reached", "A " + battery.limitPercent + "% charge limit is configured, and the battery is at that limit with no measurable charging.")
  if (status === "Not charging" || status === "Full")
    return result("idle", "Plugged in · Not charging", "External power is detected, but the battery is not charging. The reason is unknown.")
  return result("unknown", "Battery state unknown", "External power is detected, but the battery does not report a usable charging state.")
}

function duration(seconds) {
  if (!known(seconds) || seconds < 0) return "Unavailable"
  if (seconds < 60) return Math.floor(seconds) + "s"
  if (seconds < 3600) return Math.floor(seconds / 60) + "m"
  return Math.floor(seconds / 3600) + "h " + Math.floor(seconds % 3600 / 60) + "m"
}

function metric(value, suffix, decimals) {
  return known(value) ? value.toFixed(decimals === undefined ? 2 : decimals) + " " + suffix : "Unavailable"
}

function amps(value) {
  if (!known(value)) return "Unavailable"
  return value !== 0 && Math.abs(value) < 0.1 ? (value * 1000).toFixed(1) + " mA" : value.toFixed(2) + " A"
}

function view(payload, id, now) {
  var batteries = payload.batteries || []
  var battery = batteryIn(payload, id) || batteries[0] || null
  var history = payload.history || []
  var result = classify(payload, battery, history)
  result.battery = battery
  result.since = payload.timestamp
  result.events = (payload.events || []).slice().reverse()
  if (battery) {
    var previous = payload.timestamp
    for (var i = history.length - 1; i >= 0; i--) {
      var point = history[i]
      var b = batteryIn(point, battery.id)
      if (!b || previous - point.timestamp > 15 || point.acOnline !== payload.acOnline) break
      if (classify(point, b, history).code !== result.code) break
      result.since = point.timestamp
      previous = point.timestamp
    }
  }
  result.age = known(payload.timestamp) ? Math.max(0, now - payload.timestamp) : null
  if (!known(payload.timestamp) || now - payload.timestamp > 20) {
    result.code = "stale"
    result.label = "Telemetry unavailable"
    result.reason = known(payload.timestamp) ? "Last successful reading was " + duration(result.age) + " ago. Measurements below are from that reading." : "Waiting for battery readings. Check that Python 3 is installed."
  }
  var acEvents = (payload.events || []).filter(function(e) { return e.kind === "ac" && now - e.timestamp <= 120 })
  result.unstable = acEvents.length >= 3
  return result
}

function series(history, id, field) {
  return (history || []).map(function(s) {
    var b = batteryIn(s, id)
    var value = b ? b[field] : null
    if (field === "currentA" && known(value)) {
      if (b && b.status === "Discharging") value = known(value) ? -value : null
      else if (!b || b.status !== "Charging") value = flow(b || {}) === false ? 0 : null
    }
    return { timestamp: s.timestamp, value: value }
  })
}

function voltageTrend(history, id) {
  var points = series(history, id, "voltageV")
  if (points.length < 2) return "Collecting voltage history"
  var last = points[points.length - 1]
  if (!known(last.value)) return "Voltage sensor unavailable"
  var first = null
  var previous = last
  for (var i = points.length - 2; i >= 0; i--) {
    if (!known(points[i].value) || previous.timestamp - points[i].timestamp > 15) break
    if (last.timestamp - points[i].timestamp >= 60) { first = points[i]; break }
    previous = points[i]
  }
  if (!first) return "Collecting voltage history"
  var delta = last.value - first.value
  return "Voltage " + (Math.abs(delta) < 0.08 ? "roughly steady" : delta > 0 ? "rising" : "falling") + " over the last minute; cause unknown"
}

if (typeof module !== "undefined") module.exports = {
  known: known, batteryIn: batteryIn, classify: classify, view: view,
  duration: duration, metric: metric, amps: amps, series: series, voltageTrend: voltageTrend
}
