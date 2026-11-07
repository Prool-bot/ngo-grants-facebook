import test from 'node:test';
import assert from 'node:assert/strict';
import {createHmac,webcrypto} from 'node:crypto';
import {validateTelegramInitData} from '../../worker/mini_app_verify_init_data.mjs';
if(!globalThis.crypto)globalThis.crypto=webcrypto;
const token='123456789:TEST-bot-token-for-offline-tests-only';
const time=1794067200;

function signedInitData(user={id:23456789,first_name:'Олена'},ts=time){
  const params=new URLSearchParams();
  params.set('user',JSON.stringify(user));
  params.set('auth_date',String(ts));
  params.set('query_id','offline-test');
  const check=[...params].sort(([a],[b])=>a.localeCompare(b))
    .map(([key,value])=>key+'='+value).join('\n');
  const key=createHmac('sha256','WebAppData').update(token).digest();
  const hash=createHmac('sha256',key).update(check).digest('hex');
  params.set('hash',hash);
  return params.toString();
}
test('valid data returns only authenticated user ID and date',async()=>{
  const decoded=await validateTelegramInitData(signedInitData(),token,{now:time+30});
  assert.deepEqual(decoded,{userId:23456789,authDate:time});
  assert.equal(Object.isFrozen(decoded),true);
});
test('tampered user is refused',async()=>{
  const tampered=signedInitData().replace('%D0%9E%D0%BB%D0%B5%D0%BD%D0%B0','attacker');
  await assert.rejects(validateTelegramInitData(tampered,token,{now:time+30}));
});
test('replayed and future timestamps are refused',async()=>{
  await assert.rejects(validateTelegramInitData(signedInitData(),token,{now:time+4000}));
  await assert.rejects(validateTelegramInitData(signedInitData(),token,{now:time-31}));
});
test('duplicate URL parameters and missing hash are refused',async()=>{
  const data=signedInitData();
  await assert.rejects(validateTelegramInitData(data+'&auth_date='+time,token,{now:time+1}));
  await assert.rejects(validateTelegramInitData(data.replace(/&hash=.*/,''),token,{now:time+1}));
});
test('bot identity and invalid ID are refused',async()=>{
  await assert.rejects(validateTelegramInitData(
    signedInitData({id:999,is_bot:true}),token,{now:time+1}));
  await assert.rejects(validateTelegramInitData(
    signedInitData({id:-5}),token,{now:time+1}));
});
test('rejects absurd freshness settings and oversized initData',async()=>{
  await assert.rejects(validateTelegramInitData(signedInitData(),token,{now:time+1,maxAgeSeconds:100000}));
  await assert.rejects(validateTelegramInitData('a'.repeat(9000),token,{now:time+1}));
});
test('published Telegram Mini Apps documentation HMAC fixture',async()=>{
  const officialToken='5768337691:AAH5YkoiEuPk8-FZa32hStHTqXiLPtAEhx8';
  const params=new URLSearchParams();
  params.set('query_id','AAHdF6IQAAAAAN0XohDhrOrc');
  params.set('user',JSON.stringify({id:279058397,first_name:'Vladislav',
    last_name:'Kibenko',username:'vdkfrost',language_code:'ru',is_premium:true}));
  params.set('auth_date','1662771648');
  params.set('hash','c501b71e775f74ce10e377dea85a7ea24ecd640b223ea86dfe453e0eaed2e2b2');
  const result=await validateTelegramInitData(params.toString(),officialToken,
    {now:1662771660,maxAgeSeconds:3600});
  assert.equal(result.userId,279058397);
});
