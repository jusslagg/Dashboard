import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9230/json/list')).json();
const socket = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }));
let id = 0;
const pending = new Map();
const errors = [];
socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    if (pending.has(message.id)) {
        const { resolve, reject } = pending.get(message.id);
        pending.delete(message.id);
        message.error ? reject(message.error) : resolve(message.result);
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
    for (let attempt = 0; attempt < 80; attempt += 1) {
        if (await evaluate(expression)) return;
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`No se cumplió: ${expression}`);
}

try {
    await send('Runtime.enable');
    await send('Page.enable');
    await send('Network.enable');
    await send('Network.setCookie', { name: 'session', value: cookie, url: 'http://127.0.0.1:8009', httpOnly: true, sameSite: 'Lax' });
    await send('Emulation.setDeviceMetricsOverride', { width: 1078, height: 545, deviceScaleFactor: 1, mobile: false });
    await send('Page.navigate', { url: 'http://127.0.0.1:8009/reloj' });
    await waitFor(`document.getElementById('realizado')?.textContent === '1.918.750,78'`);
    const values = await evaluate(`({
        title: document.querySelector('main h2')?.textContent.trim(),
        required: requerido.textContent,
        actual: realizado.textContent,
        difference: diferencia.textContent,
        compliance: cumplimiento.textContent,
        content: document.body.innerText.trim().length,
        overlay: Boolean(document.querySelector('[data-nextjs-dialog], .vite-error-overlay, #webpack-dev-server-client-overlay'))
    })`);
    assert.deepEqual(values, {
        title: 'Reloj', required: '1.915.454,7', actual: '1.918.750,78',
        difference: '+3.296,08', compliance: '100,17%', content: values.content, overlay: false
    });
    assert(values.content > 100);
    const capture = await send('Page.captureScreenshot', { format: 'png' });
    await writeFile('.cache/reloj-reconciliado.png', Buffer.from(capture.data, 'base64'));

    await send('Page.navigate', { url: 'http://127.0.0.1:8009/cargar' });
    await waitFor(`document.querySelectorAll('[data-guardar-carga]').length === 2`);
    const guard = await evaluate(`({ buttons: document.querySelectorAll('[data-guardar-carga]').length, functionLoaded: typeof guardarDatos === 'function', saving: guardandoDatos })`);
    assert.deepEqual(guard, { buttons: 2, functionLoaded: true, saving: false });
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ values, guard, errors }));
} finally {
    await send('Browser.close');
    socket.close();
}
