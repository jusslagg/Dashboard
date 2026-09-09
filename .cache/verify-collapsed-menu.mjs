import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9234/json/list')).json();
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
    for (let attempt = 0; attempt < 100; attempt += 1) {
        if (await evaluate(expression)) return;
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`No se cumplio: ${expression}`);
}

try {
    await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');
    await send('Network.setCookie', { name: 'session', value: cookie, url: 'http://127.0.0.1:8009', httpOnly: true, sameSite: 'Lax' });
    await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
    await send('Page.navigate', { url: 'http://127.0.0.1:8009/' });
    await waitFor(`typeof toggleSidebarGroup === 'function'`);
    const initial = await evaluate(`(() => {
        const groups = [...document.querySelectorAll('[data-sidebar-group]')];
        return {count: groups.length, expanded: groups.filter(g => g.querySelector('.sidebar-group-toggle').getAttribute('aria-expanded') === 'true').length, visible: groups.filter(g => !g.querySelector('.sidebar-group-content').hidden).length};
    })()`);
    assert(initial.count >= 4 && initial.expanded === 0 && initial.visible === 0);
    await evaluate(`toggleSidebarGroup('facturacion')`);
    const opened = await evaluate(`({expanded: document.querySelector('[data-sidebar-group="facturacion"] .sidebar-group-toggle').getAttribute('aria-expanded'), hidden: document.getElementById('sidebarGroupFacturacion').hidden})`);
    assert.equal(opened.expanded, 'true'); assert.equal(opened.hidden, false);
    await evaluate(`sessionStorage.setItem('contraerMenuAlIngresar', 'true'); location.reload()`);
    await waitFor(`document.readyState === 'complete' && typeof toggleSidebarGroup === 'function'`);
    const afterLogin = await evaluate(`(() => {
        const groups = [...document.querySelectorAll('[data-sidebar-group]')];
        return {expanded: groups.filter(g => g.querySelector('.sidebar-group-toggle').getAttribute('aria-expanded') === 'true').length, visible: groups.filter(g => !g.querySelector('.sidebar-group-content').hidden).length, saved: localStorage.getItem('sidebarGroup:facturacion')};
    })()`);
    assert.deepEqual(afterLogin, {expanded: 0, visible: 0, saved: null});
    assert.deepEqual(errors, []);
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile('.cache/menu-collapsed.png', Buffer.from(shot.data, 'base64'));
    console.log(JSON.stringify({initial, opened, afterLogin, errors}));
} finally {
    await send('Browser.close'); socket.close();
}
