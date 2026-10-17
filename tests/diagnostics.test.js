const test = require('node:test');
const assert = require('node:assert/strict');
const d = require('../Diagnostics.js');

const battery = (values = {}) => ({id: 'BAT1', status: 'Not charging', percentage: 25,
  currentA: 0, voltageV: 15, powerW: 0, limitPercent: 100, ...values});
const sample = (values = {}, options = {}) => ({timestamp: 100, acOnline: true,
  batteries: [battery(values)], ...options});
const classify = (values = {}, options = {}, history = []) => {
  const s = sample(values, options);
  return d.classify(s, s.batteries[0], history);
};
const stable = (values = {}) => [90, 95, 100].map(timestamp => sample(values, {timestamp}));

test('deeply discharged pending charge is never assumed to be a charge limit or recovery', () => {
  const result = classify({percentage: 0});
  assert.equal(result.code, 'idle');
  assert.match(result.label, /Not charging/);
  assert.match(result.reason, /unknown/);
  assert.doesNotMatch(result.label, /[Rr]ecover|[Hh]ot|[Ll]imit/);
});
test('configured charge limit must actually be reached with idle measurements', () => {
  assert.equal(classify({limitPercent: 80, percentage: 25}).code, 'idle');
  assert.equal(classify({limitPercent: 80, percentage: 80}).code, 'limit');
  assert.equal(classify({limitPercent: 80, percentage: 80, currentA: null, powerW: null}).code, 'idle');
  assert.equal(classify({limitPercent: 100, percentage: 80}).code, 'idle');
});
test('normal charging and long time estimates do not imply a charge limit', () => {
  assert.equal(classify({status: 'Charging', currentA: 2, powerW: 30, timeToFullS: 40000}).code, 'charging');
});
test('small charging current needs a sustained window', () => {
  const b = {status: 'Charging', currentA: 0.08, powerW: 1.2};
  assert.equal(classify(b).code, 'charging');
  assert.equal(classify(b, {}, stable(b)).code, 'slow');
});
test('a current spike cannot create a slow charging label', () => {
  const b = {status: 'Charging', currentA: 0.08, powerW: 1.2};
  const history = stable(b);
  history[1].batteries[0].currentA = 1;
  history[1].batteries[0].powerW = 15;
  assert.equal(classify(b, {}, history).code, 'charging');
});
test('milliamp charging is shown rather than rounded away as Holding', () => {
  const b = {status: 'Charging', currentA: 0.005, powerW: 0.075};
  assert.equal(classify(b, {}, stable(b)).code, 'slow');
  assert.equal(d.amps(0.005), '5.0 mA');
  assert.equal(d.amps(null), 'Unavailable');
});
test('zero flow while reporting charging is checked before declaring no measurable charge', () => {
  const b = {status: 'Charging'};
  assert.equal(classify(b).code, 'checking');
  assert.equal(classify(b, {}, stable(b)).label, 'No measurable charging');
});
test('charging without sensors remains reported charging with an honest explanation', () => {
  const result = classify({status: 'Charging', currentA: null, powerW: null});
  assert.equal(result.code, 'charging');
  assert.match(result.reason, /unavailable/);
  assert.equal(result.currentA, null);
});
test('flow evidence may come from amps when watts are unavailable', () => {
  assert.equal(classify({status: 'Charging', currentA: 1, powerW: null}).code, 'charging');
});
test('AC disconnected overrides an inconsistent charging claim', () => {
  assert.equal(classify({status: 'Charging', currentA: 2, powerW: 30}, {acOnline: false}).code, 'conflict');
});
test('draining on AC describes observed behavior without naming an adapter fault', () => {
  const result = classify({status: 'Discharging', currentA: 2, powerW: 30});
  assert.equal(result.label, 'Battery draining on AC');
  assert.match(result.reason, /unknown/);
});
test('discharging positive ACPI current and negative signed current have the same displayed direction', () => {
  const p = sample({status: 'Discharging', currentA: 2});
  assert.equal(d.series([p], 'BAT1', 'currentA')[0].value, -2);
});
test('pending state with significant flow is a conflict, not a made-up recovery explanation', () => {
  assert.equal(classify({currentA: 1, powerW: 15}).code, 'conflict');
});
test('conflicting current and watt sensors cannot produce a confident idle or charging label', () => {
  assert.equal(classify({status: 'Charging', currentA: 0, powerW: 30}).code, 'conflict');
  assert.equal(classify({status: 'Charging', currentA: 1, powerW: 0}).code, 'conflict');
});
test('full only when the battery reports full near 100%', () => {
  assert.equal(classify({status: 'Full', percentage: 100}).code, 'full');
  assert.equal(classify({status: 'Full', percentage: 60}).code, 'idle');
});
test('missing AC detection is not treated as disconnected', () => {
  assert.equal(classify({}, {acOnline: null}).code, 'unknown');
});
test('smoothing never crosses a charge/discharge transition', () => {
  const history = stable({status: 'Discharging', currentA: 3, powerW: 45});
  const result = classify({status: 'Charging', currentA: 1, powerW: 15}, {}, history);
  assert.equal(result.currentA, 1);
});
test('smoothing stops at observation gaps', () => {
  const history = [sample({status: 'Charging', currentA: 3, powerW: 45}, {timestamp: 80}),
    sample({status: 'Charging', currentA: 1, powerW: 15})];
  assert.equal(classify({status: 'Charging', currentA: 1, powerW: 15}, {}, history).currentA, 1);
});
test('selecting a pack keeps its own metrics, not an unrelated aggregate', () => {
  const payload = sample();
  payload.batteries.push(battery({id: 'CMB0', status: 'Charging', currentA: 2, powerW: 30}));
  assert.equal(d.view(payload, 'CMB0', 100).battery.id, 'CMB0');
  assert.equal(d.view(payload, 'CMB0', 100).currentA, 2);
  assert.equal(d.view(payload, 'removed-pack', 100).battery.id, 'BAT1');
});
test('stale readings cannot masquerade as live charging', () => {
  const result = d.view(sample({status: 'Charging', currentA: 2, powerW: 30}), '', 125);
  assert.equal(result.code, 'stale');
  assert.match(result.reason, /25s ago/);
});
test('initial loading and a batteryless system are handled', () => {
  assert.equal(d.view({}, '', 100).code, 'stale');
  assert.equal(d.view({timestamp: 100, batteries: []}, '', 100).code, 'missing');
});
test('state duration stops at data gaps and power changes', () => {
  const payload = sample();
  payload.history = [sample({}, {timestamp: 50}), sample({}, {timestamp: 90}), payload];
  assert.equal(d.view(payload, '', 100).since, 90);
  payload.history[1].acOnline = false;
  assert.equal(d.view(payload, '', 100).since, 100);
});
test('connection instability requires multiple recent observed changes', () => {
  const payload = sample();
  payload.events = [20, 30, 40].map(timestamp => ({timestamp, kind: 'ac'}));
  assert.equal(d.view(payload, '', 100).unstable, true);
  assert.equal(d.view({...payload, timestamp: 300}, '', 300).unstable, false);
});
test('unknown graph direction is a gap, not an invented charge/discharge line', () => {
  assert.equal(d.series([sample({currentA: 1, powerW: 15})], 'BAT1', 'currentA')[0].value, null);
  assert.equal(d.series([sample()], 'BAT1', 'currentA')[0].value, 0);
  assert.equal(d.series([sample({currentA: null})], 'BAT1', 'currentA')[0].value, null);
});
test('voltage trend requires a minute of evidence and never diagnoses recovery', () => {
  assert.equal(d.voltageTrend([sample()], 'BAT1'), 'Collecting voltage history');
  const history = Array.from({length: 13}, (_, i) => sample({voltageV: 14 + i / 12}, {timestamp: 40 + i * 5}));
  assert.match(d.voltageTrend(history, 'BAT1'), /rising.*cause unknown/);
  assert.equal(d.voltageTrend([history[0], history[12]], 'BAT1'), 'Collecting voltage history');
});
test('null and zero stay distinct in formatting', () => {
  assert.equal(d.metric(null, 'A'), 'Unavailable');
  assert.equal(d.metric(0, 'A'), '0.00 A');
  assert.equal(d.duration(null), 'Unavailable');
  assert.equal(d.duration(3661), '1h 1m');
});
