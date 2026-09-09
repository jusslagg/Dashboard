import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const cookie=(await readFile('.cache/session-cookie.txt','utf8')).trim();
const tabs=await (await fetch('http://127.0.0.1:9237/json/list')).json();
const ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);
await new Promise(r=>ws.addEventListener('open',r,{once:true}));
let id=0; const pending=new Map(); const errors=[];
ws.addEventListener('message',e=>{const m=JSON.parse(e.data); if(m.method==='Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.text); if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}});
const send=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
const evalJs=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value};
try{
 await send('Runtime.enable');await send('Page.enable');await send('Network.enable');
 await send('Network.setCookie',{name:'session',value:cookie,url:'http://127.0.0.1:8009',httpOnly:true,sameSite:'Lax'});
 await send('Page.navigate',{url:'http://127.0.0.1:8009/matriz-proyecciones'});
 for(let i=0;i<150;i++){if(await evalJs(`typeof actualizarCampanias==='function' && document.querySelectorAll('#cliente option').length>1`))break;await new Promise(r=>setTimeout(r,100))}
 const result=await evalJs(`(()=>{const cliente=document.querySelector('#cliente');cliente.value='Galicia Seguros';actualizarCampanias();const filtro=document.querySelector('#filtroCliente');filtro.value='Galicia Seguros';actualizarFiltroCampania();return {cliente:[...cliente.options].map(o=>o.value).filter(Boolean),campanias:[...document.querySelectorAll('#campania option')].map(o=>o.value).filter(Boolean),filtroCampanias:[...document.querySelectorAll('#filtroCampania option')].map(o=>o.value).filter(Boolean)}})()`);
 assert(result.cliente.includes('Galicia Seguros'));
 assert(result.campanias.includes('GALICIA SEGUROS - COBRANZAS'));
 assert(result.campanias.includes('GALICIA SEGUROS - LITIGIOS'));
 assert(result.filtroCampanias.includes('GALICIA SEGUROS - COBRANZAS'));
 assert(result.filtroCampanias.includes('GALICIA SEGUROS - LITIGIOS'));
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({galicia:result.campanias,errors}));
}finally{await send('Browser.close');ws.close()}
