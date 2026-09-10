import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9245/json/list')).json();
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
    await send('Network.setCookie', {name: 'session', value: cookie, url: 'http://127.0.0.1:8009', httpOnly: true, sameSite: 'Lax'});
    await send('Page.navigate', {url: 'http://127.0.0.1:8009/carga-datos-personal'});
    await waitFor(`typeof prepararCargaPersonal === 'function' && datosPersonal.length > 0`);
    const result = await evaluate(`(() => {
        document.getElementById('tablaPersonal').value = '| Personal | sep-26 | ABONOS | 6421,00 |\\n| --- | --- | --- | --- |\\n| Personal SOPORTE | sep-26 | SOPORTE CONECTIVIDAD | 8.535 |\\n| Personal CX | sep-26 | TELERED | |\\n| Personal SMB | sep-26 | SMB VENTAS OUT | 979 |';
        prepararCargaPersonal();
        return {
            titulo: document.querySelector('main h1')?.textContent.trim(),
            enlaceMenu: [...document.querySelectorAll('a')].some(a => a.getAttribute('href') === '/carga-datos-personal' && a.textContent.includes('Carga de datos Personal')),
            filas: filasPreparadasPersonal.length,
            total: filasPreparadasPersonal.reduce((suma, fila) => suma + fila.horas, 0),
            tipos: filasPreparadasPersonal.map(fila => fila.tipo_plp),
            omitidas: document.getElementById('mensajePersonal').textContent.includes('1 sin horas omitida'),
            previewVisible: !document.getElementById('previewPersonal').classList.contains('hidden')
        };
    })()`);
    assert.deepEqual(result, {
        titulo: 'Carga de datos Personal', enlaceMenu: true, filas: 3, total: 15935,
        tipos: ['Personal', 'Personal Soporte', 'Personal SMB'], omitidas: true, previewVisible: true
    });
    const saved = await evaluate(`(async () => {
        const originalFetch = window.fetch;
        window.__payloadPersonal = null;
        window.fetch = async (url, options = {}) => {
            if (url === '/api/carga-datos-personal' && options.method === 'POST') {
                window.__payloadPersonal = JSON.parse(options.body);
                return new Response(JSON.stringify({success: true, mensaje: 'Prueba correcta'}), {status: 200, headers: {'Content-Type': 'application/json'}});
            }
            return originalFetch(url, options);
        };
        await guardarCargaPersonal();
        return {year: window.__payloadPersonal.year, filas: window.__payloadPersonal.filas.length, total: window.__payloadPersonal.filas.reduce((suma, fila) => suma + Number(fila.horas), 0)};
    })()`);
    assert.deepEqual(saved, {year: '2026', filas: 3, total: 15935});
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({result, saved, errors}));
} finally {
    await send('Browser.close'); socket.close();
}
