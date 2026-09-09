import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const cookie = (await readFile('.cache/session-cookie.txt', 'utf8')).trim();
const tabs = await (await fetch('http://127.0.0.1:9233/json/list')).json();
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
}
try {
    await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');
    await send('Network.setCookie', { name: 'session', value: cookie, url: 'http://127.0.0.1:8009', httpOnly: true, sameSite: 'Lax' });
    await send('Page.navigate', { url: 'http://127.0.0.1:8009/cargar' });
    await waitFor(`typeof guardarNextGenRapido === 'function' && asignaciones.length > 0`);
    const before = await evaluate(`(() => {
        window.__nextGenPosts = [];
        const fetchOriginal = window.fetch.bind(window);
        window.fetch = (url, options = {}) => {
            if (url === '/api/cargar' && options.method === 'POST') {
                window.__nextGenPosts.push(JSON.parse(options.body));
                return new Promise(resolve => setTimeout(() => resolve(new Response(JSON.stringify({success: true}), {status: 200, headers: {'Content-Type': 'application/json'}})), 300));
            }
            return fetchOriginal(url, options);
        };
        const checkbox = document.getElementById('es_next_gen');
        checkbox.checked = true;
        checkbox.dispatchEvent(new Event('change', {bubbles: true}));
        document.getElementById('nombre_next_gen').value = 'AlMundo';
        document.getElementById('next_gen_importe').value = '4512643';
        document.getElementById('next_gen_importe').dispatchEvent(new Event('input', {bubbles: true}));
        document.getElementById('mes').value = '2026-08';
        document.getElementById('fecha').value = '2026-09-08';
        calcularPreview();
        return {
            options: [...document.getElementById('nombre_next_gen').options].map(o => o.value),
            summary: document.getElementById('totalFacturadoLote').textContent,
            valid: document.getElementById('formCargar').checkValidity(),
            invalid: [...document.getElementById('formCargar').elements].filter(element => !element.checkValidity()).map(element => ({id: element.id, value: element.value, min: element.min}))
        };
    })()`);
    await evaluate(`document.querySelector('#formCargar button[type="submit"]').click()`);
    await new Promise(resolve => setTimeout(resolve, 80));
    const during = await evaluate(`({
        busy: document.querySelector('#formCargar button[type="submit"]').getAttribute('aria-busy'),
        label: document.querySelector('#formCargar button[type="submit"]').textContent.trim(),
        disabled: document.querySelector('#formCargar button[type="submit"]').disabled
    })`);
    await new Promise(resolve => setTimeout(resolve, 600));
    const after = await evaluate(`({
        posts: window.__nextGenPosts,
        message: document.getElementById('mensaje').textContent,
        hidden: document.getElementById('mensaje').classList.contains('hidden'),
        disabled: document.querySelector('#grupoBotonNextGenCarga button').disabled,
        checked: document.getElementById('es_next_gen').checked
    })`);
    console.log(JSON.stringify({before, during, after, errors}));
    assert.equal(before.summary, '$4.512.643,00');
    assert(before.valid && before.invalid.length === 0);
    assert(during.disabled);
    assert.equal(after.posts.length, 1);
    assert(after.message.includes('guardadas en agosto de 2026') && !after.hidden);
    assert.deepEqual(errors, []);
} finally {
    await send('Browser.close'); socket.close();
}
