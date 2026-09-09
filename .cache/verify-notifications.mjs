import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9231/json/list')).json();
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
    for (let attempt = 0; attempt < 120; attempt += 1) {
        if (await evaluate(expression)) return;
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`No se cumplió: ${expression}`);
}

try {
    await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');
    await send('Network.setCookie', { name: 'session', value: cookie, url: 'http://127.0.0.1:8009', httpOnly: true, sameSite: 'Lax' });
    await send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
    await send('Page.navigate', { url: 'http://127.0.0.1:8009/notificaciones-proyecciones' });
    await waitFor(`document.querySelectorAll('#tbodyNotificaciones > tr').length > 10`);
    const result = await evaluate(`({
        title: document.querySelector('main h1')?.textContent.trim(),
        rows: document.querySelectorAll('#tbodyNotificaciones > tr').length,
        positive: kpiPositivas.textContent,
        negative: kpiNegativas.textContent,
        mixed: kpiMixtas.textContent,
        metrics: metricaFiltro.options.length,
        nav: [...document.querySelectorAll('a')].some(a => a.textContent.includes('Notificaciones') && a.classList.contains('active')),
        content: document.body.innerText.trim().length,
        overlay: Boolean(document.querySelector('[data-nextjs-dialog], .vite-error-overlay, #webpack-dev-server-client-overlay'))
    })`);
    assert.equal(result.title, 'Notificaciones de cambios');
    assert(result.rows > 10 && Number(result.positive.replaceAll('.', '')) > 0 && Number(result.negative.replaceAll('.', '')) > 0);
    assert(result.metrics >= 12 && result.nav && result.content > 1000 && !result.overlay);
    const personal = await evaluate(`(() => {
        const rows = [...document.querySelectorAll('#tbodyNotificaciones > tr')];
        const parents = rows.filter(row => row.querySelector('td:nth-child(2) strong')?.textContent.trim() === 'Personal');
        const detail = parents[0]?.nextElementSibling?.querySelector('details');
        if (detail) detail.open = true;
        return { parents: parents.length, services: detail?.querySelectorAll('tbody > tr').length || 0, summary: detail?.querySelector('summary')?.textContent || '' };
    })()`);
    assert.equal(personal.parents, 1);
    assert(personal.services > 5 && personal.summary.includes('servicios de Personal'));
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile('.cache/notificaciones-proyecciones.png', Buffer.from(shot.data, 'base64'));
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ result, personal, errors }));
} finally {
    await send('Browser.close'); socket.close();
}
