import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9246/json/list')).json();
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
    for (let attempt = 0; attempt < 200; attempt++) {
        if (await evaluate(expression)) return;
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`No se cumplio: ${expression}`);
};

try {
    await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');
    await send('Network.setCookie', {name: 'session', value: cookie, url: 'http://localhost:18010', httpOnly: true, sameSite: 'Lax'});
    await send('Page.navigate', {url: 'http://localhost:18010/carga-datos-personal'});
    await waitFor(`typeof renderProformaPersonal === 'function' && document.querySelectorAll('#tablaProformaPersonal thead th').length === 17`);
    const result = await evaluate(`(() => {
        proformasPersonal = [{fdv:'Contact Center Proovedores',periodo:'202608',negocio:'MASIVO',sitio_proveedor:'CAT',segmento:'CUSTOMER CONVERGENTE',subsitio:'',tipo_hora:'NORMAL',total_horas:10220.0891,precio:21298.78,monto_fijo:217675429.3213,porcentaje_bono_kpi_vs:5,monto_variable_kpi_vs:10883771.4661,porcentaje_bono_ac:0.5,monto_variable_ac:1088377.1466,monto_variable:11972148.6127,total_proyeccion:229647577.934,bono_porcentaje_total:5.5}];
        renderProformaPersonal();
        const fila = document.querySelector('#tbodyProformaPersonal tr');
        return {
            titulo: document.querySelector('main h1')?.textContent.trim(),
            proformaVisible: !document.getElementById('contenidoProformaPersonal').classList.contains('hidden'),
            horasOcultas: document.getElementById('contenidoHorasPersonal').classList.contains('hidden'),
            pestanias: document.querySelectorAll('#tabProformaPersonal, #tabHorasPersonal').length,
            templateVisible: Boolean(document.querySelector('a[href="/api/proforma-personal/template"]')),
            registroImportaciones: Boolean(document.getElementById('tbodyImportacionesProforma')),
            columnas: document.querySelectorAll('#tablaProformaPersonal thead th').length,
            celdas: fila.querySelectorAll('td').length,
            bono: fila.querySelectorAll('td')[13].textContent.trim(),
            totalHoras: document.getElementById('kpiProformaHoras').textContent.trim()
        };
    })()`);
    assert.deepEqual(result, {titulo:'Carga de datos Personal',proformaVisible:true,horasOcultas:true,pestanias:0,templateVisible:true,registroImportaciones:true,columnas:17,celdas:17,bono:'5,5%',totalHoras:'10.220,09'});
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({result, errors}));
} catch (error) {
    const diagnostic = await evaluate(`({url: location.href, title: document.title, heading: document.querySelector('h1')?.textContent, body: document.body?.innerText?.slice(0, 500), scripts: [...document.scripts].map(s => s.src || 'inline').length, fn: typeof renderProformaPersonal})`);
    console.error(JSON.stringify({diagnostic, errors}));
    throw error;
} finally {
    await send('Browser.close'); socket.close();
}
