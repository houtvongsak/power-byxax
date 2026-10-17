import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("telemetry", Path(__file__).resolve().parents[1] / "bin/telemetry.py")
t = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t)


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def supply(self, name, **fields):
        path = self.root / name
        path.mkdir(exist_ok=True)
        for key, value in fields.items():
            (path / key).write_text(str(value))
        return path

    def snapshot(self, **fields):
        return dict(timestamp=100, acOnline=True, supplies=[], batteries=[dict(id="BAT1", status="Not charging", **fields)])

    def test_rog_units_and_disabled_upower_limit(self):
        self.supply("BAT1", type="Battery", present=1, status="Charging", capacity=25,
                    voltage_now=16000000, current_now=2000000, charge_control_end_threshold=100,
                    charge_full=2800000, charge_full_design=5600000)
        self.supply("ACAD", type="Mains", online=1)
        props = dict(Type=2, PowerSupply=True, NativePath="BAT1", UpdateTime=100,
                     ChargeThresholdEnabled=False, ChargeEndThreshold=80, ChargeStartThreshold=75)
        sample = t.collect(self.root, [props], 100)
        b = sample["batteries"][0]
        self.assertTrue(sample["acOnline"])
        self.assertEqual((b["currentA"], b["voltageV"], b["powerW"]), (2, 16, 32))
        self.assertEqual(b["limitPercent"], 100)
        self.assertIsNone(b["startPercent"])
        self.assertEqual(b["healthPercent"], 50)
        self.assertIsNone(b["temperatureC"])

    def test_battery_names_multiple_packs_usb_and_peripheral_filter(self):
        self.supply("CMB0", type="Battery", status="Discharging", capacity=20)
        self.supply("BAT9", type="Battery", status="Charging", capacity=90)
        self.supply("hid-mouse", type="Battery", scope="Device", capacity=50)
        self.supply("gone", type="Battery", present=0)
        self.supply("USB-C", type="USB", online=1)
        sample = t.collect(self.root, [], 100)
        self.assertEqual({b["id"] for b in sample["batteries"]}, {"CMB0", "BAT9"})
        self.assertTrue(sample["acOnline"])

    def test_no_battery_and_no_adapter_is_unknown(self):
        sample = t.collect(self.root, [], 100)
        self.assertEqual(sample["batteries"], [])
        self.assertIsNone(sample["acOnline"])

    def test_missing_sensors_are_null_not_zero(self):
        self.supply("BAT0", type="Battery", status="Unknown")
        b = t.collect(self.root, [], 100)["batteries"][0]
        for field in ["currentA", "voltageV", "powerW", "percentage", "limitPercent"]:
            self.assertIsNone(b[field])

    def test_power_sensor_estimates_current(self):
        self.supply("BAT0", type="Battery", status="Charging", voltage_now=12000000, power_now=24000000)
        b = t.collect(self.root, [], 100)["batteries"][0]
        self.assertEqual(b["currentA"], 2)
        self.assertTrue(b["currentEstimated"])

    def test_sysfs_status_and_rate_win_over_upower(self):
        self.supply("BAT0", type="Battery", status="Discharging", voltage_now=12000000, current_now=1000000)
        props = dict(Type=2, PowerSupply=True, NativePath="BAT0", UpdateTime=100, State=1, EnergyRate=40)
        b = t.collect(self.root, [props], 100)["batteries"][0]
        self.assertEqual((b["status"], b["powerW"]), ("Discharging", 12))
        self.assertTrue(b["conflicts"])

    def test_upower_fallback_and_enabled_limit(self):
        devices = [dict(Type=2, PowerSupply=True, NativePath="CMB0", IsPresent=True,
                        UpdateTime=100, State=5, Percentage=80, EnergyRate=0, Voltage=12,
                        ChargeThresholdEnabled=True, ChargeEndThreshold=80),
                   dict(Type=1, PowerSupply=True, Online=True)]
        sample = t.collect(self.root, devices, 100)
        b = sample["batteries"][0]
        self.assertEqual((b["status"], b["limitPercent"], b["limitSource"]), ("Not charging", 80, "UPower"))
        self.assertTrue(sample["acOnline"])

    def test_stale_upower_measurements_are_not_live(self):
        devices = [dict(Type=2, PowerSupply=True, NativePath="BAT0", IsPresent=True,
                        UpdateTime=1, State=1, EnergyRate=30, Percentage=80)]
        b = t.collect(self.root, devices, 1000)["batteries"][0]
        self.assertEqual(b["status"], "Unknown")
        self.assertIsNone(b["powerW"])
        self.assertIsNone(b["percentage"])

    def test_percentage_and_nominal_energy_from_charge(self):
        self.supply("BAT0", type="Battery", charge_now=1000000, charge_full=2000000,
                    charge_full_design=4000000, voltage_min_design=15000000)
        b = t.collect(self.root, [], 100)["batteries"][0]
        self.assertEqual((b["percentage"], b["fullWh"], b["designWh"]), (50, 30, 60))

    def test_temperature_and_signed_discharge_magnitude(self):
        self.supply("BAT0", type="Battery", status="Discharging", current_now=-1000000, temp=335)
        b = t.collect(self.root, [], 100)["batteries"][0]
        self.assertEqual(b["currentA"], 1)
        self.assertEqual(b["temperatureC"], 33.5)

    def test_limit_source_conflict_and_invalid_values(self):
        self.supply("BAT0", type="Battery", charge_control_end_threshold=100)
        props = dict(Type=2, PowerSupply=True, NativePath="BAT0", ChargeThresholdEnabled=True, ChargeEndThreshold=80)
        b = t.collect(self.root, [props], 100)["batteries"][0]
        self.assertEqual(b["limitPercent"], 100)
        self.assertTrue(b["conflicts"])
        self.supply("BAT0", charge_control_end_threshold=255, current_now="NaN")
        b = t.collect(self.root, [], 100)["batteries"][0]
        self.assertIsNone(b["limitPercent"])
        self.assertIsNone(b["currentA"])

    def test_history_records_connections_and_state_changes(self):
        first = t.with_history(self.snapshot(), {})
        second = dict(self.snapshot(), timestamp=105, acOnline=False,
                      batteries=[dict(id="BAT1", status="Discharging")])
        result = t.with_history(second, first)
        self.assertEqual([e["kind"] for e in result["events"]], ["ac", "state"])
        self.assertEqual(len(result["history"]), 2)

    def test_gap_is_not_mistaken_for_observed_unplug(self):
        first = t.with_history(self.snapshot(), {})
        result = t.with_history(dict(self.snapshot(), timestamp=200, acOnline=False), first)
        self.assertEqual([e["kind"] for e in result["events"]], ["gap"])

    def test_history_is_bounded_and_duplicate_sampling_is_coalesced(self):
        result = {}
        for timestamp in range(0, 3000, 5):
            result = t.with_history(dict(self.snapshot(), timestamp=timestamp), result)
        self.assertLessEqual(len(result["history"]), t.MAX_SAMPLES)
        duplicate = t.with_history(dict(self.snapshot(), timestamp=2996), result)
        self.assertLessEqual(len(duplicate["history"]), len(result["history"]))
        self.assertEqual(duplicate["history"][-1]['timestamp'], result["history"][-1]['timestamp'])
        self.assertGreaterEqual(result["history"][0]["timestamp"], 2995 - 1800)

    def test_corrupt_history_recovers_and_storage_is_private(self):
        path = self.root / "history.json"
        path.write_text("incomplete{")
        result = t.record(self.snapshot(), path)
        self.assertEqual(len(result["history"]), 1)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(path.read_text())["schemaVersion"], 1)

    def test_storage_failure_does_not_stop_live_reading(self):
        obstruction = self.root / "not-a-directory"
        obstruction.write_text("x")
        result = t.record(self.snapshot(), obstruction / "history.json")
        self.assertIn("storageError", result)
        self.assertEqual(result["batteries"][0]["id"], "BAT1")

    def test_malformed_history_records_are_discarded(self):
        path = self.root / "history.json"
        path.write_text(json.dumps(dict(schemaVersion=1, history=[dict(timestamp=99, batteries=None)], events=[None])))
        result = t.record(self.snapshot(), path)
        self.assertEqual(len(result["history"]), 1)
        self.assertEqual(result["events"], [])

    def test_full_native_path_does_not_duplicate_a_pack(self):
        self.supply("BAT0", type="Battery", status="Charging", capacity=40)
        props = dict(Type=2, PowerSupply=True, NativePath="/sys/devices/test/power_supply/BAT0", IsPresent=True)
        sample = t.collect(self.root, [props], 100)
        self.assertEqual(len(sample["batteries"]), 1)
        self.assertEqual(sample["batteries"][0]["id"], "BAT0")

    def test_absent_kernel_pack_is_not_resurrected_by_upower_lag(self):
        self.supply("BAT0", type="Battery", present=0)
        props = dict(Type=2, PowerSupply=True, NativePath="BAT0", IsPresent=True)
        self.assertEqual(t.collect(self.root, [props], 100)["batteries"], [])

    def test_history_checkpoints_once_per_minute_and_flushes_on_close(self):
        path = self.root / "history.json"
        history = t.History(path)
        with patch.object(t, 'record', wraps=t.record) as save:
            for i in range(13):
                history.update(dict(self.snapshot(), timestamp=100 + i * 5), monotonic=i * 5)
            self.assertEqual(save.call_count, 2)
            self.assertEqual(len(history.payload['history']), 13)
            history.flush()
            self.assertEqual(save.call_count, 2)
            history.update(dict(self.snapshot(), timestamp=165), monotonic=65)
            self.assertEqual(json.loads(path.read_text())['timestamp'], 160)
            history.flush()
            self.assertEqual(json.loads(path.read_text())['timestamp'], 165)

    def test_connection_events_are_checkpointed_immediately(self):
        path = self.root / "history.json"
        history = t.History(path)
        history.update(self.snapshot(), monotonic=0)
        history.update(dict(self.snapshot(), timestamp=105, acOnline=False), monotonic=5)
        stored = json.loads(path.read_text())
        self.assertEqual(stored['timestamp'], 105)
        self.assertEqual(stored['events'][0]['kind'], 'ac')

    def test_storage_errors_preserve_in_memory_history_and_remain_visible(self):
        obstruction = self.root / "obstruction"
        obstruction.write_text('x')
        history = t.History(obstruction / "history.json")
        for i in range(5):
            payload = history.update(dict(self.snapshot(), timestamp=100 + i * 5), monotonic=i * 5)
            self.assertIn('storageError', payload)
        self.assertEqual(len(payload['history']), 5)
        history.path = self.root / 'recovered.json'
        history.flush()
        self.assertNotIn('storageError', history.payload)
        self.assertEqual(len(json.loads(history.path.read_text())['history']), 5)

    def test_upower_queries_are_cached_and_refresh_on_connection_change(self):
        self.supply('BAT0', type='Battery', status='Charging', capacity=40, current_now=1000000, voltage_now=12000000)
        self.supply('AC', type='Mains', online=1)
        reader = t.Reader(self.root)
        with patch.object(t, 'upower_devices', return_value=[]) as query, patch.object(t.time, 'monotonic', side_effect=[0, 5, 10, 31, 32]):
            for _ in range(3): reader.sample()
            self.assertEqual(query.call_count, 1)
            query.assert_called_with(include_lines=False)
            reader.sample()
            self.assertEqual(query.call_count, 2)
            self.supply('AC', online=0)
            reader.sample()
            self.assertEqual(query.call_count, 3)

    def test_history_omits_repeated_metadata_but_keeps_diagnostic_inputs(self):
        sample = self.snapshot(currentA=0.005, powerW=0.075, voltageV=15, percentage=20, limitPercent=80, model='Repeated model', conflicts=[])
        payload = t.with_history(sample, {})
        recorded = payload['history'][0]['batteries'][0]
        self.assertEqual(recorded['currentA'], 0.005)
        self.assertEqual(recorded['limitPercent'], 80)
        self.assertNotIn('model', recorded)
        self.assertNotIn('conflicts', recorded)
        self.assertEqual(payload['batteries'][0]['model'], 'Repeated model')

    def test_invalid_encoding_and_deeply_nested_json_do_not_crash_loading(self):
        path = self.root / 'history.json'
        path.write_bytes(b'\xff')
        self.assertEqual(t.load_history(path), {})
        path.write_text('[' * 3000 + '0' + ']' * 3000)
        self.assertEqual(t.load_history(path), {})

    def test_nonfinite_historical_metrics_cannot_break_serialization(self):
        prior = dict(schemaVersion=1, history=[dict(timestamp=95, acOnline={'bad':float('inf')}, batteries=[dict(id='BAT1', status={'bad':float('inf')}, powerW=float('inf'))])], events=[])
        payload = t.with_history(self.snapshot(), prior)
        self.assertIsNone(payload['history'][0]['batteries'][0]['powerW'])
        self.assertEqual(payload['history'][0]['batteries'][0]['status'], 'Unknown')
        self.assertIsNone(payload['history'][0]['acOnline'])
        json.dumps(payload, allow_nan=False)

    def test_partial_kernel_telemetry_keeps_upower_fallback_live(self):
        self.supply('BAT0', type='Battery', status='Charging', capacity=40)
        reader = t.Reader(self.root)
        with patch.object(t, 'upower_devices', return_value=[]) as query:
            reader.sample()
            reader.sample()
            self.assertEqual(query.call_count, 2)

    def test_bad_firmware_text_is_replaced_without_crashing(self):
        path = self.supply('BAT0', type='Battery', status='Charging')
        (path / 'model_name').write_bytes(b'Battery\xff')
        self.assertIn('\ufffd', t.collect(self.root, [], 100)['batteries'][0]['model'])

    def test_watch_shutdown_flushes_latest_sample(self):
        self.supply('BAT0', type='Battery', status='Charging', current_now=1000000, voltage_now=12000000)
        state = self.root / 'state/history.json'
        process = subprocess.Popen([sys.executable, str(Path(t.__file__)), '--watch', '--interval', '2', '--no-upower',
                                    '--sysfs', str(self.root), '--state-file', str(state)], stdout=subprocess.PIPE, text=True)
        try:
            first = json.loads(process.stdout.readline())
            second = json.loads(process.stdout.readline())
            self.assertGreater(second['timestamp'], first['timestamp'])
            process.terminate()
            process.wait(timeout=5)
            self.assertEqual(json.loads(state.read_text())['timestamp'], second['timestamp'])
        finally:
            if process.poll() is None: process.kill(); process.wait()
            process.stdout.close()


if __name__ == "__main__":
    unittest.main()
