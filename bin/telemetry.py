#!/usr/bin/env python3
"""Read-only Linux battery telemetry. No third-party Python packages required."""

import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time

WINDOW_SECONDS = 30 * 60
MAX_SAMPLES = 361
MAX_EVENTS = 40
STATES = {0: "Unknown", 1: "Charging", 2: "Discharging", 3: "Empty",
          4: "Full", 5: "Not charging", 6: "Pending discharge"}


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return None


def scaled(path, divisor=1):
    value = number(read(path))
    return None if value is None else value / divisor


def bus_call(path, interface, method, *args):
    try:
        result = subprocess.run(
            ["busctl", "--system", "--json=short", "--timeout=2s", "call",
             "org.freedesktop.UPower", path, interface, method, *args],
            capture_output=True, text=True, timeout=3, check=True)
        return json.loads(result.stdout)["data"][0]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError):
        return None


def upower_devices():
    """Typed D-Bus properties avoid parsing localized CLI output."""
    paths = bus_call("/org/freedesktop/UPower", "org.freedesktop.UPower", "EnumerateDevices")
    devices = []
    for path in paths or []:
        # Avoid querying mice, headphones and other peripheral batteries.
        if not any(part in path.rsplit("/", 1)[-1] for part in ("battery_", "line_power_")):
            continue
        props = bus_call(path, "org.freedesktop.DBus.Properties", "GetAll",
                         "s", "org.freedesktop.UPower.Device")
        if isinstance(props, dict):
            devices.append({key: value["data"] for key, value in props.items()
                            if isinstance(value, dict) and "data" in value})
    return devices


def positive(value):
    value = number(value)
    return value if value is not None and value > 0 else None


def normalize_battery(path, props, now):
    """Prefer live kernel readings. UPower's measurements can lag by seconds."""
    def field(name, divisor=1, fallback=None):
        value = scaled(path / name, divisor) if path else None
        return value if value is not None else number(fallback)

    updated = number(props.get("UpdateTime"))
    fresh = updated is not None and 0 <= now - updated <= 120
    live = props if fresh else {}
    battery_id = path.name if path else str(props.get("NativePath", "Battery"))
    raw_status = read(path / "status") if path else None
    status = raw_status or STATES.get(live.get("State"), "Unknown")
    voltage = field("voltage_now", 1e6, positive(live.get("Voltage")))
    current = field("current_now", 1e6)
    power = field("power_now", 1e6)
    estimated_current = False
    if power is None and current is not None and voltage is not None:
        power = abs(current * voltage)
    elif power is None:
        power = number(live.get("EnergyRate"))
    if current is None and power is not None and voltage is not None and voltage > 0:
        current = abs(power / voltage)
        estimated_current = True

    charge = field("charge_now", 1e6)
    full_charge = field("charge_full", 1e6)
    design_charge = field("charge_full_design", 1e6)
    energy = field("energy_now", 1e6, live.get("Energy"))
    full = field("energy_full", 1e6, props.get("EnergyFull"))
    design = field("energy_full_design", 1e6, props.get("EnergyFullDesign"))
    percentage = field("capacity", fallback=live.get("Percentage"))
    if percentage is None:
        numerator, denominator = (charge, full_charge) if full_charge else (energy, full)
        if numerator is not None and denominator is not None and denominator > 0:
            percentage = numerator / denominator * 100
    if percentage is not None:
        percentage = max(0, min(100, percentage))
    nominal_voltage = field("voltage_min_design", 1e6, props.get("VoltageMinDesign"))
    if nominal_voltage and nominal_voltage > 0:
        if full is None and full_charge is not None:
            full = full_charge * nominal_voltage
        if design is None and design_charge is not None:
            design = design_charge * nominal_voltage
    health = None
    if full_charge is not None and design_charge and design_charge > 0:
        health = full_charge / design_charge * 100
    elif full is not None and design and design > 0:
        health = full / design * 100

    # UPower's 75/80 metadata alone does NOT mean a limit is enabled.
    sys_end = field("charge_control_end_threshold")
    sys_start = field("charge_control_start_threshold")
    enabled = props.get("ChargeThresholdEnabled") is True
    end = sys_end if sys_end is not None else number(props.get("ChargeEndThreshold")) if enabled else None
    start = sys_start if sys_start is not None else number(props.get("ChargeStartThreshold")) if enabled else None
    if end is not None and not 0 < end <= 100:
        end = None
    if start is not None and not 0 <= start <= 100:
        start = None
    conflicts = []
    if sys_end is not None and enabled and number(props.get("ChargeEndThreshold")) != sys_end:
        conflicts.append("Charge-limit sources disagree; showing the kernel setting.")
    if raw_status and fresh and status != STATES.get(live.get("State"), "Unknown"):
        # This is expected shortly after connection changes; kernel wins.
        conflicts.append("UPower status differs; using the live kernel reading.")
    temp = field("temp", 10)
    # UPower uses zero for unavailable temperature on many laptops.
    if temp is None and positive(live.get("Temperature")):
        temp = number(live["Temperature"])
    cycles = field("cycle_count", fallback=props.get("ChargeCycles"))
    if cycles is not None and cycles < 0:
        cycles = None
    return {
        "id": battery_id, "model": (read(path / "model_name") if path else None) or props.get("Model", ""),
        "status": status, "percentage": percentage,
        "currentA": abs(current) if current is not None else None,
        "currentEstimated": estimated_current, "voltageV": voltage,
        "powerW": abs(power) if power is not None else None,
        "energyWh": energy, "fullWh": full, "designWh": design,
        "chargeAh": charge, "healthPercent": health,
        "temperatureC": temp, "cycles": cycles,
        "limitPercent": end, "startPercent": start,
        "limitSource": "kernel" if sys_end is not None else "UPower" if enabled and end is not None else None,
        "timeToFullS": positive(live.get("TimeToFull")),
        "timeToEmptyS": positive(live.get("TimeToEmpty")),
        "source": "Kernel + UPower" if path and props else "Kernel" if path else "UPower",
        "conflicts": conflicts,
    }


def collect(root=Path("/sys/class/power_supply"), devices=None, now=None):
    now = time.time() if now is None else now
    devices = upower_devices() if devices is None else devices
    by_native = {str(d.get("NativePath")): d for d in devices if d.get("Type") == 2 and d.get("PowerSupply")}
    batteries, supplies, seen = [], [], set()
    try:
        paths = sorted(root.iterdir())
    except OSError:
        paths = []
    for path in paths:
        supply_type = read(path / "type")
        if supply_type == "Battery":
            # Exclude HID/peripheral batteries, even when exposed in sysfs.
            if read(path / "scope") == "Device" or read(path / "present") == "0":
                continue
            props = by_native.get(path.name, {})
            batteries.append(normalize_battery(path, props, now))
            seen.add(path.name)
        elif supply_type and supply_type != "Battery":
            online = read(path / "online")
            if online in ("0", "1") and read(path / "scope") != "Device":
                supplies.append({"id": path.name, "type": supply_type, "online": online == "1"})
    for native, props in by_native.items():
        if native not in seen and props.get("IsPresent"):
            batteries.append(normalize_battery(None, props, now))
    if supplies:
        online = any(s["online"] for s in supplies)
    else:
        line_devices = [d for d in devices if d.get("Type") == 1 and d.get("PowerSupply")]
        online = any(d.get("Online") for d in line_devices) if line_devices else None
    return {"timestamp": now, "acOnline": online, "supplies": supplies, "batteries": batteries}


def load_history(path):
    try:
        if path.stat().st_size > 8 * 1024 * 1024:
            return {}
        def invalid_constant(value):
            raise ValueError("Invalid JSON number: " + value)
        value = json.loads(path.read_text(), parse_constant=invalid_constant)
        if (isinstance(value, dict) and value.get("schemaVersion") == 1
                and isinstance(value.get("history"), list)
                and isinstance(value.get("events"), list)):
            return value
    except (OSError, ValueError):
        pass
    return {}


def with_history(sample, previous):
    now = sample["timestamp"]
    history = [s for s in previous.get("history", []) if isinstance(s, dict)
               and isinstance(s.get("timestamp"), (float, int))
               and isinstance(s.get("batteries"), list)
               and all(isinstance(b, dict) and isinstance(b.get("id"), str) for b in s["batteries"])
               and now - WINDOW_SECONDS <= s["timestamp"] <= now]
    events = [e for e in previous.get("events", []) if isinstance(e, dict)
              and isinstance(e.get("timestamp"), (float, int))
              and isinstance(e.get("label"), str) and isinstance(e.get("kind"), str)
              and now - WINDOW_SECONDS <= e["timestamp"] <= now]
    last = history[-1] if history else None
    # Multiple bar instances/reloads must not duplicate the same sample.
    if last and now - last["timestamp"] < 2:
        return dict(previous, **sample)
    if last and now - last["timestamp"] <= 30:
        if sample["acOnline"] is not None and last.get("acOnline") is not None and sample["acOnline"] != last["acOnline"]:
            events.append({"timestamp": now, "kind": "ac", "label": "External power connected" if sample["acOnline"] else "External power disconnected"})
        old = {b["id"]: b for b in last.get("batteries", []) if isinstance(b, dict) and "id" in b}
        current = {b["id"]: b for b in sample["batteries"]}
        for key, battery in current.items():
            if key not in old:
                events.append({"timestamp": now, "kind": "battery", "label": key + ": battery detected"})
            elif battery["status"] != old[key].get("status"):
                events.append({"timestamp": now, "kind": "state", "label": key + ": " + battery["status"]})
        for key in old.keys() - current.keys():
            events.append({"timestamp": now, "kind": "battery", "label": key + ": battery removed"})
    elif last:
        events.append({"timestamp": now, "kind": "gap", "label": "Monitoring resumed; readings unavailable during the gap"})
    history.append(sample)
    return dict(sample, schemaVersion=1, history=history[-MAX_SAMPLES:], events=events[-MAX_EVENTS:])


def record(sample, state_file):
    """Lock the shared history across monitors; replace atomically, mode 0600."""
    try:
        state_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (state_file.parent / ".history.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            payload = with_history(sample, load_history(state_file))
            fd, temp = tempfile.mkstemp(prefix=".history-", dir=state_file.parent)
            try:
                with os.fdopen(fd, "w") as out:
                    json.dump(payload, out, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
                    out.write("\n")
                os.replace(temp, state_file)
            finally:
                Path(temp).unlink(missing_ok=True)
            return payload
    except OSError as exc:
        return dict(sample, history=[sample], events=[], storageError=str(exc))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true", help="Emit newline-delimited JSON every interval")
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--sysfs", type=Path, default=Path("/sys/class/power_supply"))
    parser.add_argument("--no-upower", action="store_true", help="Only read sysfs (also useful for fixtures)")
    parser.add_argument("--state-file", type=Path, help="Record a bounded history; omitted for a read-only snapshot")
    args = parser.parse_args()
    if not math.isfinite(args.interval) or args.interval < 2:
        parser.error("interval must be at least 2 seconds")
    while True:
        start = time.monotonic()
        sample = collect(args.sysfs, devices=[] if args.no_upower else None)
        payload = record(sample, args.state_file) if args.state_file else dict(sample, history=[sample], events=[])
        try:
            print(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")), flush=True)
        except BrokenPipeError:
            break
        if not args.watch:
            break
        time.sleep(max(0.1, args.interval - (time.monotonic() - start)))


if __name__ == "__main__":
    main()
