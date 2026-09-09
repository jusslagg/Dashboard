import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9235/json/list')).json();
const socket = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }));
let id = 0;
const pending = new Map();
const errors = [];
socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    if (pending.has(message.id)) {
        const operation = pending.get(message.id); pending.delete(message.id);
        message.error ? operation.reject(message.error) : operation.resolve(message.result);
    }
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
    pending.set(++id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params }));
});
async function evaluate(expression) {
    const response = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (response.exceptionDetails) throw new Error(JSON.stringify(response.exceptionDetails));
    return response.result.value;
}
async function waitFor(expression) {
    for (let attempt = 0; attempt < 150; attempt += 1) {
        if (await evaluate(expression)) return;
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`No se cumplio: ${expression}`);
}

try {
    await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');
    await send('Network.setCookie', { name: 'session', value: cookie, url: 'http://127.0.0.1:8009', httpOnly: true, sameSite: 'Lax' });
    await send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 950, deviceScaleFactor: 1, mobile: false });
    await send('Page.navigate', { url: 'http://127.0.0.1:8009/matriz-precios' });
    await waitFor(`document.querySelectorAll('#tbodyPrecios input[data-mes]').length > 100`);
    const grid = await evaluate(`({
        headers: [...document.querySelectorAll('#theadPrecios th')].map(th => th.textContent.trim()),
        rows: document.querySelectorAll('#tbodyPrecios tr').length,
        cells: document.querySelectorAll('#tbodyPrecios input[data-mes]').length,
        toolsCollapsed: !document.querySelector('details').open,
        firstValue: document.querySelector('#tbodyPrecios input[data-mes]').value,
        help: document.querySelector('#contadorPrecios').nextElementSibling.textContent.trim()
    })`);
    assert.equal(grid.headers.length, 15);
    assert.deepEqual(grid.headers.slice(0, 3), ['Cuenta', 'Site', 'Cliente']);
    assert(grid.rows > 20 && grid.cells === grid.rows * 12 && grid.firstValue.startsWith('$ '));
    assert(grid.toolsCollapsed && grid.help.includes('meses siguientes'));
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile('.cache/price-grid.png', Buffer.from(shot.data, 'base64'));

    const save = await evaluate(`(async () => {
        window.__pricePosts = [];
        const originalFetch = window.fetch.bind(window);
        window.fetch = (url, options = {}) => {
            if (url === '/api/matriz-precios' && options.method === 'POST') {
                window.__pricePosts.push(JSON.parse(options.body));
                return Promise.resolve(new Response(JSON.stringify({success: true, mensaje: '7 precio(s) guardado(s)'}), {status: 200, headers: {'Content-Type': 'application/json'}}));
            }
            return originalFetch(url, options);
        };
        const input = [...document.querySelectorAll('#tbodyPrecios input[data-mes="2026-06"]')].find(item => Number(item.dataset.original) > 0);
        const nuevo = Number(input.dataset.original) + 123.45;
        iniciarEdicionPrecioCelda(input);
        input.value = nuevo.toLocaleString('es-AR', {useGrouping: false, minimumFractionDigits: 2, maximumFractionDigits: 2});
        await guardarPrecioCelda(input);
        return {posts: window.__pricePosts, nuevo};
    })()`);
    assert.equal(save.posts.length, 1);
    assert.equal(save.posts[0].mes, '2026-06');
    assert(Math.abs((save.posts[0].precio_base * save.posts[0].alcance_porcentaje / 100) - save.nuevo) < 0.01);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({grid, edit: {mes: save.posts[0].mes, cliente: save.posts[0].cliente, campania: save.posts[0].campania, precioFinal: save.nuevo}, errors}));
} finally {
    await send('Browser.close'); socket.close();
}
