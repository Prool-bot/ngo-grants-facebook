(function(root,factory){
  'use strict';
  const api=factory();
  if(typeof module==='object' && module.exports){module.exports=api;}
  if(root){root.NgoGrantsSchema=api;}
})(typeof globalThis==='object'?globalThis:null,function(){
  'use strict';
  const audiences={
    nonprofit:'Громадська організація / благодійний фонд',
    commercial:'Бізнес / ФОП',
    individual:'Фізична особа',
    municipal:'Територіальна громада / орган місцевого самоврядування',
    institution:'Заклад освіти / наукова установа',
    all:'Усі типи заявників'
  };
  const sectors={
    social:'Соціальна та гуманітарна сфера',education:'Освіта та наука',
    culture:'Культура та мистецтво',medical:'Охорона здоров’я',
    recovery:'Відновлення громад',environment:'Екологія та клімат',
    agriculture:'Сільське господарство',media:'Медіа та журналістика',
    rights:'Права людини',business:'Підприємництво',it:'IT та цифровізація',
    all:'Усі напрями'
  };
  const geos={ukraine:'Україна',region:'Конкретний регіон України',
    international:'Міжнародні можливості',all:'Усі країни'};
  const regions={
    vinnytsia:'Вінницька',volyn:'Волинська',dnipro:'Дніпропетровська',
    donetsk:'Донецька',zhytomyr:'Житомирська',zakarpattia:'Закарпатська',
    zaporizhzhia:'Запорізька',ivano:'Івано-Франківська',kyiv_obl:'Київська',
    kirovohrad:'Кіровоградська',luhansk:'Луганська',lviv:'Львівська',
    mykolaiv:'Миколаївська',odesa:'Одеська',poltava:'Полтавська',
    rivne:'Рівненська',sumy:'Сумська',ternopil:'Тернопільська',
    kharkiv:'Харківська',kherson:'Херсонська',khmelnytskyi:'Хмельницька',
    cherkasy:'Черкаська',chernivtsi:'Чернівецька',chernihiv:'Чернігівська',
    kyiv_city:'Місто Київ',crimea:'АР Крим / Севастополь'
  };
  const roles={lead:'Основний заявник',partner:'Партнер',either:'Обидва варіанти'};
  const formats={grant_only:'Лише грантове фінансування',any:'Усі формати підтримки'};
  const allowedKeys=['audience','sectors','geo','region','custom_sector','detail','applicant_role','funding_format'];
  function sanitizeText(value,max){
    return String(value||'').trim().replace(/\s+/g,' ').slice(0,max);
  }
  function normalize(input){
    if(!input || typeof input!=='object'||Array.isArray(input))throw Error('Некоректні параметри');
    const a=input.audience,g=input.geo;
    if(!Object.prototype.hasOwnProperty.call(audiences,a))throw Error('Оберіть тип заявника');
    if(!Object.prototype.hasOwnProperty.call(geos,g))throw Error('Оберіть географію');
    const raw=Array.isArray(input.sectors)?input.sectors:[];
    if(raw.length>12 || raw.some(x=>!Object.prototype.hasOwnProperty.call(sectors,x)))
      throw Error('Некоректний набір напрямів');
    let unique=[...new Set(raw)];
    const custom=sanitizeText(input.custom_sector,60);
    if(unique.includes('all'))unique=['all'];
    if(!unique.length&&!custom)throw Error('Оберіть хоча б один напрям');
    const region=g==='region'?input.region:'';
    if(g==='region'&&!Object.prototype.hasOwnProperty.call(regions,region))
      throw Error('Оберіть область');
    const role=input.applicant_role||'lead',format=input.funding_format||'any';
    if(!Object.prototype.hasOwnProperty.call(roles,role))throw Error('Некоректна роль заявника');
    if(!Object.prototype.hasOwnProperty.call(formats,format))throw Error('Некоректна форма підтримки');
    return {
      audience:a,sectors:unique,
      custom_sector:unique.includes('all')?'':custom,
      geo:g,region:region||'',
      detail:sanitizeText(input.detail,180),
      applicant_role:role,funding_format:format
    };
  }
  function describe(f){
    const v=normalize(f);
    return [
      ['Заявник',audiences[v.audience]],
      ['Напрями',v.sectors.map(x=>sectors[x]).concat(v.custom_sector?[v.custom_sector]:[]).join(', ')],
      ['Географія',geos[v.geo]+(v.region?' · '+regions[v.region]:'')],
      ['Проєкт',v.detail||'Без уточнення'],
      ['Роль',roles[v.applicant_role]],['Фінансування',formats[v.funding_format]]
    ];
  }
  return {audiences,sectors,geos,regions,roles,formats,allowedKeys,normalize,describe,sanitizeText};
});
