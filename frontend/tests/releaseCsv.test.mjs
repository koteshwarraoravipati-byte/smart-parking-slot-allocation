import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

// Test the actual TypeScript implementation without adding a test framework.
const source = readFileSync(new URL('../src/releaseCsv.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText;
const {buildReleaseCsv} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const entry = {id:21,admin_id:8,admin_username:'operator',booking_id:42,username:'owner',vehicle:'TEST CAR',space:'P-03',released_at:'2026-11-02T10:00:00+00:00',reason:'Vehicle departed',amount_cents:2000};

test('includes required admin booking time reason columns',()=>{
  const csv=buildReleaseCsv([entry]);
  assert.ok(csv.startsWith('\uFEFF"Audit ID","Admin","Admin ID","Booking ID","Released at (ISO 8601)","Reason"'));
  assert.ok(csv.includes('"21","operator","8","42","2026-11-02T10:00:00+00:00","Vehicle departed"'));
  assert.ok(csv.includes('"20.00"'));
});
test('quotes commas double quotes and embedded newlines',()=>{
  const csv=buildReleaseCsv([{...entry,reason:'Driver said "left", verified\nby desk'}]);
  assert.ok(csv.includes('"Driver said ""left"", verified\nby desk"'));
});
test('preserves unicode',()=>{
  assert.ok(buildReleaseCsv([{...entry,reason:'వాహనం వెళ్లింది'}]).includes('వాహనం వెళ్లింది'));
});
test('empty history exports headers only',()=>{
  assert.equal(buildReleaseCsv([]).split('\r\n').length,2);
});
test('older entries have an explicit missing reason',()=>{
  assert.ok(buildReleaseCsv([{...entry,reason:undefined}]).includes('Not recorded (older entry)'));
});
for(const dangerous of ['=1+1','+SUM(1,2)','-1+1','@SUM(1,2)','  =1+1','\t=1+1','\r=1+1','\n=1+1']){
  test('neutralizes spreadsheet formula prefix '+JSON.stringify(dangerous),()=>{
    const csv=buildReleaseCsv([{...entry,reason:dangerous,admin_username:dangerous,username:dangerous,vehicle:dangerous,space:dangerous}]);
    const protectedCell='"\''+dangerous.replace(/"/g,'""')+'"';
    assert.equal(csv.split(protectedCell).length-1,5);
  });
}
test('does not mutate audit data',()=>{
  const row=Object.freeze({...entry,reason:'=1+1'});
  buildReleaseCsv(Object.freeze([row]));
  assert.equal(row.reason,'=1+1');
});
