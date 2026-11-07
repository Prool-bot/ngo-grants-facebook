'use strict';
const assert=require('node:assert/strict');
const {test}=require('node:test');
const fs=require('node:fs');
const path=require('node:path');
const schema=require('../schema.js');
const root=path.resolve(__dirname,'..');
const valid={
 audience:'nonprofit',sectors:['social','recovery'],geo:'region',region:'kharkiv',
 detail:'Соціальний транспорт',custom_sector:'',applicant_role:'lead',funding_format:'grant_only'
};
test('matching existing Worker/Python facets, preserving exact enum IDs',()=>{
 const normalized=schema.normalize(valid);
 assert.deepEqual(normalized,valid);
 assert.equal(schema.regions.kharkiv,'Харківська');
});
test('multiple sectors are alternatives and deduplicated',()=>{
 const normalized=schema.normalize({...valid,sectors:['social','social','recovery']});
 assert.deepEqual(normalized.sectors,['social','recovery']);
});
test('all sectors removes custom sector and overrides specific selections',()=>{
 const normalized=schema.normalize({...valid,sectors:['all','social'],custom_sector:'Кіно'});
 assert.deepEqual(normalized.sectors,['all']);
 assert.equal(normalized.custom_sector,'');
});
test('rejects incomplete/invalid facet values before any future backend request',()=>{
 for(const patch of [
  {audience:'unknown'},{geo:'eu'},{geo:'region',region:'invalid'},
  {sectors:[]},{sectors:['social','unknown']},{funding_format:'donation'},
  {applicant_role:'owner'}
 ]){
  assert.throws(()=>schema.normalize({...valid,...patch}));
 }
});
test('international and nationwide modes do not retain a region',()=>{
 for(const geo of ['ukraine','international','all']){
  assert.equal(schema.normalize({...valid,geo}).region,'');
 }
});
test('details and custom sector are length bounded',()=>{
 const f=schema.normalize({...valid,custom_sector:'X'.repeat(100),detail:'A'.repeat(500)});
 assert.equal(f.custom_sector.length,60);
 assert.equal(f.detail.length,180);
});
test('preview remains offline: no POST/fetch or Telegram sendData in client',()=>{
 const code=fs.readFileSync(path.join(root,'app.js'),'utf8');
 const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
 assert.doesNotMatch(code,/\bfetch\s*\(|XMLHttpRequest|sendMessage|sendDocument/);
 assert.doesNotMatch(html,/https?:\/\//);
 assert.match(html,/Демонстрація/);
 assert.match(html,/data-native-send="false"/);
 assert.match(code,/root\.dataset\.nativeSend==='true'/);
 assert.match(code,/\.WebApp\.ready/);
});
test('approved mascot and compact positioning are retained',()=>{
 const svg=fs.readFileSync(path.join(root,'assets','mascot.svg'),'utf8');
 const css=fs.readFileSync(path.join(root,'styles.css'),'utf8');
 assert.match(svg,/data:image\/webp;base64,/);
 assert.match(css,/position:sticky/);
 assert.match(css,/prefers-reduced-motion/);
 assert.doesNotMatch(svg,/antenna/i);
});
