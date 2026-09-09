import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const cookie=(await readFile('.cache/session-cookie.txt','utf8')).trim();
const tabs=await (await fetch('http://127.0.0.1:9238/json/list')).json();
const ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.addEventListener('open',r,{once:true}));
let id=0;const pending=new Map();const errors=[];
ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}});
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
const run=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value};
try{
 await send('Runtime.enable');await send('Page.enable');await send('Network.enable');
 await send('Network.setCookie',{name:'session',value:cookie,url:'http://127.0.0.1:8009',httpOnly:true,sameSite:'Lax'});
 await send('Page.navigate',{url:'http://127.0.0.1:8009/resumen'});
 for(let i=0;i<200;i++){if(await run(`typeof filas!=='undefined' && filas.some(x=>x.campania==='GALICIA SEGUROS - LITIGIOS')`))break;await new Promise(r=>setTimeout(r,100))}
 const result=await run(`(()=>{const x=filas.find(x=>x.tipo==='total_campania'&&x.campania==='GALICIA SEGUROS - LITIGIOS');buscarResumen.value='litigios';renderResumen();return {found:!!x,september:x?.meses?.['2026-09'],visible:tbodyResumen.innerText.includes('GALICIA SEGUROS - LITIGIOS')}})()`);
 assert(result.found);assert(Math.abs(result.september-5028320.88)<.01);assert(result.visible);assert.deepEqual(errors,[]);
 console.log(JSON.stringify({litigios:result,errors}));
}finally{await send('Browser.close');ws.close()}
