const {test} = require('node:test');
const assert = require('node:assert/strict');
const X = require('./explorer.js');

test('calendar crosses year boundaries and includes absent months', () => {
  assert.deepEqual(X.calendar('2024-12', '2025-02'), ['2024-12','2025-01','2025-02']);
  assert.equal(X.shift('2024-02', -12), '2023-02');
});
test('reported values preserve zero and missing calendar months', () => {
  assert.deepEqual(X.select({'2024-01':0,'2024-03':3}, 'level', '2024-01', '2024-03'),
    [['2024-01',0],['2024-02',null],['2024-03',3]]);
});
test('year-over-year comparisons use calendar months, not the twelfth previous row', () => {
  const values = {'2023-01':100,'2023-03':20,'2024-01':110,'2024-02':15,'2024-03':10};
  const result = X.select(values, 'yoy', '2024-01', '2024-03');
  assert.ok(Math.abs(result[0][1] - 10) < 1e-10);
  assert.equal(result[1][1], null);
  assert.equal(result[2][1], -50);
});
test('transforms can read a baseline before the selected date range', () => {
  assert.deepEqual(X.select({'2023-01':5,'2024-01':5.5}, 'difference', '2024-01', '2024-01'), [['2024-01',0.5]]);
});
test('a zero baseline is missing for percent change and valid for a difference', () => {
  const values = {'2023-01':0,'2024-01':3};
  assert.equal(X.select(values,'yoy','2024-01','2024-01')[0][1], null);
  assert.equal(X.select(values,'difference','2024-01','2024-01')[0][1], 3);
});
test('reversed and unavailable windows return no observations', () => {
  assert.deepEqual(X.select({'2024-01':1},'level','2024-02','2024-01'), []);
  assert.deepEqual(X.select({'2024-01':1},'level','2025-01','2025-02'), []);
  assert.deepEqual(X.select({},'level','2025-01','2025-02'), []);
});
test('unknown transformation fails rather than silently selecting a calculation', () => {
  assert.throws(() => X.select({'2024-01':1}, 'typo', '2024-01', '2024-01'));
});
test('chart segments break across missing months, retaining real zeroes and isolated readings', () => {
  assert.deepEqual(X.segments([['a',0],['b',2],['c',null],['d',4]]), [[[0,0],[1,2]],[[3,4]]]);
  assert.deepEqual(X.segments([['a',null]]), []);
});
test('catalog prefers full history and excludes duplicate static history', () => {
  const csv='series,date,value\nep_unrate,2024-01-01,1\nfull/ep_unrate,2000-01-01,2\nfull/ep_unrate,2024-01-01,1\nextra/example,2024-01-01,0';
  const files=['ep_unrate','pre2015/ep_unrate','full/ep_unrate','extra/example'].map(id=>({file:'data/'+id+'.csv',description:id}));
  const catalog=X.catalog(csv,{files});
  assert.deepEqual(catalog.map(s=>s.id), ['extra/example','full/ep_unrate']);
  assert.equal(catalog[1].values['2000-01'],2);
  assert.equal(catalog[0].values['2024-01'],0);
});
test('CSV contains only the selection, keeps missing values blank, and quotes provenance', () => {
  const csv=X.csv({id:'full/ep_unrate',series_id:'ELPA348UR',source:'BLS, via FRED',retrieved:'2026-10-12 ("snapshot")'},'difference',[['2024-01',0],['2024-02',null]]);
  assert.match(csv, /"2024-01","difference","0"/);
  assert.match(csv, /"2024-02","difference",""/);
  assert.match(csv, /"BLS, via FRED"/);
  assert.match(csv, /"2026-10-12 \(""snapshot""\)"/);
});
