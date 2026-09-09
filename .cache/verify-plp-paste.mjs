import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9244/json/list')).json();
const socket = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }));
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
    pending.set(++id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params }));
});
const evaluate = async expression => {
    const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
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
const tabla = `| Personal | sep-26 | ABONOS | 6421,00 |
| --- | --- | --- | --- |
| Personal | sep-26 | ISLA DEGRADADOS | 3.610 |
| Personal | sep-26 | CUSTOMER ONBOARDING | 2.273 |
| Personal | sep-26 | CUSTOMER FACTURA UNIFICADA | 10.825 |
| Personal CX | sep-26 | CUSTOMER OPEN | 2.472 |
| Personal CX | sep-26 | TELERED | |
| Personal | sep-26 | RETENCIÓN CONVERGENTE | 13.342 |
| Personal | sep-26 | RETENCION CABLE ISLA TECNICA | |
| Personal | sep-26 | RETENCIÓN CABLE | 7.177 |
| Personal | sep-26 | VENTAS IN/OUT | 9.658 |
| Personal | sep-26 | VENTAS WHATSAPP | 9.280 |
| Personal | sep-26 | PERSONAL PAY TELEFONICO | |
| Personal | sep-26 | PERSONAL PAY DIGITAL | 6.213 |
| Personal SOPORTE | sep-26 | SOPORTE CONECTIVIDAD | 8.535 |
| Personal SOPORTE | sep-26 | SOPORTE ENTRETENIMIENTO | 4.148 |
| Personal SOPORTE | sep-26 | SOPORTE CALLBACK | 1.200 |
| Personal SOPORTE | sep-26 | ISLA ESPECIALIZADA MOVIL | 2.673 |
| Personal SOPORTE | sep-26 | RRSS TECNICO | 9.942 |
| Personal SOPORTE | sep-26 | CAMPAÑA | |
| Personal SOPORTE | sep-26 | ISLA PROVISION DIGITAL | 3.030 |
| Personal | sep-26 | WHATSAPP MOVIL | 2.291 |
| Personal | sep-26 | WHATSAPP FACTURA UNIFICADA | 6.252 |
| Personal | sep-26 | WHATSAPP RETENCION CONVERGENTE | 6.797 |
| Personal SMB | sep-26 | SMB VENTAS FIJO | 2.222 |
| Personal SMB | sep-26 | SMB VENTAS OUT | 979 |
| Personal SMB | sep-26 | SMB WSP VENTAS | 1.386 |`;

try {
    await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');
    await send('Network.setCookie', { name: 'session', value: cookie, url: 'http://127.0.0.1:8009', httpOnly: true, sameSite: 'Lax' });
    await send('Page.navigate', { url: 'http://127.0.0.1:8009/matriz-proyecciones' });
    await waitFor(`typeof prepararTablaPegadaPLP === 'function' && Array.isArray(proyecciones) && proyecciones.length > 0`);
    const prepared = await evaluate(`(() => {
        cambiarPestania('personal');
        document.getElementById('tablaPegadaPLP').value = ${JSON.stringify(tabla)};
        prepararTablaPegadaPLP();
        const filas = [...document.querySelectorAll('#tbodyEditorPLP tr[data-plp-dirty="1"]')];
        return {
            filas: filas.length,
            total: filas.reduce((suma, fila) => suma + Number(fila.querySelector('[data-plp="horas"]').value), 0),
            mes: document.getElementById('filtroMesEditorPLP').value,
            resumen: document.getElementById('resumenTablaPegadaPLP').textContent.replace(/\\s+/g, ' ').trim(),
            soporte: filas.filter(fila => fila.querySelector('[data-plp="tipo_plp"]').value === 'Personal Soporte').length
        };
    })()`);
    assert.equal(prepared.filas, 22);
    assert.equal(prepared.total, 120726);
    assert.equal(prepared.mes, '2026-09');
    assert.equal(prepared.soporte, 6);
    assert.match(prepared.resumen, /4 sin horas omitida/);

    const saved = await evaluate(`(async () => {
        const originalFetch = window.fetch;
        window.alert = () => {};
        window.__plpPayload = null;
        window.fetch = async (url, options = {}) => {
            if (url === '/api/proyecciones-plp/edicion-masiva' && options.method === 'POST') {
                window.__plpPayload = JSON.parse(options.body);
                return new Response(JSON.stringify({ success: true, mensaje: 'Prueba correcta' }), { status: 200, headers: { 'Content-Type': 'application/json' } });
            }
            return originalFetch(url, options);
        };
        await guardarEditorPLP();
        return {
            cantidad: window.__plpPayload.filas.length,
            total: window.__plpPayload.filas.reduce((suma, fila) => suma + Number(fila.horas), 0),
            year: window.__plpPayload.year
        };
    })()`);
    assert.deepEqual(saved, { cantidad: 22, total: 120726, year: '2026' });
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ prepared, saved, errors }));
} finally {
    await send('Browser.close'); socket.close();
}
