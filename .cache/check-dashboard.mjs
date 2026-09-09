import { writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const tabs = await (await fetch('http://127.0.0.1:9229/json/list')).json();
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
function send(method, params = {}) {
    return new Promise((resolve, reject) => {
        pending.set(++id, { resolve, reject });
        socket.send(JSON.stringify({ id, method, params }));
    });
}
async function evaluate(expression) {
    const data = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (data.exceptionDetails) throw new Error(JSON.stringify(data.exceptionDetails));
    return data.result.value;
}
async function waitFor(expression) {
    for (let attempt = 0; attempt < 70; attempt++) {
        if (await evaluate(expression)) return;
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error('No se cumplió: ' + expression);
}
try {
    await send('Runtime.enable');
    await send('Page.enable');
    await send('Emulation.setDeviceMetricsOverride', { width: 1640, height: 1050, deviceScaleFactor: 1, mobile: false });
    await send('Page.navigate', { url: 'http://127.0.0.1:8010/login' });
    await waitFor('typeof requiereSetup !== "undefined"');
    await evaluate(`fetch('/api/auth/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email: 'dashboard@example.test', password: 'Prueba123'}) }).then(r => { if (!r.ok) throw new Error('Login: ' + r.status); })`);
    await send('Page.navigate', { url: 'http://127.0.0.1:8010/' });
    await waitFor('document.getElementById("kpiCumplimientoHoras")?.textContent === "63.6%"');
    const aggregate = await evaluate(`fetch('/api/kpis').then(r => r.json()).then(data => ({hours: data.kpis.porcentaje_cumplimiento_horas, billing: data.kpis.porcentaje_cumplimiento_facturacion}))`);
    assert.deepEqual(aggregate, {hours: 63.64, billing: 94.55});
    await evaluate(`document.querySelector('#filtroCliente input[value="Cliente A"]').click()`);
    await waitFor('document.getElementById("kpiCumplimientoHoras").textContent === "50.0%"');
    assert.equal(await evaluate('document.getElementById("kpiCumplimiento").textContent'), '100.0%');
    await evaluate(`(() => { document.querySelectorAll('#filtroCliente input').forEach(input => input.checked = input.value === 'Cliente B'); document.querySelector('#filtroCliente input[value="Cliente B"]').dispatchEvent(new Event('change', {bubbles: true})); })()`);
    await waitFor('document.getElementById("kpiCumplimientoHoras").textContent === "200.0%"');
    assert.equal(await evaluate('document.getElementById("kpiCumplimiento").textContent'), '40.0%');
    assert(await evaluate('document.getElementById("kpiCumplimientoHoras").classList.contains("text-green-600")'));
    assert(await evaluate('document.getElementById("kpiCumplimiento").classList.contains("text-red-600")'));
    const capture = await send('Page.captureScreenshot', {format: 'png'});
    await writeFile('.cache/dashboard.png', Buffer.from(capture.data, 'base64'));
    const layout = await evaluate(`(() => {
        const first = document.getElementById('kpiCumplimiento').getBoundingClientRect();
        const second = document.getElementById('kpiCumplimientoHoras').getBoundingClientRect();
        return { sameRow: Math.abs(first.top - second.top) < 3, right: second.right, width: innerWidth };
    })()`);
    assert(layout.sameRow && layout.right < layout.width);
    await send('Emulation.setDeviceMetricsOverride', {width: 390, height: 844, deviceScaleFactor: 1, mobile: true});
    await evaluate('document.getElementById("kpiCumplimiento").scrollIntoView({block: "center"})');
    const mobile = await send('Page.captureScreenshot', {format: 'png'});
    await writeFile('.cache/dashboard-mobile.png', Buffer.from(mobile.data, 'base64'));
    await evaluate(`fetch('/api/kpis?cliente=SinDatos').then(r => r.json()).then(data => actualizarKPIs(data.kpis))`);
    assert.equal(await evaluate('document.getElementById("kpiCumplimientoHoras").textContent'), '0.0%');
    assert.equal(await evaluate('document.getElementById("kpiCumplimiento").textContent'), '0.0%');
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({aggregate, clientA: {hours: '50.0%', billing: '100.0%'}, clientB: {hours: '200.0%', billing: '40.0%'}, filters: true, emptyData: true, layout, errors}));
} finally {
    await send('Browser.close');
    socket.close();
}
