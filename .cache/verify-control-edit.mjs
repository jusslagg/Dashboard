import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9232/json/list')).json();
const socket = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }));
let id = 0;
const pending = new Map();
const errors = [];
socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    if (pending.has(message.id)) {
        const operation = pending.get(message.id);
        pending.delete(message.id);
        message.error ? operation.reject(message.error) : operation.resolve(message.result);
    }
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
    pending.set(++id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
});
async function evaluate(expression) {
    const response = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (response.exceptionDetails) throw new Error(JSON.stringify(response.exceptionDetails));
    return response.result.value;
}
async function waitFor(expression) {
    for (let attempt = 0; attempt < 120; attempt += 1) {
        if (await evaluate(expression)) return;
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`No se cumplio: ${expression}`);
}

try {
    await send('Runtime.enable');
    await send('Page.enable');
    await send('Network.enable');
    await send('Network.setCookie', { name: 'session', value: cookie, url: 'http://127.0.0.1:8009', httpOnly: true, sameSite: 'Lax' });
    await send('Emulation.setDeviceMetricsOverride', { width: 1100, height: 900, deviceScaleFactor: 1, mobile: false });
    await send('Page.navigate', { url: 'http://127.0.0.1:8009/control' });
    await waitFor(`typeof abrirEditar === 'function'`);
    const opened = await evaluate(`fetch('/api/datos?cliente=Spazios').then(r => r.json()).then(d => {
        const registro = d.data.find(item => item.id === 1420) || d.data[0];
        abrirEditar(registro);
        return Boolean(registro);
    })`);
    assert(opened);
    await waitFor(`!document.getElementById('modalEditar').classList.contains('hidden')`);
    const modal = await evaluate(`({
        visible: !document.getElementById('modalEditar').classList.contains('hidden'),
        cliente: document.getElementById('editCliente').value,
        horas: document.getElementById('editHorasFacturadas').value,
        valor: document.getElementById('editValorHora').value,
        objetivo: document.getElementById('editValorHoraObjetivo').value,
        save: [...document.querySelectorAll('#formEditar button')].some(b => b.textContent.includes('Guardar cambios'))
    })`);
    assert.equal(modal.cliente, 'Spazios');
    assert(Number(modal.horas) > 0 && Number(modal.valor) > 0 && Number(modal.objetivo) > 0);
    assert(modal.visible && modal.save);
    assert.deepEqual(errors, []);
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile('.cache/control-edit.png', Buffer.from(shot.data, 'base64'));
    console.log(JSON.stringify({ modal, errors }));
} finally {
    await send('Browser.close');
    socket.close();
}
