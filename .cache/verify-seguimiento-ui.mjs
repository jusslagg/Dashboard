import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9250/json/list')).json();
const socket = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => socket.addEventListener('open', resolve, {once: true}));
let id = 0;
const pending = new Map();
const errors = [];
socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
    if (pending.has(message.id)) {
        const operation = pending.get(message.id); pending.delete(message.id);
        message.error ? operation.reject(message.error) : operation.resolve(message.result);
    }
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
    pending.set(++id, {resolve, reject}); socket.send(JSON.stringify({id, method, params}));
});
const evaluate = async expression => {
    const result = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
};
const waitFor = async expression => {
    for (let attempt = 0; attempt < 150; attempt++) {
        if (await evaluate(expression)) return;
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`No se cumplió: ${expression}`);
};

try {
    await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');
    await send('Network.setCookie', {name:'session', value:cookie, url:'http://localhost:18011', httpOnly:true, sameSite:'Lax'});
    await send('Page.navigate', {url:'http://localhost:18011/carga-datos-personal'});
    await waitFor(`typeof seleccionarPestanaCargaPersonal === 'function' && document.querySelectorAll('#tabsCargaPersonal button').length === 6`);
    const result = await evaluate(`(() => {
        seleccionarPestanaCargaPersonal('2026');
        datosHojaSeguimiento = {cantidad_columnas:3,cantidad_filas:2,cantidad_formulas:1,referencias_rotas:[],anchos:{A:15,B:15,C:15},estilos:{'0':{format:'General'}},filas:[[{v:'Campaña',t:'texto',s:'0'},{v:'Horas',t:'texto',s:'0'},{v:'Total',t:'texto',s:'0'}],[{v:'SOPORTE',t:'texto',s:'0'},{v:10,t:'numero',s:'0'},{v:100,t:'numero',s:'0',f:'=B2*10'}]]};
        renderHojaSeguimiento();
        return {
            titulo: document.querySelector('main h1')?.textContent.trim(),
            tabs: document.querySelectorAll('#tabsCargaPersonal button').length,
            proformaOculta: document.getElementById('contenidoProformaPersonal').classList.contains('hidden'),
            seguimientoVisible: !document.getElementById('contenidoSeguimientoPersonal').classList.contains('hidden'),
            hoja: document.getElementById('tituloHojaSeguimiento').textContent.trim(),
            fx: document.querySelectorAll('#tbodyHojaSeguimiento span').length,
            filas: document.querySelectorAll('#tbodyHojaSeguimiento tr').length,
            logica: document.getElementById('logicaHojaSeguimiento').textContent.includes('motor de facturación')
        };
    })()`);
    assert.deepEqual(result, {titulo:'Carga de datos Personal',tabs:6,proformaOculta:true,seguimientoVisible:true,hoja:'2026',fx:1,filas:2,logica:true});
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({result, errors}));
} finally {
    await send('Browser.close'); socket.close();
}
