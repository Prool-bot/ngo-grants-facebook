'use strict';
const assert=require('node:assert/strict');
const {test}=require('node:test');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
test('standalone preview includes local image, CSS and complete working JS',()=>{
 const html=fs.readFileSync(path.join(root,'preview.html'),'utf8');
 assert.match(html,/data:image\/svg\+xml,/);
 assert.match(html,/NgoGrantsSchema/);
 assert.match(html,/const pages=\[/);
 assert.match(html,/position:sticky/);
 assert.match(html,/Це окремий прототип/);
 assert.doesNotMatch(html,/<script[^>]+src=|<link[^>]+href=/);
 assert.doesNotMatch(html,/\\bfetch\\s*\\(/);
 assert.match(html,/data-native-send="false"/);
 assert.match(html,/const live=root\\.dataset\\.nativeSend==='true'/);
});
